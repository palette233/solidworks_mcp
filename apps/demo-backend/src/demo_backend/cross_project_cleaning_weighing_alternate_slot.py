"""Discover 204 mm cleaning/weighing slots on the bounded Project03 base leaf."""

from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from typing import Any

from .cross_project_slot_acquisition import SCHEMA as REQUEST_SCHEMA
from .cross_project_slot_acquisition import screen_slot_capture


SCHEMA = "cross-project-cleaning-weighing-alternate-slot-discovery/v1"


class CrossProjectCleaningWeighingAlternateSlotError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _endpoint_index(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("EndpointId") or ""): row
        for row in catalog.get("Endpoints") or []
    }


def _origin(index: dict[str, dict[str, Any]], endpoint_id: str) -> list[float]:
    row = index.get(endpoint_id) or {}
    values = (row.get("Endpoint") or {}).get("CylinderOriginLocal")
    if not isinstance(values, list) or len(values) != 3:
        raise CrossProjectCleaningWeighingAlternateSlotError(
            f"endpoint has no local cylinder origin: {endpoint_id}"
        )
    return [float(value) for value in values]


def _center(first: list[float], second: list[float]) -> list[float]:
    return [(a + b) / 2.0 for a, b in zip(first, second, strict=True)]


def build_cleaning_weighing_alternate_slot_discovery(
    *,
    route_report: dict[str, Any],
    target_leaf_catalog: dict[str, Any],
    native_primary_target_endpoint_id: str,
    native_secondary_target_endpoint_id: str,
    discovery_tolerance_meters: float = 0.0005,
    direct_tolerance_meters: float = 1e-6,
) -> dict[str, Any]:
    if route_report.get("schemaVersion") != (
        "cross-project-cleaning-weighing-installation-route/v1"
    ):
        raise CrossProjectCleaningWeighingAlternateSlotError(
            "unsupported route report"
        )
    if route_report.get("status") != "alternate_slot_required_spacing_mismatch":
        raise CrossProjectCleaningWeighingAlternateSlotError(
            "route is not awaiting alternate slot discovery"
        )
    leaf_paths = sorted(
        {
            str((row.get("Endpoint") or {}).get("RelativeLeafHierarchyPath") or "")
            for row in target_leaf_catalog.get("Endpoints") or []
            if str((row.get("Endpoint") or {}).get("RelativeLeafHierarchyPath") or "")
        }
    )
    if len(leaf_paths) != 1:
        raise CrossProjectCleaningWeighingAlternateSlotError(
            "target catalog must be bounded to one leaf"
        )
    required_spacing = float(
        (route_report.get("source") or {}).get("locatingFeatureSpacingMeters")
        or 0.0
    )
    request_core = {
        "schemaVersion": REQUEST_SCHEMA,
        "status": "bounded_leaf_capture_complete_pending_screening",
        "intent": "在Project03 AA00静止承载叶寻找Project01 GN00的204 mm备用槽位",
        "requiredInterface": {
            "interfaceFamily": "cleaning-weighing-support-plane-plus-two-location-features",
            "locatingPairSpacingMeters": required_spacing,
            "spacingToleranceMeters": discovery_tolerance_meters,
            "parallelLocatingAxesRequired": True,
            "featuresMustBelongToStaticBaseStructure": True,
        },
        "targetedCapturePlan": {
            "mode": "one-static-native-service-support-leaf",
            "primaryLeafHierarchyPath": leaf_paths[0],
            "wholeAssemblyBlindScanRequired": False,
        },
        "executionPolicy": {
            "cadExecutionAllowed": False,
            "semanticPortPublished": False,
            "collisionOrBrepRequiredAtThisStage": False,
        },
    }
    request = {**request_core, "requestDigest": _digest(request_core)}
    screening = screen_slot_capture(request, target_leaf_catalog)
    index = _endpoint_index(target_leaf_catalog)
    native_center = _center(
        _origin(index, native_primary_target_endpoint_id),
        _origin(index, native_secondary_target_endpoint_id),
    )
    candidates = []
    for row in screening.get("candidates") or []:
        locating_ids = list(row.get("locatingEndpointIds") or [])
        if len(locating_ids) != 2:
            continue
        center = _center(
            _origin(index, locating_ids[0]), _origin(index, locating_ids[1])
        )
        residual = float(row.get("spacingResidualMeters") or 0.0)
        candidates.append(
            {
                **deepcopy(row),
                "candidateCenterLocalMeters": center,
                "nativeAg00SlotCenterLocalMeters": native_center,
                "distanceFromNativeAg00SlotMeters": round(
                    math.dist(center, native_center), 12
                ),
                "directSpacingFit": residual <= direct_tolerance_meters,
                "mechanicalMeaningConfirmed": False,
            }
        )
    candidates.sort(
        key=lambda row: (
            not row["directSpacingFit"],
            row["distanceFromNativeAg00SlotMeters"],
            row["locatingEndpointIds"],
        )
    )
    exact = [row for row in candidates if row["directSpacingFit"]]
    preferred = deepcopy(exact[0]) if exact else None
    status = (
        "alternate_slot_geometry_found_pending_mechanical_review"
        if exact
        else "no_204mm_slot_on_bounded_project03_service_leaf"
    )
    core = {
        "schemaVersion": SCHEMA,
        "status": status,
        "role": "CleaningWeighing",
        "routeId": route_report.get("routeId"),
        "sourceProjectId": "project01",
        "sourceModuleToken": "GN00",
        "targetProjectId": "project03",
        "targetBaseToken": "AA00",
        "nativeTargetModuleToken": "AG00",
        "nativeSlotCompatible": False,
        "nativeSlotBlocker": "LOCATING_FEATURE_SPACING_MISMATCH",
        "requiredSpacingMeters": required_spacing,
        "directSpacingToleranceMeters": direct_tolerance_meters,
        "captureScope": {
            "targetLeafHierarchyPath": leaf_paths[0],
            "wholeAssemblyBlindScanPerformed": False,
            "catalogEndpointCount": screening.get("catalogEndpointCount"),
            "planarEndpointCount": screening.get("planarEndpointCount"),
            "cylindricalEndpointCount": screening.get("cylindricalEndpointCount"),
        },
        "candidateCount": len(candidates),
        "exactSpacingCandidateCount": len(exact),
        "preferredForMechanicalReview": preferred,
        "candidates": candidates,
        "cadLaunchAllowed": False,
        "cadValidated": False,
        "semanticPortPublished": False,
        "mechanicalReviewRequired": [
            "确认两组10 mm孔的真实用途、螺纹/通孔属性和允许紧固方式",
            "确认候选支承面是否允许安装清洁/称重模组",
            "确认距AG00原生工位约0.55 m的位置是否属于可用服务区域",
            "确认GN00 6.5 mm圆柱定位特征与目标10 mm孔之间是否存在销、衬套或紧固件",
        ],
        "nextAction": (
            "mechanical-review-two-204mm-candidates-before-endpoint-port-authoring"
            if exact
            else "keep-incompatible-or-scan-one-other-bounded-static-leaf"
        ),
        "limitations": [
            "精确孔距只证明几何候选，不证明孔用途和紧固兼容。",
            "候选远离原生AG00工位，未验证维护空间和工艺可达性。",
            "本阶段未创建跨项目配合、未启动CAD、未执行碰撞或B-rep。",
        ],
    }
    return {**core, "discoveryDigest": _digest(core)}
