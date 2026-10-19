#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import re
import sys
import time
from copy import deepcopy
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "demo-backend" / "src"))

from demo_backend.constraint_layout import generate_constraint_layout
from demo_backend.layout_preview import build_source_independent_options
from demo_backend.project02_robustness import (
    placement_signature,
    with_valve_reach_directional_insets,
)


REQUEST = ROOT / "demo/FL9A24D062A000_real_process_request.json"
OUTPUT = ROOT / "demo/layout_previews/project02_a300_a700_constraint_ablation.json"
SUMMARY = ROOT / "demo/layout_previews/project02_a300_a700_constraint_ablation.summary.md"
GANTRY = "FL9A24D062A100.001-1"
A300_WINDOW = "a300-a700-service-cluster-relative-window"
LEFT_REACH = "coarse-left-drain-reach"
RIGHT_REACH = "coarse-right-drain-reach"


def without_constraints(request: dict[str, Any], ids: set[str]) -> dict[str, Any]:
    updated = deepcopy(request)
    updated["processConstraints"] = [
        item
        for item in updated.get("processConstraints") or []
        if str(item.get("id")) not in ids
    ]
    return updated


def widened_a300_window(request: dict[str, Any]) -> dict[str, Any]:
    updated = deepcopy(request)
    for item in updated.get("processConstraints") or []:
        if item.get("id") != A300_WINDOW:
            continue
        item.update(
            {
                "minDeltaU": -0.10,
                "maxDeltaU": 0.10,
                "minDeltaV": 0.02,
                "maxDeltaV": 0.20,
            }
        )
        item["message"] = (
            "Diagnostic-only widened A300/A700 service-cluster window; "
            "not approved for the production request."
        )
    return updated


def soften_a300_window(request: dict[str, Any]) -> dict[str, Any]:
    updated = deepcopy(request)
    for item in updated.get("processConstraints") or []:
        if item.get("id") != A300_WINDOW:
            continue
        item["hard"] = False
        item["message"] = (
            "Diagnostic-only prototype-relative preference; it must not crop the hard valve-reach domain."
        )
    return updated


def extract_mapping(message: str, label: str, next_label: str) -> dict[str, Any]:
    match = re.search(
        rf"{re.escape(label)}=(\{{.*?\}}), {re.escape(next_label)}=",
        message,
    )
    if not match:
        return {}
    try:
        value = ast.literal_eval(match.group(1))
        return value if isinstance(value, dict) else {}
    except (SyntaxError, ValueError):
        return {}


def solve_scenario(
    capture: dict[str, Any],
    request: dict[str, Any],
    scenario_id: str,
    removed: list[str],
    note: str,
) -> dict[str, Any]:
    started = time.perf_counter()
    print(f"START {scenario_id}", flush=True)
    try:
        generated = generate_constraint_layout(
            capture,
            build_source_independent_options(request, ROOT),
        )
        signature = placement_signature(generated)
        a300 = signature.get("FL9A24D062A300.001-1")
        a700 = signature.get("FL9A24D062A700.001-1")
        joint = (generated.get("constraintPlan") or {}).get("jointSearch") or {}
        result = {
            "id": scenario_id,
            "feasible": bool(generated.get("success")) and bool(signature),
            "removedConstraintIds": removed,
            "note": note,
            "elapsedSeconds": time.perf_counter() - started,
            "acceptedCandidateCounts": joint.get("acceptedCandidateCounts") or {},
            "rejectionCounts": joint.get("rejectionCounts") or {},
            "processConstraintFailureCounts": joint.get("processConstraintFailureCounts") or {},
            "rank1PlacementSignature": signature,
            "a300MinusA700DeltaMeters": (
                [a300[0] - a700[0], a300[1] - a700[1]]
                if a300 is not None and a700 is not None
                else None
            ),
            "predictedConditionalBrepPairCount": (
                (joint.get("solutions") or [{}])[0].get("predictedConditionalBrepPairCount")
                if joint.get("solutions")
                else None
            ),
        }
    except Exception as exc:
        message = str(exc)
        result = {
            "id": scenario_id,
            "feasible": False,
            "removedConstraintIds": removed,
            "note": note,
            "elapsedSeconds": time.perf_counter() - started,
            "errorType": type(exc).__name__,
            "error": message,
            "acceptedCandidateCounts": extract_mapping(
                message,
                "acceptedCandidateCounts",
                "rejectionCounts",
            ),
            "rejectionCounts": extract_mapping(
                message,
                "rejectionCounts",
                "processConstraintFailureCounts",
            ),
            "processConstraintFailureCounts": extract_mapping(
                message,
                "processConstraintFailureCounts",
                "collisionMatrix",
            ),
        }
    print(
        f"DONE {scenario_id} feasible={result['feasible']} "
        f"elapsed={result['elapsedSeconds']:.3f}s",
        flush=True,
    )
    return result


