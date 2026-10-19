"""Bounded scanner-slot discovery for one already identified support leaf.

The cross-project candidate matrix can prove that two native scanner mounts are
not interchangeable, but it cannot answer a narrower question: does the target
base already expose another, currently unregistered hole pattern on the same
static support leaf?  This module answers only that question.  It deliberately
does not search the whole assembly and never publishes a port or authorizes a
CAD insertion.
"""

from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from typing import Any

from .cross_project_slot_acquisition import SCHEMA as ACQUISITION_SCHEMA
from .cross_project_slot_acquisition import screen_slot_capture


SCHEMA = "cross-project-scanner-slot-discovery/v1"


class CrossProjectScannerSlotDiscoveryError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _one_directional_pair(
    matrix: dict[str, Any],
    *,
    source_project: str,
    source_token: str,
    target_project: str,
    target_token: str,
) -> dict[str, Any]:
    matches = [
        row
        for row in matrix.get("rows") or []
        if source_project in (row.get("sourceProjectIds") or [])
        and source_token in (row.get("sourceModuleTokens") or [])
        and target_project in (row.get("targetProjectIds") or [])
        and target_token in (row.get("targetModuleTokens") or [])
    ]
    if len(matches) != 1:
        raise CrossProjectScannerSlotDiscoveryError(
            "无法从候选矩阵唯一恢复扫描模组替换方向。"
        )
    row = matches[0]
    if row.get("primaryRole") != "Scanner":
        raise CrossProjectScannerSlotDiscoveryError("候选关系不是扫描模组关系。")
    return row


def _single_spacing(installation: dict[str, Any]) -> float:
    pairs = (
        installation.get("locatingFeatureGeometry") or {}
    ).get("pairSpacings") or []
    if len(pairs) != 1:
        raise CrossProjectScannerSlotDiscoveryError(
            "扫描安装端口必须提供唯一的双定位特征间距。"
        )
    return float(pairs[0]["distanceMeters"])


