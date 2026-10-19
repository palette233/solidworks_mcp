#!/usr/bin/env python3
"""Build the final staged-validation report for Project03 solution 1."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))
from demo_backend.project03_closure import build_project03_solution_closure  # noqa: E402


def load(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8-sig"))


def main() -> None:
    comparisons = [
        load("demo/layout_previews/project03_solution1_v1_baseline_compare_AE00_AD00.json"),
        load("demo/layout_previews/project03_solution1_v1_baseline_compare_AE00_AI00.json"),
    ]
    result = build_project03_solution_closure(
        load("demo/layout_previews/project03_solution1_v1_3d_screening.json"),
        load("demo/layout_previews/project03_selected_solution_replay.json"),
        load("demo/interference_project03_solution1_v1/conditional/FL9A24D063A000_project03_solution1_v1_leaf_details_batch.json"),
        comparisons,
        load("demo/layout_previews/project03_solution1_v1_reopened_capture.json"),
    )
    output = ROOT / "demo/layout_previews/project03_solution1_v1_closure.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    verification = load("demo/layout_previews/project03_verification_plan.json")
    verification.update({
        "status": "demo_baseline_equivalent_closed" if result["demoClosurePassed"] else "closure_failed",
        "selectedSolutionRank": result["selectedSolutionRank"],
        "replayAssemblyPath": str(ROOT / "demo/project03/FL9A24D063A000_project03_solution1_v1.SLDASM"),
        "closureReportPath": str(output),
        "demoClosurePassed": result["demoClosurePassed"],
        "productionReady": result["productionReady"],
        "zeroInterferenceClaimed": result["zeroInterferenceClaimed"],
    })
    (ROOT / "demo/layout_previews/project03_verification_plan.json").write_text(
        json.dumps(verification, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "status": result["status"],
        "demoClosurePassed": result["demoClosurePassed"],
        "productionReady": result["productionReady"],
        "prototypeExistingHitPairCount": result["conditionalExactBrep"]["prototypeExistingHitPairCount"],
        "newInterferingBodyPairCount": result["conditionalExactBrep"]["newInterferingBodyPairCount"],
        "output": str(output),
    }, ensure_ascii=False, indent=2))
    if not result["demoClosurePassed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
