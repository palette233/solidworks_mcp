from __future__ import annotations

import copy
import math
from typing import Any


class Project02OpticalPointError(ValueError):
    pass


TARGETS = {
    "scanner": {
        "componentName": "FL9A24D062A180.001-1",
        "moduleCode": "A180",
        "pointName": "scanOrigin",
        "mappingName": "A180扫描出光面",
        "requiredLeafToken": "SR-X100",
        "measuredFlag": "scanOriginMeasured",
        "heightParameter": "scanOriginHeightMeters",
        "heightSourceParameter": "scanOriginHeightSource",
    },
    "barcode": {
        "componentName": "FL9A24D062A800.001-1",
        "moduleCode": "A800",
        "pointName": "barcode",
        "mappingName": "A800条码面",
        "requiredLeafToken": None,
        "measuredFlag": "barcodeMeasured",
        "heightParameter": "barcodeHeightMeters",
        "heightSourceParameter": "barcodeHeightSource",
    },
}


def capture_entry_from_probe(
    capture: dict[str, Any],
    target: str,
    probe: dict[str, Any],
    *,
    require_leaf_hint: bool = True,
) -> dict[str, Any]:
    spec = _target(target)
    if not _value(probe, "Success", "success"):
        raise Project02OpticalPointError("The selected face probe was not successful.")
    leaf_path = str(
        _value(probe, "LeafComponentFullName", "leafComponentFullName") or ""
    )
    if spec["moduleCode"] not in leaf_path.upper():
        raise Project02OpticalPointError(
            f"Selected face is not under {spec['moduleCode']}: {leaf_path}"
        )
    required_leaf_token = spec["requiredLeafToken"]
    if (
        require_leaf_hint
        and required_leaf_token
        and required_leaf_token.upper() not in leaf_path.upper()
    ):
        raise Project02OpticalPointError(
            f"Scanner face must belong to the identified {required_leaf_token} leaf part; "
            f"selected leaf was {leaf_path}."
        )

    world_center = _vector3(
        _value(probe, "WorldCenter", "worldCenter"), "selectedFace.worldCenter"
    )
    world_normal = _unit(
        _vector3(
            _value(probe, "WorldNormal", "worldNormal"),
            "selectedFace.worldNormal",
        )
    )
    component = _component(capture, spec["componentName"])
    frame = capture.get("baseFrame") or {}
    origin = _vector3(frame.get("origin"), "baseFrame.origin")
    u_axis = _unit(_vector3(frame.get("uAxis"), "baseFrame.uAxis"))
    v_axis = _unit(_vector3(frame.get("vAxis"), "baseFrame.vAxis"))
    normal_axis = _unit(_vector3(frame.get("normal"), "baseFrame.normal"))
    layout = component.get("layout2d") or {}
    anchor_u = float(layout.get("x", 0.0))
    anchor_v = float(layout.get("y", 0.0))
    bottom_center = _vector3(
        component.get("bottomCenterWorld"),
        f"{spec['componentName']}.bottomCenterWorld",
    )
    offset_from_frame = _subtract(world_center, origin)
    local_u = _dot(offset_from_frame, u_axis) - anchor_u
    local_v = _dot(offset_from_frame, v_axis) - anchor_v
    height = _dot(_subtract(world_center, bottom_center), normal_axis)
    normal_in_layout = [
        _dot(world_normal, u_axis),
        _dot(world_normal, v_axis),
        _dot(world_normal, normal_axis),
    ]
    return {
        "target": target,
        "componentName": spec["componentName"],
        "moduleCode": spec["moduleCode"],
        "pointName": spec["pointName"],
        "faceMappingName": spec["mappingName"],
        "leafComponentFullName": leaf_path,
        "worldCenterMeters": world_center,
        "worldNormal": world_normal,
        "moduleLocalPointMeters": {"u": local_u, "v": local_v},
        "heightAboveModuleBottomMeters": height,
        "normalInLayoutFrame": normal_in_layout,
        "persistentReferenceBase64": _value(
            probe, "PersistentReferenceBase64", "persistentReferenceBase64"
        ),
        "mappingPath": _value(probe, "MappingPath", "mappingPath"),
        "geometryFingerprint": {
            "surfaceType": _value(probe, "SurfaceType", "surfaceType"),
            "areaSquareMeters": _value(
                probe, "AreaSquareMeters", "areaSquareMeters", "Area", "area"
            ),
            "localCenter": _value(probe, "LocalCenter", "localCenter"),
            "localNormal": _value(probe, "LocalNormal", "localNormal"),
        },
        "measurementStatus": "direct-face-measured",
        "coordinateInterpretation": (
            "The point is stored in the owning top-level module bottom-center frame; "
            "it remains valid when the module is moved by the layout solver."
        ),
    }


