"""Compile reviewed position decisions into queue-ready exact-pair evidence.

This is a thin interaction layer over the existing engineering review and
semantic-axis language compiler.  It never invents a station: a request must
either explicitly accept an existing recommendation or provide all required
position values in bounded natural language.
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from .mechanical_interface_contracts import MechanicalInterfaceContractError
from .parameterized_datum_engineering_review import SCHEMA as REVIEW_SCHEMA
from .parameterized_datum_position_language import (
    compile_parameterized_datum_position_instruction,
)


REQUEST_SCHEMA = "parameterized-datum-position-decision-requests/v1"
OUTPUT_SCHEMA = "parameterized-datum-position-parameters/v1"
PRIORITY_BATCH_SCHEMA = "parameterized-datum-priority-review-batch/v1"


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _validated_review(review: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    if review.get("schemaVersion") != REVIEW_SCHEMA:
        raise MechanicalInterfaceContractError("unsupported engineering review schema")
    core = {key: value for key, value in review.items() if key != "reviewDigest"}
    if _digest(core) != review.get("reviewDigest"):
        raise MechanicalInterfaceContractError("engineering review digest mismatch")
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for row in review.get("decisions") or []:
        if row.get("decisionKind") != "position_parameters":
            continue
        pair = (
            str(row.get("moduleDefinitionId") or ""),
            str(row.get("slotDefinitionId") or ""),
        )
        if not all(pair) or pair in result:
            raise MechanicalInterfaceContractError(
                f"position review pair is empty or duplicated: {pair}"
            )
        decision_core = {
            key: value for key, value in row.items() if key != "decisionDigest"
        }
        if _digest(decision_core) != row.get("decisionDigest"):
            raise MechanicalInterfaceContractError(
                f"position decision digest mismatch: {pair}"
            )
        result[pair] = row
    return result


def build_position_decision_request_template(review: dict[str, Any]) -> dict[str, Any]:
    """Build an unconfirmed request template for every position decision."""

    decisions = _validated_review(review)
    requests = []
    for pair, decision in sorted(decisions.items()):
        has_recommendation = isinstance(
            decision.get("recommendedParametersMeters"), dict
        )
        requests.append(
            {
                "moduleDefinitionId": pair[0],
                "slotDefinitionId": pair[1],
                "action": (
                    "accept_recommendation"
                    if has_recommendation
                    else "provide_position_instruction"
                ),
                "positionInstruction": None,
                "confirmed": False,
                "source": None,
                "confirmedBy": None,
                "confirmedAt": None,
                "recommendationAvailable": has_recommendation,
                "recommendedParametersMeters": copy.deepcopy(
                    decision.get("recommendedParametersMeters")
                ),
            }
        )
    core = {
        "schemaVersion": REQUEST_SCHEMA,
        "sourceReviewDigest": review["reviewDigest"],
        "requests": requests,
        "claimBoundary": (
            "Every request remains unconfirmed. Accepting a recommendation or "
            "providing coordinates defines only a CAD datum position, not fastening, "
            "clearance, process suitability or production approval."
        ),
    }
    return {**core, "requestTemplateDigest": _digest(core)}


def build_prioritized_position_recommendation_batch(
    review: dict[str, Any], *, limit: int = 8
) -> dict[str, Any]:
    """Select a bounded, review-only first batch from existing recommendations.

    The selector never confirms a decision.  A station registered on the target
    base is ranked before an exact-module cross-base consensus because it has
    direct evidence in the target base coordinate frame.  Ties are stable so a
    regenerated batch is auditable.
    """

    if limit < 5 or limit > 8:
        raise MechanicalInterfaceContractError(
            "priority recommendation batch limit must be between 5 and 8"
        )
    decisions = _validated_review(review)
    candidates: list[dict[str, Any]] = []
    for pair, decision in decisions.items():
        parameters = decision.get("recommendedParametersMeters")
        if not isinstance(parameters, dict):
            continue
        basis = str(decision.get("basis") or "")
        reference = decision.get("reference") or {}
        selection_basis = str(reference.get("selectionBasis") or "")
        if basis == "target_base_registered_role_station_projection":
            priority = 0
            evidence_class = "target_base_registered_role_station"
        elif basis == "prototype_native_role_station_projection":
            priority = 1
            evidence_class = "prototype_native_role_station_review_evidence"
        elif basis == "exact_module_native_station_semantic_coordinate_projection_demo":
            priority = 2
            evidence_class = "exact_module_native_station_demo_projection"
        elif basis == "cross_base_module_station_consensus":
            priority = 3
            evidence_class = "exact_module_cross_base_consensus"
        else:
            # The engineering review may gain new recommendation sources later.
            # Unknown sources remain reviewable but cannot outrank known evidence.
            priority = 4
            evidence_class = "other_review_recommendation"
        candidates.append(
            {
                "moduleDefinitionId": pair[0],
                "slotDefinitionId": pair[1],
                "moduleRole": decision.get("moduleRole"),
                "decisionKind": "position_parameters",
                "priorityTier": priority + 1,
                "evidenceClass": evidence_class,
                "basis": basis,
                "referenceSelectionBasis": selection_basis,
                "referenceModuleDefinitionId": reference.get(
                    "referenceModuleDefinitionId"
                ),
                "referenceBaseDefinitionIds": copy.deepcopy(
                    reference.get("sourceBaseDefinitionIds") or []
                ),
                "recommendedParametersMeters": copy.deepcopy(parameters),
                "decisionDigest": decision["decisionDigest"],
                "confirmationRequest": {
                    "moduleDefinitionId": pair[0],
                    "slotDefinitionId": pair[1],
                    "action": "accept_recommendation",
                    "positionInstruction": None,
                    "confirmed": False,
                    "source": None,
                    "confirmedBy": None,
                    "confirmedAt": None,
                    "recommendationAvailable": True,
                    "recommendedParametersMeters": copy.deepcopy(parameters),
                },
            }
        )
    candidates.sort(
        key=lambda row: (
            int(row["priorityTier"]),
            str(row["moduleDefinitionId"]),
            str(row["slotDefinitionId"]),
        )
    )
    selected = candidates[:limit]
    core = {
        "schemaVersion": PRIORITY_BATCH_SCHEMA,
        "sourceReviewDigest": review["reviewDigest"],
        "requestedBatchSize": limit,
        "availableRecommendationCount": len(candidates),
        "selectedRecommendationCount": len(selected),
        "deferredRecommendationCount": len(candidates) - len(selected),
        "selected": selected,
        "selectionPolicy": [
            "target_base_registered_role_station_projection",
            "prototype_native_role_station_projection",
            "exact_module_native_station_semantic_coordinate_projection_demo",
            "cross_base_module_station_consensus",
            "stable_pair_order",
        ],
        "claimBoundary": (
            "This packet is a bounded engineering review queue, not a confirmation "
            "or CAD execution authority. Every confirmationRequest remains false."
        ),
    }
    return {**core, "batchDigest": _digest(core)}


def build_priority_batch_confirmation_template(
    batch: dict[str, Any],
) -> dict[str, Any]:
    """Return an editable, still-unconfirmed request document for one batch."""

    if batch.get("schemaVersion") != PRIORITY_BATCH_SCHEMA:
        raise MechanicalInterfaceContractError(
            "unsupported priority recommendation batch schema"
        )
    core = {key: value for key, value in batch.items() if key != "batchDigest"}
    if _digest(core) != batch.get("batchDigest"):
        raise MechanicalInterfaceContractError(
            "priority recommendation batch digest mismatch"
        )
    requests = [
        copy.deepcopy(row["confirmationRequest"])
        for row in batch.get("selected") or []
    ]
    return {
        "schemaVersion": REQUEST_SCHEMA,
        "sourceReviewDigest": batch["sourceReviewDigest"],
        "requests": requests,
        "claimBoundary": (
            "All requests remain unconfirmed. Edit each row only after mechanical "
            "review; this document cannot start CAD while confirmed is false."
        ),
    }


def compile_position_decision_requests(
    review: dict[str, Any], requests_document: dict[str, Any]
) -> dict[str, Any]:
    """Compile a partial set of confirmed requests into queue evidence."""

    decisions = _validated_review(review)
    if requests_document.get("schemaVersion") != REQUEST_SCHEMA:
        raise MechanicalInterfaceContractError("unsupported position request schema")
    if requests_document.get("sourceReviewDigest") != review.get("reviewDigest"):
        raise MechanicalInterfaceContractError("position request review binding mismatch")
    records: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for raw in requests_document.get("requests") or []:
        pair = (
            str(raw.get("moduleDefinitionId") or ""),
            str(raw.get("slotDefinitionId") or ""),
        )
        if not all(pair) or pair in seen:
            raise MechanicalInterfaceContractError(
                f"position request pair is empty or duplicated: {pair}"
            )
        seen.add(pair)
        decision = decisions.get(pair)
        if decision is None:
            raise MechanicalInterfaceContractError(
                f"position request is absent from engineering review: {pair}"
            )
        if raw.get("confirmed") is not True:
            raise MechanicalInterfaceContractError(
                f"position request is not explicitly confirmed: {pair}"
            )
        source = str(raw.get("source") or "").strip()
        confirmed_by = str(raw.get("confirmedBy") or "").strip()
        confirmed_at = str(raw.get("confirmedAt") or "").strip()
        if not all((source, confirmed_by, confirmed_at)):
            raise MechanicalInterfaceContractError(
                f"position request confirmation provenance is incomplete: {pair}"
            )
        action = str(raw.get("action") or "")
        instruction = str(raw.get("positionInstruction") or "").strip()
        if action == "accept_recommendation":
            parameters = decision.get("recommendedParametersMeters")
            if not isinstance(parameters, dict):
                raise MechanicalInterfaceContractError(
                    f"position decision has no recommendation to accept: {pair}"
                )
            if instruction:
                raise MechanicalInterfaceContractError(
                    f"accept_recommendation must not include an instruction: {pair}"
                )
            compilation = None
            evidence_basis = "accepted_review_recommendation"
        elif action == "provide_position_instruction":
            if not instruction:
                raise MechanicalInterfaceContractError(
                    f"position instruction is required: {pair}"
                )
            compilation = compile_parameterized_datum_position_instruction(
                instruction
            )
            parameters = compilation["parametersMeters"]
            evidence_basis = "engineer_provided_semantic_axis_instruction"
        else:
            raise MechanicalInterfaceContractError(
                f"unsupported position decision action for {pair}: {action}"
            )
        record = {
            "moduleDefinitionId": pair[0],
            "slotDefinitionId": pair[1],
            "confirmed": True,
            "source": source,
            "confirmedBy": confirmed_by,
            "confirmedAt": confirmed_at,
            "parametersMeters": copy.deepcopy(parameters),
            "evidenceBasis": evidence_basis,
            "sourceReviewDigest": review["reviewDigest"],
            "sourceDecisionDigest": decision["decisionDigest"],
        }
        if compilation is not None:
            record["positionInstruction"] = instruction
            record["positionInstructionCompilation"] = compilation
        records.append(record)
    records.sort(key=lambda row: (row["moduleDefinitionId"], row["slotDefinitionId"]))
    core = {
        "schemaVersion": OUTPUT_SCHEMA,
        "sourceReviewDigest": review["reviewDigest"],
        "confirmedPairCount": len(records),
        "pairs": records,
        "claimBoundary": (
            "Confirmed position parameters only promote exact pairs to non-prototype "
            "CAD candidates. They do not authorize normal assembly before save/reopen "
            "validation and immutable pair release."
        ),
    }
    return {**core, "decisionPacketDigest": _digest(core)}
