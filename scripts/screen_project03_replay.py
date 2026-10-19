#!/usr/bin/env python3
"""Build Project03 saved-Replay pose, strict-AABB and conditional B-rep routing."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))
from demo_backend.project03_collision import build_project03_replay_screening


def load(relative: str) -> dict:
    path = Path(relative)
    if not path.is_absolute():
        path = ROOT / path
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--occupancy", default="demo/layout_previews/project03_module_occupancy.json")
    parser.add_argument("--layout", default="demo/layout_previews/project03_selected_solution_replay.json")
    parser.add_argument("--replay-result", default="demo/layout_previews/project03_solution1_v1_replay_result.json")
    parser.add_argument("--source-poses", default="demo/layout_previews/project03_top_level_poses.json")
    parser.add_argument("--output", default="demo/layout_previews/project03_solution1_v1_3d_screening.json")
    args = parser.parse_args()
    result = build_project03_replay_screening(
        load(args.occupancy),
        load(args.layout),
        load(args.replay_result),
        load(args.source_poses),
    )
    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "pose": {key: value for key, value in result["replayPoseAudit"].items() if key != "components"},
        "strictAabb": {key: value for key, value in result["strictAabb"].items() if key != "pairs"},
        "conditionalBrep": {key: value for key, value in result["conditionalBrep"].items() if key != "pairs"},
        "installationContact": {key: value for key, value in result["installationContact"].items() if key != "pairs"},
        "output": str(output),
    }, ensure_ascii=False))
    if result["status"] != "PROJECT03_PRIORITY_BREP_READY":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
