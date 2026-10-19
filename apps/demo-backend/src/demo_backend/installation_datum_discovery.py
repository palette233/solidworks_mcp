"""Discover reviewable secondary installation datums from bounded face catalogs.

The discovery step is deliberately conservative.  Prototype world geometry is
used only to screen pairs of already registered persistent face endpoints.  It
does not publish a semantic port and it never emits a pose anchor.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Iterable


SCHEMA = "installation-datum-discovery/v1"


class InstallationDatumDiscoveryError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _vector(value: Any, *, field: str) -> list[float] | None:
    if value is None:
        return None
    if not isinstance(value, list) or len(value) != 3:
        raise InstallationDatumDiscoveryError(f"{field} must be a 3-vector")
    return [float(item) for item in value]


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _norm(vector: list[float]) -> float:
    return math.sqrt(_dot(vector, vector))


def _unit(vector: list[float]) -> list[float]:
    length = _norm(vector)
    if length <= 1e-12:
        raise InstallationDatumDiscoveryError("geometry direction is zero")
    return [value / length for value in vector]


def _sub(a: list[float], b: list[float]) -> list[float]:
    return [x - y for x, y in zip(a, b)]


def _cross(a: list[float], b: list[float]) -> list[float]:
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]


def _parallel_score(a: list[float], b: list[float]) -> float:
    return abs(_dot(_unit(a), _unit(b)))


def _axis_line_distance(
    origin_a: list[float], origin_b: list[float], axis: list[float]
) -> float:
    direction = _unit(axis)
    return _norm(_cross(_sub(origin_b, origin_a), direction))


def _axial_gap(
    origin_a: list[float], origin_b: list[float], axis: list[float]
) -> float:
    return abs(_dot(_sub(origin_b, origin_a), _unit(axis)))


def _endpoint_rows(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    if catalog.get("SchemaVersion") != "solidworks-face-endpoint-catalog/v1":
        raise InstallationDatumDiscoveryError("unsupported face catalog schema")
    rows = catalog.get("Endpoints")
    if not isinstance(rows, list):
        raise InstallationDatumDiscoveryError("face catalog has no Endpoints list")
    return rows


def _endpoint_id(row: dict[str, Any]) -> str:
    value = str(row.get("EndpointId") or "")
    if not value:
        raise InstallationDatumDiscoveryError("endpoint has no EndpointId")
    return value


def _cylinders(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        endpoint = row.get("Endpoint") or {}
        if endpoint.get("SurfaceType") != "Cylinder":
            continue
        axis = _vector(endpoint.get("CylinderAxisWorld"), field="CylinderAxisWorld")
        origin = _vector(
            endpoint.get("CylinderOriginWorld"), field="CylinderOriginWorld"
        )
        if axis is None or origin is None:
            continue
        result.append(row)
    return result


def _planes(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        endpoint = row.get("Endpoint") or {}
        if endpoint.get("SurfaceType") != "Plane":
            continue
        normal = _vector(endpoint.get("FaceNormalWorld"), field="FaceNormalWorld")
        center = _vector(endpoint.get("FaceCenterWorld"), field="FaceCenterWorld")
        if normal is None or center is None:
            continue
        result.append(row)
    return result


def discover_secondary_installation_datums(
    moving_catalog: dict[str, Any],
    target_catalog: dict[str, Any],
    *,
    primary_moving_endpoint_id: str,
    primary_target_endpoint_id: str,
    support_moving_endpoint_id: str | None = None,
    support_target_endpoint_id: str | None = None,
    axis_parallel_tolerance: float = 1e-4,
    axis_line_tolerance_m: float = 2e-4,
    maximum_axial_gap_m: float = 0.05,
    minimum_primary_independence_m: float = 0.002,
    plane_parallel_tolerance: float = 1e-4,
    plane_separation_tolerance_m: float = 2e-4,
    maximum_plane_center_distance_m: float = 0.08,
) -> dict[str, Any]:
    """Screen a bounded module/base face pair for a missing anti-rotation datum."""

    moving_rows = _endpoint_rows(moving_catalog)
    target_rows = _endpoint_rows(target_catalog)
    moving_by_id = {_endpoint_id(row): row for row in moving_rows}
    target_by_id = {_endpoint_id(row): row for row in target_rows}
    if primary_moving_endpoint_id not in moving_by_id:
        raise InstallationDatumDiscoveryError("primary moving endpoint is absent")
    if primary_target_endpoint_id not in target_by_id:
        raise InstallationDatumDiscoveryError("primary target endpoint is absent")

    primary_moving = moving_by_id[primary_moving_endpoint_id]["Endpoint"]
    primary_axis = _vector(
        primary_moving.get("CylinderAxisWorld"), field="primary CylinderAxisWorld"
    )
    primary_origin = _vector(
        primary_moving.get("CylinderOriginWorld"),
        field="primary CylinderOriginWorld",
    )
    if primary_axis is None or primary_origin is None:
        raise InstallationDatumDiscoveryError("primary moving endpoint is not cylindrical")

    excluded = {
        primary_moving_endpoint_id,
        primary_target_endpoint_id,
        support_moving_endpoint_id,
        support_target_endpoint_id,
        None,
    }
    axis_candidates: list[dict[str, Any]] = []
    for moving in _cylinders(moving_rows):
        moving_id = _endpoint_id(moving)
        if moving_id in excluded:
            continue
        moving_endpoint = moving["Endpoint"]
        moving_axis = _vector(
            moving_endpoint["CylinderAxisWorld"], field="CylinderAxisWorld"
        )
        moving_origin = _vector(
            moving_endpoint["CylinderOriginWorld"], field="CylinderOriginWorld"
        )
        assert moving_axis is not None and moving_origin is not None
        axis_relation_to_primary = _parallel_score(moving_axis, primary_axis)
        if axis_relation_to_primary >= 1.0 - axis_parallel_tolerance:
            independence = _axis_line_distance(
                primary_origin, moving_origin, primary_axis
            )
        else:
            independence = float("inf")
        if independence < minimum_primary_independence_m:
            continue

        for target in _cylinders(target_rows):
            target_id = _endpoint_id(target)
            if target_id in excluded:
                continue
            target_endpoint = target["Endpoint"]
            target_axis = _vector(
                target_endpoint["CylinderAxisWorld"], field="CylinderAxisWorld"
            )
            target_origin = _vector(
                target_endpoint["CylinderOriginWorld"], field="CylinderOriginWorld"
            )
            assert target_axis is not None and target_origin is not None
            parallel = _parallel_score(moving_axis, target_axis)
            if parallel < 1.0 - axis_parallel_tolerance:
                continue
            line_distance = _axis_line_distance(
                moving_origin, target_origin, moving_axis
            )
            if line_distance > axis_line_tolerance_m:
                continue
            axial_gap = _axial_gap(moving_origin, target_origin, moving_axis)
            if axial_gap > maximum_axial_gap_m:
                continue
            axis_candidates.append(
                {
                    "candidateType": "secondary_axis",
                    "movingEndpointId": moving_id,
                    "targetEndpointId": target_id,
                    "movingFaceIndex": moving_endpoint.get("FaceIndexInBody"),
                    "targetFaceIndex": target_endpoint.get("FaceIndexInBody"),
                    "axisParallelScore": round(parallel, 12),
                    "axisLineDistanceMeters": round(line_distance, 12),
                    "axialGapMeters": round(axial_gap, 12),
                    "primaryIndependenceMeters": (
                        None
                        if math.isinf(independence)
                        else round(independence, 12)
                    ),
                    "axisRelationToPrimary": round(axis_relation_to_primary, 12),
                    "movingRadiusMeters": moving_endpoint.get("CylinderRadius"),
                    "targetRadiusMeters": target_endpoint.get("CylinderRadius"),
                    "recommendedMateType": "concentric",
                }
            )

    plane_candidates: list[dict[str, Any]] = []
    for moving in _planes(moving_rows):
        moving_id = _endpoint_id(moving)
        if moving_id in excluded:
            continue
        moving_endpoint = moving["Endpoint"]
        moving_normal = _vector(
            moving_endpoint["FaceNormalWorld"], field="FaceNormalWorld"
        )
        moving_center = _vector(
            moving_endpoint["FaceCenterWorld"], field="FaceCenterWorld"
        )
        assert moving_normal is not None and moving_center is not None
        # A direction plane only resolves rotation about the primary axis when
        # its normal is not parallel to that axis.
        if _parallel_score(moving_normal, primary_axis) >= 1.0 - plane_parallel_tolerance:
            continue
        for target in _planes(target_rows):
            target_id = _endpoint_id(target)
            if target_id in excluded:
                continue
            target_endpoint = target["Endpoint"]
            target_normal = _vector(
                target_endpoint["FaceNormalWorld"], field="FaceNormalWorld"
            )
            target_center = _vector(
                target_endpoint["FaceCenterWorld"], field="FaceCenterWorld"
            )
            assert target_normal is not None and target_center is not None
            parallel = _parallel_score(moving_normal, target_normal)
            if parallel < 1.0 - plane_parallel_tolerance:
                continue
            delta = _sub(target_center, moving_center)
            separation = abs(_dot(delta, _unit(moving_normal)))
            center_distance = _norm(delta)
            if separation > plane_separation_tolerance_m:
                continue
            if center_distance > maximum_plane_center_distance_m:
                continue
            plane_candidates.append(
                {
                    "candidateType": "direction_plane",
                    "movingEndpointId": moving_id,
                    "targetEndpointId": target_id,
                    "movingFaceIndex": moving_endpoint.get("FaceIndexInBody"),
                    "targetFaceIndex": target_endpoint.get("FaceIndexInBody"),
                    "normalParallelScore": round(parallel, 12),
                    "planeSeparationMeters": round(separation, 12),
                    "faceCenterDistanceMeters": round(center_distance, 12),
                    "recommendedMateType": "parallel",
                }
            )

    axis_candidates.sort(
        key=lambda row: (
            row["axisLineDistanceMeters"],
            row["axialGapMeters"],
            str(row["movingEndpointId"]),
            str(row["targetEndpointId"]),
        )
    )
    plane_candidates.sort(
        key=lambda row: (
            row["planeSeparationMeters"],
            row["faceCenterDistanceMeters"],
            str(row["movingEndpointId"]),
            str(row["targetEndpointId"]),
        )
    )

    if len(axis_candidates) == 1:
        status = "single_secondary_axis_candidate_pending_cad_validation"
        preferred = axis_candidates[0]
    elif axis_candidates:
        status = "ambiguous_secondary_axis_candidates_manual_review_required"
        preferred = None
    elif len(plane_candidates) == 1:
        status = "single_direction_plane_candidate_pending_cad_validation"
        preferred = plane_candidates[0]
    elif plane_candidates:
        status = "ambiguous_direction_plane_candidates_manual_review_required"
        preferred = None
    else:
        status = "manual_face_selection_required"
        preferred = None

    result = {
        "schemaVersion": SCHEMA,
        "status": status,
        "prototypeUse": {
            "purpose": "candidate_screening_only",
            "runtimePoseAnchorAllowed": False,
            "topLevelPoseCopiedToExecution": False,
            "leafPoseAnchorCopiedToExecution": False,
        },
        "knownInstallationBundle": {
            "primaryMovingEndpointId": primary_moving_endpoint_id,
            "primaryTargetEndpointId": primary_target_endpoint_id,
            "supportMovingEndpointId": support_moving_endpoint_id,
            "supportTargetEndpointId": support_target_endpoint_id,
            "knownResidualDof": 1,
            "missingDatumPurpose": "anti_rotation_about_primary_axis",
        },
        "thresholds": {
            "axisParallelTolerance": axis_parallel_tolerance,
            "axisLineToleranceMeters": axis_line_tolerance_m,
            "maximumAxialGapMeters": maximum_axial_gap_m,
            "minimumPrimaryIndependenceMeters": minimum_primary_independence_m,
            "planeParallelTolerance": plane_parallel_tolerance,
            "planeSeparationToleranceMeters": plane_separation_tolerance_m,
            "maximumPlaneCenterDistanceMeters": maximum_plane_center_distance_m,
        },
        "secondaryAxisCandidateCount": len(axis_candidates),
        "directionPlaneCandidateCount": len(plane_candidates),
        "secondaryAxisCandidates": axis_candidates,
        "directionPlaneCandidates": plane_candidates,
        "preferredCandidate": preferred,
        "decision": {
            "semanticPortPublished": False,
            "cadExecutionAllowed": preferred is not None,
            "manualReviewRequired": preferred is None,
            "nextAction": (
                "build-nonanchor-candidate-and-run-cad"
                if preferred is not None
                else "review-candidates-or-select-one-moving-and-one-target-face"
            ),
        },
    }
    result["discoveryDigest"] = _digest(result)
    return result

