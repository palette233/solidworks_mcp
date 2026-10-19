#!/usr/bin/env python3
"""Merge independently persisted Project 02 timing evidence into one report."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = {
    "solve": ROOT
    / "demo/layout_previews/project02_reduced_prototype_pipeline_run.json",
    "projection": ROOT
    / "demo/layout_previews/project02_reduced_prototype_projection_report.json",
    "screening": ROOT
    / "demo/layout_previews/project02_reduced_prototype_3d_screening.json",
    "replay": ROOT / "demo/layout_previews/project02_replay_result.json",
    "brep": ROOT / "demo/layout_previews/project02_priority_brep_batch.json",
}
DEFAULT_OUTPUT = ROOT / "demo/layout_previews/project02_pipeline_timing_summary.json"


def _resolved(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _load(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def _timing(payload: dict[str, Any] | None, key: str = "timing") -> dict[str, Any] | None:
    value = payload.get(key) if payload else None
    return value if isinstance(value, dict) else None


def _phase(name: str, path: Path, timing: dict[str, Any] | None) -> dict[str, Any]:
    if not timing:
        return {
            "name": name,
            "status": "not-run",
            "artifactPath": str(path),
            "artifactExists": path.exists(),
        }
    return {
        "name": name,
        "status": timing.get("status", "completed"),
        "artifactPath": str(path),
        "artifactExists": True,
        "pipeline": timing.get("pipeline"),
        "runId": timing.get("runId"),
        "startedAtUtc": timing.get("startedAtUtc"),
        "finishedAtUtc": timing.get("finishedAtUtc"),
        "durationSeconds": float(timing.get("durationSeconds") or 0.0),
        "stageCount": timing.get("stageCount"),
        "stages": timing.get("stages") or [],
    }


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    for name, default in DEFAULTS.items():
        parser.add_argument(f"--{name}", default=str(default))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = {name: _resolved(getattr(args, name)) for name in DEFAULTS}
    payloads = {name: _load(path) for name, path in paths.items()}

    # Use one non-overlapping top-level timer per phase. The solve artifact also
    # contains a command-line wrapper timer; solveTiming is the actual core solve.
    phases = [
        _phase("solve", paths["solve"], _timing(payloads["solve"], "solveTiming")),
        _phase("offline-pose-projection", paths["projection"], _timing(payloads["projection"])),
        _phase("world-aabb-screening", paths["screening"], _timing(payloads["screening"])),
        _phase("solidworks-replay", paths["replay"], _timing(payloads["replay"])),
        _phase("conditional-brep", paths["brep"], _timing(payloads["brep"])),
    ]
    completed = [item for item in phases if item["status"] != "not-run"]
    starts = [
        parsed
        for parsed in (_parse_datetime(item.get("startedAtUtc")) for item in completed)
        if parsed is not None
    ]
    finishes = [
        parsed
        for parsed in (_parse_datetime(item.get("finishedAtUtc")) for item in completed)
        if parsed is not None
    ]
    ranked = sorted(
        (
            {
                "name": item["name"],
                "durationSeconds": item.get("durationSeconds", 0.0),
                "shareOfRecordedPhaseTime": 0.0,
            }
            for item in completed
        ),
        key=lambda item: item["durationSeconds"],
        reverse=True,
    )
    recorded = sum(item["durationSeconds"] for item in ranked)
    for item in ranked:
        item["shareOfRecordedPhaseTime"] = (
            item["durationSeconds"] / recorded if recorded else 0.0
        )
    report = {
        "success": bool(completed),
        "schemaVersion": 1,
        "kind": "project02-independent-script-timing-summary",
        "phaseCount": len(phases),
        "completedPhaseCount": len(completed),
        "recordedPhaseDurationSeconds": round(recorded, 6),
        "observedWallWindowSeconds": (
            round((max(finishes) - min(starts)).total_seconds(), 6)
            if starts and finishes
            else None
        ),
        "phases": phases,
        "bottleneckRanking": ranked,
        "interpretation": (
            "recordedPhaseDurationSeconds sums one non-overlapping timer per completed "
            "phase. observedWallWindowSeconds may include idle gaps because scripts can be "
            "run independently. Missing Replay/B-Rep artifacts remain explicitly not-run."
        ),
    }
    output = _resolved(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
