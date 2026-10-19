#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))
from demo_backend.project03_ad00_incremental_closure import build_project03_ad00_incremental_closure
DIR = ROOT / "demo/semantic_ports/project03_AD00_second_increment_v1"
def load(path: Path) -> dict: return json.loads(path.read_text(encoding="utf-8-sig"))
def main() -> int:
    result = build_project03_ad00_incremental_closure(
        source_graph=load(ROOT / "demo/layout_previews/project03_module_mate_graph.json"),
        insert_result=load(DIR / "step02_AD00_increment.result.json"),
        poses=load(DIR / "step02_top_level_poses.json"),
        screening=load(DIR / "step02_interference_screening.json"),
        prototype_ae_ad_brep=load(ROOT / "demo/interference_project03_prototype/conditional_hits/FL9A24D063A000.001_leaf_details_FL9A24D063AE00_FL9A24D063AD00.json"),
        assembly_path=DIR / "step02_AA00_AF00_AE00_AD00_increment.SLDASM",
    )
    out=DIR / "step02_AD00_incremental_closure.json"
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":result["status"],"success":result["success"],"poseMaximumError":result["poseAudit"]["maximumTransformElementError"],"pairCount":result["collisionGate"]["pairCount"],"dynamicSweepPassed":result["dynamicSweepPassed"],"output":str(out)},ensure_ascii=False,indent=2))
    return 0 if result["success"] else 2
if __name__ == "__main__": raise SystemExit(main())
