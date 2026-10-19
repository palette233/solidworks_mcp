"""Attest and import successful CAD checkpoints created before the turn ledger."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .assembly_conversation import bind_attested_checkpoint


ASSESSMENT_SCHEMA = "historical-demo-checkpoint-import/v1"


class HistoricalCheckpointImportError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _identity(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    if not resolved.is_file():
        raise HistoricalCheckpointImportError(f"证据文件不存在：{resolved}")
    stat = resolved.stat()
    return {
        "path": str(resolved),
        "sizeBytes": stat.st_size,
        "lastWriteTimeNs": stat.st_mtime_ns,
        "sha256": _file_digest(resolved),
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HistoricalCheckpointImportError(f"无法读取JSON：{path}: {exc}") from exc
    if not isinstance(value, dict):
        raise HistoricalCheckpointImportError(f"JSON根节点必须是对象：{path}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def _project_definition_rows(
    context: dict[str, Any], catalog: dict[str, Any], project_id: str
) -> list[dict[str, Any]]:
    definitions = {
        str(row.get("moduleDefinitionId") or ""): row
        for row in catalog.get("moduleDefinitions") or []
    }
    rows: list[dict[str, Any]] = []
    for instance in context.get("instances") or []:
        definition_id = str(instance.get("moduleDefinitionId") or "")
        definition = definitions.get(definition_id)
        if definition is None:
            raise HistoricalCheckpointImportError(
                f"全局目录缺少模组定义：{definition_id}"
            )
        aliases = [
            row
            for row in definition.get("projectAliases") or []
            if str(row.get("projectId") or "").casefold() == project_id.casefold()
        ]
        if len(aliases) != 1 or not str(aliases[0].get("moduleToken") or "").strip():
            raise HistoricalCheckpointImportError(
                f"实例{instance.get('instanceId')}没有唯一的{project_id}模组编号。"
            )
        rows.append(
            {
                "instanceId": str(instance["instanceId"]),
                "moduleDefinitionId": definition_id,
                "moduleToken": str(aliases[0]["moduleToken"]).strip().upper(),
                "componentNames": [
                    str(value).strip()
                    for value in definition.get("componentNames") or []
                    if str(value).strip()
                ],
            }
        )
    return rows


def _component_token(
    component: dict[str, Any], definition_rows: list[dict[str, Any]]
) -> tuple[str | None, list[str]]:
    name = str(component.get("Name") or component.get("name") or "")
    path = str(component.get("Path") or component.get("path") or "")
    haystacks = [name.casefold(), Path(path).stem.casefold() if path else ""]
    by_token: dict[str, list[str]] = {}
    for row in definition_rows:
        token = row["moduleToken"]
        reasons = by_token.setdefault(token, [])
        if any(token.casefold() in value for value in haystacks):
            reasons.append("module_token_in_component_identity")
        for component_name in row["componentNames"]:
            stem = Path(component_name).stem.casefold()
            if stem and any(stem in value or value in stem for value in haystacks if value):
                reasons.append("catalog_component_name_match")
    candidates = sorted(token for token, reasons in by_token.items() if reasons)
    return (candidates[0] if len(candidates) == 1 else None), candidates


def infer_component_inventory_path(job: dict[str, Any]) -> Path | None:
    """Prefer the immutable engineering pose inventory when one exists."""

    engineering = job.get("engineeringCheckpoint") or {}
    evidence = Path(str(engineering.get("evidencePath") or ""))
    if evidence.name.endswith("-gate.json"):
        candidate = evidence.with_name(evidence.name.replace("-gate.json", "-poses.json"))
        if candidate.is_file():
            return candidate
    return None


def build_historical_checkpoint_import_assessment(
    context: dict[str, Any],
    catalog: dict[str, Any],
    job: dict[str, Any],
    component_inventory_path: Path,
) -> dict[str, Any]:
    """Prove that a pre-ledger job represents the current semantic context."""

    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    project_id = str(job.get("projectId") or "").strip().lower()
    if job.get("status") != "succeeded":
        blockers.append({"code": "JOB_NOT_SUCCEEDED", "detail": job.get("status")})
    if job.get("validationProfile") != "demo":
        blockers.append(
            {"code": "NOT_A_DEMO_JOB", "detail": job.get("validationProfile")}
        )
    if job.get("assemblyStatus") != "assembled":
        blockers.append(
            {"code": "ASSEMBLY_NOT_COMMITTED", "detail": job.get("assemblyStatus")}
        )
    checkpoint = job.get("demoCheckpoint")
    if not isinstance(checkpoint, dict) or not checkpoint.get("assemblyPath"):
        raise HistoricalCheckpointImportError("历史任务没有Demo检查点。")
    assembly_identity = _identity(Path(str(checkpoint["assemblyPath"])))
    inventory_identity = _identity(component_inventory_path)
    inventory = _read_json(component_inventory_path)
    inventory_assembly = str(inventory.get("assemblyPath") or "")
    if not inventory_assembly or str(Path(inventory_assembly).resolve()).casefold() != str(
        Path(assembly_identity["path"]).resolve()
    ).casefold():
        blockers.append(
            {
                "code": "INVENTORY_ASSEMBLY_MISMATCH",
                "detail": inventory_assembly,
            }
        )
    engineering_identity = (
        (job.get("engineeringCheckpoint") or {}).get("sourceAssemblyIdentity") or {}
    )
    if engineering_identity:
        if str(engineering_identity.get("sha256") or "") != assembly_identity["sha256"]:
            blockers.append(
                {
                    "code": "ENGINEERING_IDENTITY_MISMATCH",
                    "detail": engineering_identity,
                }
            )
    else:
        warnings.append(
            {
                "code": "NO_ENGINEERING_IDENTITY",
                "detail": "仅使用Demo检查点和组件清单签认，碰撞状态不参与导入。",
            }
        )

    definition_rows = _project_definition_rows(context, catalog, project_id)
    expected_tokens = [row["moduleToken"] for row in definition_rows]
    components = inventory.get("components")
    if not isinstance(components, list):
        raise HistoricalCheckpointImportError("组件清单缺少components数组。")
    observed_tokens: list[str] = []
    unresolved: list[dict[str, Any]] = []
    for component in components:
        token, candidates = _component_token(component, definition_rows)
        if token is None:
            unresolved.append(
                {
                    "name": component.get("Name") or component.get("name"),
                    "path": component.get("Path") or component.get("path"),
                    "candidateTokens": candidates,
                }
            )
        else:
            observed_tokens.append(token)
    if unresolved:
        blockers.append(
            {
                "code": "COMPONENT_IDENTITY_UNRESOLVED",
                "detail": unresolved,
            }
        )
    expected_counts = Counter(expected_tokens)
    observed_counts = Counter(observed_tokens)
    if expected_counts != observed_counts:
        blockers.append(
            {
                "code": "MODULE_MULTISET_MISMATCH",
                "expected": dict(sorted(expected_counts.items())),
                "observed": dict(sorted(observed_counts.items())),
            }
        )
    declared_count = int(inventory.get("componentCount") or len(components))
    if declared_count != len(components) or len(components) != len(definition_rows):
        blockers.append(
            {
                "code": "COMPONENT_COUNT_MISMATCH",
                "declared": declared_count,
                "observed": len(components),
                "expected": len(definition_rows),
            }
        )

    assessment = {
        "schemaVersion": ASSESSMENT_SCHEMA,
        "status": "ready_for_import" if not blockers else "blocked",
        "contextId": context["contextId"],
        "contextRevision": int(context.get("revision") or 0),
        "contextDigest": context.get("contextDigest"),
        "jobId": job.get("jobId"),
        "projectId": project_id,
        "checkpointAssemblyIdentity": assembly_identity,
        "componentInventoryIdentity": inventory_identity,
        "expectedModuleTokenCounts": dict(sorted(expected_counts.items())),
        "observedModuleTokenCounts": dict(sorted(observed_counts.items())),
        "expectedInstanceCount": len(definition_rows),
        "observedComponentCount": len(components),
        "instanceTokenBindings": [
            {"instanceId": row["instanceId"], "moduleToken": row["moduleToken"]}
            for row in definition_rows
        ],
        "blockers": blockers,
        "warnings": warnings,
        "executionBoundary": {
            "solidWorksStarted": False,
            "solidWorksAssemblyModified": False,
            "jobFileModified": False,
            "effectAfterConfirmation": "bind_checkpoint_to_current_conversation_ledger_only",
        },
        "createdAt": _now(),
    }
    assessment["assessmentDigest"] = _digest(
        {key: value for key, value in assessment.items() if key != "createdAt"}
    )
    return assessment


def commit_historical_checkpoint_import(
    context_path: Path,
    context: dict[str, Any],
    job: dict[str, Any],
    assessment: dict[str, Any],
    *,
    expected_assessment_digest: str,
    confirmed: bool,
) -> dict[str, Any]:
    if confirmed is not True:
        raise HistoricalCheckpointImportError("必须显式confirmed=true才能导入历史检查点。")
    if assessment.get("schemaVersion") != ASSESSMENT_SCHEMA:
        raise HistoricalCheckpointImportError("不支持的历史检查点评估版本。")
    if assessment.get("status") != "ready_for_import":
        raise HistoricalCheckpointImportError("历史检查点评估存在阻塞项。")
    if assessment.get("assessmentDigest") != expected_assessment_digest:
        raise HistoricalCheckpointImportError("历史检查点评估摘要已变化。")
    if assessment.get("contextId") != context.get("contextId") or int(
        assessment.get("contextRevision") or -1
    ) != int(context.get("revision") or 0):
        raise HistoricalCheckpointImportError("历史检查点评估不属于当前上下文修订。")
    if assessment.get("contextDigest") != context.get("contextDigest"):
        raise HistoricalCheckpointImportError("历史检查点评估的上下文摘要已过期。")
    for key in ("checkpointAssemblyIdentity", "componentInventoryIdentity"):
        expected_identity = assessment.get(key) or {}
        current_identity = _identity(Path(str(expected_identity.get("path") or "")))
        if current_identity["sha256"] != expected_identity.get("sha256"):
            raise HistoricalCheckpointImportError("签认输入文件在确认前发生变化。")
    output_dir = context_path.parent / "checkpoint-imports" / context["contextId"]
    output_path = output_dir / (
        f"{job['jobId']}-{assessment['checkpointAssemblyIdentity']['sha256'][:12]}.json"
    )
    attestation = deepcopy(assessment)
    attestation["importedAt"] = _now()
    _write_json(output_path, attestation)
    bind_attested_checkpoint(
        context_path,
        context,
        job,
        assessment,
        attestation_path=output_path,
    )
    return {
        "success": True,
        "status": "imported",
        "jobId": job["jobId"],
        "contextId": context["contextId"],
        "contextRevision": context["revision"],
        "assessmentDigest": assessment["assessmentDigest"],
        "attestationPath": str(output_path),
        "checkpointAssemblyIdentity": deepcopy(
            assessment["checkpointAssemblyIdentity"]
        ),
        "solidWorksStarted": False,
        "solidWorksAssemblyModified": False,
        "jobFileModified": False,
    }
