"""Solve and audit a native-hole alternate installation route for a scanner.

The solver deliberately separates two questions:

* the support plane plus two locating-hole axes determine a rigid candidate pose;
* the transformed optical ray must still reach the transport barcode lane.

Matching hole spacing alone therefore never authorizes CAD execution.  The
result is a read-only engineering candidate and remains fail-closed until the
selected holes are confirmed as usable installation features and a CAD mate
closure has passed.
"""

from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from typing import Any, Iterable

from .scanner_target_association import validate_scanner_target_association


SCHEMA = "cross-project-scanner-alternate-route-evaluation/v1"


class CrossProjectScannerAlternateRouteError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _vector(values: Iterable[Any], *, length: int = 3) -> list[float]:
    result = [float(value) for value in values]
    if len(result) != length or not all(math.isfinite(value) for value in result):
        raise CrossProjectScannerAlternateRouteError(
            f"Expected {length} finite numeric values."
        )
    return result


def _dot(first: Iterable[float], second: Iterable[float]) -> float:
    return sum(a * b for a, b in zip(first, second, strict=True))


def _add(first: Iterable[float], second: Iterable[float]) -> list[float]:
    return [a + b for a, b in zip(first, second, strict=True)]


def _sub(first: Iterable[float], second: Iterable[float]) -> list[float]:
    return [a - b for a, b in zip(first, second, strict=True)]


def _scale(vector: Iterable[float], factor: float) -> list[float]:
    return [value * factor for value in vector]


def _norm(vector: Iterable[float]) -> float:
    return math.sqrt(_dot(vector, vector))


def _normalize(vector: Iterable[float]) -> list[float]:
    values = _vector(vector)
    magnitude = _norm(values)
    if magnitude <= 1e-12:
        raise CrossProjectScannerAlternateRouteError("Cannot normalize zero vector.")
    return _scale(values, 1.0 / magnitude)


def _cross(first: Iterable[float], second: Iterable[float]) -> list[float]:
    a = _vector(first)
    b = _vector(second)
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]


def _pose(transform: Iterable[Any]) -> tuple[list[list[float]], list[float]]:
    values = _vector(transform, length=16)
    axes = [values[0:3], values[3:6], values[6:9]]
    translation = values[9:12]
    for axis in axes:
        if abs(_norm(axis) - 1.0) > 1e-6:
            raise CrossProjectScannerAlternateRouteError(
                "Source transform does not contain unit axes."
            )
    return axes, translation


def _world_point_to_local(
    point: Iterable[float], axes: list[list[float]], translation: list[float]
) -> list[float]:
    relative = _sub(_vector(point), translation)
    return [_dot(relative, axis) for axis in axes]


def _world_vector_to_local(
    vector: Iterable[float], axes: list[list[float]]
) -> list[float]:
    values = _vector(vector)
    return [_dot(values, axis) for axis in axes]


def _map_local_point(
    point: Iterable[float], axes: list[list[float]], translation: list[float]
) -> list[float]:
    values = _vector(point)
    return [
        translation[index]
        + sum(values[axis] * axes[axis][index] for axis in range(3))
        for index in range(3)
    ]


def _map_local_vector(
    vector: Iterable[float], axes: list[list[float]]
) -> list[float]:
    values = _vector(vector)
    return _normalize(
        [
            sum(values[axis] * axes[axis][index] for axis in range(3))
            for index in range(3)
        ]
    )