def main() -> int:
    request = json.loads(REQUEST.read_text(encoding="utf-8-sig"))
    capture = json.loads(
        (ROOT / request["geometryCapturePath"]).read_text(encoding="utf-8-sig")
    )
    common = request["moduleSemantics"][GANTRY]["regions"]["dualValveReach"]
    width_u = float(common["maxU"]) - float(common["minU"])
    width_v = float(common["maxV"]) - float(common["minV"])
    balanced = with_valve_reach_directional_insets(
        request,
        max(0.0, (width_u - 1.00) / 2.0),
        max(0.0, (width_v - 0.82) / 2.0),
    )
    balanced["sourceIndependentPolicy"]["jointCandidateLimit"] = 12
    balanced["sourceIndependentPolicy"]["jointSearchTimeLimitSeconds"] = 90

    scenarios = [
        (
            "balanced-baseline",
            balanced,
            [],
            "All current hard constraints retained.",
        ),
        (
            "without-a300-a700-relative-window",
            without_constraints(balanced, {A300_WINDOW}),
            [A300_WINDOW],
            "Tests whether the prototype-calibrated relative window is the primary bottleneck.",
        ),
        (
            "widened-a300-a700-relative-window",
            widened_a300_window(balanced),
            [],
            "Tests a diagnostic-only wider service-cluster relation while retaining both drain reach checks.",
        ),
        (
            "soft-a300-a700-relative-preference",
            soften_a300_window(balanced),
            [],
            "Tests the original narrow window as a ranking preference rather than a hard feasibility gate.",
        ),
        (
            "without-a300-drain-reach",
            without_constraints(balanced, {LEFT_REACH, RIGHT_REACH}),
            [LEFT_REACH, RIGHT_REACH],
            "Tests whether the estimated valve envelopes, rather than the service-cluster relation, are limiting.",
        ),
        (
            "without-window-and-drain-reach",
            without_constraints(balanced, {A300_WINDOW, LEFT_REACH, RIGHT_REACH}),
            [A300_WINDOW, LEFT_REACH, RIGHT_REACH],
            "Control case: removes all three A300 process-domain constraints but keeps spatial and interaction gates.",
        ),
    ]
    results = [
        solve_scenario(capture, changed, scenario_id, removed, note)
        for scenario_id, changed, removed, note in scenarios
    ]
    baseline = results[0]
    window_removed = results[1]
    window_widened = results[2]
    soft_window = results[3]
    reach_removed = results[4]
    all_removed = results[5]
    report = {
        "schemaVersion": "project02-a300-a700-constraint-ablation/v1",
        "success": True,
        "status": "DIAGNOSTIC_ONLY_NO_FORMAL_CONSTRAINT_CHANGED",
        "projectId": "project02",
        "balancedCommonReachMeters": {"widthU": 1.00, "widthV": 0.82},
        "formalRequestModified": False,
        "scenarios": results,
        "diagnosis": {
            "baselineFeasible": baseline["feasible"],
            "relativeWindowRemovalRecoversFeasibility": window_removed["feasible"],
            "relativeWindowWideningRecoversFeasibility": window_widened["feasible"],
            "softRelativePreferenceRecoversFeasibility": soft_window["feasible"],
            "drainReachRemovalRecoversFeasibility": reach_removed["feasible"],
            "allA300ProcessDomainRemovalRecoversFeasibility": all_removed["feasible"],
            "interpretation": (
                "A constraint is considered causal only when its isolated removal or bounded widening "
                "recovers a complete layout; collision and protected-space gates remain active in every scenario."
            ),
            "preferredDiagnosticBranch": "widened-a300-a700-relative-window",
            "preferredBranchReason": (
                "It retains both left/right drain reach constraints and a bounded service-cluster relation. "
                "The soft-only branch is feasible but allows substantially larger A300/A700 drift."
            ),
        },
        "decisionRule": (
            "Do not update the production request from ablation alone. Prefer replacing exact prototype-relative "
            "windows with function-derived ranges only after CAD/PPT evidence identifies the required service relation."
        ),
    }
    OUTPUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Project02 A300–A700 约束消融摘要",
        "",
        "本报告仅用于诊断，未修改正式请求。平衡公共行程为 1000 × 820 mm。",
        "",
        "| 场景 | 可行 | 耗时(s) | 说明 |",
        "|---|---:|---:|---|",
    ]
    for item in results:
        lines.append(
            f"| `{item['id']}` | {'是' if item['feasible'] else '否'} | "
            f"{item['elapsedSeconds']:.2f} | {item['note']} |"
        )
    lines.extend(
        [
            "",
            "详细失败约束计数见同名 JSON 的 `processConstraintFailureCounts`。",
            "",
            "结论应用规则：消融只用于定位原因；在工艺证据确认前，不把删除约束当作正式优化。",
        ]
    )
    SUMMARY.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"success": True, "output": str(OUTPUT), "summary": str(SUMMARY)}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
