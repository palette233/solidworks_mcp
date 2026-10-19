"""Run the Project 02 static-layout staged-validation closure without opening SolidWorks.

The script deliberately stops before exact B-Rep.  It proves solver constraints,
pair-policy completeness, Top-K output, visual-gate materialization, and the
world-AABB routing logic using a conservative planar-rigid projection from the
last saved CAD poses.  The projection supports changed 90-degree orientations,
but it remains an offline broad-phase estimate rather than CAD evidence.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.layout_preview import approve_case_preview, solve_case_preview  # noqa: E402
from demo_backend.pipeline_timing import PipelineTiming  # noqa: E402


def run(*arguments: str) -> None:
    completed = subprocess.run(
        [sys.executable, *arguments],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        command = " ".join(arguments)
        details = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(f"child command failed ({command}):\n{details}")


def main() -> None:
    timing = PipelineTiming("project02.offline-static-collision-closure")
    with timing.stage("solve-preview"):
        preview = solve_case_preview(ROOT, "project02", persist=True)
    selected = min(
        preview.get("solutions") or [],
        key=lambda item: (
            int(item.get("predictedConditionalBrepPairCount", 10_000)),
            float(item.get("score", 0.0)),
        ),
    )
    with timing.stage("approve-preview", solutionRank=int(selected["rank"])):
        plan = approve_case_preview(
            ROOT,
            "project02",
            int(selected["rank"]),
            reviewer_note="automated staged static-collision closure",
        )

    preview_dir = ROOT / "demo" / "layout_previews"
    solution = preview_dir / "project02_solution.json"
    projected_poses = preview_dir / "project02_static_collision_projected_poses.json"
    projection_report = preview_dir / "project02_static_collision_projection_report.json"
    screening_path = preview_dir / "project02_static_collision_screening.json"
    with timing.stage("project-saved-replay-poses"):
        run(
            "scripts/project_saved_replay_poses.py",
            "--target-layout",
            str(solution),
            "--baseline-replay",
            "demo/FL9A24D062A000_joint_v24_replay_result.json",
            "--baseline-poses",
            "demo/FL9A24D062A000_joint_v24_projected_poses.json",
            "--output-poses",
            str(projected_poses),
            "--output-report",
            str(projection_report),
        )
    with timing.stage("screen-projected-world-aabb"):
        run(
            "scripts/screen_source_independent_layout_3d.py",
            "--layout",
            str(solution),
            "--poses",
            str(projected_poses),
            "--assembly",
            "demo/FL9A24D062A000_8components_joint_v24.SLDASM",
            "--output",
            str(screening_path),
        )

    screening = json.loads(screening_path.read_text(encoding="utf-8"))
    policy = preview.get("staticCollisionPolicy") or {}
    strict_diagnostics = [
        item
        for item in preview.get("diagnostics") or []
        if item.get("type") == "strictInflatedAabbSeparation"
    ]
    offline_passed = bool(
        preview["metrics"]["hardFeasible"]
        and policy.get("coveredPairCount") == 28
        and len(strict_diagnostics) == 10
        and all(item.get("success") for item in strict_diagnostics)
        and screening.get("broadPhaseSuccess")
        and screening.get("strictAabbFailureCount") == 0
        and screening.get("unclassifiedPairCount") == 0
    )
    timing_payload = timing.finish(
        status="completed" if offline_passed else "failed"
    )
    summary = {
        "success": offline_passed,
        "status": (
            "OFFLINE_STAGED_STATIC_COLLISION_CLOSED_EXACT_BREP_PENDING"
            if offline_passed
            else "OFFLINE_STAGED_STATIC_COLLISION_FAILED"
        ),
        "elapsedSeconds": timing_payload["durationSeconds"],
        "timing": timing_payload,
        "selectedSolutionRank": int(selected["rank"]),
        "selectedSolutionPredictedConditionalBrepPairCount": int(
            selected.get("predictedConditionalBrepPairCount", 0)
        ),
        "solverHardFeasible": bool(preview["metrics"]["hardFeasible"]),
        "solverBrepCallCount": int(preview["metrics"]["solverBrepCallCount"]),
        "processValidation": [
            preview["metrics"]["processPassed"],
            preview["metrics"]["processTotal"],
        ],
        "spatialValidation": [
            preview["metrics"]["spatialPassed"],
            preview["metrics"]["spatialTotal"],
        ],
        "interactionValidation": [
            preview["metrics"]["interactionPassed"],
            preview["metrics"]["interactionTotal"],
        ],
        "pairPolicy": {
            "pairCount": policy.get("pairCount"),
            "coveredPairCount": policy.get("coveredPairCount"),
            "strictAabbPairCount": policy.get("strictAabbPairCount"),
            "conditionalBrepPairCount": policy.get("brepOnAabbOverlapPairCount"),
            "inflationPerSideMeters": policy.get("aabbInflationPerSideMeters"),
        },
        "projectedWorldAabbScreen": {
            "broadPhaseSuccess": screening.get("broadPhaseSuccess"),
            "strictAabbFailureCount": screening.get("strictAabbFailureCount"),
            "unclassifiedPairCount": screening.get("unclassifiedPairCount"),
            "needsExactBrepCheckCount": screening.get("needsExactBrepCheckCount"),
            "brepAvoidedPairCount": screening.get("brepAvoidedPairCount"),
            "brepAvoidedRatio": screening.get("brepAvoidedRatio"),
            "staticInterferenceClosed": screening.get("staticInterferenceClosed"),
        },
        "verificationPlanPath": str(
            (ROOT / "demo/layout_previews/project02_verification_plan.json").resolve()
        ),
        "selectedSolutionPath": plan.get("selectedSolutionPath"),
        "screeningPath": str(screening_path.resolve()),
        "limitations": [
            "The world boxes are a conservative planar-rigid projection from saved v24 poses, not a new SolidWorks Replay.",
            "Exact static interference remains open until the listed conditional pairs complete B-Rep with zero interference.",
            "Motion envelopes are intentionally outside the current milestone.",
        ],
    }
    output = preview_dir / "project02_static_collision_closure_summary.json"
    output.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not offline_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
