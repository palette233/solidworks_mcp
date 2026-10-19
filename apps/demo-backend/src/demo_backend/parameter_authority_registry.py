from __future__ import annotations

import hashlib
import json
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .project_assembly_profile import load_project_assembly_profile


REGISTRY_SCHEMA = "project-parameter-authority-registry/v1"
AUDIT_SCHEMA = "project-parameter-authority-audit/v1"
OVERLAY_SCHEMA = "authoritative-parameter-overlay/v1"
PRODUCTION_AUTHORITIES = {"vendor-confirmed", "engineer-confirmed"}
BASELINE_AUTHORITIES = {
    "cad-measured",
    "prototype-calibrated",
    "ppt-cad-inferred",
    "temporary-estimate",
}
DECISION_MODES = {"pending", "approve-baseline", "replace"}


class ParameterAuthorityRegistryError(ValueError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _digest(payload: Any) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parameter_authority_registry_path(project_id: str) -> Path:
    normalized = str(project_id or "").strip().lower()
    if not normalized or not normalized.replace("-", "").replace("_", "").isalnum():
        raise ParameterAuthorityRegistryError(f"非法项目编号：{project_id!r}")
    return (
        Path(__file__).resolve().parent
        / "project_profiles"
        / f"{normalized}_parameter_authorities.json"
    )


def validate_parameter_authority_registry(
    payload: dict[str, Any],
    *,
    project_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if payload.get("schemaVersion") != REGISTRY_SCHEMA:
        raise ParameterAuthorityRegistryError("不支持的参数权威注册表版本。")
    project_id = str(payload.get("projectId") or "").strip().lower()
    if not project_id:
        raise ParameterAuthorityRegistryError("参数权威注册表缺少projectId。")
    if not str(payload.get("registryVersion") or "").strip():
        raise ParameterAuthorityRegistryError("参数权威注册表缺少registryVersion。")
    profile = project_profile or load_project_assembly_profile(project_id)
    if profile["projectId"] != project_id:
        raise ParameterAuthorityRegistryError("注册表与项目装配配置的projectId不一致。")

    requirements = payload.get("requirements")
    if not isinstance(requirements, list) or not requirements:
        raise ParameterAuthorityRegistryError("参数权威注册表必须包含非空requirements。")
    known_modules = set(profile["modules"])
    seen: set[str] = set()
    normalized_requirements: list[dict[str, Any]] = []
    for raw in requirements:
        if not isinstance(raw, dict):
            raise ParameterAuthorityRegistryError("每条参数要求必须为对象。")
        requirement_id = str(raw.get("requirementId") or "").strip()
        if not requirement_id:
            raise ParameterAuthorityRegistryError("参数要求缺少requirementId。")
        if requirement_id in seen:
            raise ParameterAuthorityRegistryError(f"参数要求重复：{requirement_id}")
        seen.add(requirement_id)
        if not str(raw.get("label") or "").strip():
            raise ParameterAuthorityRegistryError(f"{requirement_id}缺少label。")
        owners = [str(value).upper() for value in raw.get("ownerModules") or []]
        if not owners:
            raise ParameterAuthorityRegistryError(f"{requirement_id}缺少ownerModules。")
        unknown = [value for value in owners if value not in known_modules]
        if unknown:
            raise ParameterAuthorityRegistryError(
                f"{requirement_id}引用未登记模组：" + "、".join(unknown)
            )
        required_keys = [str(value) for value in raw.get("requiredValueKeys") or []]
        if not required_keys or len(required_keys) != len(set(required_keys)):
            raise ParameterAuthorityRegistryError(
                f"{requirement_id}的requiredValueKeys必须非空且不得重复。"
            )

        baseline = raw.get("baseline")
        if not isinstance(baseline, dict):
            raise ParameterAuthorityRegistryError(f"{requirement_id}缺少baseline。")
        baseline_authority = str(baseline.get("authority") or "")
        if baseline_authority not in BASELINE_AUTHORITIES:
            raise ParameterAuthorityRegistryError(
                f"{requirement_id}的baseline.authority不受支持。"
            )
        evidence_paths = [str(value) for value in baseline.get("evidencePaths") or []]
        if not evidence_paths:
            raise ParameterAuthorityRegistryError(
                f"{requirement_id}的baseline缺少evidencePaths。"
            )

        decision = raw.get("decision") or {"mode": "pending"}
        if not isinstance(decision, dict):
            raise ParameterAuthorityRegistryError(f"{requirement_id}的decision必须为对象。")
        mode = str(decision.get("mode") or "pending")
        if mode not in DECISION_MODES:
            raise ParameterAuthorityRegistryError(
                f"{requirement_id}的decision.mode不受支持：{mode}"
            )
        if mode != "pending":
            authority = str(decision.get("authority") or "")
            if authority not in PRODUCTION_AUTHORITIES:
                raise ParameterAuthorityRegistryError(
                    f"{requirement_id}只有厂商或工程师确认才能生产放行。"
                )
            if not str(decision.get("approvedBy") or "").strip():
                raise ParameterAuthorityRegistryError(f"{requirement_id}缺少approvedBy。")
            if not str(decision.get("approvedAt") or "").strip():
                raise ParameterAuthorityRegistryError(f"{requirement_id}缺少approvedAt。")
            if not [str(value) for value in decision.get("evidencePaths") or []]:
                raise ParameterAuthorityRegistryError(
                    f"{requirement_id}的确认决定缺少evidencePaths。"
                )
            values = decision.get("values") or {}
            if mode == "replace":
                missing = [key for key in required_keys if key not in values]
                extra = [key for key in values if key not in required_keys]
                if missing or extra:
                    raise ParameterAuthorityRegistryError(
                        f"{requirement_id}替换值字段不匹配；缺少={missing}，多余={extra}。"
                    )
            elif values:
                raise ParameterAuthorityRegistryError(
                    f"{requirement_id}批准基线时不得同时填写替换值。"
                )

        row = deepcopy(raw)
        row["requirementId"] = requirement_id
        row["ownerModules"] = owners
        row["requiredValueKeys"] = required_keys
        row["decision"] = deepcopy(decision)
        row["decision"]["mode"] = mode
        normalized_requirements.append(row)

    result = deepcopy(payload)
    result["projectId"] = project_id
    result["requirements"] = normalized_requirements
    return result


def load_parameter_authority_registry(
    project_id: str,
    *,
    path: Path | None = None,
) -> dict[str, Any]:
    registry_path = (path or parameter_authority_registry_path(project_id)).resolve()
    if not registry_path.is_file():
        raise ParameterAuthorityRegistryError(f"参数权威注册表不存在：{registry_path}")
    try:
        raw = json.loads(registry_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ParameterAuthorityRegistryError(f"参数权威注册表JSON无效：{registry_path}") from exc
    if not isinstance(raw, dict):
        raise ParameterAuthorityRegistryError("参数权威注册表根节点必须为对象。")
    registry = validate_parameter_authority_registry(raw)
    if registry["projectId"] != str(project_id).strip().lower():
        raise ParameterAuthorityRegistryError("参数权威注册表projectId与请求不一致。")
    registry["registryPath"] = str(registry_path)
    registry["registryDigest"] = _digest(raw)
    return registry


def _evidence_status(workspace: Path, paths: list[str]) -> list[dict[str, Any]]:
    rows = []
    for raw_path in paths:
        path = Path(raw_path)
        resolved = path if path.is_absolute() else workspace / path
        exists = resolved.is_file()
        rows.append(
            {
                "path": str(resolved.resolve()),
                "exists": exists,
                "sha256": _file_digest(resolved) if exists else None,
            }
        )
    return rows


def audit_parameter_authorities(
    workspace: Path,
    project_id: str,
    *,
    path: Path | None = None,
) -> dict[str, Any]:
    workspace = workspace.resolve()
    profile = load_project_assembly_profile(project_id)
    registry = load_parameter_authority_registry(project_id, path=path)
    rows = []
    module_requirements: dict[str, list[dict[str, Any]]] = {
        token: [] for token in profile["modules"]
    }
    counts: Counter[str] = Counter()
    for requirement in registry["requirements"]:
        decision = requirement["decision"]
        mode = decision["mode"]
        baseline_evidence = _evidence_status(
            workspace, [str(value) for value in requirement["baseline"]["evidencePaths"]]
        )
        decision_evidence = _evidence_status(
            workspace, [str(value) for value in decision.get("evidencePaths") or []]
        )
        baseline_complete = all(row["exists"] for row in baseline_evidence)
        decision_complete = bool(decision_evidence) and all(
            row["exists"] for row in decision_evidence
        )
        production_accepted = mode != "pending" and decision_complete
        status = "production-confirmed" if production_accepted else "pending-authority"
        counts[status] += 1
        row = {
            "requirementId": requirement["requirementId"],
            "label": requirement["label"],
            "ownerModules": requirement["ownerModules"],
            "requiredForProduction": bool(requirement.get("requiredForProduction", True)),
            "requiredValueKeys": requirement["requiredValueKeys"],
            "baselineAuthority": requirement["baseline"]["authority"],
            "baselineEvidence": baseline_evidence,
            "baselineEvidenceComplete": baseline_complete,
            "decisionMode": mode,
            "decisionAuthority": decision.get("authority"),
            "decisionEvidence": decision_evidence,
            "productionAccepted": production_accepted,
            "status": status,
            "nextAction": (
                "由厂商或机械工程师签认现有基线，或填写完整替换值与证据。"
                if not production_accepted
                else "已形成生产权威参数决定；任何源证据变化后必须重新审计。"
            ),
        }
        rows.append(row)
        for token in requirement["ownerModules"]:
            module_requirements[token].append(row)

    modules = []
    for token, source in profile["modules"].items():
        required = [
            row for row in module_requirements[token] if row["requiredForProduction"]
        ]
        accepted = bool(required) and all(row["productionAccepted"] for row in required)
        modules.append(
            {
                "moduleToken": token,
                "moduleLabel": source["label"],
                "requirementIds": [row["requirementId"] for row in required],
                "productionAuthorityAccepted": accepted,
                "pendingRequirementIds": [
                    row["requirementId"] for row in required if not row["productionAccepted"]
                ],
            }
        )

    production_required = [row for row in rows if row["requiredForProduction"]]
    static_accepted = all(row["baselineEvidenceComplete"] for row in rows)
    production_accepted = bool(production_required) and all(
        row["productionAccepted"] for row in production_required
    )
    return {
        "schemaVersion": AUDIT_SCHEMA,
        "generatedAt": _utc_now(),
        "projectId": profile["projectId"],
        "projectProfile": {
            "profileVersion": profile["profileVersion"],
            "profileDigest": profile["profileDigest"],
        },
        "registry": {
            "registryVersion": registry["registryVersion"],
            "registryDigest": registry["registryDigest"],
            "registryPath": registry["registryPath"],
        },
        "countsByStatus": dict(sorted(counts.items())),
        "requirementCount": len(rows),
        "productionAcceptedRequirementCount": sum(
            1 for row in rows if row["productionAccepted"]
        ),
        "staticDemoParameterEvidenceAccepted": static_accepted,
        "productionParameterAuthorityAccepted": production_accepted,
        "requirements": rows,
        "modules": modules,
        "productionBlockers": [
            {
                "requirementId": row["requirementId"],
                "ownerModules": row["ownerModules"],
                "nextAction": row["nextAction"],
            }
            for row in rows
            if row["requiredForProduction"] and not row["productionAccepted"]
        ],
    }


def compile_authoritative_parameter_overlay(
    project_id: str,
    *,
    path: Path | None = None,
) -> dict[str, Any]:
    profile = load_project_assembly_profile(project_id)
    registry = load_parameter_authority_registry(project_id, path=path)
    decisions = []
    pending = []
    for requirement in registry["requirements"]:
        decision = requirement["decision"]
        if decision["mode"] == "pending":
            if requirement.get("requiredForProduction", True):
                pending.append(requirement["requirementId"])
            continue
        decisions.append(
            {
                "requirementId": requirement["requirementId"],
                "ownerModules": requirement["ownerModules"],
                "mode": decision["mode"],
                "authority": decision["authority"],
                "approvedBy": decision["approvedBy"],
                "approvedAt": decision["approvedAt"],
                "evidencePaths": decision["evidencePaths"],
                "values": deepcopy(decision.get("values") or {}),
            }
        )
    if pending:
        raise ParameterAuthorityRegistryError(
            "生产参数仍未闭环：" + "、".join(pending)
        )
    return {
        "schemaVersion": OVERLAY_SCHEMA,
        "generatedAt": _utc_now(),
        "projectId": profile["projectId"],
        "profileDigest": profile["profileDigest"],
        "registryDigest": registry["registryDigest"],
        "decisions": decisions,
        "overlayDigest": _digest(decisions),
    }
