"""Review and compile exact scanner-to-transport bindings for staged chains.

The mechanical installation of a scanner is only half of a scanner station.
The process target belongs to the *selected transport instance*, not to the
base.  This module turns the reusable measurement inventory into a thin,
auditable decision layer without inventing a new placement or CAD authority.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any


QUEUE_SCHEMA = "scanner-transport-binding-review-queue/v1"
SELECTION_SCHEMA = "scanner-transport-binding-selections/v1"
DECISION_SCHEMA = "scanner-transport-binding-decisions/v1"
CURRENT_CONTEXT_EVALUATION_SCHEMA = (
    "scanner-current-context-point-pair-evaluation/v1"
)
SAVED_CONTEXT_INVENTORY_SCHEMA = "scanner-saved-context-inventory/v1"

# ``station_gap_batch`` originally used the generic semantic-binding category
# for scanner rows.  Once a reusable scanner measurement and a validated
# transport station are both present, the gap is now classified more precisely
# as an exact cumulative-chain instance binding.  Both spellings describe the
# same input readiness for this review queue; neither is CAD authority.
_SCANNER_BINDING_READY_GAP_CATEGORIES = {
    "reusable_measurement_needs_semantic_binding",
    "scanner_exact_chain_instance_binding_required",
}


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _index_measurements(
    inventory: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    if inventory.get("schemaVersion") != "station-measurement-reuse-index/v1":
        raise ValueError("unsupported station measurement inventory")
    scanner_by_definition: dict[str, dict[str, Any]] = {}
    scanner_by_base: dict[str, dict[str, Any]] = {}
    for row in inventory.get("entries") or []:
        if row.get("role") != "Scanner":
            continue
        definition = str(row.get("nativeRoleModuleDefinitionId") or "")
        base = str(row.get("targetBaseDefinitionId") or "")
        if not definition or definition in scanner_by_definition:
            raise ValueError("scanner source measurement is empty or duplicated")
        if not base or base in scanner_by_base:
            raise ValueError("scanner target measurement is empty or duplicated")
        scanner_by_definition[definition] = row
        scanner_by_base[base] = row
    return scanner_by_definition, scanner_by_base


def _validated_transports_by_base(
    coverage: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    if coverage.get("schemaVersion") != "six-role-station-coverage/v1":
        raise ValueError("unsupported station coverage")
    result: dict[str, list[dict[str, Any]]] = {}
    for row in coverage.get("pairs") or []:
        if (
            row.get("role") != "Transport"
            or row.get("validatedStationRule") is not True
            or row.get("executableCurrentAuthority") is not True
        ):
            continue
        base = str(row.get("targetBaseDefinitionId") or "")
        definition = str(row.get("sourceModuleDefinitionId") or "")
        rules = [
            {
                "ruleId": rule.get("ruleId"),
                "ruleDigest": rule.get("ruleDigest"),
                "evidence": copy.deepcopy(rule.get("evidence") or []),
            }
            for rule in row.get("stationRules") or []
            if rule.get("validatedStationRule") is True
        ]
        if not base or not definition or not rules:
            raise ValueError("validated transport station evidence is incomplete")
        result.setdefault(base, []).append(
            {
                "transportModuleDefinitionId": definition,
                "stationRules": rules,
            }
        )
    for rows in result.values():
        rows.sort(key=lambda row: row["transportModuleDefinitionId"])
    return result


def build_scanner_transport_binding_review_queue(
    gap_report: dict[str, Any],
    coverage: dict[str, Any],
    measurement_inventory: dict[str, Any],
) -> dict[str, Any]:
    """Create review-only exact scanner/base/transport candidates.

    A candidate is emitted only when the scanner pair already has executable
    mechanical authority and the target base has a transport station that was
    independently validated.  Instance names intentionally remain unset until
    a cumulative chain has produced the concrete saved context.
    """

    if gap_report.get("schemaVersion") != "station-gap-batch-preparation/v1":
        raise ValueError("unsupported station gap report")
    source_measurements, target_measurements = _index_measurements(
        measurement_inventory
    )
    transports_by_base = _validated_transports_by_base(coverage)
    candidates: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    scanner_rows = sorted(
        [row for row in gap_report.get("queue") or [] if row.get("role") == "Scanner"],
        key=lambda row: (
            str(row.get("targetBaseDefinitionId") or ""),
            str(row.get("sourceModuleDefinitionId") or ""),
        ),
    )
    for row in scanner_rows:
        scanner = str(row.get("sourceModuleDefinitionId") or "")
        base = str(row.get("targetBaseDefinitionId") or "")
        authority = row.get("authority") or {}
        source = source_measurements.get(scanner)
        target = target_measurements.get(base)
        transports = transports_by_base.get(base) or []
        reasons: list[str] = []
        if row.get("gapCategory") not in _SCANNER_BINDING_READY_GAP_CATEGORIES:
            reasons.append("SCANNER_GAP_NOT_SEMANTIC_BINDING_READY")
        if authority.get("ready") is not True:
            reasons.append("SCANNER_MECHANICAL_AUTHORITY_MISSING")
        if source is None:
            reasons.append("SOURCE_SCANNER_OPTICAL_MEASUREMENT_MISSING")
        if target is None:
            reasons.append("TARGET_SCANNER_STATION_MEASUREMENT_MISSING")
        if not transports:
            reasons.append("VALIDATED_TRANSPORT_STATION_MISSING")
        if reasons:
            blocked.append(
                {
                    "sourceModuleDefinitionId": scanner,
                    "targetBaseDefinitionId": base,
                    "blockingReasonCodes": reasons,
                }
            )
            continue
        for transport in transports:
            candidate_core = {
                "sourceModuleDefinitionId": scanner,
                "targetBaseDefinitionId": base,
                "transportModuleDefinitionId": transport[
                    "transportModuleDefinitionId"
                ],
                "scannerMechanicalAuthority": {
                    "relationExecutionMode": authority.get("relationExecutionMode"),
                    "releaseManifestPath": authority.get("releaseManifestPath"),
                },
                "transportStationRules": copy.deepcopy(
                    transport["stationRules"]
                ),
                "sourceOpticalEvidence": copy.deepcopy(source),
                "targetBarcodeStationEvidence": copy.deepcopy(target),
                "status": "ready_for_exact_chain_instance_selection",
                "selectionTemplate": {
                    "confirmed": False,
                    "scannerInstanceId": None,
                    "transportInstanceId": None,
                    "targetBaseInstanceId": None,
                    "confirmedBy": None,
                    "confirmedAt": None,
                },
                "cadLaunchAllowed": False,
                "prototypePoseAllowedAsCadExecutionAuthority": False,
                "requiredAfterSelection": [
                    "bind_exact_saved_context_instance_ids",
                    "reproject_source_optical_frame_to_current_scanner_pose",
                    "reproject_barcode_target_to_selected_transport_pose",
                    "recompute_axis_sign_and_working_distance",
                    "compile_scanner_target_preflight",
                    "execute_mechanical_CAD_then_save_close_reopen",
                ],
                "boundary": (
                    "The candidate binds exact module definitions and reviewed geometry, "
                    "but not live instances. It is not CAD authority, measured scan success, "
                    "collision clearance, fastening or production approval."
                ),
            }
            candidates.append(
                {**candidate_core, "candidateDigest": _digest(candidate_core)}
            )
    candidates.sort(
        key=lambda row: (
            row["targetBaseDefinitionId"],
            row["sourceModuleDefinitionId"],
            row["transportModuleDefinitionId"],
        )
    )
    core = {
        "schemaVersion": QUEUE_SCHEMA,
        "status": "ready_for_chain_instance_selection" if candidates else "blocked",
        "candidates": candidates,
        "blocked": blocked,
        "summary": {
            "scannerGapCount": len(scanner_rows),
            "candidateCount": len(candidates),
            "blockedGapCount": len(blocked),
            "confirmedSelectionCount": 0,
        },
        "sourceGapReportDigest": _digest(gap_report),
        "sourceCoverageDigest": _digest(coverage),
        "sourceMeasurementInventoryDigest": _digest(measurement_inventory),
        "cadStarted": False,
        "claimBoundary": (
            "Review-only exact-definition bindings. A cumulative saved context must "
            "still supply unique instance identities before scanner target preflight."
        ),
    }
    return {**core, "queueDigest": _digest(core)}


def compile_scanner_transport_binding_selections(
    queue: dict[str, Any], selections: dict[str, Any]
) -> dict[str, Any]:
    """Compile explicit live-instance selections without starting CAD."""

    if queue.get("schemaVersion") != QUEUE_SCHEMA:
        raise ValueError("unsupported scanner transport binding queue")
    queue_core = {key: value for key, value in queue.items() if key != "queueDigest"}
    if _digest(queue_core) != queue.get("queueDigest"):
        raise ValueError("scanner transport binding queue digest mismatch")
    if selections.get("schemaVersion") != SELECTION_SCHEMA:
        raise ValueError("unsupported scanner transport selection schema")
    if selections.get("sourceQueueDigest") != queue.get("queueDigest"):
        raise ValueError("scanner transport selection queue binding mismatch")
    by_digest = {
        row["candidateDigest"]: row for row in queue.get("candidates") or []
    }
    decisions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for selection in selections.get("selections") or []:
        candidate_digest = str(selection.get("candidateDigest") or "")
        if not candidate_digest or candidate_digest in seen:
            raise ValueError("scanner transport candidate is empty or duplicated")
        seen.add(candidate_digest)
        candidate = by_digest.get(candidate_digest)
        if candidate is None:
            raise ValueError("scanner transport candidate is not in the bound queue")
        if selection.get("confirmed") is not True:
            raise ValueError("scanner transport instance selection is not confirmed")
        instance_ids = {
            key: str(selection.get(key) or "").strip()
            for key in (
                "scannerInstanceId",
                "transportInstanceId",
                "targetBaseInstanceId",
            )
        }
        provenance = {
            "confirmedBy": str(selection.get("confirmedBy") or "").strip(),
            "confirmedAt": str(selection.get("confirmedAt") or "").strip(),
        }
        if not all(instance_ids.values()) or len(set(instance_ids.values())) != 3:
            raise ValueError("scanner, transport and base instance ids must be unique")
        if not all(provenance.values()):
            raise ValueError("scanner transport selection provenance is incomplete")
        decision_core = {
            "candidateDigest": candidate_digest,
            "sourceModuleDefinitionId": candidate["sourceModuleDefinitionId"],
            "transportModuleDefinitionId": candidate[
                "transportModuleDefinitionId"
            ],
            "targetBaseDefinitionId": candidate["targetBaseDefinitionId"],
            **instance_ids,
            **provenance,
            "sourceOpticalEvidence": copy.deepcopy(
                candidate["sourceOpticalEvidence"]
            ),
            "targetBarcodeStationEvidence": copy.deepcopy(
                candidate["targetBarcodeStationEvidence"]
            ),
            "transportStationRules": copy.deepcopy(
                candidate["transportStationRules"]
            ),
            "scannerMechanicalAuthority": copy.deepcopy(
                candidate["scannerMechanicalAuthority"]
            ),
            "status": "ready_for_saved_context_scanner_target_materialization",
            "cadLaunchAllowed": False,
            "prototypePoseAllowedAsCadExecutionAuthority": False,
        }
        decisions.append(
            {**decision_core, "decisionDigest": _digest(decision_core)}
        )
    decisions.sort(
        key=lambda row: (
            row["targetBaseDefinitionId"],
            row["sourceModuleDefinitionId"],
            row["transportModuleDefinitionId"],
        )
    )
    core = {
        "schemaVersion": DECISION_SCHEMA,
        "sourceQueueDigest": queue["queueDigest"],
        "decisionCount": len(decisions),
        "decisions": decisions,
        "cadStarted": False,
        "claimBoundary": (
            "Exact instance selection only. Current saved transforms must be observed "
            "and scanner geometry recomputed before chain preflight or CAD execution."
        ),
    }
    return {**core, "decisionPacketDigest": _digest(core)}


def apply_scanner_current_context_evaluations(
    queue: dict[str, Any],
    evaluations: list[dict[str, Any]],
    *,
    evidence: list[dict[str, str]],
) -> dict[str, Any]:
    """Refine exact-definition candidates with authenticated saved-context results.

    This only changes the next-action classification.  A failed proxy cannot
    authorize CAD, while a passed proxy still requires the normal CAD/station
    evidence registration path.
    """

    if queue.get("schemaVersion") != QUEUE_SCHEMA:
        raise ValueError("unsupported scanner transport binding queue")
    queue_core = {key: value for key, value in queue.items() if key != "queueDigest"}
    if _digest(queue_core) != queue.get("queueDigest"):
        raise ValueError("scanner transport binding queue digest mismatch")
    if len(evaluations) != len(evidence):
        raise ValueError("scanner current-context evidence list is incomplete")
    candidates = copy.deepcopy(queue.get("candidates") or [])
    by_key = {
        (
            row.get("sourceModuleDefinitionId"),
            row.get("transportModuleDefinitionId"),
            row.get("targetBaseDefinitionId"),
        ): row
        for row in candidates
    }
    if len(by_key) != len(candidates):
        raise ValueError("scanner transport candidate definitions are duplicated")
    seen: set[tuple[str, str, str]] = set()
    for report, source in zip(evaluations, evidence, strict=True):
        if report.get("schemaVersion") != CURRENT_CONTEXT_EVALUATION_SCHEMA:
            raise ValueError("unsupported scanner current-context evaluation")
        report_core = {
            key: value for key, value in report.items() if key != "evaluationDigest"
        }
        if _digest(report_core) != report.get("evaluationDigest"):
            raise ValueError("scanner current-context evaluation digest mismatch")
        definitions = report.get("definitions") or {}
        key = (
            definitions.get("scanner"),
            definitions.get("transport"),
            definitions.get("targetBase"),
        )
        if None in key or key in seen or key not in by_key:
            raise ValueError("scanner current-context evaluation pair is invalid")
        seen.add(key)
        if report.get("targetAssociationBound") is not True:
            raise ValueError("scanner current-context target association is not bound")
        if not all(
            isinstance(source.get(field), str) and source[field]
            for field in ("path", "sha256")
        ):
            raise ValueError("scanner current-context source identity is incomplete")
        passed = report.get("processProxyValidationPassed") is True
        expected_status = (
            "current_context_point_pair_proxy_passed"
            if passed
            else "current_context_point_pair_geometry_mismatch"
        )
        if report.get("status") != expected_status:
            raise ValueError("scanner current-context status differs from result")
        candidate = by_key[key]
        candidate["status"] = (
            "current_context_proxy_passed_requires_station_registration"
            if passed
            else "current_context_point_pair_geometry_mismatch"
        )
        candidate["currentContextEvaluation"] = {
            "status": report["status"],
            "processProxyValidationPassed": passed,
            "instances": copy.deepcopy(report.get("instances") or {}),
            "geometry": copy.deepcopy(report.get("geometry") or {}),
            "blockingReasonCodes": copy.deepcopy(
                report.get("blockingReasonCodes") or []
            ),
            "evaluationDigest": report["evaluationDigest"],
            "source": copy.deepcopy(source),
        }
        candidate["nextAction"] = (
            "register_the_bound_current_context_through_normal_station_postcheck"
            if passed
            else "derive_a_new_scanner_station_candidate_that_reduces_cross_track_error"
        )
        candidate["cadLaunchAllowed"] = False
        candidate["candidateDigest"] = _digest(
            {key: value for key, value in candidate.items() if key != "candidateDigest"}
        )
    core = {
        **{
            key: copy.deepcopy(value)
            for key, value in queue_core.items()
            if key not in {"candidates", "summary", "claimBoundary"}
        },
        "status": "current_context_evaluations_applied",
        "candidates": candidates,
        "summary": {
            **copy.deepcopy(queue.get("summary") or {}),
            "currentContextEvaluationCount": len(evaluations),
            "currentContextProxyPassedCount": sum(
                row.get("processProxyValidationPassed") is True
                for row in evaluations
            ),
            "currentContextGeometryMismatchCount": sum(
                row.get("processProxyValidationPassed") is not True
                for row in evaluations
            ),
        },
        "claimBoundary": (
            "Exact saved-context scanner/transport/base evidence refines the next action "
            "only. It is not new CAD authority, measured scan success, collision "
            "clearance, fastening or production approval."
        ),
    }
    return {**core, "queueDigest": _digest(core)}


def apply_scanner_saved_context_inventory(
    queue: dict[str, Any], inventory: dict[str, Any]
) -> dict[str, Any]:
    """Refine unresolved scanner candidates with a repository context inventory.

    The result separates candidates that can be evaluated immediately from
    candidates that need a new cumulative-chain context.  It never authorizes
    CAD and preserves any stronger current-context geometry conclusion already
    attached to a candidate.
    """

    if queue.get("schemaVersion") != QUEUE_SCHEMA:
        raise ValueError("unsupported scanner transport binding queue")
    queue_core = {key: value for key, value in queue.items() if key != "queueDigest"}
    if _digest(queue_core) != queue.get("queueDigest"):
        raise ValueError("scanner transport binding queue digest mismatch")
    if inventory.get("schemaVersion") != SAVED_CONTEXT_INVENTORY_SCHEMA:
        raise ValueError("unsupported scanner saved-context inventory")
    inventory_core = {
        key: value for key, value in inventory.items() if key != "inventoryDigest"
    }
    if _digest(inventory_core) != inventory.get("inventoryDigest"):
        raise ValueError("scanner saved-context inventory digest mismatch")
    if (inventory.get("reviewQueue") or {}).get("queueDigest") != queue.get(
        "queueDigest"
    ):
        raise ValueError("scanner saved-context inventory queue binding mismatch")

    inventory_by_key = {}
    for row in inventory.get("candidates") or []:
        key = (
            row.get("sourceModuleDefinitionId"),
            row.get("transportModuleDefinitionId"),
            row.get("targetBaseDefinitionId"),
        )
        if None in key or key in inventory_by_key:
            raise ValueError("scanner saved-context inventory contains invalid rows")
        inventory_by_key[key] = row

    candidates = copy.deepcopy(queue.get("candidates") or [])
    for candidate in candidates:
        key = (
            candidate.get("sourceModuleDefinitionId"),
            candidate.get("transportModuleDefinitionId"),
            candidate.get("targetBaseDefinitionId"),
        )
        row = inventory_by_key.get(key)
        if row is None:
            raise ValueError("scanner candidate is missing from saved-context inventory")
        # A measured geometry result is stronger than a repository search and
        # must not be downgraded back to a context-availability status.
        if candidate.get("currentContextEvaluation") is not None:
            continue
        status = row.get("status")
        contexts = copy.deepcopy(row.get("savedContexts") or [])
        if status == "exact_saved_context_available":
            if not contexts:
                raise ValueError("exact scanner saved-context evidence is empty")
            candidate["status"] = (
                "exact_saved_context_available_requires_geometry_evaluation"
            )
            candidate["savedContextInventory"] = contexts
            candidate["nextAction"] = (
                "evaluate_scanner_transport_target_geometry_in_the_exact_saved_context"
            )
        elif status == "new_cumulative_chain_context_required":
            if contexts:
                raise ValueError("missing scanner saved-context row contains evidence")
            candidate["status"] = "new_cumulative_chain_context_required"
            candidate["savedContextInventory"] = []
            candidate["nextAction"] = (
                "build_a_new_cumulative_chain_context_with_the_exact_scanner_"
                "transport_and_base_then_save_reopen"
            )
        else:
            raise ValueError("unsupported scanner saved-context inventory status")
        candidate["cadLaunchAllowed"] = False
        candidate["candidateDigest"] = _digest(
            {key: value for key, value in candidate.items() if key != "candidateDigest"}
        )

    core = {
        **{
            key: copy.deepcopy(value)
            for key, value in queue_core.items()
            if key not in {"candidates", "summary", "claimBoundary"}
        },
        "status": "saved_context_inventory_applied",
        "candidates": candidates,
        "summary": {
            **copy.deepcopy(queue.get("summary") or {}),
            "exactSavedContextAvailableCount": sum(
                row.get("status")
                == "exact_saved_context_available_requires_geometry_evaluation"
                for row in candidates
            ),
            "newCumulativeChainContextRequiredCount": sum(
                row.get("status") == "new_cumulative_chain_context_required"
                for row in candidates
            ),
        },
        "savedContextInventory": {
            "inventoryDigest": inventory["inventoryDigest"],
            "summary": copy.deepcopy(inventory.get("summary") or {}),
        },
        "claimBoundary": (
            "Saved-context inventory only refines the next action. Missing triples "
            "require a new cumulative context and cannot be filled with prototype "
            "poses; matching triples still require current-pose geometry evaluation."
        ),
    }
    return {**core, "queueDigest": _digest(core)}
