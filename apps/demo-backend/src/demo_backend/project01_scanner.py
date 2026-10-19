from __future__ import annotations

import math
from typing import Any


SCANNER_PART = "FL209AG-00072.SLDPRT"
DETECTION_SENSOR_PART = "FL201AB-00043.SLDPRT"


def _dot(first: list[float], second: list[float]) -> float:
    return sum(first[index] * second[index] for index in range(3))


def _center(bounds: list[float]) -> list[float]:
    return [(bounds[index] + bounds[index + 3]) / 2.0 for index in range(3)]


def _normalize(vector: list[float]) -> list[float]:
    length = math.sqrt(sum(value * value for value in vector))
    if length <= 1e-12:
        raise ValueError("Cannot normalize a zero vector")
    return [value / length for value in vector]


def _installation_frame_point(
    point: list[float], interface: dict[str, Any]
) -> dict[str, float]:
    origin = [float(value) for value in interface["originWorldMeters"]]
    offset = [point[index] - origin[index] for index in range(3)]
    return {
        "u": _dot(offset, [float(value) for value in interface["flowAxisWorld"]]),
        "v": _dot(offset, [float(value) for value in interface["transverseAxisWorld"]]),
        "normal": _dot(offset, [float(value) for value in interface["upAxisWorld"]]),
    }


def _beam_from_scanner_bodies(bodies: list[dict[str, Any]]) -> dict[str, Any]:
    ranked = []
    for body in bodies:
        bounds = [float(value) for value in body["BoundingBoxWorld"]]
        spans = [bounds[index + 3] - bounds[index] for index in range(3)]
        major_axis = max(range(3), key=lambda index: spans[index])
        ordered = sorted(spans, reverse=True)
        aspect = ordered[0] / max(ordered[1], 1e-12)
        ranked.append((aspect, ordered[0], major_axis, body, bounds))
    aspect, length, major_axis, beam_body, beam_bounds = max(ranked, key=lambda item: (item[0], item[1]))
    if aspect < 8.0 or length < 0.05:
        raise ValueError("Scanner instance has no explicit elongated CAD beam body")

    scanner_bodies = [item[3] for item in ranked if item[3] is not beam_body]
    if not scanner_bodies:
        raise ValueError("Scanner instance contains a beam but no reader body")
    scanner_centers = [_center([float(value) for value in body["BoundingBoxWorld"]]) for body in scanner_bodies]
    reader_center = [
        sum(center[index] for center in scanner_centers) / len(scanner_centers)
        for index in range(3)
    ]
    low = beam_bounds[major_axis]
    high = beam_bounds[major_axis + 3]
    near = low if abs(reader_center[major_axis] - low) <= abs(reader_center[major_axis] - high) else high
    far = high if near == low else low
    origin = _center(beam_bounds)
    target = list(origin)
    origin[major_axis] = near
    target[major_axis] = far
    direction = [0.0, 0.0, 0.0]
    direction[major_axis] = 1.0 if far > near else -1.0
    return {
        "beamBodyIndex": beam_body.get("BodyIndex"),
        "beamWorldBoundsMeters": beam_bounds,
        "beamAspectRatio": aspect,
        "opticalOriginWorldMeters": origin,
        "opticalDirectionWorld": direction,
        "targetProxyWorldMeters": target,
        "modeledWorkingDistanceMeters": abs(far - near),
    }


