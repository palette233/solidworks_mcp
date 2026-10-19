#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))
from demo_backend.project01_gn00_incremental_closure import build_project01_gn00_incremental_closure  # noqa: E402
def load(path: Path) -> dict: return json.loads(path.read_text(encoding="utf-8-sig"))
def main() -> int:
    d = ROOT / "demo/semantic_ports/project01_GN00_fourth_increment_v1"
    result = build_project01_gn00_incremental_closure(source_graph=load(ROOT/"demo/layout_previews/project01_module_mate_graph.json"), insert_result=load(d/"step04_GN00_increment.result.json"), poses=load(d/"step04_top_level_poses.json"), screening=load(d/"step04_interference_screening.json"), service_points=load(ROOT/"demo/layout_previews/project01_service_points.json"), assembly_path=d/"step04_JJ00_HL00_SS00_FF00_SM00_GN00_increment.SLDASM")
    out=d/"step04_GN00_incremental_closure.json"; out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":result["status"],"success":result["success"],"componentCount":result["componentCount"],"drivingMateCount":result["drivingMateCount"],"poseMaximumError":result["poseAudit"]["maximumTransformElementError"],"collisionPairCount":result["collisionGate"]["pairCount"],"serviceTargetCount":result["serviceTargetGate"]["targetCount"],"maintenanceEnvelopePassed":result["maintenanceEnvelopeGate"]["passed"],"totalMeasuredSeconds":result["timingSeconds"]["totalMeasuredSeconds"],"output":str(out)},ensure_ascii=False,indent=2))
    return 0 if result["success"] else 2
if __name__ == "__main__": raise SystemExit(main())
