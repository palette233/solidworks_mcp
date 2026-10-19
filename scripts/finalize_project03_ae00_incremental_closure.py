#!/usr/bin/env python3
"""Finalize the first Project03 independent incremental CAD checkpoint."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.project03_incremental_closure import (  # noqa: E402
    build_project03_ae00_incremental_closure,
)


DEFAULT_DIR = ROOT / "demo/semantic_ports/project03_AE00_first_increment_v1"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, default=DEFAULT_DIR)
    args = parser.parse_args()
    directory = args.directory.resolve()
    assembly = directory / "step01_AA00_AF00_AE00_increment.SLDASM"
    result = build_project03_ae00_incremental_closure(
        source_graph=load(ROOT / "demo/layout_previews/project03_module_mate_graph.json"),
        base_result=load(directory / "step00_AA00_AF00_context.result.json"),
        insert_result=load(directory / "step01_AA00_AF00_AE00_increment.result.json"),
        poses=load(directory / "step01_top_level_poses.json"),
        screening=load(directory / "step01_interference_screening.json"),
        assembly_path=assembly,
    )
    output = directory / "step01_AE00_incremental_closure.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "success": result["success"],
        "componentCount": result["componentCount"],
        "drivingMateCount": result["drivingMateCount"],
        "poseMaximumError": result["poseAudit"]["maximumTransformElementError"],
        "collisionPairCount": result["collisionGate"]["pairCount"],
        "totalMeasuredSeconds": result["timingSeconds"]["totalMeasuredSeconds"],
        "output": str(output),
    }, ensure_ascii=False, indent=2))
    return 0 if result["success"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
