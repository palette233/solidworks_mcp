"""Discover a JJ00-only orientation datum for the Project01 GN00 module.

GN00's native prototype bundle uses JJ00 for its support plane and primary
locating axis, then references an SS00 plane to remove the final rotation.
This module asks a deliberately narrower question: does the already bounded
JJ00 support-leaf catalog contain a stable plane parallel to GN00's
anti-rotation plane?

Such a plane can remove the *semantic dependency* on the transport module,
but it does not prove a physical locating feature or cross-project mechanical
compatibility.  The report therefore stays fail-closed before CAD.
"""

from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from typing import Any, Iterable


SCHEMA = "project01-gn00-base-only-orientation-datum-candidate/v1"


class Project01Gn00BaseOnlyDatumError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _vector(values: Iterable[Any]) -> list[float]:
    result = [float(value) for value in values]
    if len(result) != 3 or not all(math.isfinite(value) for value in result):
        raise Project01Gn00BaseOnlyDatumError("Expected three finite values.")
    return result


def _dot(first: Iterable[float], second: Iterable[float]) -> float:
    return sum(a * b for a, b in zip(first, second, strict=True))


def _normalize(values: Iterable[Any]) -> list[float]:
    vector = _vector(values)
    magnitude = math.sqrt(_dot(vector, vector))
    if magnitude <= 1e-12:
        raise Project01Gn00BaseOnlyDatumError("Cannot normalize zero vector.")
    return [value / magnitude for value in vector]


