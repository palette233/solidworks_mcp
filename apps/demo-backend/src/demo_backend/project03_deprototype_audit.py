"""Compile-time ablation for Project03 temporary residual pose parameters."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from .project03_incremental_work_packet import (
    build_project03_ab00_work_packet,
    build_project03_ag00_work_packet,
)


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _module(graph: dict[str, Any], token: str) -> dict[str, Any]:
    return next(
        item
        for item in graph.get("Modules") or []
        if str(item.get("ModuleToken") or "").upper() == token.upper()
    )


def _perturb(graph: dict[str, Any], token: str, seed: float) -> dict[str, Any]:
    result = copy.deepcopy(graph)
    _module(result, token)["SourceTransform"] = [
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
        seed,
        seed + 1.0,
        seed + 2.0,
        1.0,
        0.0,
        0.0,
        0.0,
    ]
    return result


def _compiled_transform(result: dict[str, Any], token: str) -> list[float]:
    return list(_module(result["effectiveGraph"], token)["SourceTransform"])


def build_project03_pose_anchor_ablation(
    source_graph: dict[str, Any],
    prototype_assembly: Path,
    service_points: dict[str, Any],
    valve_reach: dict[str, Any],
    calibrated_parameters: dict[str, Any],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    specifications = [
        (
            "FL9A24D063AG00",
            lambda graph, parameters: build_project03_ag00_work_packet(
                graph,
                prototype_assembly,
                service_points,
                case_anchored=True,
                calibrated_parameters=parameters,
            ),
            11.0,
        ),
        (
            "FL9A24D063AB00",
            lambda graph, parameters: build_project03_ab00_work_packet(
                graph,
                prototype_assembly,
                valve_reach,
                calibrated_parameters=parameters,
            ),
            21.0,
        ),
    ]
    for token, builder, seed in specifications:
        perturbed_graph = _perturb(source_graph, token, seed)
        captured = list(_module(source_graph, token)["SourceTransform"])
        perturbed = list(_module(perturbed_graph, token)["SourceTransform"])
        baseline = builder(source_graph, calibrated_parameters)
        changed = builder(perturbed_graph, calibrated_parameters)
        baseline_compiled = _compiled_transform(baseline, token)
        changed_compiled = _compiled_transform(changed, token)
        summary = changed["summary"]
        rows.append(
            {
                "moduleToken": token,
                "capturedSourceTransformSha256": _digest(captured),
                "perturbedSourceTransformSha256": _digest(perturbed),
                "capturedSourcePoseWasPerturbed": captured != perturbed,
                "baselineCompiledTransformSha256": _digest(baseline_compiled),
                "perturbedCompiledTransformSha256": _digest(changed_compiled),
                "compiledTransformStableUnderSourcePosePerturbation": (
                    baseline_compiled == changed_compiled
                ),
                "calibratedAnchorApplied": summary.get("calibratedAnchorApplied") is True,
                "runtimePrototypeTopLevelPoseReadRequired": summary.get(
                    "runtimePrototypeTopLevelPoseReadRequired"
                ),
            }
        )

    success = all(
        row["capturedSourcePoseWasPerturbed"]
        and row["compiledTransformStableUnderSourcePosePerturbation"]
        and row["calibratedAnchorApplied"]
        and row["runtimePrototypeTopLevelPoseReadRequired"] is False
        for row in rows
    )
    return {
        "schemaVersion": "project03-pose-anchor-ablation/v1",
        "projectId": "project03",
        "success": success,
        "status": (
            "PASSED_RUNTIME_TOP_LEVEL_POSE_DETACHMENT"
            if success
            else "FAILED_RUNTIME_TOP_LEVEL_POSE_DETACHMENT"
        ),
        "moduleCount": len(rows),
        "modules": rows,
        "productionReady": False,
        "scopeBoundary": {
            "proved": "AG00 and AB00 compiled temporary anchors no longer change when the captured prototype top-level transform is perturbed.",
            "notProved": "The calibrated values remain prototype-derived and are not vendor-authoritative installation datums.",
            "nextGate": "Run the calibrated graphs in live CAD, then replace the temporary parameters with explicit engineering datums.",
        },
    }
