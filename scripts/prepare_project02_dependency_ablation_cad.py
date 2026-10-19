#!/usr/bin/env python3
"""Prepare a solved layout and projected target poses for direct CAD builds."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.pipeline_timing import PipelineTiming  # noqa: E402
from demo_backend.project02_ablation_cad import (  # noqa: E402
    materialize_ablation_cad_layout,
)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variants", nargs="+", default=("B", "C"))
    parser.add_argument(
        "--preview-path",
        type=Path,
        help="Explicit preview path; valid only when one variant is requested.",
    )
    parser.add_argument("--rank", type=int, default=1)
    parser.add_argument(
        "--authorization-note",
        required=True,
        help="User-authored reason authorizing CAD generation for these read-only candidates.",
    )
    parser.add_argument(
        "--baseline-layout",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--baseline-poses",
        type=Path,
        default=None,
    )
    args = parser.parse_args()
    if args.preview_path and len(args.variants) != 1:
        parser.error("--preview-path requires exactly one --variants value")

    iterative_variants = [
        variant for variant in args.variants if variant.upper() not in {"B", "C", "F", "G"}
    ]
    if iterative_variants and (
        args.baseline_layout is None or args.baseline_poses is None
    ):
        parser.error(
            "Iterative variants require explicit --baseline-layout and --baseline-poses "
            "from the immediately preceding accepted CAD candidate."
        )
    baseline_layout_path = (
        args.baseline_layout
        or ROOT / "demo/layout_previews/project02_selected_solution.json"
    ).resolve()
    baseline_poses_path = (
        args.baseline_poses
        or ROOT / "demo/layout_previews/project02_a600_fixed_projected_poses.json"
    ).resolve()
    output_directory = ROOT / "demo/layout_previews/project02_dependency_ablation/cad"
    output_directory.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []

    for variant in args.variants:
        lower = variant.lower()
        timer = PipelineTiming(f"project02.dependency-ablation-{lower}-cad-prepare")
        if args.preview_path:
            preview_path = args.preview_path.resolve()
        elif variant == "F":
            preview_path = ROOT / "demo/layout_previews/project02_collision_feedback/feedback_hardened_preview.json"
        elif variant == "G":
            preview_path = ROOT / "demo/layout_previews/project02_direct_geometry_calibration/cad_calibrated_preview.json"
        else:
            preview_path = ROOT / f"demo/layout_previews/project02_dependency_ablation/variant_{lower}_preview.json"
        layout_path = output_directory / f"variant_{lower}_rank{args.rank}_cad_layout.json"
        poses_path = output_directory / f"variant_{lower}_rank{args.rank}_projected_poses.json"
        projection_path = output_directory / f"variant_{lower}_rank{args.rank}_projection_report.json"
        result_path = output_directory / f"variant_{lower}_rank{args.rank}_cad_prepare_result.json"
        with timer.stage("load-baseline-and-preview"):
            baseline_layout = read_json(baseline_layout_path)
            preview = read_json(preview_path)
        with timer.stage("materialize-rank-candidate", variant=variant, rank=args.rank):
            layout = materialize_ablation_cad_layout(
                baseline_layout,
                preview,
                variant=variant,
                solution_rank=args.rank,
                authorization_note=args.authorization_note,
            )
        with timer.stage("persist-cad-layout"):
            write_json(layout_path, layout)
        with timer.stage("project-three-dimensional-target-poses"):
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/project_saved_replay_poses.py"),
                    "--target-layout",
                    str(layout_path),
                    "--baseline-replay",
                    str(baseline_layout_path),
                    "--baseline-poses",
                    str(baseline_poses_path),
                    "--output-poses",
                    str(poses_path),
                    "--output-report",
                    str(projection_path),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            if completed.returncode != 0:
                raise RuntimeError(completed.stderr or completed.stdout)
        timing = timer.finish()
        orientation_changes = (
            (layout.get("constraintPlan") or {})
            .get("selectedTopKSolution", {})
            .get("orientationChangedComponents", [])
        )
        result = {
            "success": layout_path.is_file() and poses_path.is_file(),
            "variant": variant,
            "solutionRank": args.rank,
            "layoutPath": str(layout_path),
            "projectedPosesPath": str(poses_path),
            "projectionReportPath": str(projection_path),
            "baselineLayoutPath": str(baseline_layout_path),
            "baselinePosesPath": str(baseline_poses_path),
            "orientationChangedComponents": orientation_changes,
            "timing": timing,
        }
        write_json(result_path, result)
        rows.append({**result, "resultPath": str(result_path)})

    summary = {
        "success": all(row["success"] for row in rows),
        "schemaVersion": 1,
        "variants": rows,
    }
    summary_path = output_directory / (
        "project02_collision_feedback_cad_prepare_summary.json"
        if tuple(args.variants) == ("F",)
        else "project02_direct_geometry_cad_prepare_summary.json"
        if tuple(args.variants) == ("G",)
        else "project02_dependency_ablation_cad_prepare_summary.json"
    )
    write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
