from __future__ import annotations

import math
from typing import Any


def _pick(item: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in item:
            return item[name]
    return default


def _center(bounds: list[float]) -> list[float]:
    return [(bounds[index] + bounds[index + 3]) / 2.0 for index in range(3)]


def _normalize(vector: list[float]) -> list[float]:
    length = math.sqrt(sum(value * value for value in vector))
    if length <= 1e-12:
        raise ValueError("Cannot normalize a zero vector")
    return [value / length for value in vector]


def _cross(first: list[float], second: list[float]) -> list[float]:
    return [
        first[1] * second[2] - first[2] * second[1],
        first[2] * second[0] - first[0] * second[2],
        first[0] * second[1] - first[1] * second[0],
    ]


def build_project01_first_stage_geometry(
    mate_graph: dict[str, Any], top_level_poses: dict[str, Any]
) -> dict[str, Any]:
    mates = mate_graph.get("Mates") or mate_graph.get("mates") or []
    pair_mates = [
        mate
        for mate in mates
        if set(_pick(mate, "ModuleTokens", "moduleTokens", default=[])) == {"JJ00", "SS00"}
    ]
    coincident = [mate for mate in pair_mates if _pick(mate, "MateTypeName", "mateTypeName") == "swMateCOINCIDENT"]
    concentric = [mate for mate in pair_mates if _pick(mate, "MateTypeName", "mateTypeName") == "swMateCONCENTRIC"]
    if len(coincident) != 1 or len(concentric) != 2:
        raise ValueError(f"Expected JJ00-SS00 to have 1 coincident and 2 concentric mates; found {len(coincident)} and {len(concentric)}")

    plane_endpoints = _pick(coincident[0], "Endpoints", "endpoints", default=[])
    jj_plane = next(item for item in plane_endpoints if _pick(item, "ModuleToken", "moduleToken") == "JJ00")
    ss_plane = next(item for item in plane_endpoints if _pick(item, "ModuleToken", "moduleToken") == "SS00")
    plane_center = list(_pick(jj_plane, "FaceCenterWorld", "faceCenterWorld"))
    ss_normal = list(_pick(ss_plane, "FaceNormalWorld", "faceNormalWorld"))
    up_axis = _normalize(ss_normal)

    holes = []
    for mate in concentric:
        endpoints = _pick(mate, "Endpoints", "endpoints", default=[])
        jj_endpoint = next(item for item in endpoints if _pick(item, "ModuleToken", "moduleToken") == "JJ00")
        ss_endpoint = next(item for item in endpoints if _pick(item, "ModuleToken", "moduleToken") == "SS00")
        holes.append(
            {
                "mateName": _pick(mate, "MateName", "mateName"),
                "jj00FaceCenterWorldMeters": list(_pick(jj_endpoint, "FaceCenterWorld", "faceCenterWorld")),
                "ss00FaceCenterWorldMeters": list(_pick(ss_endpoint, "FaceCenterWorld", "faceCenterWorld")),
                "jj00PersistentReferenceBase64": _pick(jj_endpoint, "SourceAssemblyPersistentReferenceBase64", "sourceAssemblyPersistentReferenceBase64"),
                "ss00PersistentReferenceBase64": _pick(ss_endpoint, "SourceAssemblyPersistentReferenceBase64", "sourceAssemblyPersistentReferenceBase64"),
            }
        )
    holes.sort(key=lambda item: item["jj00FaceCenterWorldMeters"][2])
    hole_delta = [
        holes[1]["jj00FaceCenterWorldMeters"][index] - holes[0]["jj00FaceCenterWorldMeters"][index]
        for index in range(3)
    ]
    flow_axis = _normalize(hole_delta)
    transverse_axis = _normalize(_cross(up_axis, flow_axis))
    hole_midpoint = [
        (holes[0]["jj00FaceCenterWorldMeters"][index] + holes[1]["jj00FaceCenterWorldMeters"][index]) / 2.0
        for index in range(3)
    ]
    installation_origin = list(hole_midpoint)
    dominant_up_axis = max(range(3), key=lambda index: abs(up_axis[index]))
    installation_origin[dominant_up_axis] = plane_center[dominant_up_axis]

    components = top_level_poses.get("components") or top_level_poses.get("Components") or []
    pose_by_token: dict[str, dict[str, Any]] = {}
    for component in components:
        name = str(_pick(component, "Name", "name", default=""))
        for token in ("JJ00", "SS00", "FF00", "GN00", "BD00", "SM00", "GJ00", "LM00", "ZZ00", "HL00"):
            if token in name.upper():
                pose_by_token[token] = component
                break
    if "JJ00" not in pose_by_token or "SS00" not in pose_by_token:
        raise ValueError("Top-level pose capture does not contain JJ00 and SS00")

    jj_bounds = list(_pick(pose_by_token["JJ00"], "BoundingBoxWorld", "boundingBoxWorld"))
    ss_bounds = list(_pick(pose_by_token["SS00"], "BoundingBoxWorld", "boundingBoxWorld"))
    transport_center = _center(ss_bounds)
    service_tokens = [token for token in ("GN00", "BD00", "GJ00") if token in pose_by_token]
    service_centers = {token: _center(list(_pick(pose_by_token[token], "BoundingBoxWorld", "boundingBoxWorld"))) for token in service_tokens}
    service_centroid = [sum(center[index] for center in service_centers.values()) / len(service_centers) for index in range(3)]
    # Project01's flow axis is approximately world Z, so the operation-side comparison is made on world X.
    side_sign = 1.0 if service_centroid[0] >= transport_center[0] else -1.0
    operation_plane_x = jj_bounds[3] if side_sign > 0 else jj_bounds[0]

    return {
        "schemaVersion": "project01-first-stage-geometry/v1",
        "projectId": "project01",
        "status": "PROJECT01_FIRST_STAGE_GEOMETRY_CAPTURED",
        "sourceAssemblyPath": _pick(mate_graph, "SourceAssemblyPath", "sourceAssemblyPath"),
        "mateGraphSummary": {
            "moduleCount": _pick(mate_graph, "ModuleCount", "moduleCount"),
            "interModuleMateCount": _pick(mate_graph, "InterModuleMateCount", "interModuleMateCount"),
            "mateBundleCount": _pick(mate_graph, "MateBundleCount", "mateBundleCount"),
        },
        "transportInstallationInterface": {
            "evidence": "JJ00-SS00 one coincident plane plus two concentric locating holes",
            "mateNames": [_pick(mate, "MateName", "mateName") for mate in pair_mates],
            "originWorldMeters": installation_origin,
            "flowAxisWorld": flow_axis,
            "transverseAxisWorld": transverse_axis,
            "upAxisWorld": up_axis,
            "locatingHoleSpacingMeters": math.sqrt(sum(value * value for value in hole_delta)),
            "locatingHoles": holes,
            "supportPlane": {
                "jj00FaceCenterWorldMeters": plane_center,
                "normalWorld": up_axis,
                "jj00FaceAreaSquareMeters": _pick(jj_plane, "FaceArea", "faceArea"),
                "jj00PersistentReferenceBase64": _pick(jj_plane, "SourceAssemblyPersistentReferenceBase64", "sourceAssemblyPersistentReferenceBase64"),
                "ss00PersistentReferenceBase64": _pick(ss_plane, "SourceAssemblyPersistentReferenceBase64", "sourceAssemblyPersistentReferenceBase64"),
            },
            "fullyDeterminesRigidPose": True,
            "vendorDimensionConfirmed": False,
            "authority": "prototype-mate-baseline-project01-only",
        },
        "operationSideInference": {
            "candidate": "+worldX" if side_sign > 0 else "-worldX",
            "estimatedFacePlaneWorldX": operation_plane_x,
            "exactFaceCaptured": False,
            "confidence": "medium",
            "method": "GN00/BD00/GJ00 service-cluster centroid relative to SS00 plus JJ00 world AABB",
            "transportCenterWorldMeters": transport_center,
            "serviceModuleCentersWorldMeters": service_centers,
            "serviceClusterCentroidWorldMeters": service_centroid,
        },
        "topLevelOccupancy": {
            "componentCount": len(components),
            "worldAabbAvailable": len(components),
            "subtreeMultiBoxAvailable": False,
            "jj00WorldBoundsMeters": jj_bounds,
            "ss00WorldBoundsMeters": ss_bounds,
        },
        "topologyCorrection": {
            "ff00DirectlyMatedToSs00": False,
            "ff00DirectlyMatedToJj00": True,
            "gn00DirectlyMatedToJj00": True,
            "gn00ParallelToSs00": True,
            "proposedMovableSolveObjectCount": 7,
        },
        "remainingLimits": [
            "The operation side is inferred, not an engineer-selected exact JJ00 face.",
            "SS00/FF00 process work positions are not yet extracted.",
            "Top-level AABBs do not replace subtree multi-box occupancy.",
            "Prototype mate baselines are project01-only and are not vendor dimensions.",
        ],
    }
