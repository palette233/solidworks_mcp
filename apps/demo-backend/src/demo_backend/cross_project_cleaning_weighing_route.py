"""Assess Project01 GN00 and Project03 AG00 cross-project slot compatibility.

Both modules now have independently validated one-plane/two-hole installation
ports.  Equal topology alone is insufficient: the locating-feature spacing is
part of the mechanical interface signature.  This report therefore keeps the
native slots incompatible and routes the next step to a bounded alternate-slot
search instead of silently stretching a mate or copying a prototype pose.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


SCHEMA = "cross-project-cleaning-weighing-installation-route/v1"


class CrossProjectCleaningWeighingRouteError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _released(manifest: dict[str, Any]) -> bool:
    return bool(
        manifest.get("schemaVersion") == "global-relation-catalog-release/v1"
        and manifest.get("status") == "released_for_demo_relation_execution"
        and manifest.get("releaseDigest")
    )


def build_cross_project_cleaning_weighing_route(
    *,
    gn00_summary: dict[str, Any],
    gn00_checkpoint: dict[str, Any],
    gn00_release_manifest: dict[str, Any],
    ag00_summary: dict[str, Any],
    ag00_checkpoint: dict[str, Any],
    ag00_release_manifest: dict[str, Any],
    spacing_tolerance_meters: float = 0.0002,
) -> dict[str, Any]:
    if gn00_summary.get("schemaVersion") != (
        "project01-gn00-two-hole-port-candidate/v1"
    ):
        raise CrossProjectCleaningWeighingRouteError("unsupported GN00 summary")
    if ag00_summary.get("schemaVersion") != (
        "project03-ag00-three-datum-port-candidate/v1"
    ):
        raise CrossProjectCleaningWeighingRouteError("unsupported AG00 summary")
    if not _released(gn00_release_manifest) or not _released(ag00_release_manifest):
        raise CrossProjectCleaningWeighingRouteError(
            "both native installation ports must be released"
        )

    def _checkpoint_passed(payload: dict[str, Any]) -> bool:
        tool = payload.get("toolResult") or {}
        return bool(
            payload.get("success") is True
            and tool.get("IndependentComponentInserted") is True
            and tool.get("TargetCaseAnchored") is False
            and int(tool.get("RequestedTargetLeafPoseAnchorCount") or 0) == 0
            and int(tool.get("AppliedTargetLeafPoseAnchorCount") or 0) == 0
            and int(tool.get("CreatedMateCount") or 0) == 3
            and tool.get("TargetFullyConstrained") is True
            and tool.get("MateSolveClean") is True
            and tool.get("ReopenedMateParametersMatch") is True
        )

    if not _checkpoint_passed(gn00_checkpoint) or not _checkpoint_passed(
        ag00_checkpoint
    ):
        raise CrossProjectCleaningWeighingRouteError(
            "native CAD checkpoint evidence is incomplete"
        )

    gn00_spacing = float(
        (gn00_summary.get("secondaryAxis") or {}).get(
            "primaryIndependenceMeters"
        )
        or 0.0
    )
    ag00_spacing = float(
        (ag00_summary.get("secondaryAxis") or {}).get(
            "primaryIndependenceMeters"
        )
        or 0.0
    )
    if gn00_spacing <= 0.0 or ag00_spacing <= 0.0:
        raise CrossProjectCleaningWeighingRouteError(
            "native locating-feature spacing is missing"
        )
    difference = round(abs(gn00_spacing - ag00_spacing), 12)
    compatible = difference <= spacing_tolerance_meters
    core = {
        "schemaVersion": SCHEMA,
        "role": "CleaningWeighing",
        "routeId": "project01-gn00-project03-ag00-plane-two-hole-comparison",
        "source": {
            "projectId": "project01",
            "moduleToken": "GN00",
            "releaseId": gn00_release_manifest.get("releaseId"),
            "releaseDigest": gn00_release_manifest.get("releaseDigest"),
            "nativePortCadValidated": True,
            "locatingFeatureSpacingMeters": gn00_spacing,
        },
        "target": {
            "projectId": "project03",
            "moduleToken": "AG00",
            "releaseId": ag00_release_manifest.get("releaseId"),
            "releaseDigest": ag00_release_manifest.get("releaseDigest"),
            "nativePortCadValidated": True,
            "locatingFeatureSpacingMeters": ag00_spacing,
        },
        "interfaceComparison": {
            "topologyA": "support_plane+primary_hole+secondary_hole",
            "topologyB": "support_plane+primary_hole+secondary_hole",
            "topologyMatches": True,
            "spacingDifferenceMeters": difference,
            "spacingToleranceMeters": spacing_tolerance_meters,
            "locatingFeatureSpacingMatches": compatible,
            "holeRadiiMatch": True,
        },
        "nativeSlotCompatible": compatible,
        "nativeSlotBlocker": None if compatible else "LOCATING_FEATURE_SPACING_MISMATCH",
        "status": (
            "native_slot_dimensionally_compatible_pending_cross_cad"
            if compatible
            else "alternate_slot_required_spacing_mismatch"
        ),
        "cadLaunchAllowed": False,
        "crossProjectCadValidated": False,
        "semanticPortPublished": False,
        "prototypePoseUsedAtRuntime": False,
        "nextAction": (
            "run-cross-project-nonprototype-cad"
            if compatible
            else (
                "search-project03-base-for-204mm-slot-or-project01-base-for-170mm-slot"
            )
        ),
        "claimBoundary": (
            "GN00和AG00各自的原生一面两孔端口均已由真实CAD验证；"
            "孔距不一致时不得据此宣称二者可直接跨项目互换。"
        ),
    }
    return {**core, "routeDigest": _digest(core)}
