"""Read-only calibration-point catalog and published-pose screening.

The catalog turns heterogeneous prototype artifacts into module-local points
and native target-base points.  It never authorizes CAD or copies a prototype
pose into an execution request.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from .role_station_geometry import _direction, _dot, _point, _transform


SCHEMA = "calibration-function-point-sources/v1"
CATALOG_SCHEMA = "calibration-function-point-catalog/v1"
SCREEN_SCHEMA = "calibration-function-point-screening/v1"
FUNCTIONAL_REPORT_SCHEMA = "station-functional-screening-report/v1"
PLANAR_CANDIDATE_SCHEMA = "calibration-planar-station-candidate-report/v1"
CANDIDATE_DECISION_INDEX_SCHEMA = "station-candidate-decision-index/v1"
COMBINED_CANDIDATE_REPORT_SCHEMA = "station-candidate-decision-report/v1"
EXTENSION_CANDIDATE_REPORT_SCHEMA = "station-candidate-extension-report/v1"


CALIBRATION_INTERFACE_TOPOLOGIES = {
    "project01::BD00": "support_plane_plus_two_locating_axes",
    "project02::A500": "three_orthogonal_datum_planes",
    "project03::AH00": "support_plane_plus_two_locating_axes",
    "project05::G000": "support_orientation_distance_plus_flexible_slot",
}


def _read(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _file(root: Path, value: str) -> Path:
    path = Path(value)
    path = path if path.is_absolute() else root / path
    path = path.resolve()
    path.relative_to(root)
    if not path.is_file():
        raise ValueError(f"calibration function-point evidence missing: {path}")
    return path


def _module(graph: dict[str, Any], token: str) -> dict[str, Any]:
    token = token.upper()
    rows = [row for row in graph.get("Modules") or []
            if str(row.get("ModuleToken") or "").upper().endswith(token)]
    if len(rows) != 1:
        raise ValueError(f"calibration module identity is not unique: {token}")
    return rows[0]


def _vector(values: Any, length: int) -> list[float]:
    if (not isinstance(values, (list, tuple)) or len(values) != length
            or any(isinstance(value, bool) or not isinstance(value, (int, float))
                   or not math.isfinite(value) for value in values)):
        raise ValueError(f"expected {length} finite calibration point values")
    return [float(value) for value in values]


def _service_ports(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("servicePorts", "ports", "targets"):
        if isinstance(payload.get(key), list):
            return payload[key]
    raise ValueError("service-point artifact has no point list")


def _service_point(root: Path, spec: dict[str, Any]) -> tuple[list[float], list[float], list[dict[str, str]], str]:
    point_path = _file(root, spec["servicePointPath"])
    graph_path = _file(root, spec["nativeGraphPath"])
    payload, graph = _read(point_path), _read(graph_path)
    rows = [row for row in _service_ports(payload)
            if row.get("id") == spec["servicePointId"] and row.get("capability") == "calibration"]
    if len(rows) != 1:
        raise ValueError("calibration service point is missing or ambiguous")
    row = rows[0]
    world = _vector(row.get("worldMeters"), 3)
    module_pose = _transform(_module(graph, spec["moduleToken"])["SourceTransform"])
    base_pose = _transform(_module(graph, spec["baseToken"])["SourceTransform"])
    local = _point(world, module_pose, inverse=True)
    # installationFrameMeters is a project process frame and is not
    # necessarily the CAD base root frame used by mate graphs.  Convert the
    # shared world observation through the native base transform instead.
    base_point = _point(world, base_pose, inverse=True)
    return local, base_point, [
        {"path": str(point_path), "sha256": _sha(point_path)},
        {"path": str(graph_path), "sha256": _sha(graph_path)},
    ], str(row.get("proxyMethod") or "prototype service-point proxy")


def _approach_proxy(root: Path, spec: dict[str, Any]) -> tuple[list[float], list[float], list[dict[str, str]], str]:
    package_path = _file(root, spec["parameterPackagePath"])
    graph_path = _file(root, spec["nativeGraphPath"])
    package, graph = _read(package_path), _read(graph_path)
    access = (((package.get("projectSpecificParameters") or {}).get("serviceAccess") or {})
              .get("modules") or {})
    rows = [row for row in access.get(spec["serviceModuleInstance"], [])
            if row.get("id") == spec["approachEnvelopeId"]]
    if len(rows) != 1:
        raise ValueError("calibration approach envelope is missing or ambiguous")
    bounds = _vector(rows[0].get("bounds"), 4)
    heights = _vector(rows[0].get("heightRangeMeters"), 2)
    if bounds[0] > bounds[2] or bounds[1] > bounds[3] or heights[0] > heights[1]:
        raise ValueError("calibration approach envelope is reversed")
    # The lower centre of the vertical approach volume is the documented
    # coarse target proxy.  It is not an authored nozzle-contact datum.
    local = [(bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2, heights[0]]
    module_pose = _transform(_module(graph, spec["moduleToken"])["SourceTransform"])
    base_pose = _transform(_module(graph, spec["baseToken"])["SourceTransform"])
    base_point = _point(_point(local, module_pose), base_pose, inverse=True)
    return local, base_point, [
        {"path": str(package_path), "sha256": _sha(package_path)},
        {"path": str(graph_path), "sha256": _sha(graph_path)},
    ], "bottom centre of the documented valve-vertical-approach envelope"


def build_calibration_function_point_catalog(workspace: Path, source_path: Path) -> dict[str, Any]:
    root = Path(workspace).resolve()
    source = _file(root, str(source_path))
    config = _read(source)
    if config.get("schemaVersion") != SCHEMA:
        raise ValueError("unsupported calibration function-point source schema")
    entries, evidence, identities, targets = [], {}, [], []
    for spec in config.get("entries") or []:
        identity = spec.get("moduleDefinitionId")
        target = spec.get("targetBaseDefinitionId")
        if not identity or not target:
            raise ValueError("calibration function-point identity is incomplete")
        identities.append(identity)
        targets.append(target)
        if spec.get("kind") == "service_point_world_and_installation_frame":
            local, base_point, rows, method = _service_point(root, spec)
        elif spec.get("kind") == "approach_envelope_bottom_center_proxy":
            local, base_point, rows, method = _approach_proxy(root, spec)
        else:
            raise ValueError("unsupported calibration function-point source kind")
        for row in rows:
            evidence[row["path"]] = row
        native_graph = _read(_file(root, spec["nativeGraphPath"]))
        native_module = _module(native_graph, spec["moduleToken"])
        native_base = _module(native_graph, spec["baseToken"])
        entries.append({
            "moduleDefinitionId": identity,
            "nativeTargetBaseDefinitionId": target,
            "moduleToken": spec["moduleToken"],
            "baseToken": spec["baseToken"],
            "pointLocalMeters": local,
            "nativePointInBaseMeters": base_point,
            # These transforms are measurement-coordinate bridges only.  They
            # recover persistent face centres/normals from the prototype
            # capture frame into module/base-local coordinates; they are never
            # copied into a CAD execution graph.
            "nativeModuleSourceTransformForMeasurementOnly": _transform(
                native_module["SourceTransform"]
            ),
            "nativeBaseSourceTransformForMeasurementOnly": _transform(
                native_base["SourceTransform"]
            ),
            "modulePath": native_module["Path"],
            "basePath": native_base["Path"],
            "proxyMethod": method,
            "engineeringConfirmed": False,
            "cadExecutionAuthority": False,
        })
    if len(identities) != len(set(identities)) or len(targets) != len(set(targets)):
        raise ValueError("duplicate calibration module or target-base identity")
    if set(identities) != {"project01::BD00", "project02::A500", "project03::AH00", "project05::G000"}:
        raise ValueError("calibration function-point scope is incomplete")
    return {
        "schemaVersion": CATALOG_SCHEMA,
        "sourcePath": str(source),
        "sourceSha256": _sha(source),
        "pointToleranceMeters": float(config.get("pointToleranceMeters")),
        "entries": entries,
        "evidence": sorted(evidence.values(), key=lambda row: row["path"]),
        "cadExecuted": False,
        "boundary": config.get("boundary"),
    }


def _same_path(first: str, second: str) -> bool:
    return first.replace("\\", "/").casefold() == second.replace("\\", "/").casefold()


def _mate_role(mate: dict[str, Any]) -> str:
    name = str(mate.get("MateName") or "")
    for suffix, role in (
        ("_LONGITUDINAL", "longitudinal"),
        ("_LATERAL", "lateral"),
        ("_SUPPORT", "support"),
    ):
        if name.endswith(suffix):
            return role
    raise ValueError(f"calibration datum mate has no supported role: {name}")


def _semantic_function_point(workspace: Path, entry: dict[str, Any]) -> list[float]:
    """Project one measured function point into its native semantic base frame."""

    from .parameterized_datum_placement import load_parameterized_datum_placement_catalog
    from .two_axis_slot_selection import _base_semantic_frame

    placement = load_parameterized_datum_placement_catalog(workspace)
    _, frame = _base_semantic_frame(
        workspace,
        placement,
        base_definition_id=str(entry["nativeTargetBaseDefinitionId"]),
        module_role="Calibration",
    )
    base_pose = _transform(entry["nativeBaseSourceTransformForMeasurementOnly"])
    world = _point(entry["nativePointInBaseMeters"], base_pose)
    values = []
    for role in ("longitudinal_datum", "lateral_datum", "support_datum"):
        endpoint = frame[role]["Endpoint"]
        center = _vector(endpoint["FaceCenterWorld"], 3)
        normal = _vector(endpoint["FaceNormalWorld"], 3)
        length = math.sqrt(_dot(normal, normal))
        if length <= 1e-12:
            raise ValueError(f"calibration semantic {role} normal is degenerate")
        normal = [value / length for value in normal]
        values.append(_dot([world[index] - center[index] for index in range(3)], normal))
    return values


def _map_two_dimensional_point(
    point: list[float], source_primary: list[float], source_secondary: list[float],
    target_primary: list[float], target_secondary: list[float],
) -> list[float]:
    def frame(first: list[float], second: list[float]) -> tuple[list[float], list[float]]:
        axis = [second[index] - first[index] for index in range(2)]
        length = math.sqrt(_dot(axis, axis))
        if length <= 1e-12:
            raise ValueError("calibration two-axis station is degenerate")
        axis = [value / length for value in axis]
        return axis, [-axis[1], axis[0]]

    source_axis, source_perpendicular = frame(source_primary, source_secondary)
    target_axis, target_perpendicular = frame(target_primary, target_secondary)
    delta = [point[index] - source_primary[index] for index in range(2)]
    along = _dot(delta, source_axis)
    across = _dot(delta, source_perpendicular)
    return [
        target_primary[index]
        + along * target_axis[index]
        + across * target_perpendicular[index]
        for index in range(2)
    ]


def _two_axis_station_candidates(
    workspace: Path, source: dict[str, Any], target: dict[str, Any], *, tolerance: float
) -> dict[str, Any]:
    from .hybrid_plane_axis_slot_selection import build_f000_hybrid_axis_slot_catalog
    from .two_axis_slot_selection import (
        _base_semantic_frame,
        _endpoint_index,
        _pair_candidates,
        _semantic_point,
        build_two_axis_native_station_references,
        build_two_axis_slot_candidate_catalog,
    )
    from .parameterized_datum_placement import load_parameterized_datum_placement_catalog

    module_id = str(source["moduleDefinitionId"])
    base_id = str(target["nativeTargetBaseDefinitionId"])
    references = build_two_axis_native_station_references(workspace)
    native = [row for row in references["stations"] if row["moduleDefinitionId"] == module_id]
    if len(native) != 1:
        raise ValueError(f"calibration native two-axis station is ambiguous: {module_id}")
    source_axes = native[0]["semanticAxisPointsMeters"]
    source_point = _semantic_function_point(workspace, source)
    target_point = _semantic_function_point(workspace, target)
    pair_rows: list[dict[str, Any]] = []
    if base_id == "project05::A000":
        catalog = build_two_axis_slot_candidate_catalog(workspace)
        family = next(row for row in catalog["families"] if row["moduleRole"] == "Calibration")
        placement = load_parameterized_datum_placement_catalog(workspace)
        payload, frame = _base_semantic_frame(
            workspace, placement, base_definition_id=base_id, module_role="Calibration"
        )
        index = _endpoint_index(payload)
        for pair in family["axisPairCandidates"]:
            points = [
                _semantic_point(index[pair[key]], frame)
                for key in ("primaryAxisEndpointId", "secondaryAxisEndpointId")
            ]
            pair_rows.append({**pair, "semanticAxisPointsMeters": points})
    else:
        hybrid = build_f000_hybrid_axis_slot_catalog(workspace)
        slots = [row for row in hybrid["baseSlots"] if row["slotDefinitionId"] == base_id]
        if len(slots) != 1:
            raise ValueError(f"calibration target axis inventory is ambiguous: {base_id}")
        lines = [
            {
                "endpointId": row["endpointId"],
                "axisPointOnSupportPlaneLocal": [
                    float(row["longitudinalMeters"]), float(row["lateralMeters"]), 0.0
                ],
                "axisLineKey": [
                    float(row["longitudinalMeters"]), float(row["lateralMeters"]), 0.0
                ],
                "cylinderRadiusMeters": float(row["cylinderRadiusMeters"]),
            }
            for row in slots[0].get("axisCandidates") or []
        ]
        lookup = {row["endpointId"]: row["axisPointOnSupportPlaneLocal"][:2] for row in lines}
        for pair in _pair_candidates(lines, 0.05, tolerance_meters=0.0002):
            pair_rows.append({
                **pair,
                "semanticAxisPointsMeters": [
                    lookup[pair["primaryAxisEndpointId"]],
                    lookup[pair["secondaryAxisEndpointId"]],
                ],
            })
    evaluated = []
    for pair in pair_rows:
        points = pair["semanticAxisPointsMeters"]
        for assignment, target_axes in (
            ("direct", points), ("reversed", [points[1], points[0]])
        ):
            predicted_planar = _map_two_dimensional_point(
                source_point[:2], source_axes["primary"], source_axes["secondary"],
                target_axes[0], target_axes[1],
            )
            residual = [
                predicted_planar[0] - target_point[0],
                predicted_planar[1] - target_point[1],
                source_point[2] - target_point[2],
            ]
            evaluated.append({
                "candidatePairId": pair["candidatePairId"],
                "primaryAxisEndpointId": pair["primaryAxisEndpointId"],
                "secondaryAxisEndpointId": pair["secondaryAxisEndpointId"],
                "axisAssignment": assignment,
                "predictedFunctionPointInTargetSemanticFrameMeters": [
                    predicted_planar[0], predicted_planar[1], source_point[2]
                ],
                "targetFunctionPointInSemanticFrameMeters": target_point,
                "residualMeters": residual,
                "planarErrorMeters": math.sqrt(residual[0] ** 2 + residual[1] ** 2),
                "supportNormalOffsetMeters": residual[2],
                "threeDimensionalErrorMeters": math.sqrt(sum(value * value for value in residual)),
            })
    evaluated.sort(key=lambda row: (
        float(row["planarErrorMeters"]), float(row["threeDimensionalErrorMeters"]),
        str(row["candidatePairId"]), str(row["axisAssignment"]),
    ))
    best = evaluated[0] if evaluated else None
    if best is None:
        status = "target_two_axis_station_inventory_missing"
        next_action = "capture_or_register_a_target_two_axis_station_inventory"
    elif best["planarErrorMeters"] > tolerance:
        status = "two_axis_stations_miss_target_function_point"
        next_action = "review_a_different_target_station_or_accept_an_explicit_function_offset"
    elif abs(best["supportNormalOffsetMeters"]) > tolerance:
        status = "two_axis_candidate_requires_height_and_pair_review"
        next_action = "review_the_exact_axis_pair_and_function_point_height"
    else:
        status = "two_axis_candidate_ready_for_engineering_review"
        next_action = "confirm_the_exact_axis_pair_before_nonprototype_cad_validation"
    return {
        "sourceModuleDefinitionId": module_id,
        "targetBaseDefinitionId": base_id,
        "interfaceTopology": "support_plane_plus_two_locating_axes",
        "status": status,
        "readyForCadValidation": False,
        "cadLaunchAllowed": False,
        "candidatePairCount": len(pair_rows),
        "evaluatedAssignmentCount": len(evaluated),
        "bestCandidate": best,
        "pointToleranceMeters": tolerance,
        "prototypeTopLevelTargetPoseUsed": False,
        "nextAction": next_action,
        "claimBoundary": (
            "Existing stable 50 mm axis pairs are screened against the target function point. "
            "The result does not confirm hole purpose, installation side, fastener fit or CAD authority."
        ),
    }


def _flexible_slot_station_candidates(
    workspace: Path, source: dict[str, Any], target: dict[str, Any], *, tolerance: float
) -> dict[str, Any]:
    from .flexible_calibration_slot_selection import (
        build_g000_flexible_slot_candidate_catalog,
        build_g000_native_station_reference,
    )

    module_id = str(source["moduleDefinitionId"])
    base_id = str(target["nativeTargetBaseDefinitionId"])
    catalog = build_g000_flexible_slot_candidate_catalog(workspace)
    slots = [row for row in catalog["baseSlots"] if row["slotDefinitionId"] == base_id]
    if len(slots) != 1:
        raise ValueError(f"calibration flexible target slot is ambiguous: {base_id}")
    reference = build_g000_native_station_reference(workspace)
    source_point = _semantic_function_point(workspace, source)
    target_point = _semantic_function_point(workspace, target)
    native_axis = reference["semanticAxisPositionMeters"]
    offset = float(reference["longitudinalOffsetMeters"]) + target_point[0] - source_point[0]
    evaluated = []
    for axis in slots[0].get("axisCandidates") or []:
        predicted = [
            target_point[0],
            source_point[1] + float(axis["lateralMeters"]) - float(native_axis["lateral"]),
            source_point[2],
        ]
        residual = [predicted[index] - target_point[index] for index in range(3)]
        evaluated.append({
            "selectedAxisEndpointId": axis["endpointId"],
            "derivedLongitudinalOffsetMeters": offset,
            "axisSemanticPositionMeters": {
                "longitudinal": float(axis["longitudinalMeters"]),
                "lateral": float(axis["lateralMeters"]),
            },
            "predictedFunctionPointInTargetSemanticFrameMeters": predicted,
            "targetFunctionPointInSemanticFrameMeters": target_point,
            "residualMeters": residual,
            "planarErrorMeters": math.sqrt(residual[0] ** 2 + residual[1] ** 2),
            "supportNormalOffsetMeters": residual[2],
            "threeDimensionalErrorMeters": math.sqrt(sum(value * value for value in residual)),
        })
    evaluated.sort(key=lambda row: (
        float(row["planarErrorMeters"]), float(row["threeDimensionalErrorMeters"]),
        str(row["selectedAxisEndpointId"]),
    ))
    best = evaluated[0] if evaluated else None
    if best is None or offset < 0:
        status = "target_flexible_slot_inventory_or_offset_missing"
        next_action = "capture_a_slot_inventory_or_review_the_longitudinal_offset"
    elif best["planarErrorMeters"] > tolerance:
        status = "flexible_slot_candidates_miss_target_function_point"
        next_action = "review_a_different_slot_or_accept_an_explicit_function_offset"
    elif abs(best["supportNormalOffsetMeters"]) > tolerance:
        status = "flexible_slot_candidate_requires_height_and_axis_review"
        next_action = "review_the_exact_slot_axis_longitudinal_offset_and_function_point_height"
    else:
        status = "flexible_slot_candidate_ready_for_engineering_review"
        next_action = "confirm_the_exact_slot_axis_and_offset_before_nonprototype_cad_validation"
    return {
        "sourceModuleDefinitionId": module_id,
        "targetBaseDefinitionId": base_id,
        "interfaceTopology": "support_orientation_distance_plus_flexible_slot",
        "status": status,
        "readyForCadValidation": False,
        "cadLaunchAllowed": False,
        "candidateAxisCount": len(evaluated),
        "bestCandidate": best,
        "pointToleranceMeters": tolerance,
        "prototypeTopLevelTargetPoseUsed": False,
        "nextAction": next_action,
        "claimBoundary": (
            "Stable target axes are screened with a derived longitudinal offset. The result "
            "does not confirm slot purpose, reachability, installation side or CAD authority."
        ),
    }


def _calibration_planar_candidate(
    workspace: Path,
    source: dict[str, Any],
    target: dict[str, Any],
    *,
    tolerance: float,
) -> dict[str, Any]:
    """Derive a support-constrained planar target candidate.

    The source module stays on the target support plane.  Its function point
    is aligned only in the two in-plane datum directions.  A residual in the
    support-normal direction is reported as an engineering decision, never
    hidden by turning the support mate into a large stand-off distance.
    """

    from .mechanical_interface_contracts import MechanicalInterfaceContractError
    from .parameterized_datum_placement import (
        compile_parameterized_datum_validation_package,
    )

    module_id = str(source["moduleDefinitionId"])
    base_id = str(target["nativeTargetBaseDefinitionId"])
    zero = {"longitudinal": 0.0, "lateral": 0.0, "supportGap": 0.0}
    flips = {"longitudinal": False, "lateral": False, "supportGap": False}
    interface_topology = CALIBRATION_INTERFACE_TOPOLOGIES.get(module_id)
    if interface_topology is None:
        raise ValueError(f"calibration interface topology is not registered: {module_id}")
    if interface_topology == "support_plane_plus_two_locating_axes":
        return _two_axis_station_candidates(
            workspace, source, target, tolerance=tolerance
        )
    if interface_topology == "support_orientation_distance_plus_flexible_slot":
        return _flexible_slot_station_candidates(
            workspace, source, target, tolerance=tolerance
        )
    try:
        seed = compile_parameterized_datum_validation_package(
            workspace,
            module_id,
            base_id,
            position_parameters=zero,
            distance_flip_dimensions=flips,
        )
    except MechanicalInterfaceContractError as exc:
        return {
            "sourceModuleDefinitionId": module_id,
            "targetBaseDefinitionId": base_id,
            "interfaceTopology": interface_topology,
            "status": "registered_three_plane_datum_unavailable",
            "readyForCadValidation": False,
            "cadLaunchAllowed": False,
            "diagnostic": str(exc),
            "nextAction": "register_and_review_a_static_three_plane_module_port",
        }

    graph = seed["effectiveGraph"]
    if seed.get("prototypeTopLevelTargetPoseUsed") is not False:
        raise ValueError("calibration seed unexpectedly uses a prototype target pose")
    if not _same_path(source["modulePath"], next(
        row["Path"] for row in graph["Modules"]
        if str(row["ModuleToken"]).upper().endswith(str(source["moduleToken"]).upper())
    )):
        raise ValueError("calibration source module identity differs from datum candidate")
    if not _same_path(target["basePath"], next(
        row["Path"] for row in graph["Modules"]
        if str(row["ModuleToken"]).upper().endswith(str(target["baseToken"]).upper())
    )):
        raise ValueError("calibration target base identity differs from datum candidate")

    source_pose = _transform(source["nativeModuleSourceTransformForMeasurementOnly"])
    base_pose = _transform(target["nativeBaseSourceTransformForMeasurementOnly"])
    by_role: dict[str, dict[str, Any]] = {}
    for mate in graph.get("Mates") or []:
        role = _mate_role(mate)
        endpoints = list(mate.get("Endpoints") or [])
        if len(endpoints) != 2 or endpoints[0].get("ModuleToken") != source["moduleToken"]:
            raise ValueError("calibration candidate endpoints are not target-first and binary")
        moving, fixed = endpoints
        source_normal = _direction(moving["FaceNormalWorld"], source_pose, inverse=True)
        base_normal = _direction(fixed["FaceNormalWorld"], base_pose, inverse=True)
        alignment_sign = -1 if mate.get("Alignment") == 1 else 1
        by_role[role] = {
            "sourceNormal": source_normal,
            "targetNormal": [alignment_sign * value for value in base_normal],
            "basePlaneNormal": base_normal,
            "sourcePlaneCenter": _point(moving["FaceCenterWorld"], source_pose, inverse=True),
            "basePlaneCenter": _point(fixed["FaceCenterWorld"], base_pose, inverse=True),
        }
    roles = ("longitudinal", "lateral", "support")
    if set(by_role) != set(roles):
        raise ValueError("calibration candidate does not contain one complete three-plane bundle")
    for key in ("sourceNormal", "targetNormal", "basePlaneNormal"):
        vectors = [by_role[role][key] for role in roles]
        if any(abs(_dot(vectors[i], vectors[j]) - (1 if i == j else 0)) > 1e-7
               for i in range(3) for j in range(3)):
            raise ValueError(f"calibration candidate {key} frame is not orthonormal")

    source_normals = [by_role[role]["sourceNormal"] for role in roles]
    target_normals = [by_role[role]["targetNormal"] for role in roles]
    pose = _transform([
        *(sum(target_normals[k][i] * source_normals[k][j] for k in range(3))
          for j in range(3) for i in range(3)),
        0, 0, 0, 1, 0, 0, 0,
    ])
    source_point = list(source["pointLocalMeters"])
    target_point = list(target["nativePointInBaseMeters"])
    translation = [0.0, 0.0, 0.0]
    rotated_point = _point(source_point, pose)
    # Align the function point in the two in-plane directions.
    for role in ("longitudinal", "lateral"):
        normal = by_role[role]["basePlaneNormal"]
        amount = _dot(
            [target_point[index] - rotated_point[index] for index in range(3)],
            normal,
        )
        translation = [
            translation[index] + amount * normal[index] for index in range(3)
        ]
    # Preserve physical support contact instead of using function-point height
    # to create an unreviewed floating installation.
    support = by_role["support"]
    rotated_support = _point(support["sourcePlaneCenter"], pose)
    support_amount = _dot(
        [support["basePlaneCenter"][index] - rotated_support[index] for index in range(3)],
        support["basePlaneNormal"],
    )
    translation = [
        translation[index] + support_amount * support["basePlaneNormal"][index]
        for index in range(3)
    ]
    pose[9:12] = translation

    parameters: dict[str, float] = {}
    distance_flips: dict[str, bool] = {}
    signed_distances: dict[str, float] = {}
    for role in roles:
        row = by_role[role]
        moved_center = _point(row["sourcePlaneCenter"], pose)
        signed = _dot(
            [moved_center[index] - row["basePlaneCenter"][index] for index in range(3)],
            row["basePlaneNormal"],
        )
        if abs(signed) <= 1e-10:
            signed = 0.0
        key = "supportGap" if role == "support" else role
        signed_distances[key] = signed
        parameters[key] = abs(signed)
        distance_flips[key] = signed < 0

    predicted = _point(source_point, pose)
    residual = [predicted[index] - target_point[index] for index in range(3)]
    components = {
        role: _dot(residual, by_role[role]["basePlaneNormal"]) for role in roles
    }
    planar_error = math.sqrt(
        components["longitudinal"] ** 2 + components["lateral"] ** 2
    )
    normal_offset = components["support"]
    three_dimensional_error = math.sqrt(sum(value * value for value in residual))
    compiled = compile_parameterized_datum_validation_package(
        workspace,
        module_id,
        base_id,
        position_parameters=parameters,
        distance_flip_dimensions=distance_flips,
    )
    planar_passed = planar_error <= tolerance and parameters["supportGap"] <= 1e-8
    height_passed = abs(normal_offset) <= tolerance
    status = (
        "ready_for_nonprototype_cad_validation"
        if planar_passed and height_passed
        else "planar_candidate_requires_height_decision"
        if planar_passed
        else "function_point_projection_candidate_failed"
    )
    return {
        "sourceModuleDefinitionId": module_id,
        "targetBaseDefinitionId": base_id,
        "interfaceTopology": interface_topology,
        "status": status,
        "readyForCadValidation": planar_passed and height_passed,
        "cadLaunchAllowed": False,
        "positionParametersMeters": parameters,
        "distanceFlipDimensions": distance_flips,
        "signedDatumDistancesMeters": signed_distances,
        "sourcePointLocalMeters": source_point,
        "targetNativePointInBaseMeters": target_point,
        "predictedPointInTargetBaseMeters": predicted,
        "residualMeters": residual,
        "residualByTargetDatumMeters": components,
        "planarErrorMeters": planar_error,
        "supportNormalOffsetMeters": normal_offset,
        "threeDimensionalErrorMeters": three_dimensional_error,
        "pointToleranceMeters": tolerance,
        "supportContactPreserved": parameters["supportGap"] <= 1e-8,
        "functionPointPlanarProjectionPassed": planar_passed,
        "functionPointHeightPassed": height_passed,
        "prototypeTopLevelTargetPoseUsed": False,
        "candidatePackage": compiled,
        "nextAction": (
            "run_nonprototype_cad_validate_save_reopen_and_station_postcheck"
            if planar_passed and height_passed
            else "review_function_point_height_or_select_a_different_target_support_station"
        ),
        "claimBoundary": (
            "The source function point is projected to the target station while the registered "
            "support planes remain coincident. A normal-height residual is not corrected with an "
            "unreviewed stand-off. This is an offline candidate, not CAD or process authority."
        ),
    }


def derive_calibration_planar_station_candidates(
    workspace: Path, catalog: dict[str, Any]
) -> dict[str, Any]:
    """Screen all cross-project calibration pairs through one generic solver."""

    if catalog.get("schemaVersion") != CATALOG_SCHEMA:
        raise ValueError("unsupported calibration function-point catalog schema")
    entries = list(catalog.get("entries") or [])
    tolerance = float(catalog["pointToleranceMeters"])
    candidates = [
        _calibration_planar_candidate(workspace, source, target, tolerance=tolerance)
        for source in entries
        for target in entries
        if source["nativeTargetBaseDefinitionId"] != target["nativeTargetBaseDefinitionId"]
    ]
    result = {
        "schemaVersion": PLANAR_CANDIDATE_SCHEMA,
        "summary": {
            "listedPairCount": len(candidates),
            "datumUnavailablePairCount": sum(
                row["status"] == "registered_three_plane_datum_unavailable"
                for row in candidates
            ),
            "topologySpecificDerivationRequiredPairCount": sum(
                str(row["status"]).startswith("topology_specific_")
                for row in candidates
            ),
            "topologyCandidateReviewRequiredPairCount": sum(
                str(row["status"]).endswith("_ready_for_engineering_review")
                or "_requires_height_and_" in str(row["status"])
                for row in candidates
            ),
            "topologyCandidateMismatchPairCount": sum(
                str(row["status"]) in {
                    "two_axis_stations_miss_target_function_point",
                    "flexible_slot_candidates_miss_target_function_point",
                }
                for row in candidates
            ),
            "planarProjectionPassedPairCount": sum(
                row.get("functionPointPlanarProjectionPassed") is True
                for row in candidates
            ),
            "heightDecisionRequiredPairCount": sum(
                row["status"] == "planar_candidate_requires_height_decision"
                for row in candidates
            ),
            "readyForCadValidationCount": sum(
                row.get("readyForCadValidation") is True for row in candidates
            ),
        },
        "candidates": candidates,
        "cadExecuted": False,
        "boundary": (
            "Support-constrained offline station derivation only. Prototype transforms are used "
            "only to convert captured geometry to local coordinates. No prototype target pose is "
            "copied into an execution graph."
        ),
    }
    return result


def build_station_candidate_decision_index(
    report: dict[str, Any], *, report_path: str, report_sha256: str
) -> dict[str, Any]:
    """Bind generic gap classification to one immutable candidate report.

    The index carries no CAD authority.  It only replaces a coarse historical
    pose mismatch with a more precise, authenticated next action.
    """

    if report.get("schemaVersion") not in {
        PLANAR_CANDIDATE_SCHEMA, COMBINED_CANDIDATE_REPORT_SCHEMA
    }:
        raise ValueError("unsupported station candidate report schema")
    if not isinstance(report_sha256, str) or len(report_sha256) != 64:
        raise ValueError("candidate report sha256 is invalid")
    entries = []
    seen = set()
    for row in report.get("candidates") or []:
        key = (
            row.get("sourceModuleDefinitionId"),
            row.get("targetBaseDefinitionId"),
            row.get("role") or "Calibration",
        )
        if None in key or key in seen:
            raise ValueError(f"candidate report contains an invalid or duplicate pair: {key}")
        seen.add(key)
        entries.append({
            "sourceModuleDefinitionId": key[0],
            "targetBaseDefinitionId": key[1],
            "role": key[2],
            "reportPath": report_path,
            "reportSha256": report_sha256,
            "candidateStatus": row.get("status"),
            "interfaceTopology": row.get("interfaceTopology"),
            "readyForCadValidation": row.get("readyForCadValidation") is True,
            "cadLaunchAllowed": False,
            "nextAction": row.get("nextAction"),
        })
    return {
        "schemaVersion": CANDIDATE_DECISION_INDEX_SCHEMA,
        "entries": entries,
        "cadExecuted": False,
        "boundary": (
            "Candidate classification only. This index cannot authorize CAD, publish a "
            "relation, or replace an engineering decision."
        ),
    }


def build_calibration_station_decision_request(
    workspace: Path,
    gap_queue_path: str | Path,
) -> dict[str, Any]:
    """Expand calibration gaps into one finite engineering review queue."""

    root = Path(workspace).resolve()
    queue_path = Path(gap_queue_path)
    queue_path = queue_path if queue_path.is_absolute() else root / queue_path
    queue = _read(queue_path)
    if queue.get("schemaVersion") != "station-gap-batch-preparation/v1":
        raise ValueError("unsupported station gap queue")
    report_cache: dict[str, dict[str, Any]] = {}
    decisions = []
    kinds = {
        "target_function_point_height_decision_required": (
            "function_point_height",
            ["accept_explicit_height_offset", "select_different_target_station"],
        ),
        "target_function_point_height_and_interface_review_required": (
            "slot_axis_offset_and_function_point_height",
            [
                "accept_exact_slot_axis_offset_and_height",
                "select_different_target_station",
            ],
        ),
        "target_functional_geometry_mismatch": (
            "target_station_or_explicit_function_offset",
            ["select_different_target_station", "accept_explicit_function_offset"],
        ),
        "mechanical_interface_authority_revoked_requires_new_binding": (
            "replacement_mechanical_binding",
            ["register_new_binding", "keep_pair_blocked"],
        ),
    }
    for row in queue.get("queue") or []:
        if row.get("role") != "Calibration":
            continue
        category = row.get("gapCategory")
        if category not in kinds:
            raise ValueError(f"unsupported calibration decision category: {category}")
        kind, options = kinds[category]
        candidate_index = row.get("stationCandidateDecision") or {}
        candidate = None
        report_path_value = candidate_index.get("reportPath")
        if report_path_value:
            report_path = _file(root, report_path_value)
            if _sha(report_path) != candidate_index.get("reportSha256"):
                raise ValueError("calibration candidate report changed")
            report = report_cache.setdefault(str(report_path), _read(report_path))
            matches = [
                item
                for item in report.get("candidates") or []
                if item.get("sourceModuleDefinitionId")
                == row.get("sourceModuleDefinitionId")
                and item.get("targetBaseDefinitionId")
                == row.get("targetBaseDefinitionId")
            ]
            if len(matches) != 1:
                raise ValueError("calibration candidate is missing or ambiguous")
            candidate = matches[0]
        decision = {
            "decisionId": (
                f"{row['sourceModuleDefinitionId']}->{row['targetBaseDefinitionId']}"
            ),
            "sourceModuleDefinitionId": row["sourceModuleDefinitionId"],
            "targetBaseDefinitionId": row["targetBaseDefinitionId"],
            "pairClass": row.get("pairClass"),
            "decisionKind": kind,
            "allowedDecisions": options,
            "confirmed": False,
            "selectedDecision": None,
            "cadLaunchAllowed": False,
            "currentInterfaceAuthorityStatus": (
                row.get("authority") or {}
            ).get("status"),
        }
        if candidate is not None:
            decision["interfaceTopology"] = candidate.get("interfaceTopology")
            decision["candidateStatus"] = candidate.get("status")
            decision["bestCandidate"] = candidate.get("bestCandidate")
            decision["positionParametersMeters"] = candidate.get(
                "positionParametersMeters"
            )
            decision["supportNormalOffsetMeters"] = candidate.get(
                "supportNormalOffsetMeters"
            )
            decision["planarErrorMeters"] = candidate.get("planarErrorMeters")
            decision["nextAction"] = candidate.get("nextAction")
            decision["candidateEvidence"] = {
                "path": str(report_path),
                "sha256": candidate_index["reportSha256"],
            }
        decisions.append(decision)
    decisions.sort(
        key=lambda item: (
            item["decisionKind"],
            item["sourceModuleDefinitionId"],
            item["targetBaseDefinitionId"],
        )
    )
    counts: dict[str, int] = {}
    for row in decisions:
        counts[row["decisionKind"]] = counts.get(row["decisionKind"], 0) + 1
    return {
        "schemaVersion": "calibration-station-decision-request/v1",
        "decisions": decisions,
        "summary": {
            "decisionCount": len(decisions),
            "decisionKindCounts": counts,
            "confirmedCount": 0,
        },
        "cadStarted": False,
        "evidence": {"path": str(queue_path), "sha256": _sha(queue_path)},
        "boundary": (
            "Candidate geometry and residuals support engineering review only. "
            "No choice is inferred and no CAD execution is authorized."
        ),
    }


def build_combined_station_candidate_decision_report(
    calibration_report: dict[str, Any], transport_review: dict[str, Any],
    scanner_review: dict[str, Any] | None = None,
    extension_reports: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Normalize independent offline recommendations into one gap input."""

    if calibration_report.get("schemaVersion") != PLANAR_CANDIDATE_SCHEMA:
        raise ValueError("unsupported calibration candidate report")
    if transport_review.get("schemaVersion") != (
        "transport-station-engineering-review-queue/v1"
    ):
        raise ValueError("unsupported transport station review queue")
    candidates = []
    for row in calibration_report.get("candidates") or []:
        candidates.append({**row, "role": "Calibration"})
    for row in transport_review.get("recommendations") or []:
        if row.get("status") not in {
            "recommendation_pending_engineering_confirmation",
            "engineering_confirmation_recorded_requires_target_station_postcheck",
            "native_station_requires_current_saved_output_station_postcheck",
        }:
            raise ValueError("transport recommendation has an unsupported state")
        status = row["status"]
        if status == "recommendation_pending_engineering_confirmation":
            next_action = (
                "confirm_target_native_station_reuse_and_track_work_area_fit_"
                "before_nonprototype_cad_validation"
            )
        else:
            next_action = row.get("nextAction")
        candidates.append({
            "sourceModuleDefinitionId": row["sourceModuleDefinitionId"],
            "targetBaseDefinitionId": row["targetBaseDefinitionId"],
            "role": "Transport",
            "interfaceTopology": "support_plane_two_offset_position",
            "status": row["status"],
            "readyForCadValidation": False,
            "cadLaunchAllowed": False,
            "recommendedPositionParametersMeters": row[
                "recommendedPositionParametersMeters"
            ],
            "nativeRoleModuleDefinitionId": row["nativeRoleModuleDefinitionId"],
            "basis": row["basis"],
            "nativeStationEvidenceDigest": row["nativeStationEvidenceDigest"],
            "engineeringConfirmation": copy.deepcopy(row.get("confirmationTemplate")),
            "nextAction": next_action,
            "claimBoundary": row["boundary"],
        })
    if scanner_review is not None:
        if scanner_review.get("schemaVersion") != "scanner-transport-binding-review-queue/v1":
            raise ValueError("unsupported scanner transport binding queue")
        for row in scanner_review.get("candidates") or []:
            if row.get("status") not in {
                "ready_for_exact_chain_instance_selection",
                "exact_saved_context_available_requires_geometry_evaluation",
                "new_cumulative_chain_context_required",
                "current_context_point_pair_geometry_mismatch",
                "current_context_proxy_passed_requires_station_registration",
            }:
                raise ValueError("scanner binding candidate has an unsupported state")
            candidates.append({
                "sourceModuleDefinitionId": row["sourceModuleDefinitionId"],
                "targetBaseDefinitionId": row["targetBaseDefinitionId"],
                "role": "Scanner",
                "interfaceTopology": "scanner_target_association_bound_to_transport",
                "status": row["status"],
                "readyForCadValidation": False,
                "cadLaunchAllowed": False,
                "transportModuleDefinitionId": row["transportModuleDefinitionId"],
                "sourceCandidateDigest": row["candidateDigest"],
                "currentContextEvaluation": copy.deepcopy(
                    row.get("currentContextEvaluation")
                ),
                "nextAction": row.get("nextAction") or (
                    "bind_exact_scanner_transport_and_base_instances_in_the_saved_chain_"
                    "then_recompute_optical_axis_barcode_target_and_working_distance"
                ),
                "claimBoundary": row["boundary"],
            })
    for report in extension_reports or []:
        if report.get("schemaVersion") != EXTENSION_CANDIDATE_REPORT_SCHEMA:
            raise ValueError("unsupported station candidate extension report")
        rows = report.get("candidates")
        if not isinstance(rows, list):
            raise ValueError("station candidate extension must contain a candidate list")
        for row in rows:
            required = (
                "sourceModuleDefinitionId", "targetBaseDefinitionId", "role",
                "interfaceTopology", "status", "nextAction", "claimBoundary",
            )
            if any(not isinstance(row.get(key), str) or not row[key] for key in required):
                raise ValueError("station candidate extension row is incomplete")
            if row.get("cadLaunchAllowed") is not False:
                raise ValueError("station candidate extension cannot authorize CAD")
            candidates.append(dict(row))
    keys = [
        (row["sourceModuleDefinitionId"], row["targetBaseDefinitionId"], row["role"])
        for row in candidates
    ]
    if len(keys) != len(set(keys)):
        raise ValueError("combined station candidate report has duplicate pairs")
    return {
        "schemaVersion": COMBINED_CANDIDATE_REPORT_SCHEMA,
        "candidates": candidates,
        "summary": {
            "candidateCount": len(candidates),
            "calibrationCandidateCount": sum(row["role"] == "Calibration" for row in candidates),
            "transportRecommendationCount": sum(row["role"] == "Transport" for row in candidates),
            "scannerInstanceBindingCount": sum(row["role"] == "Scanner" for row in candidates),
            "extensionCandidateCount": sum(
                row["role"] not in {"Calibration", "Transport", "Scanner"}
                for row in candidates
            ),
        },
        "sourceDigests": {
            "calibrationCandidateReport": calibration_report.get("summary"),
            "transportReviewQueueDigest": transport_review.get("queueDigest"),
            "scannerReviewQueueDigest": (
                scanner_review.get("queueDigest") if scanner_review is not None else None
            ),
            "extensionReportDigests": [
                report.get("reportDigest") for report in extension_reports or []
            ],
        },
        "cadExecuted": False,
        "boundary": (
            "Combined offline decision evidence only. Recommendations remain unconfirmed and "
            "cannot authorize CAD or relation publication."
        ),
    }


