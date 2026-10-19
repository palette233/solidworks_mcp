#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))
from demo_backend.project01_sm00_incremental_closure import build_project01_sm00_incremental_closure  # noqa: E402


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    directory = ROOT / "demo/semantic_ports/project01_SM00_third_increment_v1"
    result = build_project01_sm00_incremental_closure(
        source_graph=load(ROOT / "demo/layout_previews/project01_module_mate_graph.json"),
        insert_result=load(directory / "step03_SM00_increment.result.json"),
        poses=load(directory / "step03_top_level_poses.json"),
        screening=load(directory / "step03_interference_screening.json"),
        scanner_geometry=load(ROOT / "demo/layout_previews/project01_scanner_geometry.json"),
        assembly_path=directory / "step03_JJ00_HL00_SS00_FF00_SM00_increment.SLDASM",
    )
    output = directory / "step03_SM00_incremental_closure.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"], "success": result["success"],
        "componentCount": result["componentCount"], "drivingMateCount": result["drivingMateCount"],
        "poseMaximumError": result["poseAudit"]["maximumTransformElementError"],
        "collisionPairCount": result["collisionGate"]["pairCount"],
        "opticalStaticDemoPassed": result["opticalGate"]["staticDemoPassed"],
        "opticalEngineeringConfirmed": result["opticalGate"]["engineeringConfirmed"],
        "totalMeasuredSeconds": result["timingSeconds"]["totalMeasuredSeconds"], "output": str(output),
    }, ensure_ascii=False, indent=2))
    return 0 if result["success"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