def apply_evidence_to_request(
    request: dict[str, Any],
    evidence: dict[str, Any],
    *,
    evidence_path: str,
) -> dict[str, Any]:
    updated = copy.deepcopy(request)
    semantics = updated.setdefault("moduleSemantics", {})
    entries = evidence.get("entries") or {}
    for target, spec in TARGETS.items():
        entry = entries.get(target)
        if not isinstance(entry, dict):
            continue
        local = entry.get("moduleLocalPointMeters") or {}
        if not _finite_number(local.get("u")) or not _finite_number(local.get("v")):
            raise Project02OpticalPointError(
                f"Evidence entry '{target}' has no finite module-local point."
            )
        semantic = semantics.setdefault(spec["componentName"], {})
        semantic.setdefault("points", {})[spec["pointName"]] = {
            "u": float(local["u"]),
            "v": float(local["v"]),
        }
        parameters = semantic.setdefault("parameters", {})
        measurement_status = str(
            entry.get("measurementStatus") or "direct-face-measured"
        )
        directly_measured = measurement_status == "direct-face-measured"
        parameters[spec["measuredFlag"]] = directly_measured
        parameters[f"{spec['pointName']}MeasurementStatus"] = measurement_status
        if target == "scanner":
            parameters["scanOriginCadInferred"] = not directly_measured
        parameters[f"{spec['pointName']}EvidencePath"] = evidence_path
        height = entry.get("heightAboveModuleBottomMeters")
        if _finite_number(height):
            parameters[spec["heightParameter"]] = float(height)
            parameters[spec["heightSourceParameter"]] = (
                "selected CAD face center"
                if directly_measured
                else measurement_status
            )
            parameters.pop(f"{spec['heightParameter']}Source", None)
        if target == "barcode":
            parameters["barcodeSide"] = "high" if float(local["v"]) >= 0 else "low"
    return updated


def evidence_readiness(evidence: dict[str, Any]) -> dict[str, Any]:
    entries = evidence.get("entries") or {}
    captured = [name for name in TARGETS if isinstance(entries.get(name), dict)]
    return {
        "capturedTargets": captured,
        "missingTargets": [name for name in TARGETS if name not in captured],
        "pointCaptureComplete": len(captured) == len(TARGETS),
    }


def infer_optical_axis_from_symmetric_faces(
    first_face: dict[str, Any],
    second_face: dict[str, Any],
    *,
    maximum_relative_area_difference: float = 0.02,
    minimum_normal_alignment: float = 0.99,
) -> dict[str, Any]:
    """Infer an optical-axis origin from two visually verified symmetric windows.

    Some imported scanner models do not expose the central lens as a stable planar
    face.  The two illumination-window faces are stable and symmetric, so their
    midpoint is a reproducible CAD inference of the central optical axis.  Visual
    semantic verification is intentionally outside this geometric helper.
    """
    first_center = _vector3(
        _value(first_face, "LocalCenter", "localCenter"), "firstFace.localCenter"
    )
    second_center = _vector3(
        _value(second_face, "LocalCenter", "localCenter"), "secondFace.localCenter"
    )
    first_normal = _unit(
        _vector3(
            _value(first_face, "LocalNormal", "localNormal"),
            "firstFace.localNormal",
        )
    )
    second_normal = _unit(
        _vector3(
            _value(second_face, "LocalNormal", "localNormal"),
            "secondFace.localNormal",
        )
    )
    normal_alignment = _dot(first_normal, second_normal)
    if normal_alignment < minimum_normal_alignment:
        raise Project02OpticalPointError(
            "Symmetric optical faces must have aligned outward normals."
        )

    first_area = float(_value(first_face, "Area", "area") or 0.0)
    second_area = float(_value(second_face, "Area", "area") or 0.0)
    if first_area <= 0.0 or second_area <= 0.0:
        raise Project02OpticalPointError(
            "Symmetric optical faces must have positive areas."
        )
    relative_area_difference = abs(first_area - second_area) / max(
        first_area, second_area
    )
    if relative_area_difference > maximum_relative_area_difference:
        raise Project02OpticalPointError(
            "Symmetric optical faces have materially different areas."
        )

    separation_vector = _subtract(second_center, first_center)
    separation = math.sqrt(_dot(separation_vector, separation_vector))
    if separation <= 1e-6:
        raise Project02OpticalPointError(
            "Symmetric optical faces do not define a usable centerline."
        )
    averaged_normal = _unit(
        [first_normal[index] + second_normal[index] for index in range(3)]
    )
    midpoint = [
        (first_center[index] + second_center[index]) / 2.0 for index in range(3)
    ]
    return {
        "localCenterMeters": midpoint,
        "localOpticalAxisLine": averaged_normal,
        "opticalAxisSignResolved": False,
        "anchorSeparationMeters": separation,
        "normalAlignment": normal_alignment,
        "relativeAreaDifference": relative_area_difference,
        "method": "midpoint of visually verified symmetric illumination-window faces",
        "evidenceClass": (
            "CAD-inferred center and unsigned normal line; not a directly selected "
            "central-lens face or a confirmed beam direction"
        ),
    }


