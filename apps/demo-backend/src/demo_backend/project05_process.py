"""Explicit Project05 process semantics transcribed from 05-PPT."""
from __future__ import annotations

from typing import Any


def build_project05_process_semantics() -> dict[str, Any]:
    """Return PPT-authored semantics without inventing CAD coordinates."""

    return {
        "schemaVersion": "project05-process-semantics/v1",
        "projectId": "project05",
        "status": "PROJECT05_PROCESS_SEMANTICS_CAPTURED_CAD_COORDINATES_REQUIRED",
        "machine": {
            "singleMachineEnvelopeMillimeters": [1400.0, 1400.0, 1800.0],
            "upperConveyorHeightMillimeters": 940.0,
            "returnConveyorHeightMillimeters": 300.0,
            "conveyorInnerSideToOperatingSurfaceMillimeters": 312.0,
        },
        "transportProcess": {
            "bufferStationCount": 1,
            "workPositionCount": 2,
            "workPositionNames": ["working-position-1", "working-position-2"],
            "liftingAtBothWorkPositions": True,
            "passUnderRaisedCarrier": True,
            "cadCoordinatesAvailable": False,
            "coordinateAcquisition": "D000/K000 repeated station geometry",
        },
        "scanProcess": {
            "station": "buffer-position",
            "scannerBrand": "KEYENCE",
            "scannerModel": "SR-X100",
            "targets": ["carrier-barcode", "four-product-barcodes"],
            "productScanMode": "sequential-four-products",
            "carrierReaderShown": True,
            "productReaderShown": True,
            "barcodeLocationsConfirmed": False,
            "barcodeLocationLabel": "tentative",
            "opticalAxisAndDistanceAvailable": False,
        },
        "ccdProcess": {
            "servesWorkPositions": ["working-position-1", "working-position-2"],
            "motionBetweenWorkPositions": True,
            "feature": "product-reference-sidewall",
            "cameraModel": "OPT-XCC1-M050YJH",
            "pixelCount": [2592, 1944],
            "fieldOfViewMillimeters": [19.0, 14.25],
            "cameraWorkingDistanceMillimeters": {"nominal": 110.0, "tolerance": 2.0},
            "lightWorkingDistanceMillimeters": {"nominal": 20.0, "tolerance": 5.0},
            "pixelResolutionMillimetersPerPixel": 0.00733,
            "positioningAccuracyMillimeters": 0.025,
            "cadOpticalOriginAndAxisAvailable": False,
        },
        "workflow": [
            "carrier-enters-buffer-and-scans-carrier-plus-product-barcodes",
            "carrier-enters-working-position-1-and-lifts",
            "ccd-captures-product-position-at-working-position-1",
            "dispense-at-working-position-1",
            "second-carrier-scans-and-enters-working-position-2",
            "ccd-captures-product-position-at-working-position-2",
            "dispense-at-working-position-2",
            "carrier-lowers-and-flows-out",
        ],
        "evidence": [
            "05-PPT slide 7: 1400x1400x1800 mm, conveyor heights and 312 mm operating-surface offset",
            "05-PPT slide 9: buffer scan, two work positions, CCD capture and dispensing sequence",
            "05-PPT slide 13: two independent lift positions plus buffer station",
            "05-PPT slide 14: KEYENCE SR-X100 scans carrier and four product barcodes",
            "05-PPT slide 15: CCD field of view, working distances and positioning accuracy",
        ],
        "limitations": [
            "PPT barcode locations are explicitly tentative.",
            "PPT does not define scanner optical origin, axis or working distance.",
            "PPT does not provide CAD-local coordinates for buffer/work positions or CCD optical origin.",
        ],
    }
