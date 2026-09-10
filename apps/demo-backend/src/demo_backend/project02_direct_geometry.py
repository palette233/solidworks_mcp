from __future__ import annotations

import copy
import math
from datetime import datetime, timezone
from typing import Any, Iterable


SCHEMA_VERSION = "project02-direct-module-geometry-calibration/v1"


def _dot(first: Iterable[float], second: Iterable[float]) -> float:
    return sum(float(a) * float(b) for a, b in zip(first, second))


def _subtract(first: Iterable[float], second: Iterable[float]) -> list[float]:
    return [float(a) - float(b) for a, b in zip(first, second)]


def _component_code(name: str) -> str:
    upper = name.upper()
    if "D062A" in upper:
        return "A" + upper.split("D062A", 1)[1].split(".", 1)[0]
    if upper.startswith("T401"):
        return "T401"
    return name


def build_direct_geometry_calibration(
    layout: dict[str, Any],
    saved_poses: list[dict[str, Any]],
    *,
    component_codes: Iterable[str],
    evidence_path: str,
) -> dict[str, Any]:
    """Measure rigid-module footprint offsets from a direct assembly instance.

    The resulting offsets are relative to the solver anchor, not to the
    prototype world position.  They can therefore be reused after translation
    as long as the allowed orientation and referenced source configuration stay
    unchanged.
    """
    frame = layout.get("baseFrame") or {}
    origin = [float(value) for value in frame.get("origin") or []]
    u_axis = [float(value) for value in frame.get("uAxis") or []]
    v_axis = [float(value) for value in frame.get("vAxis") or []]
    normal = [float(value) for value in frame.get("normal") or []]
    if any(len(item) != 3 for item in (origin, u_axis, v_axis, normal)):
        raise ValueError("Layout baseFrame is incomplete.")
    layout_by_code = {
        _component_code(str(item.get("componentName") or "")): item
        for item in layout.get("components") or []
    }
    pose_by_code = {
        _component_code(str(item.get("Name", item.get("name", "")))): item
        for item in saved_poses
    }
    entries = []
    for code in component_codes:
        if code not in layout_by_code or code not in pose_by_code:
            raise ValueError(f"Direct geometry evidence is missing component {code}.")
        component = layout_by_code[code]
        pose = pose_by_code[code]
        box = [float(value) for value in pose.get("BoundingBoxWorld") or []]
        if len(box) != 6:
            raise ValueError(f"Direct geometry evidence for {code} has no world AABB.")
        corners = [
            [x, y, z]
            for x in (box[0], box[3])
            for y in (box[1], box[4])
            for z in (box[2], box[5])
        ]
        projected = [
            (
                _dot(_subtract(point, origin), u_axis),
                _dot(_subtract(point, origin), v_axis),
                _dot(_subtract(point, origin), normal),
            )
            for point in corners
        ]
        layout2d = component.get("layout2d") or {}
        anchor = [float(layout2d.get("x", 0.0)), float(layout2d.get("y", 0.0))]
        oriented_corners = [
            (point[0] - anchor[0], point[1] - anchor[1]) for point in projected
        ]
        rotation_quarters = int(
            (component.get("constraintPlacement") or {}).get("rotationQuarters", 0)
        )
        # layoutFootprintBoundsLocal is stored in the component's canonical q0
        # frame.  Direct evidence may come from q1/q2/q3, so undo that layout
        # rotation before persisting the reusable local footprint.
        radians = math.radians(-(rotation_quarters % 4) * 90.0)
        cosine, sine = math.cos(radians), math.sin(radians)
        canonical_corners = [
            (cosine * u - sine * v, sine * u + cosine * v)
            for u, v in oriented_corners
        ]
        bounds = [
            min(point[0] for point in canonical_corners),
            min(point[1] for point in canonical_corners),
            max(point[0] for point in canonical_corners),
            max(point[1] for point in canonical_corners),
        ]
        if not all(math.isfinite(value) for value in bounds):
            raise ValueError(f"Direct geometry calibration for {code} is not finite.")
        entries.append(
            {
                "componentCode": code,
                "componentName": component.get("componentName"),
                "rotationQuarters": rotation_quarters,
                "layoutFootprintBoundsLocal": bounds,
                "heightRangeMeters": [
                    min(point[2] for point in projected),
                    max(point[2] for point in projected),
                ],
                "sourceWorldAabb": box,
            }
        )
    return {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "evidencePath": evidence_path,
        "scope": "direct independently inserted module geometry",
        "entries": entries,
    }