def rebase_world_geometry_between_component_transforms(
    world_point: list[float],
    world_direction: list[float],
    from_transform: list[float],
    to_transform: list[float],
) -> dict[str, list[float]]:
    """Move world geometry between two poses of the same rigid module.

    SolidWorks Transform2 arrays store component X/Y/Z axes at indices 0..8,
    translation at 9..11 and uniform scale at 12.  The point is first expressed
    in the source component frame and then reconstructed in the target frame.
    """
    point = _vector3(world_point, "worldPoint")
    direction = _unit(_vector3(world_direction, "worldDirection"))
    source_axes, source_translation, source_scale = _transform_frame(
        from_transform, "fromTransform"
    )
    target_axes, target_translation, target_scale = _transform_frame(
        to_transform, "toTransform"
    )
    source_delta = _subtract(point, source_translation)
    local_point = [
        _dot(source_delta, axis) / source_scale for axis in source_axes
    ]
    local_direction = [_dot(direction, axis) for axis in source_axes]
    rebased_point = [
        target_translation[index]
        + target_scale
        * sum(local_point[axis] * target_axes[axis][index] for axis in range(3))
        for index in range(3)
    ]
    rebased_direction = _unit(
        [
            sum(
                local_direction[axis] * target_axes[axis][index]
                for axis in range(3)
            )
            for index in range(3)
        ]
    )
    return {
        "worldPoint": rebased_point,
        "worldDirection": rebased_direction,
        "componentLocalPoint": local_point,
        "componentLocalDirection": local_direction,
    }


def world_point_from_request(
    capture: dict[str, Any],
    request: dict[str, Any],
    component_name: str,
    point_name: str,
    height_parameter: str,
) -> list[float]:
    """Convert a source-layout semantic point to the prototype assembly world frame."""
    component = _component(capture, component_name)
    semantic = (request.get("moduleSemantics") or {}).get(component_name) or {}
    point = (semantic.get("points") or {}).get(point_name) or {}
    parameters = semantic.get("parameters") or {}
    local_u = float(point.get("u", 0.0))
    local_v = float(point.get("v", 0.0))
    height = float(parameters.get(height_parameter, 0.0))
    bottom_center = _vector3(
        component.get("bottomCenterWorld"), f"{component_name}.bottomCenterWorld"
    )
    frame = capture.get("baseFrame") or {}
    u_axis = _unit(_vector3(frame.get("uAxis"), "baseFrame.uAxis"))
    v_axis = _unit(_vector3(frame.get("vAxis"), "baseFrame.vAxis"))
    normal_axis = _unit(_vector3(frame.get("normal"), "baseFrame.normal"))
    return [
        bottom_center[index]
        + local_u * u_axis[index]
        + local_v * v_axis[index]
        + height * normal_axis[index]
        for index in range(3)
    ]


