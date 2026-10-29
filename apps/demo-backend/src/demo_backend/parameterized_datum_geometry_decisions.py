"""Compile reviewed geometry choices into queue-ready evidence documents.

The engineering review exposes three non-position decision kinds: one locating
axis, one ordered locating-axis pair, or one flexible-slot axis plus an offset.
This module is deliberately a thin confirmation layer.  It binds every choice
to the immutable review and decision digests, validates the selected identity
against the current authoritative candidate catalog, and emits the three
schemas already consumed by the datum validation queue.

No candidate is selected automatically.  A review recommendation may be
accepted explicitly, but a nearest axis is never silently treated as approved.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from .flexible_calibration_slot_selection import (
    build_g000_flexible_slot_candidate_catalog,
)
from .hybrid_plane_axis_slot_selection import (
    build_f000_hybrid_axis_slot_catalog,
)
from .mechanical_interface_contracts import MechanicalInterfaceContractError
from .parameterized_datum_engineering_review import SCHEMA as REVIEW_SCHEMA
from .two_axis_slot_selection import build_two_axis_slot_candidate_catalog


REQUEST_SCHEMA = "parameterized-datum-geometry-decision-requests/v1"
BUNDLE_SCHEMA = "parameterized-datum-geometry-decision-evidence-bundle/v1"
AXIS_SCHEMA = "hybrid-plane-axis-selection-evidence/v1"
AXIS_PAIR_SCHEMA = "two-axis-slot-selection-evidence/v1"
FLEXIBLE_SLOT_SCHEMA = "flexible-calibration-slot-selection-evidence/v1"

SUPPORTED_KINDS = {
    "axis_selection",
    "axis_pair_selection",
    "flexible_slot_selection",
}


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _validated_review(
    review: dict[str, Any],
) -> dict[tuple[str, str], dict[str, Any]]:
    if review.get("schemaVersion") != REVIEW_SCHEMA:
        raise MechanicalInterfaceContractError(
            "unsupported engineering review schema"
        )
    core = {key: value for key, value in review.items() if key != "reviewDigest"}
    if _digest(core) != review.get("reviewDigest"):
        raise MechanicalInterfaceContractError("engineering review digest mismatch")
    decisions: dict[tuple[str, str], dict[str, Any]] = {}
    for row in review.get("decisions") or []:
        if row.get("decisionKind") not in SUPPORTED_KINDS:
            continue
        pair = (
            str(row.get("moduleDefinitionId") or ""),
            str(row.get("slotDefinitionId") or ""),
        )
        if not all(pair) or pair in decisions:
            raise MechanicalInterfaceContractError(
                f"geometry review pair is empty or duplicated: {pair}"
            )
        decision_core = {
            key: value for key, value in row.items() if key != "decisionDigest"
        }
        if _digest(decision_core) != row.get("decisionDigest"):
            raise MechanicalInterfaceContractError(
                f"geometry decision digest mismatch: {pair}"
            )
        decisions[pair] = row
    return decisions


def _finite_pair(value: Any, label: str) -> dict[str, float]:
    if not isinstance(value, dict) or set(value) != {"longitudinal", "lateral"}:
        raise MechanicalInterfaceContractError(
            f"{label} must contain longitudinal and lateral metre values"
        )
    result: dict[str, float] = {}
    for key in ("longitudinal", "lateral"):
        raw = value[key]
        if (
            isinstance(raw, bool)
            or not isinstance(raw, (int, float))
            or not math.isfinite(float(raw))
        ):
            raise MechanicalInterfaceContractError(
                f"{label}.{key} must be a finite metre value"
            )
        result[key] = float(raw)
    return result


def _provenance(raw: dict[str, Any], pair: tuple[str, str]) -> dict[str, str]:
    if raw.get("confirmed") is not True:
        raise MechanicalInterfaceContractError(
            f"geometry request is not explicitly confirmed: {pair}"
        )
    result = {
        "source": str(raw.get("source") or "").strip(),
        "confirmedBy": str(raw.get("confirmedBy") or "").strip(),
        "confirmedAt": str(raw.get("confirmedAt") or "").strip(),
    }
    if not all(result.values()):
        raise MechanicalInterfaceContractError(
            f"geometry request confirmation provenance is incomplete: {pair}"
        )
    return result


def build_geometry_decision_request_template(
    review: dict[str, Any],
) -> dict[str, Any]:
    """Build an unconfirmed request for each unresolved geometry decision."""

    decisions = _validated_review(review)
    requests: list[dict[str, Any]] = []
    for pair, decision in sorted(decisions.items()):
        kind = str(decision["decisionKind"])
        if kind == "axis_selection":
            recommendation = decision.get("recommendedAxisEndpointId")
            request = {
                "moduleDefinitionId": pair[0],
                "slotDefinitionId": pair[1],
                "decisionKind": kind,
                "action": (
                    "accept_recommendation"
                    if recommendation
                    else "select_axis"
                ),
                "selectedAxisEndpointId": None,
                "requestedPositionMeters": copy.deepcopy(
                    decision.get("requestedPositionMeters")
                ),
                "recommendationAvailable": bool(recommendation),
                "recommendedAxisEndpointId": recommendation,
                "availableAxisLineCount": decision.get(
                    "availableAxisLineCount"
                ),
                "reviewedCandidateCount": len(
                    decision.get("rankedAxisCandidates") or []
                ),
            }
        elif kind == "axis_pair_selection":
            recommendation = decision.get("recommendedCandidatePairId")
            request = {
                "moduleDefinitionId": pair[0],
                "slotDefinitionId": pair[1],
                "decisionKind": kind,
                "action": (
                    "accept_recommendation"
                    if recommendation
                    else "select_axis_pair"
                ),
                "selectedCandidatePairId": None,
                "recommendationAvailable": bool(recommendation),
                "recommendedCandidatePairId": recommendation,
                "recommendedAxisAssignment": decision.get(
                    "recommendedAxisAssignment"
                ),
                "recommendedPairRmsMeters": decision.get(
                    "recommendedPairRmsMeters"
                ),
                "candidatePairCount": int(decision.get("candidatePairCount") or 0),
                "candidatePairIds": [
                    str(row["candidatePairId"])
                    for row in decision.get("axisPairCandidates") or []
                ],
            }
        else:
            recommendation = decision.get("recommendedAxisEndpointId")
            request = {
                "moduleDefinitionId": pair[0],
                "slotDefinitionId": pair[1],
                "decisionKind": kind,
                "action": (
                    "accept_recommendation"
                    if recommendation
                    else "select_flexible_slot"
                ),
                "selectedAxisEndpointId": None,
                "longitudinalOffsetMeters": None,
                "recommendationAvailable": bool(recommendation),
                "recommendedAxisEndpointId": recommendation,
                "recommendedLongitudinalOffsetMeters": decision.get(
                    "recommendedLongitudinalOffsetMeters"
                ),
                "candidateAxisLineCount": int(
                    (decision.get("reference") or {}).get(
                        "candidateAxisLineCount"
                    )
                    or 0
                ),
            }
        request.update(
            {
                "confirmed": False,
                "source": None,
                "confirmedBy": None,
                "confirmedAt": None,
                "sourceDecisionDigest": decision["decisionDigest"],
            }
        )
        requests.append(request)
    core = {
        "schemaVersion": REQUEST_SCHEMA,
        "sourceReviewDigest": review["reviewDigest"],
        "requestCount": len(requests),
        "requests": requests,
        "claimBoundary": (
            "Every geometry choice remains unconfirmed. Candidate identity, hole "
            "purpose, installation side and module envelope require engineering "
            "review. Compilation creates only non-prototype CAD validation evidence."
        ),
    }
    return {**core, "requestTemplateDigest": _digest(core)}


def _axis_candidates(workspace: Path) -> dict[tuple[str, str], set[str]]:
    catalog = build_f000_hybrid_axis_slot_catalog(workspace)
    module = str(catalog.get("moduleDefinitionId") or "")
    return {
        (module, str(slot["slotDefinitionId"])): {
            str(row["endpointId"]) for row in slot.get("axisCandidates") or []
        }
        for slot in catalog.get("baseSlots") or []
        if slot.get("state") == "explicit_axis_selection_required"
    }


def _axis_pair_candidates(workspace: Path) -> dict[tuple[str, str], set[str]]:
    catalog = build_two_axis_slot_candidate_catalog(workspace)
    result: dict[tuple[str, str], set[str]] = {}
    for family in catalog.get("families") or []:
        slot = str(family.get("slotDefinitionId") or "")
        candidates = {
            str(row["candidatePairId"])
            for row in family.get("axisPairCandidates") or []
        }
        for module in family.get("moduleDefinitionIds") or []:
            result[(str(module), slot)] = candidates
    return result


def _flexible_slot_candidates(workspace: Path) -> dict[tuple[str, str], set[str]]:
    catalog = build_g000_flexible_slot_candidate_catalog(workspace)
    module = str(catalog.get("moduleDefinitionId") or "")
    return {
        (module, str(slot["slotDefinitionId"])): {
            str(row["endpointId"]) for row in slot.get("axisCandidates") or []
        }
        for slot in catalog.get("baseSlots") or []
        if slot.get("state") == "explicit_flexible_slot_selection_required"
    }


def compile_geometry_decision_requests(
    workspace: Path,
    review: dict[str, Any],
    requests_document: dict[str, Any],
) -> dict[str, Any]:
    """Compile confirmed exact choices into the queue's three evidence schemas."""

    workspace = workspace.resolve()
    decisions = _validated_review(review)
    if requests_document.get("schemaVersion") != REQUEST_SCHEMA:
        raise MechanicalInterfaceContractError(
            "unsupported geometry request schema"
        )
    if requests_document.get("sourceReviewDigest") != review.get("reviewDigest"):
        raise MechanicalInterfaceContractError(
            "geometry request review binding mismatch"
        )
    axis_catalog = _axis_candidates(workspace)
    pair_catalog = _axis_pair_candidates(workspace)
    flexible_catalog = _flexible_slot_candidates(workspace)
    axes: list[dict[str, Any]] = []
    axis_pairs: list[dict[str, Any]] = []
    flexible_slots: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for raw in requests_document.get("requests") or []:
        pair = (
            str(raw.get("moduleDefinitionId") or ""),
            str(raw.get("slotDefinitionId") or ""),
        )
        if not all(pair) or pair in seen:
            raise MechanicalInterfaceContractError(
                f"geometry request pair is empty or duplicated: {pair}"
            )
        seen.add(pair)
        decision = decisions.get(pair)
        if decision is None:
            raise MechanicalInterfaceContractError(
                f"geometry request is absent from engineering review: {pair}"
            )
        if raw.get("decisionKind") != decision.get("decisionKind"):
            raise MechanicalInterfaceContractError(
                f"geometry request decision kind mismatch: {pair}"
            )
        if raw.get("sourceDecisionDigest") != decision.get("decisionDigest"):
            raise MechanicalInterfaceContractError(
                f"geometry request decision binding mismatch: {pair}"
            )
        provenance = _provenance(raw, pair)
        common = {
            "moduleDefinitionId": pair[0],
            "slotDefinitionId": pair[1],
            "confirmed": True,
            **provenance,
            "sourceReviewDigest": review["reviewDigest"],
            "sourceDecisionDigest": decision["decisionDigest"],
        }
        kind = str(decision["decisionKind"])
        action = str(raw.get("action") or "")
        if kind == "axis_selection":
            if action == "accept_recommendation":
                selected = str(
                    decision.get("recommendedAxisEndpointId") or ""
                )
                if not selected:
                    raise MechanicalInterfaceContractError(
                        f"axis decision has no recommendation to accept: {pair}"
                    )
                if str(raw.get("selectedAxisEndpointId") or ""):
                    raise MechanicalInterfaceContractError(
                        f"accept_recommendation must not override the axis: {pair}"
                    )
                requested_position = copy.deepcopy(
                    decision.get("requestedPositionMeters")
                )
                basis = "accepted_review_axis_recommendation"
            elif action == "select_axis":
                selected = str(raw.get("selectedAxisEndpointId") or "")
                if not selected:
                    raise MechanicalInterfaceContractError(
                        f"axis selection requires an endpoint: {pair}"
                    )
                requested_position = raw.get("requestedPositionMeters")
                if decision.get("requestedPositionMeters") is None:
                    requested_position = _finite_pair(
                        requested_position, f"requested scanner position for {pair}"
                    )
                elif requested_position is not None:
                    requested_position = _finite_pair(
                        requested_position, f"requested scanner position for {pair}"
                    )
                basis = "engineer_selected_exact_axis"
            else:
                raise MechanicalInterfaceContractError(
                    f"unsupported axis selection action for {pair}: {action}"
                )
            if selected not in axis_catalog.get(pair, set()):
                raise MechanicalInterfaceContractError(
                    f"selected axis is absent from authoritative catalog: {pair}"
                )
            axes.append(
                {
                    **common,
                    "selectedAxisEndpointId": selected,
                    "requestedPositionMeters": requested_position,
                    "evidenceBasis": basis,
                }
            )
        elif kind == "axis_pair_selection":
            if action not in {"accept_recommendation", "select_axis_pair"}:
                raise MechanicalInterfaceContractError(
                    f"unsupported axis-pair action for {pair}: {action}"
                )
            if action == "accept_recommendation":
                selected = str(decision.get("recommendedCandidatePairId") or "")
                if not selected:
                    raise MechanicalInterfaceContractError(
                        f"axis-pair decision has no recommendation: {pair}"
                    )
                if raw.get("selectedCandidatePairId"):
                    raise MechanicalInterfaceContractError(
                        f"accept_recommendation must not override the axis pair: {pair}"
                    )
                evidence_basis = "accepted_native_primary_secondary_station_recommendation"
            else:
                selected = str(raw.get("selectedCandidatePairId") or "")
                evidence_basis = "engineer_selected_exact_axis_pair"
            if selected not in pair_catalog.get(pair, set()):
                raise MechanicalInterfaceContractError(
                    f"selected axis pair is absent from authoritative catalog: {pair}"
                )
            axis_pairs.append(
                {
                    **common,
                    "selectedCandidatePairId": selected,
                    "evidenceBasis": evidence_basis,
                }
            )
        else:
            if action not in {"accept_recommendation", "select_flexible_slot"}:
                raise MechanicalInterfaceContractError(
                    f"unsupported flexible-slot action for {pair}: {action}"
                )
            if action == "accept_recommendation":
                selected = str(decision.get("recommendedAxisEndpointId") or "")
                offset = decision.get("recommendedLongitudinalOffsetMeters")
                if not selected or offset is None:
                    raise MechanicalInterfaceContractError(
                        f"flexible-slot decision has no recommendation: {pair}"
                    )
                if raw.get("selectedAxisEndpointId") or raw.get(
                    "longitudinalOffsetMeters"
                ) is not None:
                    raise MechanicalInterfaceContractError(
                        f"accept_recommendation must not override the flexible slot: {pair}"
                    )
                evidence_basis = "accepted_native_semantic_station_recommendation"
            else:
                selected = str(raw.get("selectedAxisEndpointId") or "")
                offset = raw.get("longitudinalOffsetMeters")
                evidence_basis = "engineer_selected_exact_axis_and_offset"
            if selected not in flexible_catalog.get(pair, set()):
                raise MechanicalInterfaceContractError(
                    f"selected flexible-slot axis is absent from authoritative catalog: {pair}"
                )
            if (
                isinstance(offset, bool)
                or not isinstance(offset, (int, float))
                or not math.isfinite(float(offset))
                or float(offset) < 0
            ):
                raise MechanicalInterfaceContractError(
                    f"flexible-slot selection requires a nonnegative offset: {pair}"
                )
            flexible_slots.append(
                {
                    **common,
                    "selectedAxisEndpointId": selected,
                    "longitudinalOffsetMeters": float(offset),
                    "evidenceBasis": evidence_basis,
                }
            )
    for rows in (axes, axis_pairs, flexible_slots):
        rows.sort(
            key=lambda row: (row["moduleDefinitionId"], row["slotDefinitionId"])
        )
    axis_document = {"schemaVersion": AXIS_SCHEMA, "pairs": axes}
    axis_pair_document = {"schemaVersion": AXIS_PAIR_SCHEMA, "pairs": axis_pairs}
    flexible_document = {
        "schemaVersion": FLEXIBLE_SLOT_SCHEMA,
        "pairs": flexible_slots,
    }
    core = {
        "schemaVersion": BUNDLE_SCHEMA,
        "sourceReviewDigest": review["reviewDigest"],
        "confirmedDecisionCount": len(axes) + len(axis_pairs) + len(flexible_slots),
        "confirmedAxisSelectionCount": len(axes),
        "confirmedAxisPairSelectionCount": len(axis_pairs),
        "confirmedFlexibleSlotSelectionCount": len(flexible_slots),
        "axisSelections": axis_document,
        "axisPairSelections": axis_pair_document,
        "flexibleSlotSelections": flexible_document,
        "claimBoundary": (
            "Confirmed geometry choices promote only exact pairs to non-prototype "
            "CAD candidates. They do not authorize normal assembly before CAD "
            "save/reopen validation and immutable pair release."
        ),
    }
    return {**core, "decisionBundleDigest": _digest(core)}


