"""Read-only optical compatibility audit for a scanner/transport combination.

The transported barcode is not fixed at the native scanner station: the
carrier moves along the transport flow axis.  Consequently the audit compares
the scanner ray with the transport's barcode *lane* (cross-track position and
height) and separately checks whether the scanner station lies inside the
transport envelope.  A modeled beam length is reported as a nominal value; it
is never promoted to an authoritative working-distance interval.
"""

from __future__ import annotations

import hashlib
import json
import math
from itertools import product
from pathlib import Path
from typing import Any, Iterable


SCHEMA = "cross-project-scanner-transport-process-validation/v1"


class ScannerTransportProcessValidationError(ValueError):
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
        raise ScannerTransportProcessValidationError(
            f"Expected {length} finite numeric values."
        )
    return result


def _normalize(values: Iterable[Any]) -> list[float]:
    vector = _vector(values)
    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude <= 1e-12:
        raise ScannerTransportProcessValidationError("Cannot normalize a zero vector.")
    return [value / magnitude for value in vector]


def _dot(first: Iterable[float], second: Iterable[float]) -> float:
    return sum(a * b for a, b in zip(first, second, strict=True))


def _sub(first: Iterable[float], second: Iterable[float]) -> list[float]:
    return [a - b for a, b in zip(first, second, strict=True)]


def _add(first: Iterable[float], second: Iterable[float]) -> list[float]:
    return [a + b for a, b in zip(first, second, strict=True)]


def _scale(vector: Iterable[float], factor: float) -> list[float]:
    return [value * factor for value in vector]


def _pose(transform: Iterable[Any]) -> tuple[list[list[float]], list[float]]:
    values = _vector(transform, length=16)
    axes = [values[0:3], values[3:6], values[6:9]]
    translation = values[9:12]
    for axis in axes:
        if abs(math.sqrt(_dot(axis, axis)) - 1.0) > 1e-6:
            raise ScannerTransportProcessValidationError(
                "Module transform does not contain unit rotation axes."
            )
    return axes, translation


def _source_world_to_target_world(
    point: Iterable[float],
    source_transform: Iterable[Any],
    target_transform: Iterable[Any],
) -> list[float]:
    source_axes, source_translation = _pose(source_transform)
    target_axes, target_translation = _pose(target_transform)
    relative = _sub(_vector(point), source_translation)
    local = [_dot(relative, axis) for axis in source_axes]
    return [
        target_translation[index]
        + sum(local[axis] * target_axes[axis][index] for axis in range(3))
        for index in range(3)
    ]


def _source_vector_to_target_world(
    vector: Iterable[float],
    source_transform: Iterable[Any],
    target_transform: Iterable[Any],
) -> list[float]:
    source_axes, _ = _pose(source_transform)
    target_axes, _ = _pose(target_transform)
    source_vector = _vector(vector)
    local = [_dot(source_vector, axis) for axis in source_axes]
    return _normalize(
        [
            sum(local[axis] * target_axes[axis][index] for axis in range(3))
            for index in range(3)
        ]
    )


def _frame_coordinates(
    point: Iterable[float], origin: Iterable[float], axes: list[list[float]]
) -> list[float]:
    offset = _sub(_vector(point), _vector(origin))
    return [_dot(offset, axis) for axis in axes]