def rank_optical_face_candidates(
    faces: list[dict[str, Any]],
    target_world: list[float],
    *,
    min_working_distance_meters: float = 0.07,
    max_working_distance_meters: float = 1.0,
    expected_local_direction: list[float] | None = None,
    expected_local_side_direction: list[float] | None = None,
) -> list[dict[str, Any]]:
    """Rank planar scanner faces using target direction, range, proximity and area.

    This is deliberately a candidate generator rather than an automatic semantic proof.
    A casing face can share the same normal as the optical window, so the top candidates
    still require visual review before a persistent mapping is accepted.
    """
    target = _vector3(target_world, "targetWorld")
    reviewed_direction = (
        _unit(_vector3(expected_local_direction, "expectedLocalDirection"))
        if expected_local_direction is not None
        else None
    )
    reviewed_side_direction = (
        _unit(
            _vector3(
                expected_local_side_direction, "expectedLocalSideDirection"
            )
        )
        if expected_local_side_direction is not None
        else reviewed_direction
    )
    prepared: list[dict[str, Any]] = []
    for face in faces:
        center_value = _value(face, "WorldCenter", "worldCenter")
        normal_value = _value(face, "WorldNormal", "worldNormal")
        if center_value is None or normal_value is None:
            continue
        center = _vector3(center_value, "face.worldCenter")
        normal = _unit(_vector3(normal_value, "face.worldNormal"))
        to_target = _subtract(target, center)
        distance = math.sqrt(_dot(to_target, to_target))
        if distance <= 1e-9:
            continue
        target_direction = [item / distance for item in to_target]
        signed_alignment = _dot(normal, target_direction)
        alignment = abs(signed_alignment)
        optical_axis = normal if signed_alignment >= 0 else [-item for item in normal]
        area = float(_value(face, "Area", "area") or 0.0)
        local_center_value = _value(face, "LocalCenter", "localCenter")
        local_normal_value = _value(face, "LocalNormal", "localNormal")
        local_center = (
            _vector3(local_center_value, "face.localCenter")
            if local_center_value is not None
            else None
        )
        local_normal = (
            _unit(_vector3(local_normal_value, "face.localNormal"))
            if local_normal_value is not None
            else None
        )
        prepared.append(
            {
                "source": copy.deepcopy(face),
                "worldCenter": center,
                "worldNormal": normal,
                "opticalAxisTowardTarget": optical_axis,
                "distanceToTargetMeters": distance,
                "normalAlignment": alignment,
                "areaSquareMeters": area,
                "localCenter": local_center,
                "localNormal": local_normal,
            }
        )

    if not prepared:
        return []
    distances = [item["distanceToTargetMeters"] for item in prepared]
    min_distance, max_distance = min(distances), max(distances)
    distance_span = max(max_distance - min_distance, 1e-9)
    reviewed_projections = [
        _dot(item["localCenter"], reviewed_side_direction)
        for item in prepared
        if reviewed_side_direction is not None and item["localCenter"] is not None
    ]
    min_projection = min(reviewed_projections) if reviewed_projections else 0.0
    max_projection = max(reviewed_projections) if reviewed_projections else 0.0
    projection_span = max(max_projection - min_projection, 1e-9)
    for item in prepared:
        distance = item["distanceToTargetMeters"]
        alignment = item["normalAlignment"]
        if min_working_distance_meters <= distance <= max_working_distance_meters:
            range_score = 1.0
        else:
            range_error = (
                min_working_distance_meters - distance
                if distance < min_working_distance_meters
                else distance - max_working_distance_meters
            )
            range_score = max(0.0, 1.0 - range_error / 0.25)
        proximity_score = 1.0 - (distance - min_distance) / distance_span
        area_mm2 = item["areaSquareMeters"] * 1_000_000.0
        if 80.0 <= area_mm2 <= 4000.0:
            area_score = 1.0
        elif 20.0 <= area_mm2 < 80.0:
            area_score = (area_mm2 - 20.0) / 60.0
        elif 4000.0 < area_mm2 <= 12000.0:
            area_score = (12000.0 - area_mm2) / 8000.0
        else:
            area_score = 0.0
        if reviewed_direction is not None and item["localNormal"] is not None:
            reviewed_axis_alignment = abs(
                _dot(item["localNormal"], reviewed_direction)
            )
            reviewed_side_score = (
                _dot(item["localCenter"], reviewed_side_direction) - min_projection
            ) / projection_span
            score = (
                35.0 * alignment
                + 10.0 * range_score
                + 25.0 * reviewed_axis_alignment
                + 20.0 * reviewed_side_score
                + 10.0 * area_score
            )
            score_terms = {
                "targetAlignment": 35.0 * alignment,
                "workingDistance": 10.0 * range_score,
                "reviewedOpticalAxis": 25.0 * reviewed_axis_alignment,
                "reviewedOpticalSide": 20.0 * reviewed_side_score,
                "windowAreaPrior": 10.0 * area_score,
            }
        else:
            reviewed_axis_alignment = None
            reviewed_side_score = None
            score = (
                65.0 * alignment
                + 20.0 * range_score
                + 10.0 * proximity_score
                + 5.0 * area_score
            )
            score_terms = {
                "normalAlignment": 65.0 * alignment,
                "workingDistance": 20.0 * range_score,
                "targetProximity": 10.0 * proximity_score,
                "windowAreaPrior": 5.0 * area_score,
            }
        item.update(
            {
                "score": score,
                "workingDistanceInRange": range_score == 1.0,
                "reviewedAxisAlignment": reviewed_axis_alignment,
                "reviewedSideScore": reviewed_side_score,
                "scoreTerms": score_terms,
            }
        )

    prepared.sort(key=lambda item: item["score"], reverse=True)
    for rank, item in enumerate(prepared, start=1):
        next_score = prepared[rank]["score"] if rank < len(prepared) else 0.0
        margin = item["score"] - next_score
        if (
            item["normalAlignment"] >= 0.94
            and item["workingDistanceInRange"]
            and margin >= 4.0
        ):
            confidence = "high-candidate"
        elif item["normalAlignment"] >= 0.80 and item["workingDistanceInRange"]:
            confidence = "medium-candidate"
        else:
            confidence = "low-candidate"
        item["rank"] = rank
        item["scoreMarginToNext"] = margin
        item["candidateConfidence"] = confidence
        item["semanticStatus"] = "requires-visual-review"
    return prepared