def geometry_decision_evidence_maps(
    bundle: dict[str, Any],
) -> dict[str, dict[tuple[str, str], dict[str, Any]]]:
    """Validate a compiled bundle and return maps accepted by the queue API."""

    if bundle.get("schemaVersion") != BUNDLE_SCHEMA:
        raise MechanicalInterfaceContractError(
            "unsupported geometry decision evidence bundle schema"
        )
    core = {
        key: value for key, value in bundle.items() if key != "decisionBundleDigest"
    }
    if _digest(core) != bundle.get("decisionBundleDigest"):
        raise MechanicalInterfaceContractError(
            "geometry decision evidence bundle digest mismatch"
        )
    specs = {
        "axisSelections": (AXIS_SCHEMA, "axisSelections"),
        "axisPairSelections": (AXIS_PAIR_SCHEMA, "axisPairSelections"),
        "flexibleSlotSelections": (FLEXIBLE_SLOT_SCHEMA, "flexibleSlotSelections"),
    }
    result: dict[str, dict[tuple[str, str], dict[str, Any]]] = {}
    total = 0
    for output_key, (schema, field) in specs.items():
        document = bundle.get(field)
        if not isinstance(document, dict) or document.get("schemaVersion") != schema:
            raise MechanicalInterfaceContractError(
                f"geometry decision bundle has invalid {field} document"
            )
        rows: dict[tuple[str, str], dict[str, Any]] = {}
        for raw in document.get("pairs") or []:
            pair = (
                str(raw.get("moduleDefinitionId") or ""),
                str(raw.get("slotDefinitionId") or ""),
            )
            if not all(pair) or pair in rows:
                raise MechanicalInterfaceContractError(
                    f"geometry decision bundle pair is empty or duplicated: {pair}"
                )
            rows[pair] = {
                key: copy.deepcopy(value)
                for key, value in raw.items()
                if key not in {"moduleDefinitionId", "slotDefinitionId"}
            }
        result[output_key] = rows
        total += len(rows)
    if total != int(bundle.get("confirmedDecisionCount") or 0):
        raise MechanicalInterfaceContractError(
            "geometry decision bundle confirmed count mismatch"
        )
    return result
