#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "demo-backend" / "src"))

from demo_backend.constraint_layout import generate_constraint_layout
from demo_backend.layout_preview import build_source_independent_options
from demo_backend.project02_robustness import (
    compare_signatures,
    placement_signature,
    with_valve_reach_directional_insets,
)


REQUEST = ROOT / "demo/FL9A24D062A000_real_process_request.json"
MATE_GRAPH = ROOT / "demo/layout_previews/project02_a100_internal_mate_graph.json"
ENVELOPES = ROOT / "demo/layout_previews/project02_a100_top_level_leaf_envelopes.json"
OUTPUT = ROOT / "demo/layout_previews/project02_a100_valve_axis_inference.json"
GANTRY = "FL9A24D062A100.001-1"


def aggregate_box(capture: dict[str, Any]) -> list[float]:
    boxes = [body["BoundingBoxWorld"] for body in capture.get("Bodies") or []]
    if not boxes:
        raise ValueError(f"No bodies captured for {capture.get('TopLevelComponent')}")
    return [
        min(box[0] for box in boxes), min(box[1] for box in boxes), min(box[2] for box in boxes),
        max(box[3] for box in boxes), max(box[4] for box in boxes), max(box[5] for box in boxes),
    ]


def extent(box: list[float], axis: int) -> float:
    return float(box[axis + 3]) - float(box[axis])