def build_direct_major_subassembly_occupancy(
    layout: dict[str, Any],
    leaf_capture: dict[str, Any],
    *,
    component_code: str,
    collision_partner_codes: Iterable[str],
) -> list[dict[str, Any]]:
    """Union direct leaf-body boxes by the module's first child assembly.

    This preserves the large openings between A710/A720/A730 while avoiding a
    343-body Cartesian comparison during every candidate check.
    """
    frame = layout.get("baseFrame") or {}
    origin = [float(value) for value in frame.get("origin") or []]
    u_axis = [float(value) for value in frame.get("uAxis") or []]
    v_axis = [float(value) for value in frame.get("vAxis") or []]
    normal = [float(value) for value in frame.get("normal") or []]
    layout_component = next(
        (
            item
            for item in layout.get("components") or []
            if _component_code(str(item.get("componentName") or "")) == component_code
        ),
        None,
    )
    if layout_component is None:
        raise ValueError(f"Layout is missing component {component_code}.")
    anchor_layout = layout_component.get("layout2d") or {}
    anchor = [float(anchor_layout.get("x", 0.0)), float(anchor_layout.get("y", 0.0))]
    captures = list(leaf_capture.get("captures") or [])
    capture = next(
        (
            item
            for item in captures
            if _component_code(str((item.get("TopLevelComponent") or {}).get("Name") or ""))
            == component_code
        ),
        None,
    )
    if capture is None or not bool(capture.get("CoverageComplete")):
        raise ValueError(f"Complete leaf-body capture is missing for {component_code}.")
    grouped: dict[str, dict[str, Any]] = {}
    for body in capture.get("Bodies") or []:
        component = body.get("Component") or {}
        path = str(component.get("Name") or component.get("HierarchyPath") or "")
        parts = [part for part in path.split("/") if part]
        group = parts[1] if len(parts) > 1 else parts[0] if parts else "direct-body"
        box = [float(value) for value in body.get("BoundingBoxWorld") or []]
        if len(box) != 6:
            continue
        corners = [
            [x, y, z]
            for x in (box[0], box[3])
            for y in (box[1], box[4])
            for z in (box[2], box[5])
        ]
        projected = [
            (
                _dot(_subtract(point, origin), u_axis) - anchor[0],
                _dot(_subtract(point, origin), v_axis) - anchor[1],
                _dot(_subtract(point, origin), normal),
            )
            for point in corners
        ]
        incoming_bounds = [
            min(point[0] for point in projected),
            min(point[1] for point in projected),
            max(point[0] for point in projected),
            max(point[1] for point in projected),
        ]
        incoming_height = [
            max(0.0, min(point[2] for point in projected)),
            max(1e-6, max(point[2] for point in projected)),
        ]
        current = grouped.get(group)
        if current is None:
            grouped[group] = {
                "id": f"{component_code}-direct-major-{len(grouped)}",
                "bounds": incoming_bounds,
                "heightRangeMeters": incoming_height,
                "leafComponent": group,
                "componentCode": component_code,
                "collisionPartnerCodes": sorted(set(collision_partner_codes)),
                "occupancyScope": "direct-major-subassembly-union",
                "minimumClearanceMeters": 0.01,
            }
            continue
        bounds = current["bounds"]
        height = current["heightRangeMeters"]
        current["bounds"] = [
            min(bounds[0], incoming_bounds[0]),
            min(bounds[1], incoming_bounds[1]),
            max(bounds[2], incoming_bounds[2]),
            max(bounds[3], incoming_bounds[3]),
        ]
        current["heightRangeMeters"] = [
            min(height[0], incoming_height[0]),
            max(height[1], incoming_height[1]),
        ]
    if not grouped:
        raise ValueError(f"Leaf-body capture for {component_code} contains no bodies.")
    return list(grouped.values())


