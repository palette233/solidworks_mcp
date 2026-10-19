#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.project03_macro_static_closure import (  # noqa: E402
    build_project03_macro_static_closure,
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    prior = [
        ROOT / "demo/semantic_ports/project03_AE00_first_increment_v1/step01_AE00_incremental_closure.json",
        ROOT / "demo/semantic_ports/project03_AD00_second_increment_v1/step02_AD00_incremental_closure.json",
        ROOT / "demo/semantic_ports/project03_AI00_third_increment_v1/step03_AI00_incremental_closure.json",
        ROOT / "demo/semantic_ports/project03_AG00_fourth_increment_anchored_v1/step04_AG00_incremental_closure.json",
        ROOT / "demo/semantic_ports/project03_AH00_fifth_increment_v1/step05_AH00_incremental_closure.json",
        ROOT / "demo/semantic_ports/project03_AJ00_sixth_increment_v1/step06_AJ00_incremental_closure.json",
    ]
    ab = ROOT / "demo/semantic_ports/project03_AB00_final_stage_action1_v1"
    ac = ROOT / "demo/semantic_ports/project03_AC00_final_stage_action2_v1"
    assembly = ac / "step07b_project03_full_10_object_static_diagnostic_v4b.SLDASM"
    result = build_project03_macro_static_closure(
        source_graph=load(ROOT / "demo/layout_previews/project03_module_mate_graph.json"),
        prior_closures=[load(path) for path in prior],
        ab00_result=load(ab / "step07a_AB00_increment_v2.result.json"),
        ac00_macro_result=load(ac / "step07b_AC00_static_diagnostic_v4b.result.json"),
        ac00_subtree_comparison=load(
            ac / "ac00_prototype_vs_static_diagnostic_v4b_comparison.json"
        ),
        ac00_anchor_flexible_result=load(ac / "step07b_AC00_static_snapshot_v5.result.json"),
        ac00_anchor_rigid_result=load(ac / "step07b_AC00_static_snapshot_rigid_v6.result.json"),
        ac00_prefixed_result=load(ac / "step07b_AC00_prefixed_flexible_v7.result.json"),
        poses=load(ac / "step07b_static_diagnostic_v4b_top_level_poses.json"),
        screening=load(ac / "step07b_static_diagnostic_v4b_interference_broadphase.json"),
        valve_reach=load(ROOT / "demo/layout_previews/project03_dual_valve_reach.json"),
        assembly_path=assembly,
    )
    output = ROOT / "demo/semantic_ports/project03_full_machine_increment_v1/project03_macro_static_closure.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    latest = ROOT / "demo/semantic_ports/project03_ordered_jobs/latest_ordered_closure.json"
    latest.parent.mkdir(parents=True, exist_ok=True)
    latest.write_text(
        json.dumps(
            {
                "schemaVersion": "project03-latest-ordered-closure/v2",
                "projectId": "project03",
                "status": result["status"],
                "success": result["success"],
                "macroStaticPassed": result["macroStaticPassed"],
                "fullGeometryClosed": result["fullGeometryClosed"],
                "componentCount": result["componentCount"],
                "assemblyPath": result["assemblyPath"],
                "fullClosurePath": str(output.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "macroStaticPassed": result["macroStaticPassed"],
                "fullGeometryClosed": result["fullGeometryClosed"],
                "output": str(output.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result["macroStaticPassed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
