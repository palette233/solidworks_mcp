"""Finite installation-surface gate for parameterized datum placement.

Planar mates operate on infinite mathematical planes.  This helper adds the
missing engineering check: the predicted moving-module footprint must remain
inside the finite support surface registered for the selected base slot.
"""

from __future__ import annotations

import copy
import math
from typing import Any


class FiniteSupportGateError(ValueError):
    """Raised when finite-support evidence is malformed."""


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FiniteSupportGateError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise FiniteSupportGateError(f"{label} must be finite")
    return result


def evaluate_finite_support_gate(
    *,
    module_definition_id: str,
    slot_definition_id: str,
    profile: dict[str, Any],
    position_parameters: dict[str, float],
    distance_flip_dimensions: dict[str, bool],
) -> dict[str, Any]:
    """Predict a rectangular footprint and fail closed outside the boundary."""

    if profile.get("schemaVersion") != "finite-support-profile/v1":
        raise FiniteSupportGateError("unsupported finite support profile")
    boundary = profile.get("safeBoundary") or {}
    base_datums = profile.get("baseDatumCoordinates") or {}
    directions = profile.get("distanceDirectionWhenNotFlipped") or {}
    offsets = profile.get("movingFootprintOffsetsFromDatum") or {}
    expected_parameters = {"longitudinal", "lateral", "supportGap"}
    if set(position_parameters) != expected_parameters:
        raise FiniteSupportGateError("finite support gate requires all position parameters")
    if set(distance_flip_dimensions) != expected_parameters or any(
        not isinstance(distance_flip_dimensions[key], bool)
        for key in expected_parameters
    ):
        raise FiniteSupportGateError("finite support gate requires explicit distance directions")

    min_x = _finite_number(boundary.get("minX"), "safeBoundary.minX")
    max_x = _finite_number(boundary.get("maxX"), "safeBoundary.maxX")
    min_y = _finite_number(boundary.get("minY"), "safeBoundary.minY")
    max_y = _finite_number(boundary.get("maxY"), "safeBoundary.maxY")
    if min_x >= max_x or min_y >= max_y:
        raise FiniteSupportGateError("finite support boundary is empty")

    target_datums: dict[str, float] = {}
    for role in ("longitudinal", "lateral"):
        base = _finite_number(base_datums.get(role), f"baseDatumCoordinates.{role}")
        direction = _finite_number(
            directions.get(role), f"distanceDirectionWhenNotFlipped.{role}"
        )
        if direction not in {-1.0, 1.0}:
            raise FiniteSupportGateError(
                f"distanceDirectionWhenNotFlipped.{role} must be -1 or 1"
            )
        if distance_flip_dimensions[role]:
            direction *= -1.0
        distance = _finite_number(position_parameters[role], role)
        if distance < 0:
            raise FiniteSupportGateError(f"{role} distance must be non-negative")
        target_datums[role] = base + direction * distance

    footprint = {
        "minX": target_datums["longitudinal"]
        + _finite_number(offsets.get("minLongitudinal"), "footprint.minLongitudinal"),
        "maxX": target_datums["longitudinal"]
        + _finite_number(offsets.get("maxLongitudinal"), "footprint.maxLongitudinal"),
        "minY": target_datums["lateral"]
        + _finite_number(offsets.get("minLateral"), "footprint.minLateral"),
        "maxY": target_datums["lateral"]
        + _finite_number(offsets.get("maxLateral"), "footprint.maxLateral"),
    }
    axis_checks = {
        "minXInside": footprint["minX"] >= min_x,
        "maxXInside": footprint["maxX"] <= max_x,
        "minYInside": footprint["minY"] >= min_y,
        "maxYInside": footprint["maxY"] <= max_y,
    }
    passed = all(axis_checks.values())
    return {
        "schemaVersion": "finite-support-gate-result/v1",
        "required": profile.get("required") is True,
        "passed": passed,
        "status": "PASS_FINITE_SUPPORT" if passed else "FAIL_FOOTPRINT_OUTSIDE_SUPPORT",
        "moduleDefinitionId": module_definition_id,
        "slotDefinitionId": slot_definition_id,
        "coordinateFrame": profile.get("coordinateFrame"),
        "positionParametersMeters": copy.deepcopy(position_parameters),
        "distanceFlipDimensions": copy.deepcopy(distance_flip_dimensions),
        "targetDatumCoordinates": target_datums,
        "predictedFootprint": footprint,
        "safeBoundary": {"minX": min_x, "maxX": max_x, "minY": min_y, "maxY": max_y},
        "axisChecks": axis_checks,
        "clearancesMeters": {
            "minX": footprint["minX"] - min_x,
            "maxX": max_x - footprint["maxX"],
            "minY": footprint["minY"] - min_y,
            "maxY": max_y - footprint["maxY"],
        },
        "evidence": copy.deepcopy(profile.get("evidence") or {}),
        "boundary": (
            "This is a finite planar-support containment gate. It does not evaluate "
            "collision/B-rep, fastening, load capacity or production readiness."
        ),
    }
