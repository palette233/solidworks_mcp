#!/usr/bin/env python3
"""Run one persisted layout solve and emit a compact, timed pipeline summary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.layout_preview import (  # noqa: E402
    PROJECT02_SOLVE_PROFILES,
    approve_case_preview,
    solve_case_preview,
)
from demo_backend.pipeline_timing import PipelineTiming  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project",
        default="project02",
        choices=("project01", "project02", "project03", "project05"),
    )
    parser.add_argument(
        "--profile",
        default="reduced-prototype",
        choices=PROJECT02_SOLVE_PROFILES,
        help=(
            "calibrated keeps the accepted v52 warm start/windows; reduced-prototype "
            "removes both while retaining explicit Project 02 engineering baselines."
        ),
    )
    parser.add_argument(
        "--approve-rank",
        type=int,
        default=None,
        help="Optionally materialize one candidate after the solve. Omit for visual review first.",
    )
    parser.add_argument(
        "--output",
        default="demo/layout_previews/project02_last_pipeline_run.json",
    )
    args = parser.parse_args()

    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output
    timing_output = (
        ROOT / f"demo/layout_previews/{args.project}_pipeline_timing.json"
    ).resolve()
    timer = PipelineTiming(f"{args.project}.command-line-layout")
    summary: dict[str, object] = {
        "success": False,
        "project": args.project,
        "profile": args.profile,
        "requestedApprovalRank": args.approve_rank,
    }
    try:
        with timer.stage("solve-and-persist-preview"):
            preview = solve_case_preview(
                ROOT,
                args.project,
                persist=True,
                profile=args.profile,
            )
        solutions = preview.get("solutions") or []
        metrics = preview.get("metrics") or {}
        summary.update(
            {
                "success": bool(solutions and metrics.get("hardFeasible")),
                "solutionCount": len(solutions),
                "solutionRanks": [item.get("rank") for item in solutions],
                "hardFeasible": bool(metrics.get("hardFeasible")),
                "processValidation": [
                    metrics.get("processPassed"),
                    metrics.get("processTotal"),
                ],
                "spatialValidation": [
                    metrics.get("spatialPassed"),
                    metrics.get("spatialTotal"),
                ],
                "interactionValidation": [
                    metrics.get("interactionPassed"),
                    metrics.get("interactionTotal"),
                ],
                "prototypePoseUsedForSolving": preview.get(
                    "prototypePoseUsedForSolving"
                ),
                "sourceCapturePoseUsedForAnchoring": preview.get(
                    "sourceCapturePoseUsedForAnchoring"
                ),
                "solveProfile": preview.get("solveProfile"),
                "solveTiming": preview.get("timing"),
                "artifactPaths": {
                    "solution": str(
                        (ROOT / f"demo/layout_previews/{args.project}_solution.json").resolve()
                    ),
                    "preview": str(
                        (ROOT / f"demo/layout_previews/{args.project}_preview.json").resolve()
                    ),
                    "timing": str(timing_output),
                },
            }
        )
        if args.approve_rank is not None:
            with timer.stage("approve-and-materialize", solutionRank=args.approve_rank):
                approval = approve_case_preview(
                    ROOT,
                    args.project,
                    args.approve_rank,
                    reviewer_note="approved by solve_project_layout.py",
                )
            summary["approval"] = approval
    except Exception as exc:
        summary["error"] = f"{type(exc).__name__}: {exc}"
    summary["timing"] = timer.finish(
        status="completed" if summary.get("success") else "failed"
    )
    timing_output.parent.mkdir(parents=True, exist_ok=True)
    timing_output.write_text(
        json.dumps(summary["timing"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
