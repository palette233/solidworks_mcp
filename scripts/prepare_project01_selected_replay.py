#!/usr/bin/env python3
"""Expand the approved Project 01 solve objects into a ten-module Replay layout."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "demo-backend" / "src"))

from demo_backend.project01_replay import build_project01_replay_layout  # noqa: E402


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def resolved(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selected", default="demo/layout_previews/project01_selected_solution.json")
    parser.add_argument("--occupancy", default="demo/layout_previews/project01_module_occupancy.json")
    parser.add_argument("--poses", default="demo/layout_previews/project01_top_level_poses.json")
    parser.add_argument("--output", default="demo/layout_previews/project01_selected_solution_replay.json")
    args = parser.parse_args()

    output = resolved(args.output)
    document = build_project01_replay_layout(
        load(resolved(args.selected)),
        load(resolved(args.occupancy)),
        load(resolved(args.poses)),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": True,
        "output": str(output),
        "solveObjectCount": document["constraintPlan"]["solveObjectCount"],
        "replayComponentCount": document["constraintPlan"]["replayComponentCount"],
        "maximumReplayDeltaMeters": document["constraintPlan"]["maximumReplayDeltaMeters"],
        "prototypeEquivalent": document["constraintPlan"]["prototypeEquivalent"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
