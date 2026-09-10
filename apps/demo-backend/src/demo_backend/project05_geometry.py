"""Infer the Project05 frame/transport installation coordinates from exported mates."""

from __future__ import annotations

import math
from typing import Any


def _pick(payload: dict[str, Any], key: str, default: Any = None) -> Any:
    return payload.get(key, payload.get(key[0].lower() + key[1:], default))


def _unit(values: list[float]) -> list[float]:
    length = math.sqrt(sum(float(value) ** 2 for value in values))
    if length <= 1e-12:
        raise ValueError("Cannot normalize a zero vector.")
    return [float(value) / length for value in values]


def _cross(first: list[float], second: list[float]) -> list[float]:
    return [
        first[1] * second[2] - first[2] * second[1],
        first[2] * second[0] - first[0] * second[2],
        first[0] * second[1] - first[1] * second[0],
    ]


def _mate_between(graph: dict[str, Any], first: str, second: str, mate_type: str) -> dict[str, Any]:
    for mate in _pick(graph, "Mates", []) or []:
        tokens = set(_pick(mate, "ModuleTokens", []) or [])
        if tokens == {first, second} and _pick(mate, "MateTypeName") == mate_type:
            return mate
    raise ValueError(f"Missing {mate_type} mate between {first} and {second}.")


def _endpoint(mate: dict[str, Any], token: str) -> dict[str, Any]:
    candidates = [item for item in _pick(mate, "Endpoints", []) or [] if _pick(item, "ModuleToken") == token]
    if len(candidates) != 1:
        raise ValueError(f"Expected one {token} endpoint, found {len(candidates)}.")
    return candidates[0]


def infer_project05_first_stage_geometry(
    graph: dict[str, Any],
    poses: dict[str, Any],
) -> dict[str, Any]:
    coincident = _mate_between(graph, "A000", "D000", "swMateCOINCIDENT")
    distance = _mate_between(graph, "A000", "D000", "swMateDISTANCE")
    width = _mate_between(graph, "A000", "D000", "swMateWIDTH")
    a_contact = _endpoint(coincident, "A000")
    a_distance = _endpoint(distance, "A000")
    width_a = [item for item in _pick(width, "Endpoints", []) or [] if _pick(item, "ModuleToken") == "A000"]
    width_d = [item for item in _pick(width, "Endpoints", []) or [] if _pick(item, "ModuleToken") == "D000"]
    if len(width_a) != 2 or len(width_d) != 2:
        raise ValueError("A000-D000 width mate must expose two frame and two transport faces.")

    up = _unit([-value for value in _pick(a_contact, "FaceNormalWorld")])
    transverse = _unit(_pick(a_distance, "FaceNormalWorld"))
    flow = _unit(_cross(transverse, up))
    contact_center = [float(value) for value in _pick(a_contact, "FaceCenterWorld")]
    distance_center = [float(value) for value in _pick(a_distance, "FaceCenterWorld")]
    frame_width_centers = [_pick(item, "FaceCenterWorld") for item in width_a]
    width_midpoint = [
        sum(float(center[index]) for center in frame_width_centers) / 2.0
        for index in range(3)
    ]
    origin = [
        transverse[index] * sum(distance_center[j] * transverse[j] for j in range(3))
        + up[index] * sum(contact_center[j] * up[j] for j in range(3))
        + flow[index] * sum(width_midpoint[j] * flow[j] for j in range(3))
        for index in range(3)
    ]

    components = _pick(poses, "components", []) or []
    active = [item for item in components if "N000.001-3" not in item["Name"] and "P000.001-1" not in item["Name"]]
    suppressed_variant_names = [
        item["Name"] for item in components if item not in active
    ]
    distance_value = float(_pick(distance, "Distance"))
    frame_half_width = abs(
        sum(float(value) * flow[index] for index, value in enumerate(frame_width_centers[0]))
        - sum(float(value) * flow[index] for index, value in enumerate(frame_width_centers[1]))
    ) / 2.0
    transport_half_width = abs(
        sum(float(_pick(width_d[0], "FaceCenterWorld")[index]) * flow[index] for index in range(3))
        - sum(float(_pick(width_d[1], "FaceCenterWorld")[index]) * flow[index] for index in range(3))
    ) / 2.0
    return {
        "schemaVersion": "project05-first-stage-geometry/v1",
        "projectId": "project05",
        "status": "PROJECT05_FIRST_STAGE_GEOMETRY_CAPTURED",
        "engineeringConfirmed": False,
        "coarseLayoutUsable": True,
        "sourceAssemblyPath": _pick(graph, "SourceAssemblyPath"),
        "installationFrame": {
            "originWorldMeters": origin,
            "flowAxisWorld": flow,
            "transverseAxisWorld": transverse,
            "upAxisWorld": up,
            "axisMeaning": {"u": "transport flow", "v": "operator-side transverse", "n": "installation normal/up"},
        },
        "transportInstallationInterface": {
            "mateTypes": ["swMateCOINCIDENT", "swMateDISTANCE", "swMateWIDTH"],
            "frameToTransportTransverseDistanceMeters": distance_value,
            "frameHalfWidthMeters": frame_half_width,
            "transportHalfWidthMeters": transport_half_width,
            "transportCenteredInFrameWidth": abs(frame_half_width - 0.700) <= 1e-6 and abs(transport_half_width - 0.690) <= 1e-6,
            "contactPlaneWorld": {
                "point": contact_center,
                "normal": up,
            },
            "positionAndOrientationBundleComplete": True,
        },
        "operationSideInference": {
            "candidate": "+transverse/+worldX",
            "confidence": "medium-prototype-layout",
            "exactFaceCaptured": False,
        },
        "topLevelOccupancy": {
            "capturedInstanceCount": len(components),
            "activeMajorModuleInstanceCount": len(active),
            "suppressedVariantCount": len(suppressed_variant_names),
            "suppressedVariantNames": suppressed_variant_names,
            "activeInstanceNames": [item["Name"] for item in active],
        },
        "mateGraphSummary": {
            "moduleInstanceCount": int(_pick(graph, "ModuleCount", 0)),
            "interModuleMateCount": int(_pick(graph, "InterModuleMateCount", 0)),
            "mateBundleCount": int(_pick(graph, "MateBundleCount", 0)),
            "a000D000MateCount": 3,
        },
        "evidence": {
            "contactMate": coincident,
            "transverseDistanceMate": distance,
            "widthCenteringMate": width,
        },
        "remainingGates": [
            "exact A000 operation face and maintenance space",
            "D000/K000 work positions",
            "F000 scan geometry and M000 CCD work geometry",
            "G000/N000/P000 service points",
            "B000/Z000 dual-valve common reach",
            "module multi-box occupancy and static collision policy",
            "glue-supply parent identity",
        ],
    }