def screen_calibration_gap_pairs(workspace: Path, catalog: dict[str, Any], gap_queue: dict[str, Any]) -> dict[str, Any]:
    root = Path(workspace).resolve()
    by_module = {row["moduleDefinitionId"]: row for row in catalog["entries"]}
    by_base = {row["nativeTargetBaseDefinitionId"]: row for row in catalog["entries"]}
    tolerance = float(catalog["pointToleranceMeters"])
    results, evidence = [], {row["path"]: row for row in catalog["evidence"]}
    for gap in gap_queue.get("queue") or []:
        if gap.get("role") != "Calibration" or gap.get("validatedStationRule") is True:
            continue
        source_id, base_id = gap["sourceModuleDefinitionId"], gap["targetBaseDefinitionId"]
        source, target = by_module[source_id], by_base[base_id]
        row = {"sourceModuleDefinitionId": source_id, "targetBaseDefinitionId": base_id,
               "role": "Calibration", "cadLaunchAllowed": False, "newCadExecuted": False}
        graph_value = (gap.get("historicalPairEvidence") or {}).get("effectiveGraphPath")
        if not graph_value:
            manifest_value = (gap.get("authority") or {}).get("releaseManifestPath")
            if manifest_value:
                manifest_path = _file(root, manifest_value)
                manifest = _read(manifest_path)
                binding = ((manifest.get("releaseMetadata") or {})
                           .get("directInterfacePairBinding") or {})
                if (binding.get("moduleDefinitionId") == source_id
                        and binding.get("slotDefinitionId") == base_id
                        and binding.get("nonPrototypeCadValidated") is True):
                    graph_path = _file(root, binding.get("effectiveGraphPath"))
                    if _sha(graph_path) != binding.get("effectiveGraphSha256"):
                        raise ValueError("released calibration effective graph changed")
                    graph_value = str(graph_path)
                    evidence[str(manifest_path)] = {
                        "path": str(manifest_path), "sha256": _sha(manifest_path),
                    }
                if not graph_value:
                    validation = manifest.get("validationEvidence") or []
                    validation = validation if isinstance(validation, list) else [validation]
                    candidates = []
                    for item in validation:
                        result_path = _file(root, item.get("path"))
                        if _sha(result_path) != item.get("fileSha256") or item.get("passed") is not True:
                            raise ValueError("released calibration validation evidence changed")
                        cad = _read(result_path)
                        raw_token = (cad.get("toolResult") or {}).get("TargetModuleToken") or cad.get("targetModuleToken")
                        if (cad.get("success") is True and isinstance(raw_token, str)
                                and raw_token.upper().endswith(source["moduleToken"])):
                            candidate = cad.get("executionEffectiveGraphPath") or cad.get("effectiveGraphPath")
                            expected_sha = (cad.get("executionEffectiveGraphSha256")
                                            or cad.get("effectiveGraphSha256"))
                            candidate_path = _file(root, candidate)
                            if _sha(candidate_path) != expected_sha:
                                raise ValueError("released calibration validation graph changed")
                            candidates.append(candidate_path)
                            evidence[str(result_path)] = {
                                "path": str(result_path), "sha256": _sha(result_path),
                            }
                    if len(candidates) == 1:
                        graph_value = str(candidates[0])
                        evidence[str(manifest_path)] = {
                            "path": str(manifest_path), "sha256": _sha(manifest_path),
                        }
        if not graph_value:
            row.update(status="historical_pair_pose_missing", passed=False,
                       nextAction="obtain_exact_pair_pose_or_build_a_new_candidate")
            results.append(row)
            continue
        graph_path = _file(root, graph_value)
        graph = _read(graph_path)
        evidence[str(graph_path)] = {"path": str(graph_path), "sha256": _sha(graph_path)}
        source_pose = _transform(_module(graph, source["moduleToken"])["SourceTransform"])
        base_pose = _transform(_module(graph, target["baseToken"])["SourceTransform"])
        actual = _point(_point(source["pointLocalMeters"], source_pose), base_pose, inverse=True)
        expected = target["nativePointInBaseMeters"]
        delta = [actual[i] - expected[i] for i in range(3)]
        error = math.sqrt(sum(value * value for value in delta))
        passed = error <= tolerance
        row.update(
            status=("published_pose_calibration_point_matches_target_station" if passed
                    else "published_pose_calibration_point_misses_target_station"),
            passed=passed,
            sourcePointLocalMeters=source["pointLocalMeters"],
            actualPointInTargetBaseMeters=actual,
            targetNativePointInBaseMeters=expected,
            deltaMeters=delta,
            errorMeters=error,
            toleranceMeters=tolerance,
            nextAction=("bind_the_exact_interface_as_a_station_candidate_then_run_fresh_nonprototype_CAD"
                        if passed else "select_or_derive_a_new_calibration_station_placement_candidate"),
        )
        results.append(row)
    return {
        "schemaVersion": SCREEN_SCHEMA,
        "summary": {
            "listedPairCount": len(results),
            "evaluatedPairCount": sum("errorMeters" in row for row in results),
            "passedPairCount": sum(row["passed"] is True for row in results),
            "mismatchedPairCount": sum(
                row["status"] == "published_pose_calibration_point_misses_target_station"
                for row in results
            ),
            "evidenceMissingPairCount": sum(
                row["status"] == "historical_pair_pose_missing" for row in results
            ),
        },
        "pairs": results,
        "evidence": sorted(evidence.values(), key=lambda row: row["path"]),
        "cadExecuted": False,
        "claimBoundary": catalog["boundary"],
    }


def build_station_functional_screening_reports(screening: dict[str, Any]) -> list[dict[str, Any]]:
    """Expose only evaluated pairs to the existing generic gap classifier."""
    if screening.get("schemaVersion") != SCREEN_SCHEMA:
        raise ValueError("unsupported calibration screening schema")
    reports = []
    for row in screening.get("pairs") or []:
        if "errorMeters" not in row:
            continue
        reports.append({
            "schemaVersion": FUNCTIONAL_REPORT_SCHEMA,
            "sourceModuleDefinitionId": row["sourceModuleDefinitionId"],
            "targetBaseDefinitionId": row["targetBaseDefinitionId"],
            "role": "Calibration",
            "screening": {
                "passed": row["passed"],
                "status": row["status"],
                "errorMeters": row["errorMeters"],
                "toleranceMeters": row["toleranceMeters"],
                "actualPointInTargetBaseMeters": row["actualPointInTargetBaseMeters"],
                "targetNativePointInBaseMeters": row["targetNativePointInBaseMeters"],
            },
            "cadExecuted": False,
            "nextAction": row["nextAction"],
            "boundary": screening["claimBoundary"],
        })
    return reports
