"""Durable orchestration for project-independent CAD transaction manifests.

The packet executor deliberately executes one packet at a time.  This module
adds the missing manifest-level contract: immutable manifest binding,
checkpoint chaining, boundary pause/resume, and rollback to the last committed
CAD checkpoint when a packet is rejected.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

from .global_cad_packet_executor import (
    GlobalCadPacketExecutionError,
    sha256_file,
    validate_cad_manifest_release_authority,
)
from .global_manifest_seed_import import (
    EXTERNAL_SEED_SCHEMA,
    GlobalManifestSeedImportError,
    validate_external_manifest_seed_evidence,
)
from .global_command_audit import build_global_command_audit
from .global_manifest_job_user_summary import (
    write_global_manifest_job_user_summary,
)
from .assembly_timing_report import write_assembly_timing_report
from .assembly_user_failure import build_assembly_user_failure
from .semantic_assembly_jobs import (
    AssemblyJobError,
    AssemblyJobExecutor,
    DurableAssemblyJobStore,
    canonical_json,
)


MANIFEST_JOB_PLAN_SCHEMA = "global-cad-manifest-job-plan/v1"
STEP_EVIDENCE_SCHEMA = "global-cad-manifest-step-evidence/v1"
COMMAND_AUDIT_BINDING_SCHEMA = "global-manifest-job-command-audit-binding/v1"
# SolidWorks SaveAs still observes a legacy Windows path limit even when Python
# can create longer paths. Reserve room for the CAD application's save helpers.
CAD_OUTPUT_PATH_MAX_CHARS = 240


class GlobalCadManifestOrchestrationError(AssemblyJobError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GlobalCadManifestOrchestrationError(
            f"无法读取JSON证据：{path}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise GlobalCadManifestOrchestrationError(f"JSON根节点必须为对象：{path}")
    return value


def _workspace_path(workspace: Path, value: str | None) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    path = Path(text)
    return path.resolve() if path.is_absolute() else (workspace / path).resolve()


def _build_command_audit_binding(
    workspace: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
    selected_packets: list[dict[str, Any]],
) -> dict[str, Any]:
    """Bind the natural-language-to-CAD trace to a durable manifest job."""

    context_id = str(manifest.get("contextId") or "").strip()
    release_binding = manifest.get("relationReleaseBinding") or {}
    catalog_path = _workspace_path(
        workspace, release_binding.get("releasedCatalogRelativePath")
    )
    if catalog_path is None:
        expected_catalog_digest = str(manifest.get("catalogDigest") or "").strip()
        catalog_candidates = (
            workspace
            / "demo"
            / "global_assembly_catalog"
            / "v1"
            / "global_module_catalog.json",
            workspace
            / "demo"
            / "global_assembly_catalog"
            / "v1"
            / "global_module_catalog.combination-v1-preview.json",
        )
        for candidate in catalog_candidates:
            if not candidate.is_file():
                continue
            candidate_catalog = _read_json(candidate)
            if (
                not expected_catalog_digest
                or candidate_catalog.get("catalogDigest") == expected_catalog_digest
            ):
                catalog_path = candidate.resolve()
                break
    context_candidates = (
        manifest_path.with_name(f"{context_id}.json"),
        workspace / "demo" / "global_assembly_contexts" / f"{context_id}.json",
    )
    context_path = next(
        (path.resolve() for path in context_candidates if path.is_file()),
        context_candidates[-1].resolve(),
    )
    dag_candidates = (
        manifest_path.with_name(f"{context_id}.transaction-dag.json"),
        manifest_path.parent / "transaction-dag.json",
        workspace
        / "demo"
        / "global_assembly_contexts"
        / f"{context_id}.transaction-dag.json",
    )
    dag_path = next((path.resolve() for path in dag_candidates if path.is_file()), None)
    sources = {
        "catalogPath": str(catalog_path) if catalog_path else None,
        "contextPath": str(context_path),
        "transactionDagPath": str(dag_path) if dag_path else None,
        "manifestPath": str(manifest_path),
    }
    missing = [
        name
        for name, path in (
            ("catalog", catalog_path),
            ("context", context_path),
            ("transactionDAG", dag_path),
        )
        if path is None or not path.is_file()
    ]
    if missing:
        return {
            "schemaVersion": COMMAND_AUDIT_BINDING_SCHEMA,
            "status": "unavailable",
            "blockers": [f"AUDIT_SOURCE_MISSING:{name}" for name in missing],
            "sources": sources,
            "selectedPacketIds": [str(row.get("packetId") or "") for row in selected_packets],
        }

    catalog = _read_json(catalog_path)
    context = _read_json(context_path)
    dag = _read_json(dag_path)
    audit = build_global_command_audit(catalog, context, dag, manifest)
    selected_packet_ids = {
        str(row.get("packetId") or "") for row in selected_packets
    }
    selected_commands = [
        row
        for row in audit.get("commands") or []
        if row.get("operation") == "add_base_instance"
        or selected_packet_ids.intersection(
            str(value) for value in row.get("cadPacketIds") or []
        )
    ]
    source_sha = {
        key.replace("Path", "Sha256"): sha256_file(Path(value))
        for key, value in sources.items()
        if key != "manifestPath" and value
    }
    payload = {
        **audit,
        "jobSelection": {
            "selectedPacketIds": sorted(selected_packet_ids),
            "selectedCommandCount": len(selected_commands),
            "selectedCommands": selected_commands,
        },
    }
    return {
        "schemaVersion": COMMAND_AUDIT_BINDING_SCHEMA,
        "status": (
            "complete"
            if audit.get("mappedCommandCount") == audit.get("commandCount")
            else "incomplete"
        ),
        "blockers": [],
        "sources": {**sources, **source_sha},
        "selectedPacketIds": sorted(selected_packet_ids),
        "auditDigest": _digest(payload),
        "payload": payload,
    }


def _validate_manifest(
    manifest: dict[str, Any],
    *,
    allow_ready_slice_from_blocked_manifest: bool = False,
) -> None:
    if manifest.get("schemaVersion") != "global-cad-transaction-manifest/v1":
        raise GlobalCadManifestOrchestrationError("不支持的CAD事务清单版本。")
    expected = str(manifest.get("manifestDigest") or "")
    actual = _digest(
        {key: value for key, value in manifest.items() if key != "manifestDigest"}
    )
    if not expected or expected != actual:
        raise GlobalCadManifestOrchestrationError("CAD事务清单摘要不一致。")
    if (
        not allow_ready_slice_from_blocked_manifest
        and manifest.get("status") != "ready_for_generic_executor_implementation"
    ):
        codes = [str(row.get("code") or "") for row in manifest.get("blockers") or []]
        raise GlobalCadManifestOrchestrationError(
            "CAD事务清单尚未满足通用执行条件：" + ", ".join(filter(None, codes))
        )
    packets = list(manifest.get("packets") or [])
    if not packets:
        raise GlobalCadManifestOrchestrationError("CAD事务清单没有可执行数据包。")
    for packet in packets:
        packet_expected = str(packet.get("packetDigest") or "")
        packet_actual = _digest(
            {key: value for key, value in packet.items() if key != "packetDigest"}
        )
        if packet_expected != packet_actual:
            raise GlobalCadManifestOrchestrationError(
                f"数据包{packet.get('packetId')}摘要不一致。"
            )
        if (
            not allow_ready_slice_from_blocked_manifest
            and packet.get("status") != "ready_for_executor_implementation"
        ):
            raise GlobalCadManifestOrchestrationError(
                f"数据包{packet.get('packetId')}未满足执行条件。"
            )


def _packet_module_token(packet: dict[str, Any]) -> str:
    operation = str(packet.get("operation") or "")
    if operation in {"ADD_RELATION", "VERIFY_RELATION"}:
        relation_tokens = sorted(
            {
                str(value).strip().upper()
                for value in packet.get("relationModuleTokens") or []
                if str(value).strip()
            }
        )
        if len(relation_tokens) != 2:
            raise GlobalCadManifestOrchestrationError(
                f"数据包{packet.get('packetId')}无法唯一确定关系两端模组令牌。"
            )
        return relation_tokens[0]
    projects = {
        str((row.get("templateEvidenceSource") or {}).get("projectId") or "").lower()
        for row in packet.get("connections") or []
    }
    projects.discard("")
    aliases = list(packet.get("targetProjectAliases") or [])
    if len(projects) == 1:
        project = next(iter(projects))
        matching_aliases = [
            row for row in aliases if str(row.get("projectId") or "").lower() == project
        ]
        # A cross-project relation is commonly published by the project that
        # owns the provided slot, while the inserted target belongs to another
        # project.  Template provenance therefore cannot erase an otherwise
        # unique target alias.  Use it only when it actually matches one of the
        # target definition's aliases.
        if matching_aliases:
            aliases = matching_aliases
    tokens = sorted(
        {
            str(row.get("moduleToken") or "").strip().upper()
            for row in aliases
            if str(row.get("moduleToken") or "").strip()
        }
    )
    if len(tokens) != 1:
        raise GlobalCadManifestOrchestrationError(
            f"数据包{packet.get('packetId')}无法唯一确定目标模组令牌。"
        )
    return tokens[0]


def _project_id(manifest: dict[str, Any], packets: list[dict[str, Any]]) -> str:
    projects = {
        str(alias.get("projectId") or "").strip().lower()
        for packet in packets
        for alias in packet.get("targetProjectAliases") or []
        if str(alias.get("projectId") or "").strip()
    }
    projects.update(
        str((connection.get("templateEvidenceSource") or {}).get("projectId") or "")
        .strip()
        .lower()
        for packet in packets
        for connection in packet.get("connections") or []
        if str((connection.get("templateEvidenceSource") or {}).get("projectId") or "").strip()
    )
    return next(iter(projects)) if len(projects) == 1 else "project-global"


def build_manifest_job_plan(
    workspace: Path,
    manifest_path: Path,
    *,
    start_order: int = 1,
    packet_limit: int | None = None,
) -> dict[str, Any]:
    """Bind a contiguous manifest slice to an immutable durable-job plan."""

    workspace = workspace.resolve()
    manifest_path = manifest_path.resolve()
    try:
        manifest_path.relative_to(workspace)
    except ValueError as exc:
        raise GlobalCadManifestOrchestrationError(
            "CAD事务清单必须位于当前工作区内。"
        ) from exc
    manifest = _read_json(manifest_path)
    _validate_manifest(manifest, allow_ready_slice_from_blocked_manifest=True)
    packets = sorted(
        list(manifest.get("packets") or []), key=lambda row: int(row.get("order") or 0)
    )
    orders = [int(row.get("order") or 0) for row in packets]
    if orders != list(range(1, len(packets) + 1)):
        raise GlobalCadManifestOrchestrationError("数据包order必须从1开始连续递增。")
    if start_order < 1 or start_order > len(packets):
        raise GlobalCadManifestOrchestrationError("start_order超出清单范围。")
    if packet_limit is not None and packet_limit < 1:
        raise GlobalCadManifestOrchestrationError("packet_limit必须大于0。")
    selected = packets[start_order - 1 :]
    if packet_limit is not None:
        selected = selected[:packet_limit]
    if not selected:
        raise GlobalCadManifestOrchestrationError("选定范围没有可执行数据包。")
    blocked_selected = [
        str(packet.get("packetId") or "")
        for packet in selected
        if packet.get("status") != "ready_for_executor_implementation"
    ]
    if blocked_selected:
        raise GlobalCadManifestOrchestrationError(
            "选定的数据包尚未满足执行条件：" + ", ".join(blocked_selected)
        )
    try:
        release_authority = validate_cad_manifest_release_authority(
            workspace,
            manifest,
            packets=selected,
        )
    except GlobalCadPacketExecutionError as exc:
        raise GlobalCadManifestOrchestrationError(str(exc)) from exc

    steps = []
    for packet in selected:
        token = _packet_module_token(packet)
        connections = list(packet.get("connections") or [])
        execution_strategy = str(
            packet.get("executionStrategy") or "incremental_component_insert"
        )
        requested_driving_mate_count = 0
        requested_validation_relation_count = 0
        for connection in connections:
            for mate in connection.get("mates") or []:
                application_mode = str(
                    (mate.get("advancedOptions") or {}).get("applicationMode")
                    or "drive"
                ).strip().lower()
                if application_mode == "validate_only":
                    requested_validation_relation_count += 1
                else:
                    requested_driving_mate_count += 1
        provenance_mate_count = requested_driving_mate_count
        if execution_strategy == "calibrated_static_snapshot_insert":
            requested_driving_mate_count = 0
        steps.append(
            {
                "stepId": str(packet["packetId"]),
                "moduleToken": token,
                "packetId": str(packet["packetId"]),
                "packetOrder": int(packet["order"]),
                "packetDigest": str(packet["packetDigest"]),
                "targetInstanceId": packet.get("targetInstanceId"),
                "operation": packet.get("operation"),
                "executionStrategy": execution_strategy,
                "drivingExecutionOverride": packet.get(
                    "drivingExecutionOverride"
                ),
                "relationModuleTokens": packet.get("relationModuleTokens") or [],
                "connectionCount": len(connections),
                # requestedMateCount remains a compatibility alias for the
                # number of relations that actually drive CAD placement.
                "requestedMateCount": requested_driving_mate_count,
                "requestedDrivingMateCount": requested_driving_mate_count,
                "sourceMateProvenanceCount": provenance_mate_count,
                "requestedValidationRelationCount": (
                    requested_validation_relation_count
                ),
                "requestedRelationCount": (
                    requested_driving_mate_count
                    + requested_validation_relation_count
                ),
                "cumulativeInputKind": (packet.get("cumulativeInput") or {}).get("kind"),
            }
        )
    expected_seed = None
    first_input_kind = str(steps[0].get("cumulativeInputKind") or "")
    if start_order > 1:
        prior = packets[start_order - 2]
        expected_seed = {
            "packetId": str(prior["packetId"]),
            "packetDigest": str(prior["packetDigest"]),
            "moduleToken": _packet_module_token(prior),
        }
    elif first_input_kind == "existing_assembly_checkpoint_required":
        first = selected[0]
        expected_seed = {
            "packetId": "external-existing-assembly",
            "packetDigest": _digest(
                {
                    "contextId": manifest.get("contextId"),
                    "contextDigest": manifest.get("contextDigest"),
                    "firstPacketId": first.get("packetId"),
                    "firstPacketDigest": first.get("packetDigest"),
                }
            ),
            "moduleToken": _packet_module_token(first),
        }
    plan = {
        "schemaVersion": MANIFEST_JOB_PLAN_SCHEMA,
        "projectId": _project_id(manifest, selected),
        "contextId": manifest.get("contextId"),
        "contextRevision": manifest.get("contextRevision"),
        "contextDigest": manifest.get("contextDigest"),
        "manifestPath": str(manifest_path),
        "manifestFileSha256": sha256_file(manifest_path),
        "manifestDigest": manifest.get("manifestDigest"),
        "relationReleaseBinding": release_authority["binding"],
        "releaseAuthority": release_authority,
        "validationProfile": "generic-cad-transaction-manifest-v1",
        "startOrder": start_order,
        "packetLimit": packet_limit,
        "stepCount": len(steps),
        "steps": steps,
        "requiresSeedCheckpoint": expected_seed is not None,
        "expectedSeed": expected_seed,
        "collisionStatus": "not_evaluated",
        "executionBoundary": {
            "solidWorksExecuted": False,
            "collisionGateExecuted": False,
            "statement": "仅在每包CAD验证通过后提交检查点；碰撞门禁不属于当前范围。",
        },
        "commandAudit": _build_command_audit_binding(
            workspace, manifest_path, manifest, selected
        ),
    }
    plan["planDigest"] = _digest(plan)
    return plan


def validate_seed_evidence(
    plan: dict[str, Any], assembly_path: Path, evidence_path: Path
) -> dict[str, Any]:
    expected = plan.get("expectedSeed")
    if not expected:
        raise GlobalCadManifestOrchestrationError("从首包执行的任务不接受外部种子。")
    assembly_path = assembly_path.resolve()
    evidence_path = evidence_path.resolve()
    if not assembly_path.is_file() or not evidence_path.is_file():
        raise GlobalCadManifestOrchestrationError("种子装配体或执行证据不存在。")
    evidence = _read_json(evidence_path)
    evidence_schema = evidence.get("schemaVersion")
    if evidence_schema == EXTERNAL_SEED_SCHEMA:
        try:
            validate_external_manifest_seed_evidence(evidence, plan=plan)
        except GlobalManifestSeedImportError as exc:
            raise GlobalCadManifestOrchestrationError(str(exc)) from exc
    elif evidence_schema != "global-cad-packet-execution/v1":
        raise GlobalCadManifestOrchestrationError(
            "种子证据既不是通用CAD数据包执行证据，也不是受控外部检查点证据。"
        )
    if evidence.get("success") is not True:
        raise GlobalCadManifestOrchestrationError("种子数据包执行未成功。")
    if str(evidence.get("packetId") or "") != str(expected["packetId"]):
        raise GlobalCadManifestOrchestrationError("种子数据包编号与清单前缀不匹配。")
    if str(evidence.get("packetDigest") or "") != str(expected["packetDigest"]):
        raise GlobalCadManifestOrchestrationError("种子数据包摘要与清单前缀不匹配。")
    recorded_output = Path(str(evidence.get("outputAssemblyPath") or "")).resolve()
    if recorded_output != assembly_path:
        raise GlobalCadManifestOrchestrationError("种子装配体路径与证据记录不一致。")
    actual_sha = sha256_file(assembly_path)
    if str(evidence.get("outputAssemblySha256") or "") != actual_sha:
        raise GlobalCadManifestOrchestrationError("种子装配体内容摘要与证据不一致。")
    return {
        "packetId": expected["packetId"],
        "packetDigest": expected["packetDigest"],
        "moduleToken": expected["moduleToken"],
        "assemblySha256": actual_sha,
    }


def read_manifest_job_events(store: DurableAssemblyJobStore, job_id: str) -> list[dict[str, Any]]:
    """Return the durable event ledger without exposing callers to JSONL files."""

    store.load(job_id)
    path = store._dir(job_id) / "events.jsonl"
    if not path.is_file():
        return []
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise GlobalCadManifestOrchestrationError(
                f"任务事件记录第{line_number}行损坏：{exc}"
            ) from exc
        if isinstance(value, dict):
            events.append(value)
    return events


def manifest_job_status_view(
    store: DurableAssemblyJobStore, job_id: str, *, include_events: bool = True
) -> dict[str, Any]:
    """Build a UI/API-oriented view of a durable manifest job."""

    job = store.load(job_id)
    steps = list(job.get("steps") or [])
    completed = sum(1 for step in steps if step.get("status") == "succeeded")
    failed_step = next((step for step in steps if step.get("status") == "failed"), None)
    failed_step_operation = str((failed_step or {}).get("operation") or "").upper()
    if failed_step and not failed_step_operation:
        failed_step_operation = next(
            (
                str(row.get("operation") or "").upper()
                for row in (job.get("plan") or {}).get("steps") or []
                if str(row.get("stepId") or "")
                == str(failed_step.get("stepId") or "")
            ),
            "",
        )
    checkpoint = job.get("lastCommittedCheckpoint")
    job_directory = store._dir(job_id)
    command_audit_path = job_directory / "command-audit.json"
    timing_report_path = job_directory / "timing-report.json"
    user_summary_path = job_directory / "user-summary.json"
    audit_binding = (job.get("plan") or {}).get("commandAudit") or {}
    view = {
        "schemaVersion": "global-cad-manifest-job-status/v1",
        "jobId": job["jobId"],
        "projectId": job.get("projectId"),
        "contextId": (job.get("plan") or {}).get("contextId"),
        "status": job.get("status"),
        "assemblyStatus": job.get("assemblyStatus"),
        "validationStatus": job.get("validationStatus") or "not_requested",
        "collisionStatus": job.get("collisionStatus") or "not_evaluated",
        "progress": {
            "completedSteps": completed,
            "totalSteps": len(steps),
            "currentStepId": next(
                (step.get("stepId") for step in steps if step.get("status") == "running"),
                None,
            ),
            "nextStepId": next(
                (step.get("stepId") for step in steps if step.get("status") == "pending"),
                None,
            ),
        },
        "pauseRequested": bool(job.get("pauseRequested")),
        "failure": (
            {
                "stepId": failed_step.get("stepId") if failed_step else None,
                "failureKind": (
                    "read_only_validation_failed"
                    if failed_step_operation == "VERIFY_RELATION"
                    else "assembly_transaction_failed"
                ),
                "reason": job.get("error") or (failed_step or {}).get("error"),
                "userExplanation": build_assembly_user_failure(
                    blockers=(failed_step or {}).get("blockers") or [],
                    status="failed",
                    raw_error=str(
                        job.get("error") or (failed_step or {}).get("error") or ""
                    ),
                    stage="cad_execution",
                ),
                "rollback": job.get("rollback"),
            }
            if job.get("status") == "failed"
            else None
        ),
        "lastCheckpoint": checkpoint,
        "executionDurationSeconds": job.get("executionDurationSeconds", 0.0),
        "steps": steps,
        "createdAt": job.get("createdAt"),
        "startRequestedAt": job.get("startRequestedAt"),
        "startedAt": job.get("startedAt"),
        "completedAt": job.get("completedAt"),
        "updatedAt": job.get("updatedAt"),
        "executionBoundary": {
            "collisionGateExecuted": False,
            "collisionStatement": "碰撞/B-rep不属于当前装配编排验收范围。",
        },
        "commandAudit": {
            "status": audit_binding.get("status") or "unavailable",
            "path": str(command_audit_path) if command_audit_path.is_file() else None,
            "digest": audit_binding.get("auditDigest"),
        },
        "timingReport": {
            "path": str(timing_report_path) if timing_report_path.is_file() else None,
            "status": "available" if timing_report_path.is_file() else "pending",
        },
        "userSummary": {
            "path": str(user_summary_path) if user_summary_path.is_file() else None,
            "markdownPath": (
                str(job_directory / "user-summary.md")
                if (job_directory / "user-summary.md").is_file()
                else None
            ),
            "status": (
                (_read_json(user_summary_path).get("status") or "unavailable")
                if user_summary_path.is_file()
                else "pending"
            ),
        },
    }
    if include_events:
        view["events"] = read_manifest_job_events(store, job_id)
    return view


def write_manifest_job_artifacts(
    store: DurableAssemblyJobStore, job_id: str
) -> dict[str, str | None]:
    """Materialize audit and timing artifacts for every durable job state."""

    job = store.load(job_id)
    directory = store._dir(job_id)
    directory.mkdir(parents=True, exist_ok=True)
    binding = (job.get("plan") or {}).get("commandAudit") or {}
    audit_path = directory / "command-audit.json"
    audit_payload = binding.get("payload")
    if not isinstance(audit_payload, dict):
        audit_payload = {
            "schemaVersion": "global-command-audit-unavailable/v1",
            "status": binding.get("status") or "unavailable",
            "blockers": binding.get("blockers") or ["COMMAND_AUDIT_NOT_BOUND"],
            "sources": binding.get("sources") or {},
            "selectedPacketIds": binding.get("selectedPacketIds") or [],
        }
    audit_path.write_text(
        json.dumps(audit_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    timing_path = write_assembly_timing_report(directory)
    user_summary = write_global_manifest_job_user_summary(job, directory)
    return {
        "commandAuditPath": str(audit_path),
        "timingReportPath": str(timing_path),
        "userSummaryPath": str(user_summary["jsonPath"]),
        "userSummaryMarkdownPath": str(user_summary["markdownPath"]),
        "userSummaryStatus": str(user_summary["status"]),
    }


def run_manifest_job(
    store: DurableAssemblyJobStore,
    job_id: str,
    step_runner,
) -> dict[str, Any]:
    """Execute a job and always refresh its standard audit/timing artifacts."""

    write_manifest_job_artifacts(store, job_id)
    result = AssemblyJobExecutor(store, step_runner).run(job_id)
    write_manifest_job_artifacts(store, job_id)
    return result


CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


def _cad_output_path(run_dir: Path, context_id: str, packet_id: str) -> Path:
    """Keep legacy readable names when safe, otherwise shorten deterministically."""
    run_dir = run_dir.resolve()
    output = run_dir / f"{context_id}-{packet_id}.SLDASM"

    def windows_length(path: Path) -> int:
        return len(str(path).encode("utf-16-le")) // 2

    if windows_length(output) <= CAD_OUTPUT_PATH_MAX_CHARS:
        return output
    key = _digest({"contextId": context_id, "packetId": packet_id})[:12]
    output = run_dir / f"asm-{key}.SLDASM"
    if windows_length(output) > CAD_OUTPUT_PATH_MAX_CHARS:
        raise GlobalCadManifestOrchestrationError(
            "CAD输出目录过长，缩短文件名后仍超过"
            f"{CAD_OUTPUT_PATH_MAX_CHARS}字符预算；请使用更短的任务目录。"
            "已在启动CAD前阻断，未覆盖任何装配体。"
        )
    return output


def manifest_cad_step_runner(
    workspace: Path,
    store: DurableAssemblyJobStore,
    *,
    timeout_seconds: int = 2400,
    pause_after_packet: str | None = None,
    fail_before_packet: str | None = None,
    command_runner: CommandRunner = subprocess.run,
):
    """Create a real packet runner suitable for :class:`AssemblyJobExecutor`.

    ``pause_after_packet`` and ``fail_before_packet`` are explicit diagnostic
    controls.  They make pause/resume and rollback reproducible without
    corrupting a SolidWorks file.
    """

    workspace = workspace.resolve()

    def run(job: dict[str, Any], step: dict[str, Any], previous: Path | None) -> dict[str, Any]:
        plan = job.get("plan") or {}
        if plan.get("schemaVersion") != MANIFEST_JOB_PLAN_SCHEMA:
            raise GlobalCadManifestOrchestrationError("任务未绑定通用CAD清单计划。")
        manifest_path = Path(str(plan.get("manifestPath") or "")).resolve()
        if not manifest_path.is_file():
            raise GlobalCadManifestOrchestrationError("任务绑定的CAD事务清单已丢失。")
        if sha256_file(manifest_path) != str(plan.get("manifestFileSha256") or ""):
            raise GlobalCadManifestOrchestrationError("CAD事务清单在任务创建后发生变化。")
        current_manifest = _read_json(manifest_path)
        _validate_manifest(
            current_manifest,
            allow_ready_slice_from_blocked_manifest=True,
        )
        if current_manifest.get("manifestDigest") != plan.get("manifestDigest"):
            raise GlobalCadManifestOrchestrationError("任务与当前CAD事务清单摘要不一致。")
        step_plan = next(
            (
                row
                for row in plan.get("steps") or []
                if str(row.get("stepId")) == str(step.get("stepId"))
            ),
            None,
        )
        if not step_plan:
            raise GlobalCadManifestOrchestrationError("任务步骤不在绑定的清单切片中。")
        packet_id = str(step_plan["packetId"])
        current_packet = next(
            (
                row
                for row in current_manifest.get("packets") or []
                if str(row.get("packetId")) == packet_id
            ),
            None,
        )
        if current_packet is None:
            raise GlobalCadManifestOrchestrationError("任务数据包已从CAD事务清单中消失。")
        try:
            live_release_authority = validate_cad_manifest_release_authority(
                workspace,
                current_manifest,
                packets=[current_packet],
            )
        except GlobalCadPacketExecutionError as exc:
            raise GlobalCadManifestOrchestrationError(str(exc)) from exc
        expected_release_authority = plan.get("releaseAuthority") or {}
        if any(
            live_release_authority.get(key) != expected_release_authority.get(key)
            for key in (
                "status",
                "binding",
                "authorizedDrivingTemplateIds",
                "authorizedTemplateCombinationIds",
            )
        ):
            raise GlobalCadManifestOrchestrationError(
                "关系发布授权与任务创建时的绑定不一致。"
            )
        if packet_id == fail_before_packet:
            raise GlobalCadManifestOrchestrationError(
                f"诊断故障注入：在{packet_id}执行前停止；未修改CAD。"
            )
        expected_kind = str(step_plan.get("cumulativeInputKind") or "")
        if expected_kind == "previous_transaction_checkpoint" and previous is None:
            raise GlobalCadManifestOrchestrationError(
                f"{packet_id}要求上一已提交检查点，但任务中不存在。"
            )
        if expected_kind == "existing_assembly_checkpoint_required" and previous is None:
            raise GlobalCadManifestOrchestrationError(
                f"{packet_id}是既有实例关系事务，必须提供已签认装配体检查点。"
            )
        if expected_kind == "base_module_source" and previous is not None:
            raise GlobalCadManifestOrchestrationError("首包不得继承外部检查点。")

        attempt = int(step.get("attemptCount") or 1)
        run_dir = store._dir(str(job["jobId"])) / "packet-runs" / f"{packet_id}-attempt-{attempt:02d}"
        output = _cad_output_path(run_dir, str(plan.get("contextId") or ""), packet_id)
        command = [
            sys.executable,
            str(workspace / "scripts" / "run_global_cad_transaction_packet.py"),
            str(manifest_path),
            packet_id,
            "--output",
            str(output),
            "--run-dir",
            str(run_dir),
        ]
        if previous is not None:
            command.extend(["--input-checkpoint", str(previous.resolve())])
        environment = os.environ.copy()
        backend = workspace / "apps" / "demo-backend" / "src"
        environment["PYTHONPATH"] = str(backend)
        started_at = _now()
        started = perf_counter()
        completed = command_runner(
            command,
            cwd=workspace,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
        duration = round(perf_counter() - started, 6)
        run_dir.mkdir(parents=True, exist_ok=True)
        orchestrator_stdout = run_dir / "orchestrator.stdout.log"
        orchestrator_stderr = run_dir / "orchestrator.stderr.log"
        orchestrator_stdout.write_text(completed.stdout or "", encoding="utf-8")
        orchestrator_stderr.write_text(completed.stderr or "", encoding="utf-8")
        envelope_path = run_dir / "execution-envelope.json"
        envelope = _read_json(envelope_path) if envelope_path.is_file() else {}
        cad_result_path = run_dir / "cad-result.json"
        cad_result = _read_json(cad_result_path) if cad_result_path.is_file() else {}
        cache = envelope.get("baseWrapperCache") or {}
        cache_lookup = cache.get("lookup") or {}
        timing_breakdown = {
            "orchestratorWallSeconds": duration,
            "cadAdapterDurationSeconds": cad_result.get("durationSeconds"),
            "baseWrapperCacheStatus": cache.get("status", "not_applicable"),
            "baseWrapperExecutionDecision": cache.get("executionDecision"),
            "estimatedPreparationSecondsAvoided": (
                cache_lookup.get("cachedPreparationDurationSeconds")
                if cache.get("executionDecision") == "reuse_verified_cache"
                else 0.0
            ),
        }
        accepted = bool(
            completed.returncode == 0
            and envelope.get("success") is True
            and envelope.get("packetId") == packet_id
            and envelope.get("packetDigest") == step_plan.get("packetDigest")
            and envelope.get("sourceAssemblyUnchanged") is True
            and envelope.get("executionSourceUnchanged") is True
            and output.is_file()
        )
        fallback_verification = None
        if step_plan.get("executionStrategy") == "calibrated_static_snapshot_insert":
            tool_result = cad_result.get("toolResult") or {}
            leaf_comparison = tool_result.get("TargetLeafPoseAnchorComparison") or {}
            expected_leaf_count = int(
                ((step_plan.get("drivingExecutionOverride") or {}).get(
                    "expectedInternalLeafPoseAnchorCount"
                ))
                or 2
            )
            fallback_verification = {
                "targetCaseAnchored": tool_result.get("TargetCaseAnchored") is True,
                "caseAnchorPoseMatch": tool_result.get("CaseAnchorPoseMatch") is True,
                "requestedInternalLeafPoseAnchorCount": tool_result.get(
                    "RequestedTargetLeafPoseAnchorCount"
                ),
                "appliedInternalLeafPoseAnchorCount": tool_result.get(
                    "AppliedTargetLeafPoseAnchorCount"
                ),
                "internalLeafPoseAnchorsStable": leaf_comparison.get("Stable") is True,
                "targetConstraintStateAccepted": tool_result.get(
                    "TargetConstraintStateAccepted"
                )
                is True,
                "reopenedMateParametersMatch": tool_result.get(
                    "ReopenedMateParametersMatch"
                )
                is True,
                "portable": False,
                "scope": (step_plan.get("drivingExecutionOverride") or {}).get(
                    "scope"
                ),
            }
            accepted = bool(
                accepted
                and fallback_verification["targetCaseAnchored"]
                and fallback_verification["caseAnchorPoseMatch"]
                and fallback_verification["requestedInternalLeafPoseAnchorCount"]
                == expected_leaf_count
                and fallback_verification["appliedInternalLeafPoseAnchorCount"]
                == expected_leaf_count
                and fallback_verification["internalLeafPoseAnchorsStable"]
                and fallback_verification["targetConstraintStateAccepted"]
                and fallback_verification["reopenedMateParametersMatch"]
            )
        evidence = {
            "schemaVersion": STEP_EVIDENCE_SCHEMA,
            "jobId": job["jobId"],
            "stepId": step["stepId"],
            "packetId": packet_id,
            "packetDigest": step_plan.get("packetDigest"),
            "manifestDigest": plan.get("manifestDigest"),
            "relationReleaseBinding": plan.get("relationReleaseBinding"),
            "releaseAuthority": live_release_authority,
            "attempt": attempt,
            "startedAt": started_at,
            "completedAt": _now(),
            "durationSeconds": duration,
            "timingBreakdown": timing_breakdown,
            "inputCheckpointPath": str(previous.resolve()) if previous else None,
            "outputAssemblyPath": str(output),
            "executionEnvelopePath": str(envelope_path) if envelope_path.is_file() else None,
            "returnCode": completed.returncode,
            "accepted": accepted,
            "calibratedFallbackVerification": fallback_verification,
            "collisionStatus": "not_evaluated",
        }
        orchestration_evidence = run_dir / "orchestration-step-evidence.json"
        orchestration_evidence.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        if accepted and packet_id == pause_after_packet:
            store.request_pause(str(job["jobId"]))
        return {
            "accepted": accepted,
            "assemblyPath": str(output),
            "evidencePath": str(orchestration_evidence),
            "cadActionEvidencePaths": [
                str(path)
                for path in (
                    envelope_path,
                    run_dir / "execution-plan.json",
                    run_dir / "cad-result.json",
                    orchestrator_stdout,
                    orchestrator_stderr,
                )
                if path.is_file()
            ],
            "validationProfile": "generic-cad-transaction-manifest-v1",
            "validationEvidenceKind": "cad-packet-save-close-reopen-envelope",
            "assemblyStatus": "assembled" if accepted else "rejected",
            "collisionStatus": "not_evaluated",
            "packetId": packet_id,
            "packetDigest": step_plan.get("packetDigest"),
            "manifestDigest": plan.get("manifestDigest"),
            "relationReleaseBinding": plan.get("relationReleaseBinding"),
            "releaseAuthority": live_release_authority,
            "timingBreakdown": timing_breakdown,
            "message": (
                "CAD事务包已提交。"
                if accepted
                else f"CAD事务包未通过硬验证（returnCode={completed.returncode}）。"
            ),
        }

    return run

