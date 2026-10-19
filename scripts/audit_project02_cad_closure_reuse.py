#!/usr/bin/env python3
"""Reuse Project 02 CAD closure when an approved layout is geometrically identical."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "demo-backend" / "src"))

from demo_backend.layout_closure_reuse import build_closure_reuse_report  # noqa: E402


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.resolve().read_text(encoding="utf-8"))


def resolved(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def update_verification_plan(path: Path, report: dict[str, Any]) -> None:
    payload = read_json(path)
    payload["cadClosureReuse"] = report
    if report["success"]:
        payload["status"] = "cad_closure_reused"
        for stage in payload.get("stages") or []:
            if stage.get("id") in {
                "solidworks_replay",
                "world_aabb_broad_phase",
                "candidate_brep",
            }:
                stage["status"] = "completed_via_equivalent_layout_reuse"
                stage["blockedBy"] = []
                stage["referenceAssemblyPath"] = report["priorCadClosure"].get(
                    "assemblyPath"
                )
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--selected",
        default="demo/layout_previews/project02_selected_solution.json",
    )
    parser.add_argument(
        "--preview", default="demo/layout_previews/project02_preview.json"
    )
    parser.add_argument(
        "--closed-replay",
        default="demo/layout_previews/project02_prototype_context_optical_solved_v52_result.json",
    )
    parser.add_argument(
        "--closed-plan",
        default="demo/layout_previews/project02_v52_cad_execution_plan.json",
    )
    parser.add_argument(
        "--verification-plan",
        default="demo/layout_previews/project02_verification_plan.json",
    )
    parser.add_argument(
        "--output",
        default="demo/layout_previews/project02_current_cad_closure_reuse.json",
    )
    args = parser.parse_args()

    selected_path = resolved(args.selected)
    preview_path = resolved(args.preview)
    replay_path = resolved(args.closed_replay)
    closed_plan_path = resolved(args.closed_plan)
    verification_path = resolved(args.verification_plan)
    output_path = resolved(args.output)
    report = build_closure_reuse_report(
        selected=read_json(selected_path),
        preview=read_json(preview_path),
        closed_replay=read_json(replay_path),
        closed_plan=read_json(closed_plan_path),
        closed_plan_path=closed_plan_path,
    )
    report.update(
        {
            "selectedLayoutPath": str(selected_path.resolve()),
            "previewPath": str(preview_path.resolve()),
            "closedReplayEvidencePath": str(replay_path.resolve()),
            "closedCadPlanPath": str(closed_plan_path.resolve()),
        }
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    update_verification_plan(verification_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
