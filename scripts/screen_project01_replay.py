#!/usr/bin/env python3
"""Build saved-Replay pose, strict-AABB and conditional B-rep routing for Project 01."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))
from demo_backend.project01_collision import build_project01_replay_screening  # noqa: E402


def load(relative: str) -> dict:
    path = Path(relative)
    if not path.is_absolute():
        path = ROOT / path
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--occupancy", default="demo/layout_previews/project01_module_occupancy.json")
    parser.add_argument("--layout", default="demo/layout_previews/project01_selected_solution_replay.json")
    parser.add_argument("--replay-result", default="demo/layout_previews/project01_solution1_v1_replay_result.json")
    parser.add_argument("--source-poses", default="demo/layout_previews/project01_top_level_poses.json")
    parser.add_argument("--output", default="demo/layout_previews/project01_solution1_v1_3d_screening.json")
    args = parser.parse_args()
    result = build_project01_replay_screening(load(args.occupancy), load(args.layout), load(args.replay_result), load(args.source_poses))
    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "pose": result["replayPoseAudit"], "strictAabb": {key: value for key, value in result["strictAabb"].items() if key != "pairs"}, "conditionalBrep": {key: value for key, value in result["conditionalBrep"].items() if key != "pairs"}, "installationContact": {key: value for key, value in result["installationContact"].items() if key != "pairs"}, "output": str(output)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
