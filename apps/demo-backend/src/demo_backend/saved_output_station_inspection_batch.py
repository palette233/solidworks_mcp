"""Persistent status for serial read-only inspection batches."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from time import perf_counter
from typing import Any

from .saved_output_station_inspection import (
    authenticate_saved_output_station_inspection_binding,
    build_saved_output_station_inspection_plan,
)


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve(workspace: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (workspace / path).resolve()


def _completed_state_passed(plan: dict[str, Any]) -> bool:
    state_path = Path(plan["outputStatePath"])
    process_path = Path(plan["processReportPath"])
    if not state_path.is_file() or not process_path.is_file():
        return False
    state = _read(state_path)
    process = _read(process_path)
    checks = state.get("checks") or {}
    process_request_path = Path(str(process.get("requestPath") or "")).resolve()
    expected_request_path = Path(str(plan.get("requestPath") or "")).resolve()
    state_assembly_path = Path(str(state.get("assemblyPath") or "")).resolve()
    expected_assembly_path = Path(str(plan.get("outputAssemblyPath") or "")).resolve()
    reference_mappings = plan.get("referenceResolutionMappings") or []
    reference_folders = plan.get("referenceSearchFolders") or []
    reference_state_matches = (
        not reference_folders
        or (
            state.get("referenceSearchSettingsRestored") is True
            and (state.get("referenceSearchFolders") or []) == reference_folders
        )
    )
    return bool(
        process.get("returnCode") == 0
        and process_request_path == expected_request_path
        and process.get("requestDigest") == plan.get("requestDigest")
        and process.get("cadReexecuted") is False
        and process.get("readOnly") is True
        and (process.get("referenceResolutionMappings") or []) == reference_mappings
        and (process.get("referenceSearchFolders") or []) == reference_folders
        and state.get("success") is True
        and state_assembly_path == expected_assembly_path
        and state.get("assemblySha256") == plan.get("outputAssemblySha256")
        and (state.get("observed") or {}).get("readOnly") is True
        and reference_state_matches
        and checks
        and all(value is True for value in checks.values())
    )


def build_saved_output_inspection_batch_status(
    workspace: Path, batch_report_paths: list[Path]
) -> dict[str, Any]:
    clock = perf_counter()
    workspace = workspace.resolve()
    if not batch_report_paths:
        raise ValueError("at least one batch report is required")
    rows: list[dict[str, Any]] = []
    report_bindings: list[dict[str, str]] = []
    identities: set[tuple[str, str]] = set()
    request_paths: set[Path] = set()
    deferred_rows: list[dict[str, Any]] = []
    for report_path in batch_report_paths:
        report_path = report_path.resolve()
        report_path.relative_to(workspace)
        report = _read(report_path)
        if report.get("schemaVersion") != "saved-output-inspection-batch/v1":
            raise ValueError("unsupported saved-output inspection batch")
        if report.get("cadStarted") is not False:
            raise ValueError("request batch unexpectedly claims CAD execution")
        report_bindings.append(
            {
                "path": report_path.relative_to(workspace).as_posix(),
                "sha256": _sha256(report_path),
            }
        )
        for item in report.get("requests") or []:
            identity = (
                str(item.get("sourceModuleDefinitionId") or ""),
                str(item.get("targetBaseDefinitionId") or ""),
            )
            if not all(identity) or identity in identities:
                raise ValueError("duplicate or incomplete exact pair in batch set")
            identities.add(identity)
            request_path = _resolve(workspace, str(item.get("requestPath") or ""))
            request_path.relative_to(workspace)
            if request_path in request_paths:
                raise ValueError("duplicate request path in batch set")
            request_paths.add(request_path)

            request = _read(request_path)
            output_state = _resolve(
                workspace, str(request.get("outputStatePath") or "")
            )
            process_report = _resolve(
                workspace, str(request.get("processReportPath") or "")
            )
            state_exists = output_state.exists()
            process_exists = process_report.exists()
            if state_exists and process_exists:
                plan = authenticate_saved_output_station_inspection_binding(
                    workspace, request_path
                )
                runtime_state = (
                    "passed_readonly_postcheck"
                    if _completed_state_passed(plan)
                    else "failed_readonly_postcheck"
                )
            elif state_exists or process_exists:
                plan = authenticate_saved_output_station_inspection_binding(
                    workspace, request_path
                )
                runtime_state = "incomplete_evidence_requires_review"
            else:
                plan = build_saved_output_station_inspection_plan(
                    workspace, request_path
                )
                runtime_state = "pending_readonly_postcheck"
            rows.append(
                {
                    "sourceModuleDefinitionId": identity[0],
                    "targetBaseDefinitionId": identity[1],
                    "role": item.get("role"),
                    "requestPath": request_path.relative_to(workspace).as_posix(),
                    "runtimeState": runtime_state,
                    "outputStatePath": output_state.relative_to(workspace).as_posix(),
                    "processReportPath": process_report.relative_to(workspace).as_posix(),
                    "readOnly": plan["readOnly"],
                    "recreatesMatesOrComponents": plan["recreatesMatesOrComponents"],
                }
            )
        for item in report.get("deferredRequests") or []:
            identity = (
                str(item.get("sourceModuleDefinitionId") or ""),
                str(item.get("targetBaseDefinitionId") or ""),
            )
            if not all(identity) or identity in identities:
                raise ValueError("duplicate or incomplete deferred exact pair")
            identities.add(identity)
            binding = item.get("deferralManifest") or {}
            manifest_path = Path(str(binding.get("path") or "")).resolve()
            if (
                not manifest_path.is_file()
                or _sha256(manifest_path) != binding.get("sha256")
            ):
                raise ValueError("deferred inspection evidence is missing or changed")
            manifest = _read(manifest_path)
            reason_code = str(manifest.get("reasonCode") or "")
            supported_reason = reason_code in {
                "source_model_unresolved_references",
                "historical_output_not_pair_isolated",
            }
            reason_evidence_valid = False
            if reason_code == "source_model_unresolved_references":
                reason_evidence_valid = bool(manifest.get("unresolvedReferences"))
            elif reason_code == "historical_output_not_pair_isolated":
                details = manifest.get("contextDetails") or {}
                reason_evidence_valid = (
                    int(details.get("expectedTopLevelComponentCount") or 0) >= 2
                    and int(details.get("observedTopLevelComponentCount") or 0)
                    > int(details.get("expectedTopLevelComponentCount") or 0)
                    and bool(details.get("observedTopLevelComponentNames"))
                )
            if (
                manifest.get("schemaVersion")
                != "saved-output-inspection-deferral/v1"
                or manifest.get("sourceModuleDefinitionId") != identity[0]
                or manifest.get("targetBaseDefinitionId") != identity[1]
                or manifest.get("strictStationValidationPassed") is not False
                or not supported_reason
                or not reason_evidence_valid
            ):
                raise ValueError("deferred inspection manifest is invalid")
            for evidence in manifest.get("evidence") or []:
                evidence_path = Path(str(evidence.get("path") or "")).resolve()
                if (
                    not evidence_path.is_file()
                    or _sha256(evidence_path) != evidence.get("sha256")
                ):
                    raise ValueError("deferred inspection source evidence changed")
            deferred_rows.append(
                {
                    "sourceModuleDefinitionId": identity[0],
                    "targetBaseDefinitionId": identity[1],
                    "role": item.get("role"),
                    "runtimeState": f"deferred_{reason_code}",
                    "reasonCode": reason_code,
                    "reason": manifest.get("reason"),
                    "nextAction": manifest.get("nextAction"),
                    "deferralManifestPath": str(manifest_path),
                    "strictStationValidationPassed": False,
                }
            )
    rows.sort(
        key=lambda row: (
            row["role"],
            row["sourceModuleDefinitionId"],
            row["targetBaseDefinitionId"],
        )
    )
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["runtimeState"]] = counts.get(row["runtimeState"], 0) + 1
    for row in deferred_rows:
        state = row["runtimeState"]
        counts[state] = counts.get(state, 0) + 1
    failed = sum(
        count
        for state, count in counts.items()
        if state in {
            "failed_readonly_postcheck",
            "incomplete_evidence_requires_review",
        }
    )
    pending = [
        row for row in rows if row["runtimeState"] == "pending_readonly_postcheck"
    ]
    passed_count = counts.get("passed_readonly_postcheck", 0)
    resolved_count = passed_count + len(deferred_rows)
    return {
        "schemaVersion": "saved-output-inspection-batch-status/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "durationSeconds": perf_counter() - clock,
        "batchReports": report_bindings,
        "requestCount": len(rows),
        "workItemCount": len(rows) + len(deferred_rows),
        "strictPassedCount": passed_count,
        "deferredCount": len(deferred_rows),
        "resolvedWorkItemCount": resolved_count,
        "runtimeStateCounts": counts,
        "status": (
            "blocked_by_failed_or_incomplete_evidence"
            if failed
            else "complete"
            if not pending
            else "ready_for_next_readonly_postcheck"
        ),
        "nextRequestPath": pending[0]["requestPath"] if pending and not failed else None,
        "rows": rows,
        "deferredRows": deferred_rows,
        "executionPolicy": {
            "serial": True,
            "stopAfterFailure": True,
            "skipPassedRequests": True,
            "cadReexecutionAllowed": False,
            "componentOrMateMutationAllowed": False,
            "cleanSolidWorksSessionRequired": True,
        },
    }
