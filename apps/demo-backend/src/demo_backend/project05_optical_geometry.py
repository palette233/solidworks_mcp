"""Extract coarse Project05 optical evidence from complete module leaf captures.

The CAD contains explicit F000 coloured beam solids and an M000 subtree named
as a CCD assembly.  These features are strong enough to establish coarse axis
directions and occupancy, but they do not authoritatively identify barcode
faces, the camera sensor plane, or calibrated working origins.
"""

from __future__ import annotations

from itertools import product
from typing import Any, Iterable


def _box(body: dict[str, Any]) -> list[float]:
    value = body.get("BoundingBoxWorld", body.get("boundingBoxWorld"))
    if not isinstance(value, list) or len(value) != 6:
        raise ValueError("Captured optical body is missing a six-value world AABB")
    return [float(item) for item in value]


def _path(body: dict[str, Any]) -> str:
    component = body.get("Component", body.get("component", {})) or {}
    return str(component.get("HierarchyPath", component.get("hierarchyPath", "")))


def _matching_bodies(capture: dict[str, Any], token: str) -> list[dict[str, Any]]:
    rows = [body for body in capture.get("bodies") or [] if token.casefold() in _path(body).casefold()]
    if not rows:
        raise ValueError(f"Required optical CAD leaf {token!r} was not captured")
    return rows


def _union(rows: Iterable[dict[str, Any]]) -> list[float]:
    boxes = [_box(row) for row in rows]
    return [min(box[index] for box in boxes) for index in range(3)] + [
        max(box[index + 3] for box in boxes) for index in range(3)
    ]


def _center(box: list[float]) -> list[float]:
    return [(box[index] + box[index + 3]) / 2.0 for index in range(3)]


def _dot(first: Iterable[float], second: Iterable[float]) -> float:
    return sum(float(a) * float(b) for a, b in zip(first, second))


def _sub(first: Iterable[float], second: Iterable[float]) -> list[float]:
    return [float(a) - float(b) for a, b in zip(first, second)]


def _add_scaled(origin: Iterable[float], axis: Iterable[float], distance: float) -> list[float]:
    return [float(value) + float(direction) * distance for value, direction in zip(origin, axis)]


def _installation_point(point: Iterable[float], frame: dict[str, Any]) -> dict[str, float]:
    relative = _sub(point, frame["originWorldMeters"])
    return {
        "u": _dot(relative, frame["flowAxisWorld"]),
        "v": _dot(relative, frame["transverseAxisWorld"]),
        "normal": _dot(relative, frame["upAxisWorld"]),
    }


def _axis_segment(box: list[float], frame: dict[str, Any]) -> dict[str, Any]:
    extents = [box[index + 3] - box[index] for index in range(3)]
    axis_index = max(range(3), key=extents.__getitem__)
    direction = [0.0, 0.0, 0.0]
    direction[axis_index] = 1.0
    center = _center(box)
    first = list(center)
    second = list(center)
    first[axis_index] = box[axis_index]
    second[axis_index] = box[axis_index + 3]
    return {
        "worldAabbMeters": box,
        "axisWorldUnsigned": direction,
        "lengthMeters": extents[axis_index],
        "endpointWorldMeters": [first, second],
        "endpointInstallationMeters": [
            _installation_point(first, frame),
            _installation_point(second, frame),
        ],
        "directionSignConfirmed": False,
    }


def _frame_point(frame: dict[str, Any], u: float, v: float, normal: float) -> list[float]:
    result = [float(value) for value in frame["originWorldMeters"]]
    for axis, scale in (
        (frame["flowAxisWorld"], u),
        (frame["transverseAxisWorld"], v),
        (frame["upAxisWorld"], normal),
    ):
        result = _add_scaled(result, axis, scale)
    return result


def _dominant_installation_axis(segment: dict[str, Any]) -> str:
    first, second = segment["endpointInstallationMeters"]
    deltas = {key: abs(float(second[key]) - float(first[key])) for key in ("u", "v", "normal")}
    return max(deltas, key=deltas.__getitem__)


