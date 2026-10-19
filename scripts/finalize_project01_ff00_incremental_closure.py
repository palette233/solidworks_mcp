#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.project01_ff00_incremental_closure import (  # noqa: E402
    build_project01_ff00_incremental_closure,
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    directory = ROOT / "demo/semantic_ports/project01_FF00_second_increment_v1"
    result = build_project01_ff00_incremental_closure(
        source_graph=load(ROOT / "demo/layout_previews/project01_module_mate_graph.json"),
        insert_result=load(directory / "step02_FF00_increment.result.json"),
        poses=load(directory / "step02_top_level_poses.json"),
        screening=load(directory / "step02_interference_screening.json"),
        assembly_path=directory / "step02_JJ00_HL00_SS00_FF00_increment.SLDASM",
    )
    output = directory / "step02_FF00_incremental_closure.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "success": result["success"],
        "staticCheckpointPassed": result["staticCheckpointPassed"],
        "dynamicCheckpointPassed": result["dynamicCheckpointPassed"],
        "poseMaximumError": result["poseAudit"]["maximumTransformElementError"],
        "collisionPairCount": result["collisionGate"]["pairCount"],
        "totalMeasuredSeconds": result["timingSeconds"]["totalMeasuredSeconds"],
        "output": str(output),
    }, ensure_ascii=False, indent=2))
    return 0 if result["success"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
