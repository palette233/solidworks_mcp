#!/usr/bin/env python3
"""Diagnose which exact A300/A700 collision escape pose satisfies every hard rule.

This is a solver-only diagnostic.  It never approves a candidate or mutates a CAD
assembly.  Each scenario pins only the A300-to-A700 planar relation in a narrow
window, keeps the remaining reduced-prototype constraints, and records the exact
hard-constraint rejection counters.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.constraint_layout import generate_constraint_layout  # noqa: E402
from demo_backend.layout_preview import (  # noqa: E402
    apply_project02_solve_profile,
    build_source_independent_options,
)


A300 = "FL9A24D062A300.001-1"
A700 = "FL9A24D062A700.001-1"
DIAGNOSTIC_ID = "diagnostic-a300-a700-forced-clear-relation"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def component_xy(solution: dict[str, Any], name: str) -> tuple[float, float]:
    component = next(
        item for item in solution.get("components") or [] if item.get("componentName") == name
    )
    layout = component["layout2d"]
    return float(layout["x"]), float(layout["y"])


def extract_mapping(message: str, label: str, next_label: str) -> dict[str, Any]:
    match = re.search(rf"{re.escape(label)}=(\{{.*?\}}), {re.escape(next_label)}=", message)
    if not match:
        return {}
    try:
        value = ast.literal_eval(match.group(1))
        return value if isinstance(value, dict) else {}
    except (SyntaxError, ValueError):
        return {}


def forced_request(
    request: dict[str, Any],
    *,
    solution_path: Path,
    delta_u: float,
    delta_v: float,
) -> dict[str, Any]:
    changed = deepcopy(request)
    changed.setdefault("sourceIndependentPolicy", {})[
        "solverGeneratedWarmStartReplayResultPath"
    ] = str(solution_path.resolve())
    changed["sourceIndependentPolicy"]["jointCandidateLimit"] = max(
        24, int(changed["sourceIndependentPolicy"].get("jointCandidateLimit") or 0)
    )
    changed["sourceIndependentPolicy"]["jointSearchTimeLimitSeconds"] = max(
        90.0,
        float(changed["sourceIndependentPolicy"].get("jointSearchTimeLimitSeconds") or 0),
    )
    changed["processConstraints"] = [
        item
        for item in changed.get("processConstraints") or []
        if item.get("id") != DIAGNOSTIC_ID
        and not (
            item.get("type") == "relativeAnchorWindow"
            and item.get("component") == A300
            and item.get("referenceComponent") == A700
        )
    ]
    tolerance = 0.00005
    changed["processConstraints"].append(
        {
            "id": DIAGNOSTIC_ID,
            "type": "relativeAnchorWindow",
            "component": A300,
            "referenceComponent": A700,
            "minDeltaU": delta_u - tolerance,
            "maxDeltaU": delta_u + tolerance,
            "minDeltaV": delta_v - tolerance,
            "maxDeltaV": delta_v + tolerance,
            "hard": True,
            "retainInReducedPrototype": True,
            "source": "diagnostic-only forced exact collision escape relation",
        }
    )
    return changed


def run_scenario(
    request: dict[str, Any],
    capture: dict[str, Any],
    solution_path: Path,
    scenario: dict[str, Any],
) -> dict[str, Any]:
    started = time.perf_counter()
    changed = forced_request(
        request,
        solution_path=solution_path,
        delta_u=float(scenario["deltaU"]),
        delta_v=float(scenario["deltaV"]),
    )
    profiled, profile_metadata = apply_project02_solve_profile(
        changed, "reduced-prototype"
    )
    try:
        generated = generate_constraint_layout(
            capture,
            build_source_independent_options(profiled, ROOT),
        )
        by_name = {
            item["componentName"]: item
            for item in generated.get("components") or []
        }
        a300 = by_name[A300]["layout2d"]
        a700 = by_name[A700]["layout2d"]
        joint = (generated.get("constraintPlan") or {}).get("jointSearch") or {}
        return {
            **scenario,
            "feasible": True,
            "elapsedSeconds": time.perf_counter() - started,
            "actualDeltaU": float(a300["x"]) - float(a700["x"]),
            "actualDeltaV": float(a300["y"]) - float(a700["y"]),
            "acceptedCandidateCounts": joint.get("acceptedCandidateCounts") or {},
            "rejectionCounts": joint.get("rejectionCounts") or {},
            "processConstraintFailureCounts": joint.get("processConstraintFailureCounts") or {},
            "profileMetadata": profile_metadata,
        }
    except Exception as exc:
        message = str(exc)
        return {
            **scenario,
            "feasible": False,
            "elapsedSeconds": time.perf_counter() - started,
            "errorType": type(exc).__name__,
            "error": message,
            "acceptedCandidateCounts": extract_mapping(
                message, "acceptedCandidateCounts", "rejectionCounts"
            ),
            "rejectionCounts": extract_mapping(
                message, "rejectionCounts", "processConstraintFailureCounts"
            ),
            "processConstraintFailureCounts": extract_mapping(
                message, "processConstraintFailureCounts", "collisionMatrix"
            ),
            "profileMetadata": profile_metadata,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--solution", type=Path, required=True)
    parser.add_argument("--feedback", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    request_path = args.request.resolve()
    solution_path = args.solution.resolve()
    request = load(request_path)
    solution = load(solution_path)
    feedback = load(args.feedback.resolve())
    geometry_path = Path(str(request["geometryCapturePath"]))
    if not geometry_path.is_absolute():
        geometry_path = ROOT / geometry_path
    capture = load(geometry_path.resolve())

    a300_xy = component_xy(solution, A300)
    a700_xy = component_xy(solution, A700)
    current_u = a300_xy[0] - a700_xy[0]
    current_v = a300_xy[1] - a700_xy[1]
    exclusion = feedback["confirmedCollisionPairs"][0]["relativePoseExclusion"]
    offsets = exclusion.get("candidateEscapeOffsetsMeters") or []
    margin = 0.0001
    scenarios: list[dict[str, Any]] = []
    labels = ("negative-u", "positive-v", "negative-v", "positive-u")
    for label, offset in zip(labels, offsets):
        du, dv = float(offset[0]), float(offset[1])
        du += (margin if du > 0 else -margin if du < 0 else 0.0)
        dv += (margin if dv > 0 else -margin if dv < 0 else 0.0)
        scenarios.append(
            {
                "id": f"exact-escape-{label}",
                "kind": "exact-leaf-aabb-clearance",
                "deltaU": current_u + du,
                "deltaV": current_v + dv,
            }
        )
    scenarios.append(
        {
            "id": "prototype-service-relation",
            "kind": "prototype-derived-reference",
            "deltaU": 0.0,
            "deltaV": 0.12075,
        }
    )

    results = []
    for scenario in scenarios:
        print(f"START {scenario['id']}", flush=True)
        result = run_scenario(request, capture, solution_path, scenario)
        results.append(result)
        print(
            f"DONE {scenario['id']} feasible={result['feasible']} "
            f"elapsed={result['elapsedSeconds']:.3f}s",
            flush=True,
        )

    feasible = [item for item in results if item["feasible"]]
    report = {
        "schemaVersion": "project02-a300-a700-escape-pose-diagnostic/v1",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "success": True,
        "status": (
            "FEASIBLE_ESCAPE_RELATION_FOUND"
            if feasible
            else "ALL_ESCAPE_RELATIONS_REJECTED"
        ),
        "cadMutationPerformed": False,
        "sourceRequest": str(request_path),
        "sourceSolution": str(solution_path),
        "sourceFeedback": str(args.feedback.resolve()),
        "currentRejectedRelation": {"deltaU": current_u, "deltaV": current_v},
        "scenarios": results,
        "recommendedScenarioId": feasible[0]["id"] if feasible else None,
        "nextGate": (
            "Persist the first feasible relation as a collision-feedback repair target, solve, Replay, and recheck changed pairs."
            if feasible
            else "Audit the dominant hard-constraint rejection counts before changing any formal rule."
        ),
    }
    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.output.resolve().write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if feasible else 2


if __name__ == "__main__":
    raise SystemExit(main())
