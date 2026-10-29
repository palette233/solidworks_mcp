"""Persistent execution state for the broad-combination CAD batch.

This layer plans one exact item at a time and authenticates every resume.  The
six parameterized items use the existing end-to-end queue adapter, while the
final direct item uses the direct-interface CAD and immutable publication
bridge.  Neither path may complete the batch without exact-pair release proof.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

from .broad_combination_cad_validation_batch import (
    BATCH_SCHEMA,
    validate_broad_combination_cad_validation_batch,
)
from .direct_interface_relation_release import (
    plan_direct_interface_cad_validation,
)
from .mechanical_interface_contracts import MechanicalInterfaceContractError
from .parameterized_datum_validation_execution import (
    inspect_materialized_validation_queue,
    plan_next_parameterized_datum_validation,
)


STATE_SCHEMA = "broad-combination-cad-validation-state/v1"


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _relative(workspace: Path, path: Path) -> str:
    return path.resolve().relative_to(workspace.resolve()).as_posix()


def build_broad_combination_cad_validation_state(
    workspace: Path, batch: dict[str, Any]
) -> dict[str, Any]:
    workspace = workspace.resolve()
    validate_broad_combination_cad_validation_batch(workspace, batch)
    queue = str(
        (batch.get("sourceBindings") or {}).get("parameterizedQueueDirectory")
        or ""
    )
    if not queue:
        raise MechanicalInterfaceContractError(
            "broad CAD batch has no parameterized queue binding"
        )
    core = {
        "schemaVersion": STATE_SCHEMA,
        "batchDigest": batch["batchDigest"],
        "status": "pending",
        "currentParameterizedQueueDirectory": queue,
        "completedItemCount": 0,
        "failedItemId": None,
        "items": [
            {
                "itemId": row["itemId"],
                "sequence": row["sequence"],
                "status": "pending",
                "attemptCount": 0,
                "completionEvidence": None,
                "failureEvidence": None,
            }
            for row in batch["items"]
        ],
    }
    return {**core, "stateDigest": _digest(core)}


def validate_broad_combination_cad_validation_state(
    batch: dict[str, Any], state: dict[str, Any]
) -> None:
    if batch.get("schemaVersion") != BATCH_SCHEMA:
        raise MechanicalInterfaceContractError("unsupported broad CAD batch schema")
    if state.get("schemaVersion") != STATE_SCHEMA:
        raise MechanicalInterfaceContractError("unsupported broad CAD state schema")
    expected = _digest(
        {key: value for key, value in state.items() if key != "stateDigest"}
    )
    if state.get("stateDigest") != expected:
        raise MechanicalInterfaceContractError("broad CAD state digest mismatch")
    if state.get("batchDigest") != batch.get("batchDigest"):
        raise MechanicalInterfaceContractError("broad CAD state belongs to another batch")
    expected_ids = [row["itemId"] for row in batch.get("items") or []]
    state_ids = [row.get("itemId") for row in state.get("items") or []]
    if state_ids != expected_ids:
        raise MechanicalInterfaceContractError("broad CAD state item order changed")
    completed = sum(row.get("status") == "completed" for row in state["items"])
    if int(state.get("completedItemCount") or 0) != completed:
        raise MechanicalInterfaceContractError("broad CAD completed count mismatch")
    failed = [row for row in state["items"] if row.get("status") == "failed"]
    failed_id = state.get("failedItemId")
    if bool(failed) != bool(failed_id) or (
        failed and failed[0].get("itemId") != failed_id
    ):
        raise MechanicalInterfaceContractError("broad CAD failed-item state mismatch")
    if len(failed) > 1:
        raise MechanicalInterfaceContractError("broad CAD state has multiple failures")


def _state_item(state: dict[str, Any], item_id: str) -> dict[str, Any]:
    matches = [row for row in state["items"] if row.get("itemId") == item_id]
    if len(matches) != 1:
        raise MechanicalInterfaceContractError("broad CAD state item is not unique")
    return matches[0]


def plan_next_broad_combination_cad_validation(
    workspace: Path,
    batch: dict[str, Any],
    state: dict[str, Any],
    *,
    batch_directory: Path,
) -> dict[str, Any]:
    """Plan the next resumable action without connecting to SolidWorks."""

    workspace = workspace.resolve()
    batch_directory = batch_directory.resolve()
    validate_broad_combination_cad_validation_batch(workspace, batch)
    validate_broad_combination_cad_validation_state(batch, state)
    if state.get("failedItemId"):
        raise MechanicalInterfaceContractError(
            "broad CAD batch is stop-on-failure; resolve or reset the recorded failure"
        )
    pending_state = next(
        (row for row in state["items"] if row.get("status") == "pending"), None
    )
    if pending_state is None:
        return {
            "schemaVersion": "broad-combination-cad-validation-next-plan/v1",
            "action": "batch_complete",
            "batchDigest": batch["batchDigest"],
        }
    item = next(
        row for row in batch["items"] if row["itemId"] == pending_state["itemId"]
    )
    if item["adapter"] == "parameterized_datum_queue":
        queue_dir = workspace / str(state["currentParameterizedQueueDirectory"])
        runtime = inspect_materialized_validation_queue(queue_dir)
        failed_rows = [
            row
            for row in runtime["pairs"]
            if row.get("runtimeState") == "cad_failed_stop_queue"
        ]
        if failed_rows:
            raise MechanicalInterfaceContractError(
                "current parameterized queue contains a failed CAD item"
            )
        adapter_plan = plan_next_parameterized_datum_validation(
            workspace, queue_dir
        )
        actual = (
            adapter_plan["moduleDefinitionId"],
            adapter_plan["slotDefinitionId"],
        )
        expected = (item["moduleDefinitionId"], item["baseDefinitionId"])
        if actual != expected:
            raise MechanicalInterfaceContractError(
                f"parameterized queue next pair differs from batch order: "
                f"expected={expected}, actual={actual}"
            )
        successor = batch_directory / (
            f"queue-successor-{int(item['sequence']):02d}"
        )
        runner = workspace / "scripts/run_parameterized_datum_validation_queue.py"
        command = [
            sys.executable,
            str(runner),
            "run-next",
            str(queue_dir),
            "--successor-queue-dir",
            str(successor),
        ]
        return {
            "schemaVersion": "broad-combination-cad-validation-next-plan/v1",
            "action": "run_parameterized_item_and_publish",
            "batchDigest": batch["batchDigest"],
            "item": copy.deepcopy(item),
            "currentQueueDirectory": _relative(workspace, queue_dir),
            "successorQueueDirectory": _relative(workspace, successor),
            "adapterPlan": adapter_plan,
            "command": command,
            "preconditions": copy.deepcopy(batch["executionPolicy"]),
        }
    if item["adapter"] == "direct_interface":
        package_path = workspace / str(item["validationPackagePath"])
        candidate = package_path.parent
        result_path = candidate / "cad-result.json"
        output_candidates = list(candidate.glob("*-direct-validation-v1.SLDASM"))
        if not result_path.is_file() and output_candidates:
            raise MechanicalInterfaceContractError(
                "direct CAD output exists without authenticated cad-result.json; "
                "manual evidence audit is required before retry"
            )
        if result_path.is_file():
            try:
                existing_result = json.loads(
                    result_path.read_text(encoding="utf-8-sig")
                )
            except (OSError, json.JSONDecodeError) as exc:
                raise MechanicalInterfaceContractError(
                    "direct CAD result cannot be authenticated"
                ) from exc
            if existing_result.get("success") is not True:
                return {
                    "schemaVersion": "broad-combination-cad-validation-next-plan/v1",
                    "action": "direct_item_failed_evidence_requires_superseding_candidate",
                    "batchDigest": batch["batchDigest"],
                    "item": copy.deepcopy(item),
                    "candidateDirectory": _relative(workspace, candidate),
                    "cadResultPath": _relative(workspace, result_path),
                    "preconditions": {
                        **copy.deepcopy(batch["executionPolicy"]),
                        "solidWorksOpenDocumentCountMustEqual": None,
                        "cadSessionRequired": False,
                    },
                }
            return {
                "schemaVersion": "broad-combination-cad-validation-next-plan/v1",
                "action": "finish_direct_publication_without_rerunning_cad",
                "batchDigest": batch["batchDigest"],
                "item": copy.deepcopy(item),
                "candidateDirectory": _relative(workspace, candidate),
                "command": None,
                "preconditions": {
                    **copy.deepcopy(batch["executionPolicy"]),
                    "solidWorksOpenDocumentCountMustEqual": None,
                    "cadSessionRequired": False,
                },
            }
        adapter_plan = plan_direct_interface_cad_validation(workspace, candidate)
        actual = (
            adapter_plan["moduleDefinitionId"],
            adapter_plan["slotDefinitionId"],
        )
        expected = (item["moduleDefinitionId"], item["baseDefinitionId"])
        if actual != expected:
            raise MechanicalInterfaceContractError(
                "direct-interface plan differs from batch item: "
                f"expected={expected}, actual={actual}"
            )
        return {
            "schemaVersion": "broad-combination-cad-validation-next-plan/v1",
            "action": "run_direct_item_and_publish",
            "batchDigest": batch["batchDigest"],
            "item": copy.deepcopy(item),
            "adapterPlan": adapter_plan,
            "command": copy.deepcopy(adapter_plan["command"]),
            "preconditions": copy.deepcopy(batch["executionPolicy"]),
        }
    raise MechanicalInterfaceContractError("unsupported broad CAD batch adapter")


def mark_broad_combination_item_completed(
    batch: dict[str, Any],
    state: dict[str, Any],
    *,
    item_id: str,
    completion_evidence: dict[str, Any],
    successor_queue_directory: str | None = None,
) -> dict[str, Any]:
    """Record one authenticated completion; used by the runner after publishing."""

    validate_broad_combination_cad_validation_state(batch, state)
    result = copy.deepcopy(state)
    row = _state_item(result, item_id)
    first_pending = next(
        (candidate for candidate in result["items"] if candidate["status"] == "pending"),
        None,
    )
    if first_pending is None or first_pending["itemId"] != item_id:
        raise MechanicalInterfaceContractError(
            "broad CAD completion must follow the immutable batch order"
        )
    if completion_evidence.get("exactPairReleased") is not True:
        raise MechanicalInterfaceContractError(
            "broad CAD completion requires exact-pair release evidence"
        )
    if not str(completion_evidence.get("releaseManifestPath") or ""):
        raise MechanicalInterfaceContractError(
            "broad CAD completion has no release manifest binding"
        )
    row["status"] = "completed"
    row["attemptCount"] = int(row.get("attemptCount") or 0) + 1
    row["completionEvidence"] = copy.deepcopy(completion_evidence)
    if successor_queue_directory is not None:
        result["currentParameterizedQueueDirectory"] = successor_queue_directory
    result["completedItemCount"] = sum(
        candidate["status"] == "completed" for candidate in result["items"]
    )
    result["status"] = (
        "completed"
        if result["completedItemCount"] == len(result["items"])
        else "pending"
    )
    result.pop("stateDigest", None)
    result["stateDigest"] = _digest(result)
    validate_broad_combination_cad_validation_state(batch, result)
    return result


def mark_broad_combination_item_failed(
    batch: dict[str, Any],
    state: dict[str, Any],
    *,
    item_id: str,
    failure_evidence: dict[str, Any],
) -> dict[str, Any]:
    validate_broad_combination_cad_validation_state(batch, state)
    result = copy.deepcopy(state)
    row = _state_item(result, item_id)
    if row.get("status") != "pending":
        raise MechanicalInterfaceContractError("only a pending item may fail")
    row["status"] = "failed"
    row["attemptCount"] = int(row.get("attemptCount") or 0) + 1
    row["failureEvidence"] = copy.deepcopy(failure_evidence)
    result["status"] = "failed_stop_queue"
    result["failedItemId"] = item_id
    result.pop("stateDigest", None)
    result["stateDigest"] = _digest(result)
    validate_broad_combination_cad_validation_state(batch, result)
    return result


def recover_failed_broad_combination_item_completed(
    batch: dict[str, Any],
    state: dict[str, Any],
    *,
    item_id: str,
    completion_evidence: dict[str, Any],
    successor_queue_directory: str | None = None,
) -> dict[str, Any]:
    """Recover a failed publication after CAD evidence was already produced.

    This transition is deliberately separate from the normal completion path:
    it preserves the original failure evidence, records explicit recovery
    evidence, and never increments the CAD attempt count.  Callers must first
    authenticate the immutable relation release and the successor queue.
    """

    validate_broad_combination_cad_validation_state(batch, state)
    if state.get("failedItemId") != item_id:
        raise MechanicalInterfaceContractError(
            "only the currently recorded failed broad CAD item may be recovered"
        )
    result = copy.deepcopy(state)
    row = _state_item(result, item_id)
    if row.get("status") != "failed":
        raise MechanicalInterfaceContractError(
            "broad CAD recovery requires a failed item"
        )
    first_incomplete = next(
        (
            candidate
            for candidate in result["items"]
            if candidate.get("status") != "completed"
        ),
        None,
    )
    if first_incomplete is None or first_incomplete.get("itemId") != item_id:
        raise MechanicalInterfaceContractError(
            "broad CAD recovery must follow the immutable batch order"
        )
    if completion_evidence.get("exactPairReleased") is not True:
        raise MechanicalInterfaceContractError(
            "broad CAD recovery requires exact-pair release evidence"
        )
    if completion_evidence.get("naturalLanguageAuthorityReady") is not True:
        raise MechanicalInterfaceContractError(
            "broad CAD recovery requires natural-language authority evidence"
        )
    if not str(completion_evidence.get("releaseManifestPath") or ""):
        raise MechanicalInterfaceContractError(
            "broad CAD recovery has no release manifest binding"
        )
    batch_item = next(row for row in batch["items"] if row["itemId"] == item_id)
    if (
        batch_item.get("adapter") == "parameterized_datum_queue"
        and not str(successor_queue_directory or "")
    ):
        raise MechanicalInterfaceContractError(
            "broad CAD recovery has no authenticated successor queue"
        )
    row["status"] = "completed"
    row["completionEvidence"] = copy.deepcopy(completion_evidence)
    row["recoveryEvidence"] = {
        "publicationRecoveredWithoutCadRerun": True,
        "originalFailureEvidence": copy.deepcopy(row.get("failureEvidence")),
    }
    result["failedItemId"] = None
    if successor_queue_directory is not None:
        result["currentParameterizedQueueDirectory"] = successor_queue_directory
    result["completedItemCount"] = sum(
        candidate["status"] == "completed" for candidate in result["items"]
    )
    result["status"] = (
        "completed"
        if result["completedItemCount"] == len(result["items"])
        else "pending"
    )
    result.pop("stateDigest", None)
    result["stateDigest"] = _digest(result)
    validate_broad_combination_cad_validation_state(batch, result)
    return result
