#!/usr/bin/env python3
"""Expand the approved Project 05 solution into an eleven-module Replay layout."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
import time


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "demo-backend" / "src"))

from demo_backend.project05_replay import build_project05_replay_layout  # noqa: E402
from demo_backend.pipeline_timing import utc_now_iso  # noqa: E402


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _resolved(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selected", default="demo/layout_previews/project05_selected_solution.json")
    parser.add_argument("--occupancy", default="demo/layout_previews/project05_module_occupancy.json")
    parser.add_argument("--poses", default="demo/layout_previews/project05_top_level_poses.json")
    parser.add_argument("--output", default="demo/layout_previews/project05_selected_solution_replay.json")
    parser.add_argument("--direct-poses-output", default="demo/layout_previews/project05_selected_solution_direct_poses.json")
    parser.add_argument("--timing-output", default="demo/layout_previews/project05_replay_preparation_timing.json")
    args = parser.parse_args()

    started_at = utc_now_iso()
    started = time.perf_counter()
    output = _resolved(args.output)
    direct_poses_output = _resolved(args.direct_poses_output)
    timing_output = _resolved(args.timing_output)
    document = build_project05_replay_layout(
        _load(_resolved(args.selected)),
        _load(_resolved(args.occupancy)),
        _load(_resolved(args.poses)),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    direct_poses = [
        {
            "Name": item["componentName"],
            "Path": item["filePath"],
            "Translation": item["targetComponentTranslation"],
            "XAxis": item["targetXAxisWorld"],
            "YAxis": item["targetYAxisWorld"],
            "ZAxis": item["targetZAxisWorld"],
            "BoundingBoxWorld": item["boundingBoxWorld"],
        }
        for item in document["components"]
    ]
    direct_poses_output.parent.mkdir(parents=True, exist_ok=True)
    direct_poses_output.write_text(
        json.dumps(direct_poses, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    timing = {
        "schemaVersion": 1,
        "pipeline": "project05.replay-preparation",
        "status": "completed",
        "startedAtUtc": started_at,
        "finishedAtUtc": utc_now_iso(),
        "durationSeconds": round(time.perf_counter() - started, 6),
        "solveObjectCount": document["constraintPlan"]["solveObjectCount"],
        "replayComponentCount": document["constraintPlan"]["replayComponentCount"],
        "prototypeEquivalent": document["constraintPlan"]["prototypeEquivalent"],
    }
    timing_output.write_text(json.dumps(timing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": True,
        "output": str(output.resolve()),
        "directPosesOutput": str(direct_poses_output.resolve()),
        "timingOutput": str(timing_output.resolve()),
        "durationSeconds": timing["durationSeconds"],
        "solveObjectCount": document["constraintPlan"]["solveObjectCount"],
        "replayComponentCount": document["constraintPlan"]["replayComponentCount"],
        "maximumReplayDeltaMeters": document["constraintPlan"]["maximumReplayDeltaMeters"],
        "prototypeEquivalent": document["constraintPlan"]["prototypeEquivalent"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
