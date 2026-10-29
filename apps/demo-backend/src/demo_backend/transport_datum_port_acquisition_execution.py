"""Persistent read/advance helpers for transport datum-port acquisition.

This state machine is intentionally split at the SolidWorks boundary.  It can
plan a bounded scan and materialize a deterministic review, but it cannot
auto-confirm faces or authorize normal assembly execution.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .transport_datum_port_acquisition import (
    ACQUISITION_ROOT,
    PLAN_SCHEMA,
    REVIEW_SCHEMA,
    TransportDatumPortAcquisitionError,
    _digest,
    _read,
    load_confirmed_transport_datum_source_specs,
    review_transport_datum_leaf_scan,
)


STATUS_SCHEMA = "transport-datum-port-acquisition-status/v1"


def _slug(module_definition_id: str) -> str:
    return module_definition_id.replace("::", "-").replace(":", "-").lower()


def _load_plan(path: Path) -> dict[str, Any]:
    plan = _read(path)
    if plan.get("schemaVersion") != PLAN_SCHEMA:
        raise TransportDatumPortAcquisitionError("unsupported acquisition plan schema")
    core = {key: value for key, value in plan.items() if key != "planDigest"}
    if _digest(core) != plan.get("planDigest"):
        raise TransportDatumPortAcquisitionError("acquisition plan digest mismatch")
    return plan


def _load_review(path: Path, expected: dict[str, Any]) -> dict[str, Any]:
    review = _read(path)
    if review.get("schemaVersion") != REVIEW_SCHEMA:
        raise TransportDatumPortAcquisitionError(
            f"unsupported transport review schema: {path}"
        )
    core = {key: value for key, value in review.items() if key != "reviewDigest"}
    if _digest(core) != review.get("reviewDigest"):
        raise TransportDatumPortAcquisitionError(
            f"transport review digest mismatch: {path}"
        )
    if review.get("reviewDigest") != expected.get("reviewDigest"):
        raise TransportDatumPortAcquisitionError(
            f"transport review is stale for current scan: {path}"
        )
    return review


def inspect_transport_datum_port_acquisition(
    workspace: Path,
    *,
    plan_path: Path | None = None,
) -> dict[str, Any]:
    """Return the authoritative state and the first legal next action."""

    workspace = workspace.resolve()
    plan_path = (
        plan_path.resolve()
        if plan_path is not None
        else workspace / ACQUISITION_ROOT / "scan-plan.json"
    )
    plan = _load_plan(plan_path)
    confirmed_specs = load_confirmed_transport_datum_source_specs(workspace)
    rows: list[dict[str, Any]] = []
    pending_actions: list[dict[str, Any]] = []
    for item in plan.get("items") or []:
        definition_id = str(item.get("moduleDefinitionId") or "")
        slug = _slug(definition_id)
        scan_path = (workspace / str(item.get("scanOutputPath") or "")).resolve()
        review_path = workspace / ACQUISITION_ROOT / "reviews" / f"{slug}-review.json"
        confirmed_path = (
            workspace / ACQUISITION_ROOT / "confirmed-ports" / f"{slug}.json"
        )
        row: dict[str, Any] = {
            "moduleDefinitionId": definition_id,
            "moduleToken": item.get("moduleToken"),
            "scanCatalogPath": str(scan_path),
            "reviewPath": str(review_path),
            "confirmedPortPath": str(confirmed_path),
            "cadExecutionAuthorized": False,
            "normalAssemblyExecutionAuthorized": False,
        }
        if not scan_path.is_file():
            row.update(
                {
                    "state": "bounded_leaf_scan_required",
                    "candidateCount": None,
                }
            )
            action = {
                "action": "run_bounded_leaf_scan",
                "moduleDefinitionId": definition_id,
                "requiresZeroDocumentSolidWorksSession": True,
                "command": item.get("command"),
            }
        else:
            seed = _read(workspace / str(item.get("seedCatalogPath") or ""))
            scan = _read(scan_path)
            expected_review = review_transport_datum_leaf_scan(item, seed, scan)
            if not review_path.is_file():
                row.update(
                    {
                        "state": "candidate_review_generation_required",
                        "candidateCount": expected_review["candidateCount"],
                    }
                )
                action = {
                    "action": "materialize_candidate_review",
                    "moduleDefinitionId": definition_id,
                    "requiresZeroDocumentSolidWorksSession": False,
                    "command": [
                        "python",
                        "scripts/review_transport_datum_leaf_scan.py",
                        "--module-definition-id",
                        definition_id,
                        "--output",
                        str(review_path),
                    ],
                }
            else:
                review = _load_review(review_path, expected_review)
                if definition_id not in confirmed_specs:
                    row.update(
                        {
                            "state": "engineering_confirmation_required",
                            "candidateCount": review["candidateCount"],
                            "candidateIds": [
                                candidate["candidateId"]
                                for candidate in review.get("candidates") or []
                            ],
                            "roleAssignmentRequired": True,
                        }
                    )
                    action = {
                        "action": "confirm_candidate_and_direction_roles",
                        "moduleDefinitionId": definition_id,
                        "requiresZeroDocumentSolidWorksSession": False,
                        "candidateCount": review["candidateCount"],
                        "reviewPath": str(review_path),
                        "confirmedOutputPath": str(confirmed_path),
                        "requiredInputs": [
                            "selectedCandidateId",
                            "longitudinalEndpointId",
                            "lateralEndpointId",
                            "confirmationSource",
                        ],
                    }
                else:
                    row.update(
                        {
                            "state": "confirmed_port_ready_for_catalog_registration",
                            "candidateCount": review["candidateCount"],
                            "confirmationDigest": confirmed_specs[definition_id][
                                "confirmationDigest"
                            ],
                        }
                    )
                    action = None
        rows.append(row)
        if action is not None:
            pending_actions.append(action)

    state_counts: dict[str, int] = {}
    for row in rows:
        state = str(row["state"])
        state_counts[state] = state_counts.get(state, 0) + 1
    if pending_actions:
        priority = {
            "materialize_candidate_review": 0,
            "run_bounded_leaf_scan": 1,
            "confirm_candidate_and_direction_roles": 2,
        }
        next_action = min(
            enumerate(pending_actions),
            key=lambda item: (
                priority.get(str(item[1].get("action") or ""), 99),
                item[0],
            ),
        )[1]
    else:
        next_action = {
            "action": "refresh_parameterized_catalog_and_validation_queue",
            "requiresZeroDocumentSolidWorksSession": False,
            "confirmedModuleDefinitionIds": sorted(confirmed_specs),
            "commands": [
                ["python", "scripts/build_parameterized_datum_placement_catalog.py"],
                [
                    "python",
                    "scripts/run_parameterized_datum_validation_queue.py",
                    "refresh-successor",
                    "<current-validation-queue-directory>",
                    "--successor-queue-dir",
                    "<new-immutable-successor-directory>",
                ],
                ["python", "scripts/build_broad_combination_coverage.py"],
            ],
        }
    core = {
        "schemaVersion": STATUS_SCHEMA,
        "planPath": str(plan_path),
        "planDigest": plan["planDigest"],
        "items": rows,
        "summary": {
            "itemCount": len(rows),
            "stateCounts": state_counts,
            "confirmedPortCount": len(
                [
                    row
                    for row in rows
                    if row["state"]
                    == "confirmed_port_ready_for_catalog_registration"
                ]
            ),
            "normalAssemblyExecutionAuthorizedCount": 0,
            "pendingActionCounts": {
                action_name: sum(
                    str(action.get("action") or "") == action_name
                    for action in pending_actions
                )
                for action_name in sorted(
                    {
                        str(action.get("action") or "")
                        for action in pending_actions
                    }
                )
            },
        },
        "nextAction": next_action,
        "claimBoundary": (
            "A confirmed port is only catalog input. Position parameters, "
            "non-prototype CAD validation, save/reopen and exact pair release "
            "remain mandatory before normal cumulative assembly."
        ),
    }
    return {**core, "statusDigest": _digest(core)}


def materialize_next_transport_datum_review(
    workspace: Path,
    *,
    plan_path: Path | None = None,
) -> dict[str, Any]:
    """Write the first deterministic review whose bounded scan already exists."""

    workspace = workspace.resolve()
    plan_path = (
        plan_path.resolve()
        if plan_path is not None
        else workspace / ACQUISITION_ROOT / "scan-plan.json"
    )
    plan = _load_plan(plan_path)
    for item in plan.get("items") or []:
        definition_id = str(item["moduleDefinitionId"])
        scan_path = (workspace / str(item["scanOutputPath"])).resolve()
        review_path = (
            workspace
            / ACQUISITION_ROOT
            / "reviews"
            / f"{_slug(definition_id)}-review.json"
        )
        if not scan_path.is_file() or review_path.exists():
            continue
        review = review_transport_datum_leaf_scan(
            item,
            _read(workspace / str(item["seedCatalogPath"])),
            _read(scan_path),
        )
        review_path.parent.mkdir(parents=True, exist_ok=True)
        review_path.write_text(
            json.dumps(review, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return {
            "action": "candidate_review_materialized",
            "moduleDefinitionId": definition_id,
            "reviewPath": str(review_path),
            "candidateCount": review["candidateCount"],
            "reviewDigest": review["reviewDigest"],
        }
    raise TransportDatumPortAcquisitionError(
        "no scanned transport item is waiting for review materialization"
    )
