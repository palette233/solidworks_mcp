from __future__ import annotations

import math
from typing import Any


def _center(bounds: list[float]) -> list[float]:
    return [(float(bounds[index]) + float(bounds[index + 3])) / 2.0 for index in range(3)]


def _dot(first: list[float], second: list[float]) -> float:
    return sum(first[index] * second[index] for index in range(3))


def _frame_point(point: list[float], interface: dict[str, Any]) -> dict[str, float]:
    origin = [float(value) for value in interface["originWorldMeters"]]
    offset = [point[index] - origin[index] for index in range(3)]
    return {
        "u": _dot(offset, interface["flowAxisWorld"]),
        "v": _dot(offset, interface["transverseAxisWorld"]),
        "normal": _dot(offset, interface["upAxisWorld"]),
    }


def _distance(first: list[float], second: list[float]) -> float:
    return math.sqrt(sum((first[index] - second[index]) ** 2 for index in range(3)))


def infer_project03_scanner_geometry(
    leaf_capture: dict[str, Any], first_stage_geometry: dict[str, Any]
) -> dict[str, Any]:
    captures = leaf_capture.get("captures") or []
    capture = next(
        (
            item
            for item in captures
            if "AI00" in str((item.get("TopLevelComponent") or {}).get("Name", "")).upper()
        ),
        None,
    )
    if capture is None or not capture.get("CoverageComplete"):
        raise ValueError("Project03 AI00 leaf-body capture is absent or incomplete")

    bodies = capture.get("Bodies") or []
    scanner_bodies = [
        item
        for item in bodies
        if "FL209AG-00072" in str((item.get("Component") or {}).get("Name", "")).upper()
    ]
    if len(scanner_bodies) != 2:
        raise ValueError(f"Expected one two-body FL209AG-00072 scanner; found {len(scanner_bodies)} bodies")

    def dimensions(item: dict[str, Any]) -> list[float]:
        bounds = [float(value) for value in item["BoundingBoxWorld"]]
        return [bounds[index + 3] - bounds[index] for index in range(3)]

    scanner_bodies.sort(key=lambda item: max(dimensions(item)) / max(min(dimensions(item)), 1e-9), reverse=True)
    beam = scanner_bodies[0]
    housing = scanner_bodies[1]
    beam_bounds = [float(value) for value in beam["BoundingBoxWorld"]]
    beam_dimensions = dimensions(beam)
    dominant_axis = max(range(3), key=lambda index: beam_dimensions[index])
    beam_center = _center(beam_bounds)
    endpoints = []
    for bound_index in (dominant_axis, dominant_axis + 3):
        endpoint = list(beam_center)
        endpoint[dominant_axis] = beam_bounds[bound_index]
        endpoints.append(endpoint)
    housing_center = _center([float(value) for value in housing["BoundingBoxWorld"]])
    endpoints.sort(key=lambda point: _distance(point, housing_center))
    optical_origin = endpoints[0]
    target_proxy = endpoints[1]
    working_distance = _distance(optical_origin, target_proxy)
    optical_direction = [
        (target_proxy[index] - optical_origin[index]) / working_distance for index in range(3)
    ]

    line_module_bodies = [
        item
        for item in bodies
        if "FL412AI-00411" in str((item.get("Component") or {}).get("Name", "")).upper()
    ]
    line_bounds = [
        min(float(item["BoundingBoxWorld"][index]) for item in line_module_bodies)
        for index in range(3)
    ] + [
        max(float(item["BoundingBoxWorld"][index]) for item in line_module_bodies)
        for index in range(3, 6)
    ]
    line_dimensions = [line_bounds[index + 3] - line_bounds[index] for index in range(3)]
    line_axis_index = max(range(3), key=lambda index: line_dimensions[index])
    motion_axis = [0.0, 0.0, 0.0]
    motion_axis[line_axis_index] = 1.0

    identity_bodies = [
        item
        for item in bodies
        if "FL201AQ-00046" in str((item.get("Component") or {}).get("Name", "")).upper()
    ]
    if len(identity_bodies) != 1:
        raise ValueError(f"Expected one FL201AQ-00046 carrier identity head; found {len(identity_bodies)}")
    identity_bounds = [float(value) for value in identity_bodies[0]["BoundingBoxWorld"]]
    identity_dimensions = [identity_bounds[index + 3] - identity_bounds[index] for index in range(3)]
    identity_normal_axis = min(range(3), key=lambda index: identity_dimensions[index])
    identity_normal = [0.0, 0.0, 0.0]
    identity_normal[identity_normal_axis] = 1.0
    identity_center = _center(identity_bounds)

    interface = first_stage_geometry["transportInstallationInterface"]
    return {
        "schemaVersion": "project03-scanner-geometry/v1",
        "projectId": "project03",
        "status": "PROJECT03_SCANNER_GEOMETRY_PARTIALLY_INFERRED",
        "authority": "project03-explicit-cad-beam-plus-03-ppt-slide-16",
        "coarseLayoutUsable": True,
        "engineeringConfirmed": False,
        "scannerModel": "KEYENCE SR-X100",
        "scannerCount": 1,
        "processSummary": "1个显式SR-X100上扫产品条码；相邻载具身份/RFID候选头角色待确认",
        "scanners": [
            {
                "role": "productBarcodeScanner",
                "componentName": (beam.get("Component") or {}).get("Name"),
                "partFileName": "24D063电气-FL209AG-00072.SLDPRT",
                "beamBodyIndex": beam.get("BodyIndex"),
                "beamWorldBoundsMeters": beam_bounds,
                "opticalOriginWorldMeters": optical_origin,
                "opticalDirectionWorld": optical_direction,
                "targetProxyWorldMeters": target_proxy,
                "targetProxyInstallationFrameMeters": _frame_point(target_proxy, interface),
                "modeledWorkingDistanceMeters": working_distance,
                "barcodeFaceNormalWorld": [-value for value in optical_direction],
                "motionAxisWorldUnsigned": motion_axis,
                "sequenceCount": 4,
                "confidence": "high",
            }
        ],
        "carrierIdentityDevice": {
            "role": "carrierIdentityRfidOrProximityHead",
            "componentName": (identity_bodies[0].get("Component") or {}).get("Name"),
            "partFileName": "24D063电气-FL201AQ-00046.SLDPRT",
            "worldCenterMeters": identity_center,
            "installationFramePointMeters": _frame_point(identity_center, interface),
            "thinAxisNormalWorldUnsigned": identity_normal,
            "confidence": "medium",
        },
        "barcodeInterfaces": {
            "productBarcode": {
                "status": "available",
                "side": "top-facing barcode read from below along +worldY",
                "faceNormalWorld": [-value for value in optical_direction],
            },
            "carrierBarcode": {
                "status": "partial",
                "reason": "PPT image labels a carrier barcode scanner, but current AI00 CAD exposes only one SR-X100 plus a separate thin identity head; no second optical beam is present.",
            },
        },
        "captureCoverage": {
            "leafComponentCount": capture.get("LeafComponentCount"),
            "bodyCount": capture.get("BodyCount"),
            "failedBodyCount": capture.get("FailedBodyCount"),
            "coverageComplete": capture.get("CoverageComplete"),
        },
        "evidence": [
            "03-PPT slide 16 specifies KEYENCE SR-X100 and simultaneous RFID/barcode reading at the buffer position.",
            "AI00 CAD contains one FL209AG-00072 with an explicit 100 mm beam body aligned with +worldY.",
            "The FL412AI-00411 line-module long axis aligns with the Project03 transport axis, supporting sequential product scanning.",
            "A separate FL201AQ-00046 thin head is colocated near the scan zone and is retained as a medium-confidence carrier identity proxy.",
        ],
        "interpretationLimits": [
            "The 100 mm beam is a Project03 CAD modeling baseline, not a vendor-certified SR-X100 working-distance range.",
            "The product target is the beam endpoint proxy, not a persistently named printed barcode face.",
            "The CAD/PPT discrepancy about a second carrier barcode reader remains open; carrier barcode side cannot be marked fully available.",
            "The line-module axis is treated as unsigned; PLC scan stops and travel endpoints are not yet extracted.",
        ],
    }
