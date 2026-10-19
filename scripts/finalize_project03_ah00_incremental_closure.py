#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))
from demo_backend.project03_ah00_incremental_closure import build_project03_ah00_incremental_closure  # noqa: E402

DIR = ROOT / "demo/semantic_ports/project03_AH00_fifth_increment_v1"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    result = build_project03_ah00_incremental_closure(
        source_graph=load(ROOT / "demo/layout_previews/project03_module_mate_graph.json"),
        insert_result=load(DIR / "step05_AH00_increment.result.json"),
        poses=load(DIR / "step05_top_level_poses.json"),
        screening=load(DIR / "step05_interference_screening.json"),
        service_points=load(ROOT / "demo/layout_previews/project03_service_points.json"),
        assembly_path=DIR / "step05_AA00_AF00_AE00_AD00_AI00_AG00_AH00_increment.SLDASM",
    )
    output = DIR / "step05_AH00_incremental_closure.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "success": result["success"], "pairCount": result["collisionGate"]["pairCount"], "output": str(output)}, ensure_ascii=False, indent=2))
    return 0 if result["success"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