def solve(capture: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    return generate_constraint_layout(capture, build_source_independent_options(request, ROOT))


def run_scenario(
    capture: dict[str, Any],
    request: dict[str, Any],
    baseline_signature: dict[str, tuple[float, float, float, float]],
    scenario_id: str,
    inset_u: float,
    inset_v: float,
    joint_candidate_limit: int | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        changed = with_valve_reach_directional_insets(request, inset_u, inset_v)
        if joint_candidate_limit is not None:
            changed["sourceIndependentPolicy"]["jointCandidateLimit"] = joint_candidate_limit
            changed["sourceIndependentPolicy"]["jointSearchTimeLimitSeconds"] = 180
        common = changed["moduleSemantics"][GANTRY]["regions"]["dualValveReach"]
        generated = solve(capture, changed)
        signature = placement_signature(generated)
        comparison = compare_signatures(baseline_signature, signature) if signature else None
        validation = generated.get("constraintPlan", {}).get("combinedValidation") or {}
        return {
            "id": scenario_id,
            "insetUMetersPerSide": inset_u,
            "insetVMetersPerSide": inset_v,
            "jointCandidateLimit": joint_candidate_limit or request["sourceIndependentPolicy"]["jointCandidateLimit"],
            "commonReachLocalMeters": common,
            "commonWidthUMeters": common["maxU"] - common["minU"],
            "commonWidthVMeters": common["maxV"] - common["minV"],
            "feasible": bool(generated.get("success")) and bool(signature),
            "layoutComparison": comparison,
            "replayRequiredIfApplied": bool(signature) and not bool((comparison or {}).get("equivalent")),
            "hardFailureCount": len(validation.get("hardFailures") or []),
            "elapsedSeconds": time.perf_counter() - started,
        }
    except Exception as exc:
        return {
            "id": scenario_id,
            "insetUMetersPerSide": inset_u,
            "insetVMetersPerSide": inset_v,
            "jointCandidateLimit": joint_candidate_limit or request["sourceIndependentPolicy"]["jointCandidateLimit"],
            "feasible": False,
            "layoutComparison": None,
            "replayRequiredIfApplied": False,
            "error": f"{type(exc).__name__}: {exc}",
            "elapsedSeconds": time.perf_counter() - started,
        }


def main() -> int:
    request = json.loads(REQUEST.read_text(encoding="utf-8-sig"))
    graph = json.loads(MATE_GRAPH.read_text(encoding="utf-8-sig"))
    envelopes = json.loads(ENVELOPES.read_text(encoding="utf-8-sig"))
    capture_by_name = {
        item["TopLevelComponent"]["Name"]: item for item in envelopes["captures"]
    }
    boxes = {name: aggregate_box(item) for name, item in capture_by_name.items()}

    bridge = boxes["FL9A24D062A120.001-1"]
    head = boxes["FL9A24D062A110.001-1"]
    side_a = boxes["FL9A24D062A150.001-1"]
    side_b = boxes["FL9A24D062A160.001-1"]
    rail_overlap_x = min(side_a[3], side_b[3]) - max(side_a[0], side_b[0])
    cross_span_z = extent(bridge, 2)
    head_span_z = extent(head, 2)
    bridge_span_x = extent(bridge, 0)
    spacing = float(request["moduleSemantics"][GANTRY]["parameters"]["estimatedValveHeadSpacingMeters"])
    named_limit = next(
        (mate for mate in graph.get("Mates") or [] if mate.get("MateName") == "LimitDistance1"),
        None,
    )

    # These are deliberately a conservative bracket, not a measured stroke:
    # whole subassembly AABBs include cable carriers, hoses and brackets.
    conservative_u = max(0.0, cross_span_z - head_span_z - spacing)
    conservative_v = max(0.0, rail_overlap_x - bridge_span_x)

    geometry_capture = json.loads(
        (ROOT / request["geometryCapturePath"]).read_text(encoding="utf-8-sig")
    )
    baseline = solve(geometry_capture, request)
    baseline_signature = placement_signature(baseline)
    baseline_common = request["moduleSemantics"][GANTRY]["regions"]["dualValveReach"]
    width_u = float(baseline_common["maxU"]) - float(baseline_common["minU"])
    width_v = float(baseline_common["maxV"]) - float(baseline_common["minV"])
    optimistic_insets = (max(0.0, (width_u - 1.04) / 2), max(0.0, (width_v - 0.86) / 2))
    balanced_insets = (max(0.0, (width_u - 1.00) / 2), max(0.0, (width_v - 0.82) / 2))
    candidate_specs = [
        ("current-10pct-envelope", 0.0, 0.0, None),
        ("geometry-optimistic", *optimistic_insets, None),
        ("geometry-balanced", *balanced_insets, None),
        ("geometry-balanced-expanded-search", *balanced_insets, 24),
        (
            "whole-moving-envelope-conservative",
            max(0.0, (width_u - conservative_u) / 2),
            max(0.0, (width_v - conservative_v) / 2),
            None,
        ),
    ]
    scenarios = [
        run_scenario(
            geometry_capture,
            request,
            baseline_signature,
            name,
            inset_u,
            inset_v,
            joint_candidate_limit,
        )
        for name, inset_u, inset_v, joint_candidate_limit in candidate_specs
    ]
    optimistic = next(item for item in scenarios if item["id"] == "geometry-optimistic")
    balanced = next(item for item in scenarios if item["id"] == "geometry-balanced")
    balanced_expanded = next(
        item for item in scenarios if item["id"] == "geometry-balanced-expanded-search"
    )

    report = {
        "schemaVersion": "project02-a100-valve-axis-inference/v1",
        "success": True,
        "status": "GEOMETRY_BRACKET_CAPTURED_EXACT_AXIS_LIMITS_PENDING",
        "projectId": "project02",
        "sourceAssembly": envelopes.get("assemblyPath"),
        "evidence": {
            "topLevelModuleCount": len(capture_by_name),
            "capturedLeafBodyCount": sum(int(item.get("BodyCount") or 0) for item in envelopes["captures"]),
            "coverageComplete": all(bool(item.get("CoverageComplete")) for item in envelopes["captures"]),
            "interModuleMateCount": graph.get("InterModuleMateCount"),
            "namedLimitDistanceMate": {
                "found": named_limit is not None,
                "name": (named_limit or {}).get("MateName"),
                "solidWorksMateType": (named_limit or {}).get("MateTypeName"),
                "currentDistanceMeters": (named_limit or {}).get("Distance"),
                "interpretation": "Current bridge position only; the exported type is an ordinary distance mate, not a proven min/max axis limit.",
            },
            "topLevelAggregateWorldBoxesMeters": boxes,
        },
        "axisMappingInference": {
            "layoutAxisU": "approximately A100 world Z / bridge cross-axis",
            "layoutAxisV": "approximately A100 world X / long side-rail axis",
            "confidence": "MEDIUM",
            "basis": "A100 local envelope dimensions match the captured world-Z and world-X structural spans respectively.",
        },
        "geometryMeasurementsMeters": {
            "crossBeamSpanWorldZ": cross_span_z,
            "valveHeadAssemblySpanWorldZ": head_span_z,
            "estimatedValveHeadSpacing": spacing,
            "sideRailCommonSpanWorldX": rail_overlap_x,
            "movingBridgeAssemblySpanWorldX": bridge_span_x,
        },
        "wholeMovingEnvelopeConservativeCommonReachMeters": {
            "widthU": conservative_u,
            "widthV": conservative_v,
            "interpretation": "Conservative bracket only; whole subassembly AABBs are larger than the actual slider footprints.",
        },
        "solverSensitivity": scenarios,
        "diagnosis": {
            "currentModelMayBeOptimistic": True,
            "optimisticGeometryCandidateFeasible": bool(optimistic.get("feasible")),
            "optimisticGeometryCandidateChangesLayout": bool(optimistic.get("replayRequiredIfApplied")),
            "optimisticMaximumPoseShiftMeters": (optimistic.get("layoutComparison") or {}).get("maxXyErrorMeters"),
            "balancedGeometryCandidateFeasible": bool(balanced.get("feasible")),
            "balancedExpandedSearchFeasible": bool(balanced_expanded.get("feasible")),
            "expandedSearchCandidateLimit": balanced_expanded.get("jointCandidateLimit"),
            "blockingModule": "FL9A24D062A300.001-1",
            "blockingClass": "PROCESS_DOMAIN_CONFLICT",
            "interpretation": "Doubling the retained joint candidates did not recover the balanced geometry case; the next improvement should target A300/A700 service-cluster process domains or obtain authoritative axis limits, not merely increase search time.",
        },
        "decision": {
            "applyToProductionRequest": False,
            "reason": "No authoritative min/max mate or vendor stroke was found. Geometry candidates are for coarse sensitivity only.",
            "recommendedNextInput": "Record each axis at its two mechanical/software limits, or supply vendor stroke and valve-tip offsets in the A100 local frame.",
            "replayNow": False,
            "replayRule": "Replay only after a selected reach remains feasible and changes the rank-1 rigid placement.",
        },
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"success": True, "output": str(OUTPUT), "scenarios": scenarios}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
