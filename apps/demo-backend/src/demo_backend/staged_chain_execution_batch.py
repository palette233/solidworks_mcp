"""Inspect an immutable recompilation batch for serial staged-chain execution."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from time import perf_counter
from typing import Any


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_staged_chain_execution_batch_status(
    workspace: Path, batch_report_path: Path
) -> dict[str, Any]:
    """Return the next run/resume action without starting CAD."""

    clock = perf_counter()
    workspace = workspace.resolve()
    batch_report_path = batch_report_path.resolve()
    batch_report_path.relative_to(workspace)
    report = _read(batch_report_path)
    if report.get("schemaVersion") != "staged-chain-registry-recompilation-batch/v1":
        raise ValueError("unsupported staged-chain recompilation batch")
    if report.get("cadStarted") is not False:
        raise ValueError("recompilation batch unexpectedly claims CAD execution")
    rows: list[dict[str, Any]] = []
    next_action: dict[str, str] | None = None
    identities: set[str] = set()
    counts: dict[str, int] = {}
    for order, source in enumerate(report.get("chains") or [], start=1):
        compilation_path = (workspace / source["compilationPath"]).resolve()
        compilation_path.relative_to(workspace)
        if _sha256(compilation_path) != source.get("compilationSha256"):
            raise ValueError("compiled chain evidence changed")
        compilation = _read(compilation_path)
        chain_id = str(compilation.get("chainId") or "")
        if not chain_id or chain_id in identities:
            raise ValueError("compiled chain identity is empty or duplicated")
        identities.add(chain_id)
        if (
            compilation.get("status") != "ready_not_started"
            or compilation.get("cadStarted") is not False
            or compilation.get("targetStationPreflightPassed") is not True
        ):
            raise ValueError("compiled chain is not an authenticated ready input")
        output_root = compilation_path.parent
        chain_path = Path(str(compilation.get("chainPath") or "")).resolve()
        if (
            not chain_path.is_file()
            or _sha256(chain_path) != compilation.get("chainSha256")
        ):
            raise ValueError("compiled chain payload changed")
        chain = _read(chain_path)
        stage_ids = [str(stage.get("stageId") or "") for stage in chain.get("stages") or []]
        if not stage_ids or not all(stage_ids) or len(set(stage_ids)) != len(stage_ids):
            raise ValueError("compiled chain has invalid stage identities")
        committed = [
            stage_id
            for stage_id in stage_ids
            if (output_root / stage_id / "stage-closure.json").is_file()
            and (output_root / stage_id / "station-postcheck.json").is_file()
        ]
        attempts = sorted((output_root / "run-attempts").glob("attempt-*.json"))
        latest = _read(attempts[-1]) if attempts else None
        if latest and latest.get("success") is True:
            if (
                len(committed) != len(stage_ids)
                or latest.get("targetStationValidated") is not True
            ):
                raise ValueError("successful chain attempt lacks committed station evidence")
            runtime_state = "completed_target_station_validated"
            action = None
        elif not attempts and not committed:
            runtime_state = "ready_not_started"
            action = "run"
        else:
            runtime_state = "resume_required"
            action = "resume"
        counts[runtime_state] = counts.get(runtime_state, 0) + 1
        if next_action is None and action is not None:
            next_action = {
                "action": action,
                "outputRoot": output_root.relative_to(workspace).as_posix(),
                "chainId": chain_id,
            }
        rows.append(
            {
                "order": order,
                "chainId": chain_id,
                "outputRoot": output_root.relative_to(workspace).as_posix(),
                "stageCount": len(stage_ids),
                "committedStageCount": len(committed),
                "runtimeState": runtime_state,
                "nextAction": action,
                "latestAttemptPath": (
                    attempts[-1].relative_to(workspace).as_posix() if attempts else None
                ),
            }
        )
    completed = counts.get("completed_target_station_validated", 0)
    return {
        "schemaVersion": "staged-chain-execution-batch-status/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "durationSeconds": perf_counter() - clock,
        "sourceBatchReport": {
            "path": batch_report_path.relative_to(workspace).as_posix(),
            "sha256": _sha256(batch_report_path),
        },
        "chainCount": len(rows),
        "completedChainCount": completed,
        "runtimeStateCounts": counts,
        "status": "complete" if completed == len(rows) else "ready_for_next_chain_action",
        "nextAction": next_action,
        "chains": rows,
        "executionPolicy": {
            "serial": True,
            "stopAfterUnresolvedFailure": True,
            "resumeBeforeStartingNextChain": True,
            "skipCommittedStages": True,
            "cleanSolidWorksSessionRequired": True,
        },
    }
