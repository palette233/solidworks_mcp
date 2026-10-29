"""Aggregate multiple immutable datum-validation queues into one serial workset."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from time import perf_counter
from typing import Any

from .parameterized_datum_validation_execution import (
    inspect_materialized_validation_queue,
)


ACTIONABLE_STATES = {
    "pending_cad_validation",
    "cad_succeeded_pending_pair_release",
    "cad_succeeded_pending_target_station_postcheck",
    "target_station_postcheck_succeeded_pending_pair_release",
    "pair_released_pending_relation_release",
}
COMPLETE_STATES = {"relation_released_for_cumulative_execution"}
FAILED_STATES = {
    "cad_failed_stop_queue",
    "target_station_postcheck_failed_stop_queue",
    "materialized_package_missing",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_parameterized_datum_validation_batch_status(
    workspace: Path, queue_directories: list[Path]
) -> dict[str, Any]:
    """Authenticate and classify an ordered set of existing queue directories."""

    clock = perf_counter()
    workspace = workspace.resolve()
    if not queue_directories:
        raise ValueError("at least one validation queue directory is required")
    queues: list[dict[str, Any]] = []
    identities: set[tuple[str, str]] = set()
    next_queue: str | None = None
    blocked = False
    counts: dict[str, int] = {}
    for order, raw_dir in enumerate(queue_directories, start=1):
        queue_dir = raw_dir.resolve()
        queue_dir.relative_to(workspace)
        manifest = queue_dir / "validation-queue.json"
        status = inspect_materialized_validation_queue(queue_dir)
        queue_states: list[str] = []
        pairs: list[dict[str, Any]] = []
        for row in status.get("pairs") or []:
            identity = (
                str(row.get("moduleDefinitionId") or ""),
                str(row.get("slotDefinitionId") or ""),
            )
            if not all(identity) or identity in identities:
                raise ValueError("duplicate or incomplete exact pair in batch set")
            identities.add(identity)
            state = str(row.get("runtimeState") or "")
            if state not in ACTIONABLE_STATES | COMPLETE_STATES | FAILED_STATES:
                raise ValueError(f"unsupported queue runtime state: {state}")
            counts[state] = counts.get(state, 0) + 1
            queue_states.append(state)
            pairs.append(
                {
                    "moduleDefinitionId": identity[0],
                    "slotDefinitionId": identity[1],
                    "role": row.get("moduleRole"),
                    "runtimeState": state,
                    "candidateDirectory": row.get("candidateDirectory"),
                }
            )
        has_failure = any(state in FAILED_STATES for state in queue_states)
        has_action = any(state in ACTIONABLE_STATES for state in queue_states)
        if has_failure:
            blocked = True
        if next_queue is None and not blocked and has_action:
            next_queue = queue_dir.relative_to(workspace).as_posix()
        queues.append(
            {
                "order": order,
                "queueDirectory": queue_dir.relative_to(workspace).as_posix(),
                "manifestSha256": _sha256(manifest),
                "queueDigest": status["queueDigest"],
                "runtimeStateCounts": status["runtimeStateCounts"],
                "pairs": pairs,
            }
        )
        # Stop-on-failure applies to this and every later queue in the ordered set.
        if has_failure:
            next_queue = None
    actionable_count = sum(counts.get(state, 0) for state in ACTIONABLE_STATES)
    failed_count = sum(counts.get(state, 0) for state in FAILED_STATES)
    complete_count = sum(counts.get(state, 0) for state in COMPLETE_STATES)
    return {
        "schemaVersion": "parameterized-datum-validation-batch-status/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "durationSeconds": perf_counter() - clock,
        "queueCount": len(queues),
        "pairCount": len(identities),
        "runtimeStateCounts": counts,
        "actionablePairCount": actionable_count,
        "completePairCount": complete_count,
        "failedPairCount": failed_count,
        "status": (
            "blocked_by_failed_queue"
            if failed_count
            else "complete"
            if actionable_count == 0
            else "ready_for_next_serial_cad_action"
        ),
        "nextQueueDirectory": next_queue,
        "queues": queues,
        "executionPolicy": {
            "serial": True,
            "stopAfterFailure": True,
            "skipCompletedPairs": True,
            "cleanSolidWorksSessionRequired": True,
            "nonPrototypeInitialPoseRequired": True,
            "saveCloseReopenRequired": True,
            "targetStationPostcheckRequired": True,
        },
    }
