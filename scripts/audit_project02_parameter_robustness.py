#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "demo-backend" / "src"))

from demo_backend.constraint_layout import generate_constraint_layout
from demo_backend.layout_preview import build_source_independent_options
from demo_backend.project02_robustness import (
    compare_signatures,
    placement_signature,
    with_scan_tolerance,
    with_service_space_scale,
    with_valve_reach_inset,
)


def solve(capture: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    return generate_constraint_layout(capture, build_source_independent_options(request, ROOT))


def scenario(
    capture: dict[str, Any],
    base_request: dict[str, Any],
    baseline_signature: dict[str, tuple[float, float, float, float]],
    scenario_id: str,
    parameter: str,
    value: float,
    mutate: Callable[[dict[str, Any], float], dict[str, Any]],
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        generated = solve(capture, mutate(base_request, value))
        signature = placement_signature(generated)
        comparison = compare_signatures(baseline_signature, signature)
        validation = generated.get("constraintPlan", {}).get("combinedValidation") or {}
        return {
            "id": scenario_id,
            "parameter": parameter,
            "value": value,
            "feasible": bool(generated.get("success")) and bool(signature),
            "layoutComparison": comparison,
            "replayRequiredIfApplied": bool(signature) and not comparison["equivalent"],
            "processPassed": (generated.get("constraintPlan", {}).get("processValidation") or {}).get("passedCount"),
            "processTotal": (generated.get("constraintPlan", {}).get("processValidation") or {}).get("constraintCount"),
            "hardFailureCount": len(validation.get("hardFailures") or []),
            "elapsedSeconds": time.perf_counter() - started,
        }
    except Exception as exc:  # the audit must retain failed stress points
        return {
            "id": scenario_id,
            "parameter": parameter,
            "value": value,
            "feasible": False,
            "layoutComparison": None,
            "replayRequiredIfApplied": False,
            "error": f"{type(exc).__name__}: {exc}",
            "elapsedSeconds": time.perf_counter() - started,
        }


def summarize(rows: list[dict[str, Any]], parameter: str) -> dict[str, Any]:
    selected = [row for row in rows if row["parameter"] == parameter]
    feasible = [row for row in selected if row["feasible"]]
    unchanged = [
        row for row in feasible if (row.get("layoutComparison") or {}).get("equivalent")
    ]
    return {
        "testedValues": [row["value"] for row in selected],
        "feasibleValues": [row["value"] for row in feasible],
        "layoutPreservingValues": [row["value"] for row in unchanged],
        "maximumTestedFeasibleValue": max((row["value"] for row in feasible), default=None),
        "maximumTestedLayoutPreservingValue": max((row["value"] for row in unchanged), default=None),
        "firstTestedFailureValue": next((row["value"] for row in selected if not row["feasible"]), None),
    }


def main() -> int:
    request = json.loads((ROOT / "demo/FL9A24D062A000_real_process_request.json").read_text(encoding="utf-8-sig"))
    geometry_path = ROOT / request["geometryCapturePath"]
    capture = json.loads(geometry_path.read_text(encoding="utf-8-sig"))
    baseline = solve(capture, request)
    baseline_signature = placement_signature(baseline)
    if not baseline_signature:
        raise RuntimeError("Baseline Project02 solve has no rank-1 placement")

    rows: list[dict[str, Any]] = []
    for value in (0.005, 0.01, 0.02, 0.03, 0.05):
        rows.append(scenario(capture, request, baseline_signature, f"scan-{value:g}", "dynamicScanStopToleranceMeters", value, with_scan_tolerance))
    for value in (1.0, 1.25, 1.5):
        rows.append(scenario(capture, request, baseline_signature, f"service-{value:g}", "serviceProtectedSpaceScaleFactor", value, with_service_space_scale))
    for value in (0.0, 0.025, 0.05, 0.075):
        rows.append(scenario(capture, request, baseline_signature, f"reach-{value:g}", "valveReachUniformInsetMeters", value, with_valve_reach_inset))

    report = {
        "schemaVersion": "project02-parameter-robustness/v1",
        "success": all(row["feasible"] for row in rows if row["value"] in {0.005, 1.0, 0.0}),
        "status": "COARSE_PARAMETER_SENSITIVITY_AUDITED",
        "projectId": "project02",
        "baselineHardFeasible": bool(baseline.get("success")),
        "scenarioCount": len(rows),
        "scenarios": rows,
        "summary": {
            "dynamicScan": summarize(rows, "dynamicScanStopToleranceMeters"),
            "serviceAccess": summarize(rows, "serviceProtectedSpaceScaleFactor"),
            "dualValveReach": summarize(rows, "valveReachUniformInsetMeters"),
        },
        "interpretation": {
            "feasible": "The solver found a coarse layout under the tested parameter.",
            "layoutPreserving": "Rank-1 rigid poses equal the current approved layout; CAD closure may remain reusable after normal gate checks.",
            "layoutChanged": "A new visual review and Replay/B-rep route is required if this parameter is applied.",
            "notProductionTolerance": "Only discrete stress points were tested; this is not a continuous certified tolerance analysis.",
        },
        "engineeringConfirmed": False,
    }
    output = ROOT / "demo/layout_previews/project02_parameter_robustness.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
