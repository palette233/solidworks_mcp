from __future__ import annotations

import math
from typing import Any


def _pick(item: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in item:
            return item[name]
    return default


def _center(bounds: list[float]) -> list[float]:
    return [(float(bounds[index]) + float(bounds[index + 3])) / 2.0 for index in range(3)]


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


def _has_suffix(token: str, suffix: str) -> bool:
    return str(token).upper().endswith(suffix.upper())


def build_project03_first_stage_geometry(
    mate_graph: dict[str, Any], top_level_poses: dict[str, Any]
) -> dict[str, Any]:
    """Recover the Project03 frame/transport coordinate and top-level topology."""

    mates = mate_graph.get("Mates") or mate_graph.get("mates") or []
    pair_mates = []
    for mate in mates:
        tokens = _pick(mate, "ModuleTokens", "moduleTokens", default=[])
        if len(tokens) == 2 and any(_has_suffix(token, "AA00") for token in tokens) and any(_has_suffix(token, "AE00") for token in tokens):
            pair_mates.append(mate)
    coincident = [mate for mate in pair_mates if _pick(mate, "MateTypeName", "mateTypeName") == "swMateCOINCIDENT"]
    concentric = [mate for mate in pair_mates if _pick(mate, "MateTypeName", "mateTypeName") == "swMateCONCENTRIC"]
    if len(coincident) != 1 or len(concentric) != 2:
        raise ValueError(f"Expected AA00-AE00 to have 1 coincident and 2 concentric mates; found {len(coincident)} and {len(concentric)}")

    plane_endpoints = _pick(coincident[0], "Endpoints", "endpoints", default=[])
    aa_plane = next(item for item in plane_endpoints if _has_suffix(_pick(item, "ModuleToken", "moduleToken", default=""), "AA00"))
    ae_plane = next(item for item in plane_endpoints if _has_suffix(_pick(item, "ModuleToken", "moduleToken", default=""), "AE00"))
    plane_center = list(_pick(aa_plane, "FaceCenterWorld", "faceCenterWorld"))
    up_axis = _normalize(list(_pick(ae_plane, "FaceNormalWorld", "faceNormalWorld")))

    holes = []
    for mate in concentric:
        endpoints = _pick(mate, "Endpoints", "endpoints", default=[])
        aa_endpoint = next(item for item in endpoints if _has_suffix(_pick(item, "ModuleToken", "moduleToken", default=""), "AA00"))
        ae_endpoint = next(item for item in endpoints if _has_suffix(_pick(item, "ModuleToken", "moduleToken", default=""), "AE00"))
        holes.append(
            {
                "mateName": _pick(mate, "MateName", "mateName"),
                "aa00FaceCenterWorldMeters": list(_pick(aa_endpoint, "FaceCenterWorld", "faceCenterWorld")),
                "ae00FaceCenterWorldMeters": list(_pick(ae_endpoint, "FaceCenterWorld", "faceCenterWorld")),
                "aa00PersistentReferenceBase64": _pick(aa_endpoint, "SourceAssemblyPersistentReferenceBase64", "sourceAssemblyPersistentReferenceBase64"),
                "ae00PersistentReferenceBase64": _pick(ae_endpoint, "SourceAssemblyPersistentReferenceBase64", "sourceAssemblyPersistentReferenceBase64"),
            }
        )
    holes.sort(key=lambda item: item["aa00FaceCenterWorldMeters"][2])
    hole_delta = [
        holes[1]["aa00FaceCenterWorldMeters"][index] - holes[0]["aa00FaceCenterWorldMeters"][index]
        for index in range(3)
    ]
    flow_axis = _normalize(hole_delta)
    transverse_axis = _normalize(_cross(up_axis, flow_axis))
    origin = [
        (holes[0]["aa00FaceCenterWorldMeters"][index] + holes[1]["aa00FaceCenterWorldMeters"][index]) / 2.0
        for index in range(3)
    ]
    dominant_up = max(range(3), key=lambda index: abs(up_axis[index]))
    origin[dominant_up] = plane_center[dominant_up]

    components = top_level_poses.get("components") or top_level_poses.get("Components") or []
    pose_by_code: dict[str, dict[str, Any]] = {}
    major_codes = [f"A{letter}00" for letter in "ABCDEFGHIJ"]
    for component in components:
        name = str(_pick(component, "Name", "name", default="")).upper()
        for code in major_codes:
            if f"D063{code}.001" in name:
                pose_by_code[code] = component
                break
    if "AA00" not in pose_by_code or "AE00" not in pose_by_code:
        raise ValueError("Top-level pose capture does not contain Project03 AA00 and AE00")

    aa_bounds = list(_pick(pose_by_code["AA00"], "BoundingBoxWorld", "boundingBoxWorld"))
    ae_bounds = list(_pick(pose_by_code["AE00"], "BoundingBoxWorld", "boundingBoxWorld"))
    transport_center = _center(ae_bounds)
    service_codes = [code for code in ("AG00", "AH00", "AJ00") if code in pose_by_code]
    service_centers = {
        code: _center(list(_pick(pose_by_code[code], "BoundingBoxWorld", "boundingBoxWorld")))
        for code in service_codes
    }
    service_centroid = [
        sum(center[index] for center in service_centers.values()) / len(service_centers)
        for index in range(3)
    ]
    side_sign = 1.0 if service_centroid[0] >= transport_center[0] else -1.0
    operation_plane_x = aa_bounds[3] if side_sign > 0 else aa_bounds[0]

    top_names = [str(_pick(item, "Name", "name", default="")) for item in components]
    major_names = [
        name
        for name in top_names
        if any(f"D063{code}.001" in name.upper() for code in major_codes)
    ]
    loose_names = [name for name in top_names if name not in major_names]
    bundle_pairs = {
        frozenset((str(_pick(bundle, "FirstModuleToken", "firstModuleToken")), str(_pick(bundle, "SecondModuleToken", "secondModuleToken"))))
        for bundle in mate_graph.get("MateBundles") or mate_graph.get("mateBundles") or []
    }

    def directly_mated(first_suffix: str, second_suffix: str) -> bool:
        return any(
            any(_has_suffix(token, first_suffix) for token in pair)
            and any(_has_suffix(token, second_suffix) for token in pair)
            for pair in bundle_pairs
        )

    return {
        "schemaVersion": "project03-first-stage-geometry/v1",
        "projectId": "project03",
        "status": "PROJECT03_FIRST_STAGE_GEOMETRY_CAPTURED",
        "sourceAssemblyPath": _pick(mate_graph, "SourceAssemblyPath", "sourceAssemblyPath"),
        "mateGraphSummary": {
            "moduleCount": _pick(mate_graph, "ModuleCount", "moduleCount"),
            "interModuleMateCount": _pick(mate_graph, "InterModuleMateCount", "interModuleMateCount"),
            "mateBundleCount": _pick(mate_graph, "MateBundleCount", "mateBundleCount"),
            "ignoredUnresolvedMateCount": _pick(mate_graph, "IgnoredUnresolvedMateCount", "ignoredUnresolvedMateCount"),
        },
        "transportInstallationInterface": {
            "evidence": "AA00-AE00 one coincident support plane plus two concentric locating holes",
            "mateNames": [_pick(mate, "MateName", "mateName") for mate in pair_mates],
            "originWorldMeters": origin,
            "flowAxisWorld": flow_axis,
            "transverseAxisWorld": transverse_axis,
            "upAxisWorld": up_axis,
            "locatingHoleSpacingMeters": math.sqrt(sum(value * value for value in hole_delta)),
            "locatingHoles": holes,
            "supportPlane": {
                "aa00FaceCenterWorldMeters": plane_center,
                "normalWorld": up_axis,
                "aa00FaceAreaSquareMeters": _pick(aa_plane, "FaceArea", "faceArea"),
                "aa00PersistentReferenceBase64": _pick(aa_plane, "SourceAssemblyPersistentReferenceBase64", "sourceAssemblyPersistentReferenceBase64"),
                "ae00PersistentReferenceBase64": _pick(ae_plane, "SourceAssemblyPersistentReferenceBase64", "sourceAssemblyPersistentReferenceBase64"),
            },
            "fullyDeterminesRigidPose": True,
            "vendorDimensionConfirmed": False,
            "authority": "prototype-mate-baseline-project03-only",
        },
        "operationSideInference": {
            "candidate": "+worldX" if side_sign > 0 else "-worldX",
            "estimatedFacePlaneWorldX": operation_plane_x,
            "exactFaceCaptured": False,
            "confidence": "medium",
            "method": "AG00/AH00/AJ00 service-cluster centroid relative to AE00 plus AA00 world AABB",
            "transportCenterWorldMeters": transport_center,
            "serviceModuleCentersWorldMeters": service_centers,
            "serviceClusterCentroidWorldMeters": service_centroid,
        },
        "topLevelOccupancy": {
            "capturedInstanceCount": len(components),
            "majorModuleCount": len(major_names),
            "looseAuxiliaryInstanceCount": len(loose_names),
            "majorModuleNames": major_names,
            "looseAuxiliaryInstanceNames": loose_names,
            "worldAabbAvailable": len(components),
            "subtreeMultiBoxAvailable": False,
            "aa00WorldBoundsMeters": aa_bounds,
            "ae00WorldBoundsMeters": ae_bounds,
        },
        "topology": {
            "allIndependentModulesDirectlyMatedToAa00": all(
                directly_mated("AA00", suffix)
                for suffix in ("AB00", "AD00", "AE00", "AF00", "AG00", "AH00", "AI00", "AJ00")
            ),
            "ac00DirectlyMatedToAb00": directly_mated("AB00", "AC00"),
            "ad00DirectlyMatedToAe00": directly_mated("AD00", "AE00"),
            "scannerDirectlyMatedToAa00": directly_mated("AA00", "AI00"),
            "proposedMovableSolveObjectCount": 7,
        },
        "remainingLimits": [
            "Operation side is inferred from the service cluster, not an engineer-selected exact AA00 face.",
            "AE00/AD00 work positions and AI00 optical targets are not yet extracted.",
            "Top-level AABBs do not replace subtree multi-box occupancy.",
            "The five loose top-level parts are context/auxiliary instances and are excluded from the module count only after explicit audit.",
        ],
    }