def infer_project01_scanner_geometry(
    leaf_capture: dict[str, Any], first_stage_geometry: dict[str, Any]
) -> dict[str, Any]:
    captures = leaf_capture.get("captures") or []
    capture = next(
        (
            item
            for item in captures
            if "SM00" in str((item.get("TopLevelComponent") or {}).get("Name", "")).upper()
        ),
        None,
    )
    if capture is None or not capture.get("CoverageComplete"):
        raise ValueError("SM00 leaf-body capture is absent or incomplete")

    interface = first_stage_geometry["transportInstallationInterface"]
    flow = _normalize([float(value) for value in interface["flowAxisWorld"]])
    transverse = _normalize([float(value) for value in interface["transverseAxisWorld"]])
    up = _normalize([float(value) for value in interface["upAxisWorld"]])
    grouped: dict[str, list[dict[str, Any]]] = {}
    detection_sensor_instances: set[str] = set()
    for body in capture.get("Bodies") or []:
        component = body.get("Component") or {}
        path = str(component.get("Path") or "").upper()
        name = str(component.get("Name") or "")
        if path.endswith(SCANNER_PART):
            grouped.setdefault(name, []).append(body)
        elif path.endswith(DETECTION_SENSOR_PART):
            detection_sensor_instances.add(name)
    if len(grouped) != 2:
        raise ValueError(f"Expected exactly two {SCANNER_PART} instances; found {len(grouped)}")

    scanners = []
    for component_name, bodies in grouped.items():
        scanner = _beam_from_scanner_bodies(bodies)
        direction = scanner["opticalDirectionWorld"]
        up_alignment = _dot(direction, up)
        transverse_alignment = _dot(direction, transverse)
        if up_alignment > 0.9:
            role = "productBarcodeScanner"
            scanner["motionAxisWorld"] = flow
            scanner["processBehavior"] = "moves along the line module to scan four product barcodes in sequence"
        elif transverse_alignment > 0.9:
            role = "carrierBarcodeScanner"
            scanner["barcodeFaceNormalWorld"] = [-value for value in direction]
            scanner["processBehavior"] = "fixed side scanner reads the carrier barcode at the buffer station"
        else:
            raise ValueError(
                f"Scanner beam does not align with Project01 up/transverse axes: {direction}"
            )
        scanner.update(
            {
                "role": role,
                "componentName": component_name,
                "partFileName": SCANNER_PART,
                "targetProxyInstallationFrameMeters": _installation_frame_point(
                    scanner["targetProxyWorldMeters"], interface
                ),
                "confidence": "high",
            }
        )
        scanners.append(scanner)
    scanners.sort(key=lambda item: item["role"])
    by_role = {item["role"]: item for item in scanners}
    carrier = by_role["carrierBarcodeScanner"]
    product = by_role["productBarcodeScanner"]
    station_spacing = math.dist(
        carrier["targetProxyWorldMeters"], product["targetProxyWorldMeters"]
    )

    return {
        "schemaVersion": "project01-scanner-geometry/v1",
        "projectId": "project01",
        "status": "PROJECT01_SCANNER_GEOMETRY_INFERRED",
        "authority": "prototype-explicit-optical-beam-and-ppt-baseline-project01-only",
        "coarseLayoutUsable": True,
        "engineeringConfirmed": False,
        "scannerModel": "KEYENCE SR-X100",
        "scannerCount": len(scanners),
        "scanners": scanners,
        "carrierBarcodeInterface": {
            "targetProxyWorldMeters": carrier["targetProxyWorldMeters"],
            "targetProxyInstallationFrameMeters": carrier[
                "targetProxyInstallationFrameMeters"
            ],
            "barcodeFaceNormalWorld": carrier["barcodeFaceNormalWorld"],
            "barcodeSide": "+transverse side of the buffer carrier",
        },
        "productScanInterface": {
            "targetProxyWorldMeters": product["targetProxyWorldMeters"],
            "targetProxyInstallationFrameMeters": product[
                "targetProxyInstallationFrameMeters"
            ],
            "motionAxisWorld": product["motionAxisWorld"],
            "sequenceCount": 4,
        },
        "sharedBufferStationTargetSpacingMeters": station_spacing,
        "nonBarcodeDetectionSensor": {
            "partFileName": DETECTION_SENSOR_PART,
            "componentInstances": sorted(detection_sensor_instances),
            "role": "carrierMissingProductDetection",
        },
        "captureCoverage": {
            "leafComponentCount": capture.get("LeafComponentCount"),
            "bodyCount": capture.get("BodyCount"),
            "failedBodyCount": capture.get("FailedBodyCount"),
            "coverageComplete": capture.get("CoverageComplete"),
        },
        "evidence": [
            "Project01 PPT slide 17 identifies two KEYENCE SR-X100 readers: carrier and product barcode scanners.",
            "Each FL209AG-00072 CAD instance contains an explicit 200 mm red beam body.",
            "The side beam aligns with +transverse; the moving product beam aligns with +up and its line module aligns with flow.",
        ],
        "interpretationLimits": [
            "The 200 mm value is the prototype CAD beam length, not a vendor-certified SR-X100 working-distance limit.",
            "Beam endpoints are coarse barcode target proxies; the actual printed barcode face remains a semantic surface on the carrier/product.",
            "The product reader travel endpoints are not yet extracted; only its motion axis and four-scan sequence are established.",
        ],
    }