def _endpoint_index(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if catalog.get("SchemaVersion") != "solidworks-face-endpoint-catalog/v1":
        raise Project01Gn00BaseOnlyDatumError("Unsupported endpoint catalog.")
    return {
        str(row.get("EndpointId") or ""): row
        for row in catalog.get("Endpoints") or []
    }


def build_project01_gn00_base_only_datum_candidate(
    *,
    native_endpoint_catalog: dict[str, Any],
    jj00_support_leaf_catalog: dict[str, Any],
    gn00_anti_rotation_endpoint_id: str,
    jj00_primary_support_endpoint_id: str,
    parallel_cosine_minimum: float = 0.999999,
    independence_cosine_maximum: float = 1e-6,
    minimum_face_area_square_meters: float = 0.001,
) -> dict[str, Any]:
    """Build a read-only JJ00 orientation-datum candidate report."""

    native = _endpoint_index(native_endpoint_catalog)
    target = _endpoint_index(jj00_support_leaf_catalog)
    if gn00_anti_rotation_endpoint_id not in native:
        raise Project01Gn00BaseOnlyDatumError("GN00 anti-rotation endpoint is absent.")
    if jj00_primary_support_endpoint_id not in native:
        raise Project01Gn00BaseOnlyDatumError("JJ00 primary support endpoint is absent.")
    source_endpoint = native[gn00_anti_rotation_endpoint_id].get("Endpoint") or {}
    support_endpoint = native[jj00_primary_support_endpoint_id].get("Endpoint") or {}
    source_normal = _normalize(source_endpoint.get("FaceNormalWorld") or [])
    support_normal = _normalize(support_endpoint.get("FaceNormalWorld") or [])
    if abs(_dot(source_normal, support_normal)) > independence_cosine_maximum:
        raise Project01Gn00BaseOnlyDatumError(
            "Native anti-rotation plane is not independent of the support plane."
        )

    candidates: list[dict[str, Any]] = []
    for endpoint_id, row in target.items():
        endpoint = row.get("Endpoint") or {}
        if str(endpoint.get("ModuleToken") or "").upper() != "JJ00":
            continue
        if endpoint.get("SurfaceType") != "Plane":
            continue
        normal_values = endpoint.get("FaceNormalWorld")
        if not normal_values:
            continue
        normal = _normalize(normal_values)
        parallel_cosine = abs(_dot(source_normal, normal))
        support_independence = abs(_dot(support_normal, normal))
        area = float(endpoint.get("FaceArea") or 0.0)
        if (
            parallel_cosine < parallel_cosine_minimum
            or support_independence > independence_cosine_maximum
            or area < minimum_face_area_square_meters
        ):
            continue
        candidates.append(
            {
                "endpointId": endpoint_id,
                "leafHierarchyPath": endpoint.get("LeafHierarchyPath"),
                "relativeLeafHierarchyPath": endpoint.get(
                    "RelativeLeafHierarchyPath"
                ),
                "faceAreaSquareMeters": area,
                "faceCenterWorldMeters": deepcopy(
                    endpoint.get("FaceCenterWorld") or []
                ),
                "faceNormalWorld": normal,
                "sourceParallelCosine": parallel_cosine,
                "supportIndependenceCosine": support_independence,
                "recoveryConfidence": row.get("RecoveryConfidence"),
                "alignment": (
                    "aligned" if _dot(source_normal, normal) >= 0.0 else "anti_aligned"
                ),
            }
        )
    candidates.sort(
        key=lambda row: (
            -row["faceAreaSquareMeters"],
            0 if row["alignment"] == "aligned" else 1,
            row["endpointId"],
        )
    )
    selected = deepcopy(candidates[0]) if candidates else None
    status = (
        "base_only_orientation_datum_candidate_pending_mechanical_meaning_and_cad"
        if selected
        else "blocked_no_jj00_orientation_datum_candidate"
    )
    core = {
        "schemaVersion": SCHEMA,
        "status": status,
        "projectId": "project01",
        "moduleToken": "GN00",
        "nativeArchitecture": {
            "primaryProviderModuleToken": "JJ00",
            "antiRotationProviderModuleToken": "SS00",
            "primaryMateTopology": ["coincident_support_plane", "concentric_axis"],
            "completionMateTopology": ["parallel_anti_rotation_plane"],
            "expectedResidualDofBeforeAntiRotation": 1,
        },
        "proposedArchitecture": {
            "providerModuleTokens": ["JJ00"],
            "mateTopology": [
                "coincident_support_plane",
                "concentric_axis",
                "parallel_orientation_datum",
            ],
            "semanticTransportDependencyRemoved": selected is not None,
            "physicalAntiRotationFeatureProven": False,
        },
        "boundedSearch": {
            "targetModuleToken": "JJ00",
            "targetLeafScope": sorted(
                {
                    str((row.get("Endpoint") or {}).get("RelativeLeafHierarchyPath") or "")
                    for row in target.values()
                    if str((row.get("Endpoint") or {}).get("ModuleToken") or "").upper()
                    == "JJ00"
                }
            ),
            "wholeAssemblyBlindScanPerformed": False,
            "parallelCosineMinimum": parallel_cosine_minimum,
            "supportIndependenceCosineMaximum": independence_cosine_maximum,
            "minimumFaceAreaSquareMeters": minimum_face_area_square_meters,
        },
        "candidateCount": len(candidates),
        "selectedCandidate": selected,
        "candidates": candidates,
        "comparisonToProject03Ag00": {
            "gn00CandidateTopology": "support_plane+primary_hole+orientation_plane",
            "ag00ReleasedTopology": "support_plane+primary_hole+secondary_hole",
            "providerArchitectureNowComparable": selected is not None,
            "directMechanicalTopologyCompatible": False,
            "remainingBlockers": [
                "MATE_TOPOLOGY_MISMATCH",
                "PHYSICAL_ANTI_ROTATION_MEANING_UNCONFIRMED",
                "LOCATING_FEATURE_GEOMETRY_NOT_COMPARABLE",
            ],
        },
        "candidatePoseSolved": False,
        "cadLaunchAllowed": False,
        "semanticPortPublished": False,
        "directCrossProjectCompatibilityProven": False,
        "collisionOrBrepRequired": False,
        "nextAction": (
            "confirm-jj00-plane-is-valid-orientation-datum-then-run-base-only-gn00-cad"
            if selected
            else "capture-bounded-jj00-orientation-datum-or-second-locating-feature"
        ),
        "limitations": [
            "平行基准只消除方向自由度，不证明该JJ00面与GN00形成物理接触或紧固。",
            "消除SS00语义依赖不等于GN00与AG00机械接口兼容。",
            "本报告不创建配合、不保存装配体，也不执行碰撞或B-rep。",
        ],
        "project06Included": False,
    }
    return {**core, "candidateDigest": _digest(core)}
