from __future__ import annotations

from copy import deepcopy
from typing import Any


TRANSPORT_NAME = "FL9A24D062A800.001-1"


def build_project02_dynamic_scan_window(
    request: dict[str, Any],
    scan_station_inference: dict[str, Any],
    optical_evidence: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Add a conservative, explicitly provisional carrier-stop window.

    The current CAD proves which carrier is at the scan station but contains no
    PLC tolerance.  For coarse layout we therefore bound longitudinal stop
    error by half of the measured QR width.  This is a geometry-derived estimate,
    not a controls or production acceptance value.
    """

    if not (
        scan_station_inference.get("success") is True
        and scan_station_inference.get("usableForCoarseLayout") is True
        and scan_station_inference.get("selectedCarrierInstance")
        == "056-19475000-00_ASM_165_ASM-8"
    ):
        raise ValueError("Carrier-8 scan-station inference is not ready")

    barcode_evidence = (optical_evidence.get("entries") or {}).get("barcode") or {}
    dimensions = barcode_evidence.get("faceDimensionsMeters")
    if not isinstance(dimensions, list) or len(dimensions) != 2:
        raise ValueError("Measured barcode face dimensions are missing")
    width = min(float(value) for value in dimensions)
    if width <= 0:
        raise ValueError("Measured barcode face dimensions must be positive")
    tolerance = width / 2.0

    updated = deepcopy(request)
    semantics = updated.get("moduleSemantics") or {}
    transport = semantics.get(TRANSPORT_NAME)
    if not isinstance(transport, dict):
        raise ValueError(f"Transport semantic is missing: {TRANSPORT_NAME}")
    points = transport.setdefault("points", {})
    barcode = points.get("barcode") or {}
    u = float(barcode["u"])
    v = float(barcode["v"])
    low_name = "barcodeStopLowU"
    high_name = "barcodeStopHighU"
    points[low_name] = {"u": u - tolerance, "v": v}
    points[high_name] = {"u": u + tolerance, "v": v}

    parameters = transport.setdefault("parameters", {})
    barcode_height = float(parameters["barcodeHeightMeters"])
    parameters.update(
        {
            "dynamicScanWindowPointNames": [low_name, high_name],
            "dynamicScanStopToleranceMeters": tolerance,
            "dynamicScanStopToleranceAxis": "transport-local-u",
            "dynamicScanStopToleranceConfirmed": False,
            "dynamicScanWindowAcceptedForCoarseLayout": True,
            f"{low_name}HeightMeters": barcode_height,
            f"{high_name}HeightMeters": barcode_height,
            "dynamicScanStopToleranceSource": (
                "coarse geometry estimate: half of the directly measured 10 mm "
                "QR face width; replace with PLC/fixture tolerance"
            ),
        }
    )

    report = {
        "schemaVersion": "project02-dynamic-scan-window/v1",
        "success": True,
        "status": "COARSE_DYNAMIC_SCAN_WINDOW_READY_ENGINEERING_CONFIRMATION_PENDING",
        "projectId": "project02",
        "scannerModuleCode": "A180",
        "transportModuleCode": "A800",
        "carrierInstance": scan_station_inference["selectedCarrierInstance"],
        "nominalBarcodePointLocalMeters": {"u": u, "v": v},
        "windowAxis": "transport-local-u",
        "estimatedStopToleranceMeters": tolerance,
        "windowEndpointsLocalMeters": {
            low_name: points[low_name],
            high_name: points[high_name],
        },
        "evidence": {
            "barcodeFaceDimensionsMeters": dimensions,
            "candidateCount": scan_station_inference.get("candidateCount"),
            "nearestDistanceMarginMeters": scan_station_inference.get(
                "nearestDistanceMarginMeters"
            ),
        },
        "usableForCoarseLayout": True,
        "engineeringConfirmed": False,
        "plcTriggerConfirmed": False,
        "dynamicStopToleranceConfirmed": False,
        "generatedConstraintPolicy": {
            "pointDistanceForBothEndpoints": True,
            "lineOfSightForBothEndpoints": True,
            "directedPointingForBothEndpoints": True,
            "hardInCurrentCoarseModel": True,
        },
        "replacementInput": (
            "Replace estimatedStopToleranceMeters with the PLC trigger/fixture stop "
            "tolerance and confirm whether the scanner or carrier moves during capture."
        ),
    }
    return updated, report
