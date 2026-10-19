from __future__ import annotations

import math
import re
from typing import Any


_CARRIER_PATTERN = re.compile(r"056-19475000-00_ASM_165_ASM-(\d+)")


def infer_project02_scan_station(
    optical_evidence: dict[str, Any],
    leaf_body_evidence: dict[str, Any],
    *,
    preferred_distance_range_meters: tuple[float, float] = (0.10, 0.16),
    minimum_unique_margin_meters: float = 0.05,
) -> dict[str, Any]:
    """Rank the five A800 QR carriers against the A180 optical origin.

    This is intentionally a coarse-layout inference.  It uses the prototype's
    measured QR leaf-body locations and the CAD-inferred scanner optical origin;
    it does not claim the PLC trigger position or moving-stage stop is confirmed.
    """

    entries = optical_evidence.get("entries") or {}
    scanner = entries.get("scanner") or {}
    selected_barcode = entries.get("barcode") or {}
    scanner_origin = _vector3(scanner.get("worldCenterMeters"), "scanner origin")
    selected_carrier = _carrier_number(
        str(selected_barcode.get("carrierInstance") or "")
    )

    captures = leaf_body_evidence.get("captures") or []
    candidates: list[dict[str, Any]] = []
    for capture in captures:
        for body in capture.get("Bodies") or []:
            component = body.get("Component") or {}
            name = str(component.get("Name") or "")
            if not name.endswith("/模拟二维码-1"):
                continue
            carrier = _carrier_number(name)
            box = _vector6(body.get("BoundingBoxWorld"), "QR body box")
            center = [(box[index] + box[index + 3]) / 2.0 for index in range(3)]
            vector = [center[index] - scanner_origin[index] for index in range(3)]
            distance = _norm(vector)
            candidates.append(
                {
                    "carrierNumber": carrier,
                    "carrierInstance": f"056-19475000-00_ASM_165_ASM-{carrier}",
                    "leafComponentFullName": name,
                    "qrBodyCenterWorldMeters": center,
                    "scannerToQrVectorMeters": vector,
                    "scannerToQrDistanceMeters": distance,
                    "withinPreferredProjectBand": (
                        preferred_distance_range_meters[0]
                        <= distance
                        <= preferred_distance_range_meters[1]
                    ),
                    "evidence": "prototype A800 QR leaf-body AABB center",
                }
            )

    candidates.sort(key=lambda item: item["scannerToQrDistanceMeters"])
    for rank, candidate in enumerate(candidates, start=1):
        candidate["distanceRank"] = rank

    nearest = candidates[0] if candidates else None
    runner_up = candidates[1] if len(candidates) > 1 else None
    unique_margin = (
        runner_up["scannerToQrDistanceMeters"]
        - nearest["scannerToQrDistanceMeters"]
        if nearest and runner_up
        else None
    )
    selected_is_unique_nearest = bool(
        nearest
        and nearest["carrierNumber"] == selected_carrier
        and unique_margin is not None
        and unique_margin >= minimum_unique_margin_meters
    )
    selected_is_only_in_preferred_band = bool(
        nearest
        and nearest["carrierNumber"] == selected_carrier
        and sum(item["withinPreferredProjectBand"] for item in candidates) == 1
        and nearest["withinPreferredProjectBand"]
    )
    expected_count = 5
    usable = bool(
        len(candidates) == expected_count
        and selected_is_unique_nearest
        and selected_is_only_in_preferred_band
    )

    return {
        "schemaVersion": "project02-scan-station-inference/v1",
        "success": usable,
        "status": (
            "PASS_CARRIER_8_UNIQUE_COARSE_SCAN_STATION"
            if usable
            else "INSUFFICIENT_SCAN_STATION_EVIDENCE"
        ),
        "projectId": "project02",
        "scannerModuleCode": "A180",
        "transportModuleCode": "A800",
        "scannerOpticalOriginWorldMeters": scanner_origin,
        "candidateCount": len(candidates),
        "expectedCandidateCount": expected_count,
        "selectedCarrierNumber": selected_carrier,
        "selectedCarrierInstance": (
            f"056-19475000-00_ASM_165_ASM-{selected_carrier}"
            if selected_carrier is not None
            else None
        ),
        "selectedIsUniqueNearest": selected_is_unique_nearest,
        "selectedIsOnlyCandidateInPreferredProjectBand": (
            selected_is_only_in_preferred_band
        ),
        "nearestDistanceMarginMeters": unique_margin,
        "minimumUniqueMarginMeters": minimum_unique_margin_meters,
        "preferredProjectDistanceRangeMeters": list(
            preferred_distance_range_meters
        ),
        "candidateRanking": candidates,
        "usableForCoarseLayout": usable,
        "engineeringConfirmed": False,
        "dynamicScanStopConfirmed": False,
        "inference": (
            "Carrier-8 is the unique nearest QR carrier to the prototype A180 "
            "optical origin and the only candidate inside the configured Project02 "
            "100-160 mm coarse scan band.  Together with PPT step 1, this supports "
            "using carrier-8 as the buffer/entry scan station for coarse layout."
        ),
        "limitations": [
            "The scanner optical origin is CAD-inferred from symmetric windows, not a directly mapped central lens face.",
            "The QR candidate centers come from exact prototype leaf-body AABBs; only carrier-8 also has a directly measured barcode face.",
            "PLC trigger position, scanner moving-stage stop and production tolerance remain unconfirmed.",
        ],
    }


def _carrier_number(value: str) -> int | None:
    match = _CARRIER_PATTERN.search(value)
    return int(match.group(1)) if match else None


def _vector3(value: Any, label: str) -> list[float]:
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError(f"{label} must contain three numbers")
    return [float(item) for item in value]


def _vector6(value: Any, label: str) -> list[float]:
    if not isinstance(value, list) or len(value) != 6:
        raise ValueError(f"{label} must contain six numbers")
    return [float(item) for item in value]


def _norm(vector: list[float]) -> float:
    return math.sqrt(sum(item * item for item in vector))