def derive_common_axis_clearance_offsets(
    exact_detail: dict[str, Any],
    base_frame: dict[str, Any],
    *,
    moving_component_code: str,
    clearance_meters: float,
) -> list[list[float]]:
    """Return four conservative 2-D shifts that clear every reported body pair."""
    origin = [float(value) for value in base_frame.get("origin") or []]
    u_axis = [float(value) for value in base_frame.get("uAxis") or []]
    v_axis = [float(value) for value in base_frame.get("vAxis") or []]
    if any(len(item) != 3 for item in (origin, u_axis, v_axis)):
        raise ValueError("Layout baseFrame is incomplete.")
    if clearance_meters < 0 or not math.isfinite(clearance_meters):
        raise ValueError("clearance_meters must be finite and non-negative.")

    thresholds = {"u_negative": [], "u_positive": [], "v_negative": [], "v_positive": []}

    def projected_bounds(box: list[float]) -> list[float]:
        points = [
            [x, y, z]
            for x in (box[0], box[3])
            for y in (box[1], box[4])
            for z in (box[2], box[5])
        ]
        projected = [
            (_dot(_subtract(point, origin), u_axis), _dot(_subtract(point, origin), v_axis))
            for point in points
        ]
        return [
            min(item[0] for item in projected),
            min(item[1] for item in projected),
            max(item[0] for item in projected),
            max(item[1] for item in projected),
        ]

    for pair in exact_detail.get("InterferingBodyPairs") or []:
        first_name = str((pair.get("FirstComponent") or {}).get("Name") or "")
        second_name = str((pair.get("SecondComponent") or {}).get("Name") or "")
        first_code = _component_code(first_name.split("/", 1)[0])
        second_code = _component_code(second_name.split("/", 1)[0])
        if moving_component_code not in {first_code, second_code}:
            continue
        first_box = projected_bounds([float(value) for value in pair["FirstBoundingBoxWorld"]])
        second_box = projected_bounds([float(value) for value in pair["SecondBoundingBoxWorld"]])
        moving, fixed = (
            (first_box, second_box) if first_code == moving_component_code else (second_box, first_box)
        )
        thresholds["u_negative"].append(fixed[0] - clearance_meters - moving[2])
        thresholds["u_positive"].append(fixed[2] + clearance_meters - moving[0])
        thresholds["v_negative"].append(fixed[1] - clearance_meters - moving[3])
        thresholds["v_positive"].append(fixed[3] + clearance_meters - moving[1])
    if not thresholds["u_negative"]:
        raise ValueError(f"Exact detail contains no collision rows for {moving_component_code}.")
    epsilon = 1e-6
    offsets = [
        [min(thresholds["u_negative"]) - epsilon, 0.0],
        [max(thresholds["u_positive"]) + epsilon, 0.0],
        [0.0, min(thresholds["v_negative"]) - epsilon],
        [0.0, max(thresholds["v_positive"]) + epsilon],
    ]
    return sorted(offsets, key=lambda item: (math.hypot(*item), abs(item[1]), abs(item[0])))


def apply_direct_geometry_calibration(
    request: dict[str, Any],
    calibration: dict[str, Any],
    *,
    promote_strict_pairs: Iterable[tuple[str, str]] = (),
) -> tuple[dict[str, Any], dict[str, Any]]:
    if calibration.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError("Unsupported direct-module geometry calibration schema.")
    updated = copy.deepcopy(request)
    semantics = updated.get("moduleSemantics") or {}
    by_code = {_component_code(name): name for name in semantics}
    applied = []
    for entry in calibration.get("entries") or []:
        code = str(entry.get("componentCode") or "")
        if code not in by_code:
            raise ValueError(f"Calibrated component {code} is absent from module semantics.")
        name = by_code[code]
        parameters = semantics[name].setdefault("parameters", {})
        bounds = [float(value) for value in entry.get("layoutFootprintBoundsLocal") or []]
        if len(bounds) != 4:
            raise ValueError(f"Calibrated component {code} has an invalid footprint.")
        parameters["layoutFootprintBoundsLocal"] = bounds
        if entry.get("occupancyBoxesLocal"):
            parameters["occupancyBoxesLocal"] = copy.deepcopy(entry["occupancyBoxesLocal"])
        parameters["layoutFootprintEvidence"] = {
            "kind": "directAssemblyWorldAabbProjection",
            "evidencePath": calibration.get("evidencePath"),
            "rotationQuarters": int(entry.get("rotationQuarters") or 0),
        }
        applied.append(code)

    policy = updated.get("staticCollisionPolicy") or {}
    strict = [list(pair) for pair in policy.get("strictAabbPairs") or []]
    conditional = [list(pair) for pair in policy.get("brepOnAabbOverlapPairs") or []]
    promoted = []
    for first_code, second_code in promote_strict_pairs:
        if first_code not in by_code or second_code not in by_code:
            raise ValueError(f"Strict promotion pair {first_code}-{second_code} is unresolved.")
        target_codes = frozenset((first_code.upper(), second_code.upper()))

        def normalized_pair(pair: Iterable[str]) -> frozenset[str]:
            return frozenset(_component_code(str(value)).upper() for value in pair)

        conditional = [pair for pair in conditional if normalized_pair(pair) != target_codes]
        if not any(normalized_pair(pair) == target_codes for pair in strict):
            strict.append(sorted((first_code, second_code)))
        promoted.append([first_code, second_code])
    policy["strictAabbPairs"] = strict
    policy["brepOnAabbOverlapPairs"] = conditional
    updated["directModuleGeometryCalibration"] = {
        "schemaVersion": calibration["schemaVersion"],
        "evidencePath": calibration.get("evidencePath"),
        "calibratedComponentCodes": applied,
        "promotedStrictPairs": promoted,
    }
    return updated, updated["directModuleGeometryCalibration"]
