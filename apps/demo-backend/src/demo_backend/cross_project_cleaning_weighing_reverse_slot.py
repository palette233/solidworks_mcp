"""Screen the bounded Project01 base leaf for the Project03 AG00 spacing."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .cross_project_slot_acquisition import SCHEMA as REQUEST_SCHEMA
from .cross_project_slot_acquisition import screen_slot_capture


SCHEMA = "cross-project-cleaning-weighing-reverse-slot-discovery/v1"


class CrossProjectCleaningWeighingReverseSlotError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _request(*, leaf_path: str, spacing: float, tolerance: float) -> dict[str, Any]:
    core = {
        "schemaVersion": REQUEST_SCHEMA,
        "status": "bounded_leaf_capture_complete_pending_screening",
        "requiredInterface": {
            "interfaceFamily": (
                "cleaning-weighing-support-plane-plus-two-location-features"
            ),
            "locatingPairSpacingMeters": spacing,
            "spacingToleranceMeters": tolerance,
            "parallelLocatingAxesRequired": True,
            "featuresMustBelongToStaticBaseStructure": True,
        },
        "targetedCapturePlan": {
            "mode": "one-static-native-service-support-leaf",
            "primaryLeafHierarchyPath": leaf_path,
            "wholeAssemblyBlindScanRequired": False,
        },
    }
    return {**core, "requestDigest": _digest(core)}


def build_cleaning_weighing_reverse_slot_discovery(
    *,
    target_leaf_catalog: dict[str, Any],
    required_spacing_meters: float = 0.17,
    engineering_tolerance_meters: float = 0.0002,
    exploratory_tolerance_meters: float = 0.0005,
) -> dict[str, Any]:
    leaf_paths = sorted(
        {
            str((row.get("Endpoint") or {}).get("RelativeLeafHierarchyPath") or "")
            for row in target_leaf_catalog.get("Endpoints") or []
            if str((row.get("Endpoint") or {}).get("RelativeLeafHierarchyPath") or "")
        }
    )
    if len(leaf_paths) != 1:
        raise CrossProjectCleaningWeighingReverseSlotError(
            "target catalog must be bounded to one leaf"
        )
    if exploratory_tolerance_meters <= engineering_tolerance_meters:
        raise CrossProjectCleaningWeighingReverseSlotError(
            "exploratory tolerance must exceed engineering tolerance"
        )

    strict = screen_slot_capture(
        _request(
            leaf_path=leaf_paths[0],
            spacing=required_spacing_meters,
            tolerance=engineering_tolerance_meters,
        ),
        target_leaf_catalog,
    )
    exploratory = screen_slot_capture(
        _request(
            leaf_path=leaf_paths[0],
            spacing=required_spacing_meters,
            tolerance=exploratory_tolerance_meters,
        ),
        target_leaf_catalog,
    )
    near_matches = list(exploratory.get("candidates") or [])
    status = (
        "strict_slot_found_pending_mechanical_review"
        if strict.get("candidateCount")
        else "no_strict_slot_relaxed_near_match_rejected"
        if near_matches
        else "no_170mm_slot_on_bounded_project01_service_leaf"
    )
    core = {
        "schemaVersion": SCHEMA,
        "status": status,
        "role": "CleaningWeighing",
        "sourceProjectId": "project03",
        "sourceModuleToken": "AG00",
        "targetProjectId": "project01",
        "targetBaseToken": "JJ00",
        "requiredSpacingMeters": required_spacing_meters,
        "engineeringToleranceMeters": engineering_tolerance_meters,
        "exploratoryToleranceMeters": exploratory_tolerance_meters,
        "captureScope": {
            "targetLeafHierarchyPath": leaf_paths[0],
            "wholeAssemblyBlindScanPerformed": False,
            "catalogEndpointCount": strict.get("catalogEndpointCount"),
            "planarEndpointCount": strict.get("planarEndpointCount"),
            "cylindricalEndpointCount": strict.get("cylindricalEndpointCount"),
        },
        "strictCandidateCount": int(strict.get("candidateCount") or 0),
        "strictCandidates": list(strict.get("candidates") or []),
        "relaxedNearMatchCount": len(near_matches),
        "relaxedNearMatches": near_matches,
        "toleranceRelaxationAccepted": False,
        "cadLaunchAllowed": False,
        "cadValidated": False,
        "semanticPortPublished": False,
        "nextAction": (
            "prefer-project03-aa00-204mm-candidates-for-mechanical-review"
            if not strict.get("candidateCount")
            else "mechanical-review-before-port-authoring"
        ),
        "limitations": [
            "探索容差只用于识别近似孔对，不能覆盖工程容差。",
            "本结果只覆盖一个已登记静止基座叶，不代表整个JJ00不存在其他槽位。",
            "本阶段未创建跨项目配合、未启动CAD、未执行碰撞或B-rep。",
        ],
    }
    return {**core, "discoveryDigest": _digest(core)}
