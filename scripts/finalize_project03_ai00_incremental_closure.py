#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.project03_ai00_incremental_closure import (  # noqa: E402
    build_project03_ai00_incremental_closure,
)


DIR = ROOT / "demo/semantic_ports/project03_AI00_third_increment_v1"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    result = build_project03_ai00_incremental_closure(
        source_graph=load(ROOT / "demo/layout_previews/project03_module_mate_graph.json"),
        failed_all_driving_result=load(DIR / "step03_AI00_increment.result.json"),
        insert_result=load(DIR / "step03_AI00_increment_v2.result.json"),
        poses=load(DIR / "step03_top_level_poses_v2.json"),
        screening=load(DIR / "step03_interference_screening_v2.json"),
        scanner_geometry=load(ROOT / "demo/layout_previews/project03_scanner_geometry.json"),
        prototype_ae_ai_brep=load(
            ROOT
            / "demo/interference_project03_prototype/conditional_hits/FL9A24D063A000.001_leaf_details_FL9A24D063AE00_FL9A24D063AI00.json"
        ),
        assembly_path=DIR / "step03_AA00_AF00_AE00_AD00_AI00_increment_v2.SLDASM",
    )
    output = DIR / "step03_AI00_incremental_closure.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": result["status"],
                "success": result["success"],
                "drivingMateCount": result["relationSemantics"]["drivingMateCount"],
                "validationRelationCount": result["relationSemantics"]["validationRelationCount"],
                "poseMaximumError": result["poseAudit"]["maximumTransformElementError"],
                "pairCount": result["collisionGate"]["pairCount"],
                "opticalProductionReady": result["opticalGate"]["productionReady"],
                "output": str(output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result["success"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