def _toward_work_face_proxy(box: list[float], frame: dict[str, Any]) -> list[float]:
    points = [
        [x, y, z]
        for x, y, z in product(
            (box[0], box[3]), (box[1], box[4]), (box[2], box[5])
        )
    ]
    projected = [_installation_point(point, frame) for point in points]
    min_normal = min(item["normal"] for item in projected)
    mid_u = (min(item["u"] for item in projected) + max(item["u"] for item in projected)) / 2.0
    mid_v = (min(item["v"] for item in projected) + max(item["v"] for item in projected)) / 2.0
    return _frame_point(frame, mid_u, mid_v, min_normal)


def build_project05_optical_geometry(
    f000_capture: dict[str, Any],
    m000_capture: dict[str, Any],
    first_stage_geometry: dict[str, Any],
    work_positions: dict[str, Any],
) -> dict[str, Any]:
    if not f000_capture.get("coverageComplete"):
        raise ValueError("Project05 F000 world capture is incomplete")
    if not m000_capture.get("coverageComplete"):
        raise ValueError("Project05 M000 world capture is incomplete")
    frame = first_stage_geometry["installationFrame"]

    scan_beams = []
    for beam_id, part_token in (
        ("f000-explicit-beam-a", "FL5C251093F110002.01"),
        ("f000-explicit-beam-b", "FL5C251093F100003.01"),
    ):
        rows = _matching_bodies(f000_capture, part_token)
        scan_beams.append({
            "beamId": beam_id,
            "sourcePartToken": part_token,
            "sourceHierarchyPaths": sorted({_path(row) for row in rows}),
            **_axis_segment(_union(rows), frame),
            "roleCandidates": ["carrier-barcode", "four-product-barcodes"],
            "roleConfirmed": False,
        })

    by_axis = {_dominant_installation_axis(item): item for item in scan_beams}
    if "u" not in by_axis or "v" not in by_axis:
        raise ValueError("Project05 F000 explicit beams do not establish two independent plan axes")
    u_beam = by_axis["u"]
    v_beam = by_axis["v"]
    u_cross = sum(point["u"] for point in v_beam["endpointInstallationMeters"]) / 2.0
    v_cross = sum(point["v"] for point in u_beam["endpointInstallationMeters"]) / 2.0
    beams_by_height = sorted(
        scan_beams,
        key=lambda item: sum(point["normal"] for point in item["endpointInstallationMeters"]) / 2.0,
    )
    carrier_beam, product_beam = beams_by_height[0], beams_by_height[-1]
    carrier_normal = sum(point["normal"] for point in carrier_beam["endpointInstallationMeters"]) / 2.0
    product_normal = sum(point["normal"] for point in product_beam["endpointInstallationMeters"]) / 2.0
    transport_lane_v = sum(
        float((item.get("installationFramePointMeters") or {})["v"])
        for item in work_positions.get("workPositions") or []
    ) / len(work_positions.get("workPositions") or [])
    scanner_side = "+v/operator-side" if v_cross >= transport_lane_v else "-v/opposite-side"
    scan_station = {
        "planCenterInstallationMeters": {"u": u_cross, "v": v_cross},
        "carrierBarcodeTargetProxyInstallationMeters": {
            "u": u_cross, "v": v_cross, "normal": carrier_normal,
        },
        "productBarcodeTargetProxyInstallationMeters": {
            "u": u_cross, "v": v_cross, "normal": product_normal,
        },
        "carrierBeamId": carrier_beam["beamId"],
        "productBeamId": product_beam["beamId"],
        "roleMethod": "lower explicit beam assigned to carrier barcode; upper explicit beam assigned to header/product barcodes",
        "roleEngineeringConfirmed": False,
        "scannerSideRelativeToTransport": scanner_side,
        "transportLaneV": transport_lane_v,
        "coarseLayoutUsable": True,
    }

    camera_rows = _matching_bodies(m000_capture, "FL802AD-00111")
    optical_stack_rows = _matching_bodies(m000_capture, "FL801AA-00089")
    camera_box = _union(camera_rows)
    optical_stack_box = _union(optical_stack_rows)
    axis = [-float(value) for value in frame["upAxisWorld"]]
    camera_face = _toward_work_face_proxy(camera_box, frame)
    light_face = _toward_work_face_proxy(optical_stack_box, frame)
    camera_nominal_target = _add_scaled(camera_face, axis, 0.110)
    light_nominal_target = _add_scaled(light_face, axis, 0.020)
    positions = work_positions.get("workPositions") or []
    work_normals = [
        float((item.get("installationFramePointMeters") or {}).get("normal"))
        for item in positions
        if (item.get("installationFramePointMeters") or {}).get("normal") is not None
    ]
    camera_target_frame = _installation_point(camera_nominal_target, frame)
    light_target_frame = _installation_point(light_nominal_target, frame)
    ccd_work_targets = []
    for index, item in enumerate(positions, start=1):
        target = item["installationFramePointMeters"]
        origin_frame = {
            "u": float(target["u"]),
            "v": float(target["v"]),
            "normal": float(target["normal"]) + 0.110,
        }
        ccd_work_targets.append({
            "id": str(item.get("stableId") or f"work-position-{index}"),
            "targetInstallationMeters": {
                "u": float(target["u"]),
                "v": float(target["v"]),
                "normal": float(target["normal"]),
            },
            "requiredOpticalOriginInstallationMeters": origin_frame,
            "requiredOpticalOriginWorldMeters": _frame_point(
                frame, origin_frame["u"], origin_frame["v"], origin_frame["normal"]
            ),
        })
    two_position_coverage = len(ccd_work_targets) == 2

    return {
        "schemaVersion": "project05-optical-geometry/v1",
        "projectId": "project05",
        "status": "PROJECT05_OPTICAL_AXES_CAPTURED_PRECISE_TARGETS_PENDING",
        "engineeringConfirmed": False,
        "scanner": {
            "moduleToken": "F000",
            "captureCoverageComplete": True,
            "explicitBeamCount": len(scan_beams),
            "beams": scan_beams,
            "scanStation": scan_station,
            "axisGeometryCoarseLayoutUsable": True,
            "workingDistanceConfirmed": False,
            "barcodeTargetFacesConfirmed": False,
            "remainingBlockers": [
                "map beam A/B to carrier versus product barcode roles",
                "register carrier and four product barcode faces",
                "confirm SR-X100 usable distance and trigger positions",
            ],
        },
        "ccd": {
            "moduleToken": "M000",
            "captureCoverageComplete": True,
            "cameraBodySourcePartToken": "FL802AD-00111",
            "opticalStackSourcePartToken": "FL801AA-00089",
            "axisWorld": axis,
            "axisMethod": "camera/lens stack is collinear with negative installation up axis",
            "cameraFaceProxyWorldMeters": camera_face,
            "cameraNominalTargetWorldMeters": camera_nominal_target,
            "cameraNominalTargetInstallationMeters": camera_target_frame,
            "lightFaceProxyWorldMeters": light_face,
            "lightNominalTargetWorldMeters": light_nominal_target,
            "lightNominalTargetInstallationMeters": light_target_frame,
            "nominalCameraWorkingDistanceMeters": 0.110,
            "nominalLightWorkingDistanceMeters": 0.020,
            "fieldOfViewMeters": [0.019, 0.01425],
            "workPositionNormalCoordinatesMeters": work_normals,
            "workPositionOpticalTargets": ccd_work_targets,
            "twoWorkPositionCoverageCoarseLayoutUsable": two_position_coverage,
            "axisGeometryCoarseLayoutUsable": True,
            "preciseOpticalOriginConfirmed": False,
            "remainingBlockers": [
                "replace housing-face proxy with authored sensor/lens reference",
                "register product reference sidewall at both work positions",
                "validate camera and light target planes against the moving M000 state",
            ],
        },
        "releaseDecision": {
            "coarseOpticalOrientationMayBeUsed": True,
            "coarseScanStationMayBeUsed": True,
            "coarseCcdTwoPositionCoverageMayBeUsed": two_position_coverage,
            "preciseOpticalConstraintMayBeUsed": False,
            "top3GateContribution": "coarse-available-production-partial",
        },
        "limitations": [
            "F000 beam direction signs and scanner roles are not uniquely encoded by body AABBs.",
            "M000 working points use housing/optical-stack face proxies, not authored optical datums.",
            "No barcode face or product sidewall face has been registered yet.",
        ],
    }
