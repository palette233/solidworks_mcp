"""Aggregate the existing station-closure worksets into one serial program."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

from .parameterized_datum_validation_batch import (
    build_parameterized_datum_validation_batch_status,
)
from .saved_output_station_inspection_batch import (
    build_saved_output_inspection_batch_status,
)
from .staged_chain_execution_batch import (
    build_staged_chain_execution_batch_status,
)


def build_station_closure_program_status(
    workspace: Path,
    saved_output_batch_reports: list[Path],
    fresh_validation_queue_directories: list[Path],
    scanner_chain_batch_report: Path,
    six_role_chain_batch_report: Path | None = None,
) -> dict[str, Any]:
    """Return one authoritative next action across the three existing worksets.

    The function does not start CAD and does not reinterpret any lower-level
    result.  It only enforces the required order: historical read-only
    postchecks, fresh non-prototype CAD, then current-context scanner chains.
    """

    clock = perf_counter()
    workspace = workspace.resolve()
    saved = build_saved_output_inspection_batch_status(
        workspace, saved_output_batch_reports
    )
    fresh = build_parameterized_datum_validation_batch_status(
        workspace, fresh_validation_queue_directories
    )
    scanner = build_staged_chain_execution_batch_status(
        workspace, scanner_chain_batch_report
    )
    six_role = (
        build_staged_chain_execution_batch_status(
            workspace, six_role_chain_batch_report
        )
        if six_role_chain_batch_report is not None
        else None
    )
    phases = [
        {
            "phaseId": "saved_output_readonly_postchecks",
            "order": 1,
            "status": saved["status"],
            "totalCount": saved.get("workItemCount", saved["requestCount"]),
            "completedCount": saved.get(
                "resolvedWorkItemCount",
                saved["runtimeStateCounts"].get("passed_readonly_postcheck", 0),
            ),
            "strictPassedCount": saved.get(
                "strictPassedCount",
                saved["runtimeStateCounts"].get("passed_readonly_postcheck", 0),
            ),
            "deferredCount": saved.get("deferredCount", 0),
            "nextInput": saved.get("nextRequestPath"),
        },
        {
            "phaseId": "fresh_nonprototype_cad_validations",
            "order": 2,
            "status": fresh["status"],
            "totalCount": fresh["pairCount"],
            "completedCount": fresh["completePairCount"],
            "nextInput": fresh.get("nextQueueDirectory"),
        },
        {
            "phaseId": "scanner_current_context_chains",
            "order": 3,
            "status": scanner["status"],
            "totalCount": scanner["chainCount"],
            "completedCount": scanner["completedChainCount"],
            "nextInput": (scanner.get("nextAction") or {}).get("outputRoot"),
        },
    ]
    if six_role is not None:
        phases.append(
            {
                "phaseId": "new_six_role_cumulative_chain",
                "order": 4,
                "status": six_role["status"],
                "totalCount": six_role["chainCount"],
                "completedCount": six_role["completedChainCount"],
                "nextInput": (six_role.get("nextAction") or {}).get("outputRoot"),
            }
        )
    next_action: dict[str, Any] | None = None
    program_status = "complete"
    for phase in phases:
        if phase["status"] == "complete":
            continue
        if phase["status"].startswith("blocked_"):
            program_status = "blocked_by_current_phase"
            next_action = {
                "phaseId": phase["phaseId"],
                "action": "review_failure",
                "input": phase["nextInput"],
            }
        else:
            program_status = "ready_for_next_serial_action"
            if phase["phaseId"] == "saved_output_readonly_postchecks":
                action = "run_readonly_postcheck"
            elif phase["phaseId"] == "fresh_nonprototype_cad_validations":
                action = "advance_fresh_validation_queue"
            else:
                source = (
                    six_role
                    if phase["phaseId"] == "new_six_role_cumulative_chain"
                    else scanner
                )
                action = (source.get("nextAction") or {}).get("action")
                if not action:
                    raise ValueError("chain phase is incomplete without a next action")
                suffix = (
                    "six_role_chain"
                    if phase["phaseId"] == "new_six_role_cumulative_chain"
                    else "scanner_chain"
                )
                action = f"{action}_{suffix}"
            next_action = {
                "phaseId": phase["phaseId"],
                "action": action,
                "input": phase["nextInput"],
            }
        break
    return {
        "schemaVersion": "station-closure-program-status/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "durationSeconds": perf_counter() - clock,
        "status": program_status,
        "nextAction": next_action,
        "phases": phases,
        "worksets": {
            "savedOutputReadonlyPostchecks": saved,
            "freshNonprototypeCadValidations": fresh,
            "scannerCurrentContextChains": scanner,
            "newSixRoleCumulativeChain": six_role,
        },
        "executionPolicy": {
            "serialAcrossPhases": True,
            "stopAfterCurrentPhaseFailure": True,
            "doNotSkipIncompleteEarlierPhase": True,
            "cleanSolidWorksSessionRequired": True,
            "collisionOrBrepRequired": False,
            "fasteningRequired": False,
        },
    }