def _endpoint_index(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if catalog.get("SchemaVersion") != "solidworks-face-endpoint-catalog/v1":
        raise CrossProjectScannerAlternateRouteError(
            "Unsupported face endpoint catalog."
        )
    return {
        str(row.get("EndpointId") or ""): row.get("Endpoint") or {}
        for row in catalog.get("Endpoints") or []
    }


def _find_transform(graph: dict[str, Any], token: str) -> list[float]:
    token_upper = token.upper()
    rows = [
        row
        for row in graph.get("Modules") or []
        if token_upper in str(row.get("ModuleToken") or "").upper()
    ]
    if len(rows) != 1:
        raise CrossProjectScannerAlternateRouteError(
            f"Expected one source transform for {token}; found {len(rows)}."
        )
    return _vector(rows[0].get("SourceTransform") or [], length=16)


def _orthonormal_frame(
    hole_one: list[float], hole_two: list[float], support_normal: list[float]
) -> list[list[float]]:
    x_axis = _normalize(_sub(hole_two, hole_one))
    z_axis = _normalize(support_normal)
    y_axis = _normalize(_cross(z_axis, x_axis))
    x_axis = _normalize(_cross(y_axis, z_axis))
    return [x_axis, y_axis, z_axis]


def _rotation_axes(
    source_frame: list[list[float]], target_frame: list[list[float]]
) -> list[list[float]]:
    def map_vector(vector: list[float]) -> list[float]:
        coordinates = [_dot(vector, axis) for axis in source_frame]
        return [
            sum(
                coordinates[axis] * target_frame[axis][index]
                for axis in range(3)
            )
            for index in range(3)
        ]

    return [
        _normalize(map_vector([1.0, 0.0, 0.0])),
        _normalize(map_vector([0.0, 1.0, 0.0])),
        _normalize(map_vector([0.0, 0.0, 1.0])),
    ]


def _closest_ray_to_line(
    ray_origin: list[float],
    ray_direction: list[float],
    line_origin: list[float],
    line_direction: list[float],
) -> tuple[float, float, float]:
    """Return ray distance, line coordinate and shortest line-to-line error."""

    offset = _sub(ray_origin, line_origin)
    a = _dot(ray_direction, ray_direction)
    b = _dot(ray_direction, line_direction)
    c = _dot(line_direction, line_direction)
    d = _dot(ray_direction, offset)
    e = _dot(line_direction, offset)
    denominator = a * c - b * b
    if abs(denominator) <= 1e-12:
        return float("inf"), float("inf"), float("inf")
    ray_distance = (b * e - c * d) / denominator
    line_coordinate = (a * e - b * d) / denominator
    ray_point = _add(ray_origin, _scale(ray_direction, ray_distance))
    line_point = _add(line_origin, _scale(line_direction, line_coordinate))
    return ray_distance, line_coordinate, _norm(_sub(ray_point, line_point))


def build_scanner_alternate_route_evaluation(
    *,
    discovery: dict[str, Any],
    endpoint_recovery: dict[str, Any],
    source_face_catalog: dict[str, Any],
    target_face_catalog: dict[str, Any],
    source_graph: dict[str, Any],
    prior_process_evidence: dict[str, Any],
    source_support_endpoint_id: str,
    source_hole_endpoint_ids: list[str],
    target_association: dict[str, Any] | None = None,
    source_module_token: str = "AI00",
    cross_track_tolerance_meters: float = 0.005,
    mechanical_residual_tolerance_meters: float = 1e-6,
) -> dict[str, Any]:
    """Evaluate every discovered slot and both mechanically valid normal parities."""

    # These are acceptance limits, not knobs for making an incompatible route
    # pass. A stricter experiment is allowed; relaxing the established limits
    # requires a separately reviewed policy, not a caller-provided number.
    for name, value, upper_limit in (
        ("cross-track", cross_track_tolerance_meters, 0.005),
        ("mechanical", mechanical_residual_tolerance_meters, 1e-6),
    ):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 < value <= upper_limit:
            raise CrossProjectScannerAlternateRouteError(
                f"{name} tolerance must be positive and cannot exceed {upper_limit} m."
            )
    if discovery.get("schemaVersion") != "cross-project-scanner-slot-discovery/v1":
        raise CrossProjectScannerAlternateRouteError("Unsupported discovery report.")
    if endpoint_recovery.get("allRecovered") is not True:
        raise CrossProjectScannerAlternateRouteError(
            "Selected target endpoints have not all been recovered."
        )
    if len(source_hole_endpoint_ids) != 2:
        raise CrossProjectScannerAlternateRouteError(
            "Exactly two source locating holes are required."
        )
    source_index = _endpoint_index(source_face_catalog)
    target_index = _endpoint_index(target_face_catalog)
    required_source = [source_support_endpoint_id, *source_hole_endpoint_ids]
    missing_source = [key for key in required_source if key not in source_index]
    if missing_source:
        raise CrossProjectScannerAlternateRouteError(
            f"Missing source endpoints: {missing_source}."
        )

    source_transform = _find_transform(source_graph, source_module_token)
    source_axes, source_translation = _pose(source_transform)
    support = source_index[source_support_endpoint_id]
    source_holes = [source_index[key] for key in source_hole_endpoint_ids]
    source_hole_local = [
        _world_point_to_local(row.get("FaceCenterWorld") or [], source_axes, source_translation)
        for row in source_holes
    ]
    source_support_local = _world_point_to_local(
        support.get("FaceCenterWorld") or [], source_axes, source_translation
    )
    source_support_normal_local = _normalize(
        _world_vector_to_local(
            support.get("FaceNormalWorld") or [], source_axes
        )
    )
    source_frame = _orthonormal_frame(
        source_hole_local[0], source_hole_local[1], source_support_normal_local
    )

    source_process = prior_process_evidence.get("sourceScanner") or {}
    optical_origin_local = _world_point_to_local(
        source_process.get("opticalOriginWorldMeters") or [],
        source_axes,
        source_translation,
    )
    optical_direction_local = _normalize(
        _world_vector_to_local(
            source_process.get("opticalDirectionWorld") or [], source_axes
        )
    )
    target_transport = prior_process_evidence.get("targetTransport") or {}
    installation_frame = target_transport.get("installationFrameWorld") or {}
    transport_origin = _vector(installation_frame.get("origin") or [])
    flow_axis = _normalize(installation_frame.get("flowAxis") or [])
    transverse_axis = _normalize(installation_frame.get("transverseAxis") or [])
    up_axis = _normalize(installation_frame.get("upAxis") or [])
    lane = target_transport.get("barcodeLaneReference") or {}
    lane_origin = _add(
        transport_origin,
        _add(
            _scale(transverse_axis, float(lane["transverseCoordinateMeters"])),
            _scale(up_axis, float(lane["normalCoordinateMeters"])),
        ),
    )
    flow_interval = _vector(
        target_transport.get("conservativeFlowEnvelopeMeters") or [], length=2
    )
    distance_range = (
        prior_process_evidence.get("readOnlyChecks") or {}
    ).get("workingDistanceRangeEvidence") or {}
    min_distance = float(distance_range.get("minimumMeters") or 0.0)
    max_distance = float(distance_range.get("maximumMeters") or 0.0)
    if not (0.0 <= min_distance < max_distance):
        raise CrossProjectScannerAlternateRouteError(
            "Working-distance range evidence is unavailable."
        )

    evaluations: list[dict[str, Any]] = []
    for candidate_index, candidate in enumerate(discovery.get("candidates") or []):
        if candidate.get("directFit") is not True:
            continue
        hole_ids = list(candidate.get("locatingEndpointIds") or [])
        support_ids = list(candidate.get("supportPlaneEndpointIds") or [])
        if len(hole_ids) != 2:
            continue
        if any(key not in target_index for key in [*hole_ids, *support_ids]):
            continue
        target_holes = [
            _vector(
                target_index[key].get("CylinderOriginWorld")
                or target_index[key].get("FaceCenterWorld")
                or []
            )
            for key in hole_ids
        ]
        for support_id in support_ids:
            target_support = target_index[support_id]
            target_support_point = _vector(
                target_support.get("FaceCenterWorld") or []
            )
            target_support_normal = _normalize(
                target_support.get("FaceNormalWorld") or []
            )
            for normal_parity in (1, -1):
                target_frame = _orthonormal_frame(
                    target_holes[0],
                    target_holes[1],
                    _scale(target_support_normal, normal_parity),
                )
                candidate_axes = _rotation_axes(source_frame, target_frame)
                candidate_translation = [
                    target_holes[0][index]
                    - sum(
                        source_hole_local[0][axis]
                        * candidate_axes[axis][index]
                        for axis in range(3)
                    )
                    for index in range(3)
                ]
                # A concentric mate permits translation along the hole axis.
                # Move only in that direction until the support planes coincide.
                mapped_support = _map_local_point(
                    source_support_local, candidate_axes, candidate_translation
                )
                plane_residual = _dot(
                    _sub(mapped_support, target_support_point), target_support_normal
                )
                candidate_translation = _add(
                    candidate_translation,
                    _scale(target_support_normal, -plane_residual),
                )
                mapped_support = _map_local_point(
                    source_support_local, candidate_axes, candidate_translation
                )
                support_residual = abs(
                    _dot(
                        _sub(mapped_support, target_support_point),
                        target_support_normal,
                    )
                )
                hole_residuals = []
                for source_hole, target_hole in zip(
                    source_hole_local, target_holes, strict=True
                ):
                    delta = _sub(
                        _map_local_point(
                            source_hole, candidate_axes, candidate_translation
                        ),
                        target_hole,
                    )
                    perpendicular = _sub(
                        delta,
                        _scale(target_support_normal, _dot(delta, target_support_normal)),
                    )
                    hole_residuals.append(_norm(perpendicular))
                mechanical_passed = bool(
                    support_residual <= mechanical_residual_tolerance_meters
                    and max(hole_residuals) <= mechanical_residual_tolerance_meters
                )

                optical_origin = _map_local_point(
                    optical_origin_local, candidate_axes, candidate_translation
                )
                optical_direction = _map_local_vector(
                    optical_direction_local, candidate_axes
                )
                ray_distance, flow_coordinate, cross_track_error = (
                    _closest_ray_to_line(
                        optical_origin,
                        optical_direction,
                        lane_origin,
                        flow_axis,
                    )
                )
                axis_toward_lane = ray_distance > 0.0
                station_in_envelope = (
                    flow_interval[0] <= flow_coordinate <= flow_interval[1]
                )
                distance_passed = min_distance <= ray_distance <= max_distance
                cross_track_passed = (
                    cross_track_error <= cross_track_tolerance_meters
                )
                process_proxy_passed = bool(
                    axis_toward_lane
                    and station_in_envelope
                    and distance_passed
                    and cross_track_passed
                )
                transform = [
                    *candidate_axes[0],
                    *candidate_axes[1],
                    *candidate_axes[2],
                    *candidate_translation,
                    1.0,
                    0.0,
                    0.0,
                    0.0,
                ]
                evaluations.append(
                    {
                        "candidateIndex": candidate_index,
                        "supportPlaneEndpointId": support_id,
                        "locatingEndpointIds": hole_ids,
                        "normalParity": (
                            "source_support_normal_aligned_to_target"
                            if normal_parity == 1
                            else "source_support_normal_anti_aligned_to_target"
                        ),
                        "candidateTransform": transform,
                        "mechanicalChecks": {
                            "supportPlaneResidualMeters": support_residual,
                            "locatingAxisPerpendicularResidualMeters": hole_residuals,
                            "mechanicalResidualToleranceMeters": mechanical_residual_tolerance_meters,
                            "passed": mechanical_passed,
                        },
                        "processProxyChecks": {
                            "opticalOriginWorldMeters": optical_origin,
                            "opticalDirectionWorld": optical_direction,
                            "requiredWorkingDistanceMeters": ray_distance,
                            "workingDistanceRangeMeters": [min_distance, max_distance],
                            "transportFlowCoordinateMeters": flow_coordinate,
                            "transportFlowEnvelopeMeters": flow_interval,
                            "crossTrackErrorMeters": cross_track_error,
                            "crossTrackToleranceMeters": cross_track_tolerance_meters,
                            "axisPointsTowardBarcodeLane": axis_toward_lane,
                            "stationInsideTransportEnvelope": station_in_envelope,
                            "workingDistancePassed": distance_passed,
                            "crossTrackPassed": cross_track_passed,
                            "passed": process_proxy_passed,
                        },
                    }
                )

    if not evaluations:
        raise CrossProjectScannerAlternateRouteError(
            "No evaluable direct-fit alternate slot candidates were found."
        )
    evaluations.sort(
        key=lambda row: (
            not row["mechanicalChecks"]["passed"],
            not row["processProxyChecks"]["passed"],
            row["processProxyChecks"]["crossTrackErrorMeters"],
            abs(row["processProxyChecks"]["requiredWorkingDistanceMeters"]),
            row["candidateIndex"],
            row["supportPlaneEndpointId"],
        )
    )
    selected = deepcopy(evaluations[0])
    mechanical_passed = selected["mechanicalChecks"]["passed"] is True
    process_passed = selected["processProxyChecks"]["passed"] is True
    association_blockers = validate_scanner_target_association(
        target_association, prior_process_evidence=prior_process_evidence
    )
    if target_association:
        inputs = target_association.get("sourceInputDigests") or {}
        if inputs.get("scannerGraph") != _digest(source_graph) or inputs.get("targetFaceCatalog") != _digest(target_face_catalog):
            association_blockers.append("SCANNER_TARGET_GEOMETRY_INPUTS_CHANGED")
    recovered_ids = {
        row.get("endpointId") for row in endpoint_recovery.get("results") or []
        if row.get("success") is True
    }
    selected_recovered = {
        selected["supportPlaneEndpointId"], *selected["locatingEndpointIds"]
    }.issubset(recovered_ids)
    if not selected_recovered:
        association_blockers.append("SELECTED_SCANNER_SLOT_ENDPOINT_RECOVERY_MISSING")
    association_blockers = sorted(set(association_blockers))
    status = (
        "mechanical_and_process_proxy_passed_pending_review_and_cad"
        if mechanical_passed and process_passed and not association_blockers
        else "blocked_before_cad_missing_target_association_evidence"
        if mechanical_passed and process_passed
        else "blocked_process_proxy_mismatch"
        if mechanical_passed
        else "blocked_mechanical_pose_solve"
    )
    relation = discovery.get("sourceRelation") or {}
    core = {
        "schemaVersion": SCHEMA,
        "status": status,
        "routeId": "project03-ai00-to-project01-jj00-alternate-200mm",
        "sourceScanner": {
            "projectId": relation.get("sourceProjectId"),
            "moduleToken": relation.get("sourceModuleToken"),
            "supportPlaneEndpointId": source_support_endpoint_id,
            "locatingEndpointIds": source_hole_endpoint_ids,
            "sourceTransform": source_transform,
        },
        "targetContext": {
            "projectId": relation.get("targetProjectId"),
            "baseModuleToken": "JJ00",
            "transportModuleToken": "SS00",
            "barcodeLaneAuthority": lane.get("source"),
            "engineeringConfirmedBarcodeSurface": lane.get(
                "engineeringConfirmedBarcodeSurface"
            )
            is True,
        },
        "candidatePoseTransformSolved": mechanical_passed,
        "processProxyValidationPassed": process_passed,
        "targetAssociationDigest": (target_association or {}).get("associationDigest"),
        "targetAssociationCheck": {
            "passed": not association_blockers,
            "blockingReasonCodes": association_blockers,
            "selectedSlotEndpointsRecovered": selected_recovered,
        },
        "processCandidateReady": mechanical_passed and process_passed and not association_blockers,
        "calculationEvidence": {
            "performed": True,
            "kind": "offline_rigid_pose_and_barcode_lane_proxy",
            "evidenceGrade": "prototype_measured_proxy",
            "workingDistanceMeters": selected["processProxyChecks"]["requiredWorkingDistanceMeters"],
            "engineeringConfirmedBarcodeSurface": False,
        },
        "cadEvidence": {
            "performed": False,
            "nonPrototypeMateClosurePassed": None,
            "savedReopened": None,
        },
        "engineeringProcessValidationPassed": False,
        "measuredScanSuccess": False,
        "selectedCandidate": selected,
        "evaluatedPoseCount": len(evaluations),
        "candidateEvaluations": evaluations,
        "cadLaunchAllowed": False,
        "semanticPortPublished": False,
        "productionReady": False,
        "mechanicalReviewRequired": [
            "confirm-selected-hole-purpose-is-module-installation",
            "confirm-hole-thread-or-fastener-specification",
            "confirm-support-and-hole-load-capacity",
        ],
        "limitations": [
            "条码目标仍是Project01原型光束端点形成的通道代理，不是真实条码面。",
            "没有执行SolidWorks配合、保存重开、碰撞或B-rep。",
            "孔径与孔距匹配不证明孔用途、螺纹和承载能力满足安装要求。",
        ],
        "nextAction": (
            "mechanical-review-selected-hole-purpose-then-run-non-source-pose-cad"
            if process_passed
            else "reject-current-alternate-slot-or-register-a-different-scanner-process-target"
        ),
        "project06Included": False,
    }
    return {**core, "evaluationDigest": _digest(core)}