def _target(target: str) -> dict[str, Any]:
    normalized = str(target).strip().lower()
    if normalized not in TARGETS:
        raise Project02OpticalPointError(
            f"Unsupported optical target '{target}'; expected scanner or barcode."
        )
    return TARGETS[normalized]


def _component(capture: dict[str, Any], component_name: str) -> dict[str, Any]:
    matches = [
        item
        for item in capture.get("components") or []
        if str(item.get("componentName") or "").lower() == component_name.lower()
    ]
    if len(matches) != 1:
        raise Project02OpticalPointError(
            f"Expected one captured component '{component_name}', found {len(matches)}."
        )
    return matches[0]


def _value(item: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in item:
            return item[name]
    return None


def _vector3(value: Any, label: str) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise Project02OpticalPointError(f"{label} must contain three numbers.")
    result = [float(item) for item in value]
    if not all(math.isfinite(item) for item in result):
        raise Project02OpticalPointError(f"{label} must contain finite numbers.")
    return result


def _unit(value: list[float]) -> list[float]:
    magnitude = math.sqrt(sum(item * item for item in value))
    if magnitude <= 1e-12:
        raise Project02OpticalPointError("A direction vector has zero length.")
    return [item / magnitude for item in value]


def _dot(first: list[float], second: list[float]) -> float:
    return sum(a * b for a, b in zip(first, second))


def _subtract(first: list[float], second: list[float]) -> list[float]:
    return [a - b for a, b in zip(first, second)]


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _transform_frame(
    value: Any, label: str
) -> tuple[list[list[float]], list[float], float]:
    if not isinstance(value, (list, tuple)) or len(value) < 13:
        raise Project02OpticalPointError(
            f"{label} must contain a SolidWorks 16-value Transform2 array."
        )
    data = [float(item) for item in value]
    if not all(math.isfinite(item) for item in data[:13]):
        raise Project02OpticalPointError(f"{label} contains non-finite values.")
    axes = [_unit(data[index : index + 3]) for index in (0, 3, 6)]
    if any(abs(_dot(axes[first], axes[second])) > 1e-6 for first, second in ((0, 1), (0, 2), (1, 2))):
        raise Project02OpticalPointError(f"{label} rotation axes are not orthogonal.")
    scale = data[12]
    if abs(scale) <= 1e-12:
        raise Project02OpticalPointError(f"{label} has zero scale.")
    return axes, data[9:12], scale
