#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.project03_deprototype_audit import (  # noqa: E402
    build_project03_pose_anchor_ablation,
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "demo/semantic_ports/project03_deprototype_ablation_v1/project03_pose_anchor_ablation.json",
    )
    args = parser.parse_args()
    graph = load(ROOT / "demo/layout_previews/project03_module_mate_graph.json")
    geometry = load(ROOT / "demo/layout_previews/project03_first_stage_geometry.json")
    result = build_project03_pose_anchor_ablation(
        graph,
        Path(geometry["sourceAssemblyPath"]),
        load(ROOT / "demo/layout_previews/project03_service_points.json"),
        load(ROOT / "demo/layout_previews/project03_dual_valve_reach.json"),
        load(ROOT / "demo/semantic_ports/project03_calibrated_parameters_v1.json"),
    )
    result["generatedAt"] = datetime.now(timezone.utc).isoformat()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["success"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
