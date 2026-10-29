"""Compile bounded Chinese datum-position instructions into metre parameters.

The parser deliberately accepts semantic base-frame axes only.  Bare X/Y/Z is
not portable across project coordinate systems and therefore fails closed.
"""

from __future__ import annotations

import math
import re
from typing import Any

from .mechanical_interface_contracts import MechanicalInterfaceContractError


AXES = ("longitudinal", "lateral", "supportGap")
AXIS_LABELS = {
    "longitudinal": r"(?:基座)?纵向",
    "lateral": r"(?:基座)?横向",
    "supportGap": r"(?:支承|支撑)(?:高度|间隙)",
}
NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)"
UNIT = r"(?:毫米|mm|厘米|cm|米|m)"
UNCHANGED = re.compile(r"(?:其余|其他)(?:位置)?参数(?:保持)?不变")


def _metres(number: str, unit: str) -> float:
    value = float(number)
    normalized = unit.lower()
    if normalized in {"毫米", "mm"}:
        value /= 1000.0
    elif normalized in {"厘米", "cm"}:
        value /= 100.0
    elif normalized not in {"米", "m"}:
        raise MechanicalInterfaceContractError(f"unsupported position unit: {unit}")
    if not math.isfinite(value):
        raise MechanicalInterfaceContractError("position value must be finite")
    return value


def _finite_current(parameters: dict[str, Any] | None) -> dict[str, float] | None:
    if parameters is None:
        return None
    if set(parameters) != set(AXES):
        raise MechanicalInterfaceContractError(
            "current position parameters must contain longitudinal, lateral and supportGap"
        )
    result: dict[str, float] = {}
    for key in AXES:
        value = parameters[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise MechanicalInterfaceContractError("current position values must be numeric")
        number = float(value)
        if not math.isfinite(number) or number < 0:
            raise MechanicalInterfaceContractError(
                "current position values must be finite and nonnegative"
            )
        result[key] = number
    return result


def _patterns(axis: str) -> tuple[re.Pattern[str], re.Pattern[str]]:
    label = AXIS_LABELS[axis]
    absolute = re.compile(
        rf"{label}(?:位置|距离|偏移)?\s*"
        rf"(?:(?:调整为|设置为|设为|增加到|减少到|为|=|:|：))?\s*"
        rf"(?P<number>{NUMBER})\s*(?P<unit>{UNIT})",
        re.IGNORECASE,
    )
    delta = re.compile(
        rf"(?:沿)?{label}\s*(?P<verb>移动|调整|偏移|增加|减少)\s*"
        rf"(?P<number>{NUMBER})\s*(?P<unit>{UNIT})",
        re.IGNORECASE,
    )
    return absolute, delta


def compile_parameterized_datum_position_instruction(
    instruction: str,
    *,
    current_parameters_meters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile one bounded absolute or delta instruction.

    Absolute instructions must provide all three axes unless a complete current
    state and an explicit "其余位置参数不变" phrase are present.  Delta commands
    always require both.
    """

    text = str(instruction or "").strip()
    if not text:
        raise MechanicalInterfaceContractError("position instruction is empty")
    if re.search(r"(?:^|[^A-Za-z])(?:X|Y|Z)(?:轴|方向|\s|=|:|：)", text, re.I):
        raise MechanicalInterfaceContractError(
            "bare X/Y/Z is ambiguous; use base longitudinal, lateral and support height"
        )
    current = _finite_current(current_parameters_meters)
    absolute_values: dict[str, float] = {}
    delta_values: dict[str, float] = {}
    matches: list[dict[str, Any]] = []
    for axis in AXES:
        absolute_pattern, delta_pattern = _patterns(axis)
        delta_matches = list(delta_pattern.finditer(text))
        absolute_matches = list(absolute_pattern.finditer(text))
        # The absolute expression can start inside a delta phrase. Remove any
        # overlap so "纵向移动10毫米" is classified only as a delta.
        absolute_matches = [
            match
            for match in absolute_matches
            if not any(
                match.start() >= delta.start() and match.end() <= delta.end()
                for delta in delta_matches
            )
        ]
        if len(absolute_matches) > 1 or len(delta_matches) > 1:
            raise MechanicalInterfaceContractError(
                f"position instruction repeats axis: {axis}"
            )
        if absolute_matches and delta_matches:
            raise MechanicalInterfaceContractError(
                f"position instruction mixes absolute and delta for axis: {axis}"
            )
        if absolute_matches:
            match = absolute_matches[0]
            value = _metres(match.group("number"), match.group("unit"))
            absolute_values[axis] = value
            matches.append(
                {"axis": axis, "mode": "absolute", "valueMeters": value}
            )
        if delta_matches:
            match = delta_matches[0]
            value = _metres(match.group("number"), match.group("unit"))
            verb = match.group("verb")
            if verb == "减少":
                value = -abs(value)
            elif verb == "增加":
                value = abs(value)
            delta_values[axis] = value
            matches.append({"axis": axis, "mode": "delta", "valueMeters": value})

    if not matches:
        raise MechanicalInterfaceContractError(
            "position instruction contains no recognized semantic axis parameter"
        )
    if absolute_values and delta_values:
        raise MechanicalInterfaceContractError(
            "one instruction cannot mix absolute and delta position modes"
        )
    unchanged = bool(UNCHANGED.search(text))
    if delta_values:
        if current is None or not unchanged:
            raise MechanicalInterfaceContractError(
                "delta position instruction requires current parameters and an explicit unchanged clause"
            )
        result = dict(current)
        for axis, delta in delta_values.items():
            result[axis] += delta
        mode = "delta_from_confirmed_current"
    else:
        if len(absolute_values) == len(AXES):
            result = dict(absolute_values)
        elif current is not None and unchanged:
            result = dict(current)
            result.update(absolute_values)
        else:
            raise MechanicalInterfaceContractError(
                "absolute instruction must provide all three parameters or explicitly preserve current values"
            )
        mode = "absolute_in_base_datum_frame"
    if any(not math.isfinite(value) or value < 0 for value in result.values()):
        raise MechanicalInterfaceContractError(
            "compiled position parameters must be finite and nonnegative"
        )
    return {
        "schemaVersion": "parameterized-datum-position-instruction-compilation/v1",
        "instruction": text,
        "coordinateFrame": "selected_base_semantic_datum_frame",
        "mode": mode,
        "parametersMeters": {key: result[key] for key in AXES},
        "recognizedChanges": matches,
        "currentParametersMeters": current,
        "unchangedClausePresent": unchanged,
        "claimBoundary": (
            "The instruction defines a CAD datum position only. It does not prove "
            "physical fastening, collision clearance or production readiness."
        ),
    }
