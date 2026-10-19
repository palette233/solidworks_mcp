#!/usr/bin/env python3
"""Feed a stopped exact-BRep batch back into the current Project02 solve."""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.layout_preview import approve_case_preview, solve_case_preview  # noqa: E402
from demo_backend.project02_collision_feedback import (  # noqa: E402
    apply_collision_feedback,
    build_collision_feedback,
    evaluate_feedback_gate,
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def has_durable_replay_layout(document: dict) -> bool:
    components = document.get("components")
    if isinstance(components, list) and components:
        return True
    return any(
        step.get("tool") == "apply_captured_common_base_layout"
        and isinstance((step.get("payload") or {}).get("components"), list)
        and bool((step.get("payload") or {}).get("components"))
        for step in document.get("steps") or []
        if isinstance(step, dict)
    )


def focused_collision_batch(batch: dict) -> dict:
    rows = [
        row
        for row in batch.get("pairs") or []
        if row.get("exactCheckComplete") is True
        and int(row.get("failedBodyPairCount") or 0) == 0
        and row.get("hasInterference") is True
        and int(row.get("interferingBodyPairCount") or 0) > 0
    ]
    if not rows:
        raise ValueError("The batch contains no complete confirmed collision row")
    return {
        "assemblyPath": batch.get("assemblyPath"),
        "assemblySha256Before": batch.get("assemblySha256Before"),
        "assemblySha256After": batch.get("assemblySha256After"),
        "assemblyChangedDuringCheck": batch.get("assemblyChangedDuringCheck"),
        "pairs": rows,
        "requestedPairCount": len(rows),
        "completedPairCount": len(rows),
        "acceptedPairCount": 0,
        "hardFailureCount": len(rows),
        "sourceStoppedBatch": True,
    }


def write_failure_report(
    output_dir: Path,
    *,
    args: argparse.Namespace,
    feedback: dict,
    metadata: dict,
    artifacts: dict,
    error: Exception,
) -> Path:
    """Persist an actionable report even when the feedback solve has no layout."""
    report = {
        "schemaVersion": "project02-current-collision-feedback/v1",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "success": False,
        "status": "FEEDBACK_SOLVE_NO_FEASIBLE_LAYOUT",
        "sourceBatch": str(args.batch.resolve()),
        "confirmedCollisionPairCount": len(
            feedback.get("confirmedCollisionPairs") or []
        ),
        "feedbackMetadata": metadata,
        "errorType": type(error).__name__,
        "error": str(error),
        "traceback": traceback.format_exc(),
        "artifacts": artifacts,
        "nextGate": (
            "Diagnose each exact escape pose against process, spatial, and interaction "
            "hard constraints; do not Replay or continue lower-priority B-rep checks."
        ),
    }
    report_path = output_dir / "feedback_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--preview", type=Path, required=True)
    parser.add_argument("--solution", type=Path, required=True)
    parser.add_argument(
        "--request",
        type=Path,
        default=ROOT / "demo/FL9A24D062A000_real_process_request.json",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    source_batch = load(args.batch.resolve())
    rejected_preview = load(args.preview.resolve())
    solution = load(args.solution.resolve())
    request = load(args.request.resolve())

    focused = focused_collision_batch(source_batch)
    focused_path = output_dir / "confirmed_collision_batch.json"
    focused_path.write_text(
        json.dumps(focused, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    feedback = build_collision_feedback(
        focused_path,
        rejected_preview=rejected_preview,
        request=request,
        base_frame=solution.get("baseFrame") or {},
    )
    feedback_path = output_dir / "collision_feedback.json"
    feedback_path.write_text(
        json.dumps(feedback, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    hardened, metadata = apply_collision_feedback(request, feedback)
    # Collision escape offsets are local refinements around the rejected
    # solver candidate.  Feed that candidate back only as an unlocked
    # previous-solver seed; the reduced-prototype profile still removes any
    # prototype Replay warm start and does not lock a component pose.
    if has_durable_replay_layout(solution):
        hardened.setdefault("sourceIndependentPolicy", {})[
            "solverGeneratedWarmStartReplayResultPath"
        ] = str(args.solution.resolve())
    else:
        hardened.setdefault("sourceIndependentPolicy", {}).pop(
            "solverGeneratedWarmStartReplayResultPath", None
        )
        metadata["warmStartSkipped"] = {
            "path": str(args.solution.resolve()),
            "reason": "input has no durable Replay component layout",
        }
    # This is a local repair of an otherwise accepted complete layout. Preserve
    # the previous placements as first-to-validate seeds for every unaffected
    # module, while leaving every pose unlocked. A300's exact CAD escape
    # candidates still have the higher priority group inside the solver.
    for semantic in (hardened.get("moduleSemantics") or {}).values():
        semantic.setdefault("parameters", {})[
            "prioritizeWarmStartCandidate"
        ] = True
    request_path = output_dir / "feedback_hardened_request.json"
    request_path.write_text(
        json.dumps(hardened, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    artifacts = {
        "focusedBatch": str(focused_path),
        "feedback": str(feedback_path),
        "hardenedRequest": str(request_path),
        "preview": str(output_dir / "feedback_hardened_preview.json"),
        "selectedSolution": str(
            ROOT / "demo/layout_previews/project02_selected_solution.json"
        ),
    }
    try:
        preview = solve_case_preview(
            ROOT,
            "project02",
            persist=True,
            profile="reduced-prototype",
            request_override=hardened,
        )
    except Exception as exc:
        report_path = write_failure_report(
            output_dir,
            args=args,
            feedback=feedback,
            metadata=metadata,
            artifacts=artifacts,
            error=exc,
        )
        print(report_path.read_text(encoding="utf-8"))
        return 2
    preview_copy = output_dir / "feedback_hardened_preview.json"
    preview_copy.write_text(
        json.dumps(preview, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    gate = evaluate_feedback_gate(preview, feedback)
    solutions = preview.get("solutions") or []
    success = bool(solutions and gate.get("passed"))
    approval = None
    if success:
        approval = approve_case_preview(
            ROOT,
            "project02",
            int(solutions[0]["rank"]),
            reviewer_note=(
                "automated candidate selection after exact A300/A700 collision feedback; "
                "CAD verification remains mandatory"
            ),
        )
    report = {
        "schemaVersion": "project02-current-collision-feedback/v1",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "success": success,
        "status": (
            "FEEDBACK_SOLVE_PASSED_NEW_CAD_REPLAY_REQUIRED"
            if success
            else "FEEDBACK_SOLVE_FAILED"
        ),
        "sourceBatch": str(args.batch.resolve()),
        "confirmedCollisionPairCount": len(
            feedback.get("confirmedCollisionPairs") or []
        ),
        "feedbackMetadata": metadata,
        "compatibilityGate": gate,
        "solutionCount": len(solutions),
        "selectedRank": int(solutions[0]["rank"]) if success else None,
        "approval": approval,
        "artifacts": {**artifacts, "preview": str(preview_copy)},
        "nextGate": "Replay new candidate and rerun changed-pair AABB/B-Rep checks",
    }
    report_path = output_dir / "feedback_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if success else 2


if __name__ == "__main__":
    raise SystemExit(main())