def build_scanner_slot_discovery(
    matrix: dict[str, Any],
    face_catalog: dict[str, Any],
    *,
    source_project: str,
    source_token: str,
    target_project: str,
    target_token: str,
    target_leaf_hierarchy_path: str,
    native_slot_center_local: list[float] | None = None,
    discovery_tolerance_meters: float = 0.0005,
    direct_compatibility_tolerance_meters: float = 1e-6,
) -> dict[str, Any]:
    """Find exact or near scanner locating patterns on one static target leaf.

    ``discovery_tolerance_meters`` is intentionally broad enough to expose near
    patterns for engineering review.  Direct installation uses the same tight
    nominal-spacing tolerance as the cross-project compatibility matrix.  A
    near hit therefore cannot silently become a released slot.
    """

    if matrix.get("schemaVersion") != "cross-project-module-candidate-matrix/v1":
        raise CrossProjectScannerSlotDiscoveryError("不支持的候选矩阵版本。")
    if discovery_tolerance_meters <= 0:
        raise CrossProjectScannerSlotDiscoveryError("发现容差必须大于零。")
    if direct_compatibility_tolerance_meters <= 0:
        raise CrossProjectScannerSlotDiscoveryError("直接兼容容差必须大于零。")
    if direct_compatibility_tolerance_meters > discovery_tolerance_meters:
        raise CrossProjectScannerSlotDiscoveryError(
            "直接兼容容差不能大于发现容差。"
        )

    row = _one_directional_pair(
        matrix,
        source_project=source_project,
        source_token=source_token,
        target_project=target_project,
        target_token=target_token,
    )
    selected = row.get("selectedAssessment") or {}
    source_installation = selected.get("sourceInstallation") or {}
    target_installation = selected.get("targetInstallation") or {}
    required_spacing = _single_spacing(source_installation)
    native_spacing = _single_spacing(target_installation)

    request_core = {
        "schemaVersion": ACQUISITION_SCHEMA,
        "status": "bounded_leaf_capture_complete_pending_screening",
        "intent": (
            f"在{target_project}/{target_token}原生扫描支承叶上寻找可安装"
            f"{source_project}/{source_token}的未登记扫描槽位"
        ),
        "sourceModule": {
            "projectId": source_project,
            "moduleToken": source_token,
            "moduleDefinitionId": row.get("sourceModuleDefinitionId"),
            "installationPortId": source_installation.get("modulePortId"),
        },
        "targetBase": {
            "projectId": target_project,
            "moduleToken": "base-of-native-scanner-slot",
        },
        "nativeTargetReference": {
            "projectId": target_project,
            "moduleToken": target_token,
            "moduleDefinitionId": row.get("targetModuleDefinitionId"),
            "nativeSlotPortId": target_installation.get("targetSlotPortId"),
            "nativeLocatingSpacingMeters": native_spacing,
        },
        "requiredInterface": {
            "interfaceFamily": "scanner-support-plane-plus-two-location-features",
            "locatingPairSpacingMeters": required_spacing,
            "spacingToleranceMeters": discovery_tolerance_meters,
            "spacingToleranceAuthority": "bounded-geometry-discovery-only",
            "parallelLocatingAxesRequired": True,
            "featuresMustBelongToStaticBaseStructure": True,
        },
        "targetedCapturePlan": {
            "mode": "one-static-native-scanner-support-leaf",
            "primaryLeafHierarchyPath": target_leaf_hierarchy_path,
            "wholeAssemblyBlindScanRequired": False,
        },
        "executionPolicy": {
            "cadExecutionAllowed": False,
            "semanticPortPublished": False,
            "unregisteredSlotInferred": False,
            "collisionOrBrepRequiredAtThisStage": False,
        },
    }
    request = {**request_core, "requestDigest": _digest(request_core)}
    screening = screen_slot_capture(request, face_catalog)

    endpoint_index = {
        str(row.get("EndpointId") or ""): row
        for row in face_catalog.get("Endpoints") or []
    }
    candidates = []
    for candidate in screening.get("candidates") or []:
        residual = float(candidate.get("spacingResidualMeters") or 0.0)
        locating_origins = [
            (endpoint_index.get(str(endpoint_id)) or {}).get("Endpoint", {}).get(
                "CylinderOriginLocal"
            )
            for endpoint_id in candidate.get("locatingEndpointIds") or []
        ]
        candidate_center = None
        native_displacement = None
        if len(locating_origins) == 2 and all(
            isinstance(origin, list) and len(origin) == 3
            for origin in locating_origins
        ):
            candidate_center = [
                sum(float(origin[index]) for origin in locating_origins) / 2
                for index in range(3)
            ]
            if (
                isinstance(native_slot_center_local, list)
                and len(native_slot_center_local) == 3
            ):
                native_displacement = math.dist(
                    candidate_center,
                    [float(value) for value in native_slot_center_local],
                )
        candidates.append(
            {
                **deepcopy(candidate),
                "candidateCenterLocal": candidate_center,
                "nativeSlotCenterLocal": deepcopy(native_slot_center_local),
                "nativeStationDisplacementMeters": native_displacement,
                "directCompatibilityToleranceMeters": (
                    direct_compatibility_tolerance_meters
                ),
                "directFit": residual <= direct_compatibility_tolerance_meters,
            }
        )
    direct = [candidate for candidate in candidates if candidate["directFit"]]
    near = [candidate for candidate in candidates if not candidate["directFit"]]
    direct.sort(
        key=lambda candidate: (
            candidate["nativeStationDisplacementMeters"]
            if candidate["nativeStationDisplacementMeters"] is not None
            else float("inf"),
            len(candidate.get("supportPlaneEndpointIds") or []),
            candidate.get("locatingEndpointIds") or [],
        )
    )
    selected_candidate = deepcopy(direct[0]) if direct else None
    alternate_candidates = deepcopy(direct[1:]) if direct else []
    if direct:
        status = (
            "direct_slot_candidate_selected_pending_endpoint_recovery_"
            "and_process_validation"
        )
        next_action = (
            "recover-selected-endpoints-run-non-source-pose-cad-validation-"
            "then-check-optical-target"
        )
        disposition = "candidate_direct_slot_requires_validation"
    elif near:
        status = "near_geometry_found_but_direct_installation_incompatible"
        next_action = "design-adapter-or-author-new-target-hole-pattern"
        disposition = "adapter_or_new_hole_pattern_required"
    else:
        status = "no_direct_slot_on_native_scanner_support_leaf"
        next_action = "design-adapter-or-select-another-bounded-static-support-leaf"
        disposition = "adapter_or_additional_bounded_capture_required"

    core = {
        "schemaVersion": SCHEMA,
        "status": status,
        "sourceMatrixDigest": matrix.get("matrixDigest"),
        "sourceRelation": {
            "sourceProjectId": source_project,
            "sourceModuleToken": source_token,
            "targetProjectId": target_project,
            "nativeTargetModuleToken": target_token,
            "matrixStatus": row.get("status"),
            "matrixBlockers": deepcopy(row.get("blockers") or []),
        },
        "requiredLocatingSpacingMeters": required_spacing,
        "nativeTargetLocatingSpacingMeters": native_spacing,
        "captureScope": {
            "targetLeafHierarchyPath": target_leaf_hierarchy_path,
            "wholeAssemblyBlindScanPerformed": False,
            "catalogEndpointCount": screening.get("catalogEndpointCount"),
            "planarEndpointCount": screening.get("planarEndpointCount"),
            "cylindricalEndpointCount": screening.get("cylindricalEndpointCount"),
        },
        "tolerances": {
            "discoveryToleranceMeters": discovery_tolerance_meters,
            "directCompatibilityToleranceMeters": (
                direct_compatibility_tolerance_meters
            ),
            "meaning": (
                "发现容差只用于暴露近似孔列；只有直接兼容容差内的名义孔距"
                "才允许进入端点恢复和配合验证。"
            ),
        },
        "candidateCount": len(candidates),
        "directCandidateCount": len(direct),
        "nearCandidateCount": len(near),
        "candidates": candidates,
        "selectionRule": {
            "primary": "minimum_displacement_from_native_scanner_station",
            "secondary": "fewest_compatible_support_planes_then_endpoint_id",
            "authority": "prototype-native-slot-local-geometry",
            "doesNotProveOpticalCompatibility": True,
        },
        "selectedCandidate": selected_candidate,
        "alternateDirectCandidates": alternate_candidates,
        "engineeringDisposition": {
            "code": disposition,
            "directCombinationAllowed": False,
            "cadInsertionAllowed": False,
            "semanticPortPublished": False,
            "nextAction": next_action,
            "project06Included": False,
        },
        "limitations": [
            "只扫描原生扫描槽位所在的一个静止支承叶，不代表整个基座不存在其他孔系。",
            "近似孔距不能用于创建两个精确同心配合。",
            "机械孔列命中不等于扫描光轴、工作距离或条码目标区已经兼容。",
            "本阶段不执行碰撞或B-rep，也不虚构转接件。",
        ],
    }
    return {**core, "discoveryDigest": _digest(core)}