def _find_module_transform(graph: dict[str, Any], token: str) -> list[float]:
    rows = [
        row
        for row in graph.get("Modules") or []
        if str(row.get("ModuleToken") or "").upper() == token.upper()
    ]
    if len(rows) != 1:
        raise ScannerTransportProcessValidationError(
            f"Expected one {token} module transform; found {len(rows)}."
        )
    return _vector(rows[0].get("SourceTransform") or [], length=16)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_scanner_transport_process_validation(
    *,
    optical_validation: dict[str, Any],
    project01_scanner_geometry: dict[str, Any],
    project01_first_stage_geometry: dict[str, Any],
    project01_source_graph: dict[str, Any],
    final_ss00_graph: dict[str, Any],
    final_assembly_path: Path,
    cross_track_tolerance_meters: float = 0.005,
    working_distance_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Audit AI00 against the moving barcode lane of the installed SS00."""

    if project01_scanner_geometry.get("schemaVersion") != "project01-scanner-geometry/v1":
        raise ScannerTransportProcessValidationError("Unsupported scanner geometry evidence.")
    if project01_first_stage_geometry.get("schemaVersion") != "project01-first-stage-geometry/v1":
        raise ScannerTransportProcessValidationError("Unsupported first-stage geometry evidence.")
    assembly = final_assembly_path.resolve()
    if not assembly.is_file():
        raise FileNotFoundError(assembly)

    source_transform = _find_module_transform(project01_source_graph, "SS00")
    final_transform = _find_module_transform(final_ss00_graph, "SS00")
    interface = project01_first_stage_geometry.get("transportInstallationInterface") or {}
    source_origin = _vector(interface.get("originWorldMeters") or [])
    source_axes = [
        _normalize(interface.get("flowAxisWorld") or []),
        _normalize(interface.get("transverseAxisWorld") or []),
        _normalize(interface.get("upAxisWorld") or []),
    ]
    final_origin = _source_world_to_target_world(
        source_origin, source_transform, final_transform
    )
    final_axes = [
        _source_vector_to_target_world(axis, source_transform, final_transform)
        for axis in source_axes
    ]

    nominal_distance = float(optical_validation.get("modeledWorkingDistanceMeters") or 0.0)
    if nominal_distance <= 0:
        raise ScannerTransportProcessValidationError("Modeled working distance is absent.")
    ray_direction = _normalize(optical_validation.get("opticalDirectionWorld") or [])
    ray_proxy = _vector(optical_validation.get("targetProxyWorldMeters") or [])
    ray_origin = _sub(ray_proxy, _scale(ray_direction, nominal_distance))
    ray_origin_frame = _frame_coordinates(ray_origin, final_origin, final_axes)
    ray_proxy_frame = _frame_coordinates(ray_proxy, final_origin, final_axes)
    ray_direction_frame = [_dot(ray_direction, axis) for axis in final_axes]

    product_interface = project01_scanner_geometry.get("productScanInterface") or {}
    lane_reference = product_interface.get("targetProxyInstallationFrameMeters") or {}
    lane_v = float(lane_reference["v"])
    lane_normal = float(lane_reference["normal"])
    # The carrier can move to the AI00 station, therefore U is supplied by the
    # current scanner station while V/normal define the reusable barcode lane.
    lane_target_frame = [ray_proxy_frame[0], lane_v, lane_normal]
    delta_to_lane = _sub(lane_target_frame, ray_origin_frame)
    distance_along_axis = _dot(delta_to_lane, ray_direction_frame)
    perpendicular = _sub(delta_to_lane, _scale(ray_direction_frame, distance_along_axis))
    cross_track_error = math.sqrt(_dot(perpendicular, perpendicular))
    nominal_proxy_error = math.sqrt(
        _dot(_sub(ray_proxy_frame, lane_target_frame), _sub(ray_proxy_frame, lane_target_frame))
    )

    bounds = _vector(
        ((project01_first_stage_geometry.get("topLevelOccupancy") or {}).get(
            "ss00WorldBoundsMeters"
        ) or []),
        length=6,
    )
    mapped_corners = [
        _source_world_to_target_world(
            corner, source_transform, final_transform
        )
        for corner in product(
            (bounds[0], bounds[3]),
            (bounds[1], bounds[4]),
            (bounds[2], bounds[5]),
        )
    ]
    flow_coordinates = [
        _frame_coordinates(corner, final_origin, final_axes)[0]
        for corner in mapped_corners
    ]
    flow_interval = [min(flow_coordinates), max(flow_coordinates)]
    station_in_envelope = flow_interval[0] <= ray_proxy_frame[0] <= flow_interval[1]
    axis_toward_lane = distance_along_axis > 0
    coarse_alignment_passed = bool(
        station_in_envelope
        and axis_toward_lane
        and cross_track_error <= float(cross_track_tolerance_meters)
    )

    distance_range = working_distance_evidence or {}
    has_distance_range = all(
        isinstance(distance_range.get(key), (int, float))
        for key in ("minimumMeters", "maximumMeters")
    ) and float(distance_range.get("maximumMeters") or 0.0) > float(
        distance_range.get("minimumMeters") or 0.0
    )
    working_distance_passed = (
        float(distance_range["minimumMeters"])
        <= distance_along_axis
        <= float(distance_range["maximumMeters"])
        if has_distance_range
        else None
    )
    static_demo_passed = coarse_alignment_passed and working_distance_passed is True
    engineering_process_passed = False
    status = (
        "static_demo_passed_barcode_surface_proxy"
        if static_demo_passed
        else "blocked_working_distance_out_of_range"
        if coarse_alignment_passed and working_distance_passed is False
        else "coarse_geometry_compatible_working_distance_unconfirmed"
        if coarse_alignment_passed
        else "blocked_cross_project_optical_geometry_mismatch"
    )
    core = {
        "schemaVersion": SCHEMA,
        "status": status,
        "sourceScanner": {
            "projectId": "project03",
            "moduleToken": "AI00",
            "scannerModel": optical_validation.get("scannerModel"),
            "modeledNominalWorkingDistanceMeters": nominal_distance,
            "opticalOriginWorldMeters": ray_origin,
            "opticalDirectionWorld": ray_direction,
            "cadBeamEndpointProxyWorldMeters": ray_proxy,
        },
        "targetTransport": {
            "projectId": "project01",
            "moduleToken": "SS00",
            "sourceTransform": source_transform,
            "installedTransform": final_transform,
            "installationFrameWorld": {
                "origin": final_origin,
                "flowAxis": final_axes[0],
                "transverseAxis": final_axes[1],
                "upAxis": final_axes[2],
            },
            "conservativeFlowEnvelopeMeters": flow_interval,
            "barcodeLaneReference": {
                "source": "Project01 product-scanner CAD beam endpoint proxy",
                "flowCoordinateBehavior": "dynamic-with-carrier",
                "transverseCoordinateMeters": lane_v,
                "normalCoordinateMeters": lane_normal,
                "engineeringConfirmedBarcodeSurface": False,
            },
        },
        "readOnlyChecks": {
            "scannerStationFlowCoordinateMeters": ray_proxy_frame[0],
            "scannerStationInsideTransportEnvelope": station_in_envelope,
            "scannerRayOriginInstallationFrameMeters": ray_origin_frame,
            "scannerCadBeamEndpointInstallationFrameMeters": ray_proxy_frame,
            "barcodeLaneTargetAtScannerStationMeters": lane_target_frame,
            "rayDirectionInstallationFrame": ray_direction_frame,
            "axisPointsTowardBarcodeLane": axis_toward_lane,
            "requiredWorkingDistanceMeters": distance_along_axis,
            "crossTrackErrorMeters": cross_track_error,
            "crossTrackToleranceMeters": float(cross_track_tolerance_meters),
            "nominalCadEndpointToLaneErrorMeters": nominal_proxy_error,
            "coarseAxisLaneAlignmentPassed": coarse_alignment_passed,
            "workingDistanceRangeEvidence": distance_range or None,
            "authoritativeWorkingDistanceRangeAvailable": has_distance_range,
            "workingDistanceCompatibilityPassed": working_distance_passed,
        },
        "coarseProcessGeometryPassed": coarse_alignment_passed,
        "staticDemoProcessValidationPassed": static_demo_passed,
        "engineeringProcessValidationPassed": engineering_process_passed,
        "productionReady": False,
        "finalAssemblyPath": str(assembly),
        "finalAssemblySha256": _sha256(assembly),
        "limitations": [
            "AI00的100 mm长度是Project03 CAD光束基线，不是KEYENCE确认的最小/最大工作距离。",
            "SS00条码通道来自Project01产品扫描器光束端点代理，不是已登记的真实条码面。",
            "SS00纵向区间来自整模组AABB，只证明扫描站落在保守包络内，不等于确认PLC停位。",
            "本报告只做只读工艺几何验证，不执行碰撞或B-rep。",
        ],
        "nextAction": (
            "register-real-ss00-barcode-surface-and-verify-code-size-field-of-view"
            if static_demo_passed
            else "confirm-ai00-working-distance-range-and-register-ss00-barcode-surface"
            if coarse_alignment_passed
            else "repair-scanner-station-or-orientation-before-cad-release"
        ),
        "project06Included": False,
    }
    return {**core, "validationDigest": _digest(core)}
