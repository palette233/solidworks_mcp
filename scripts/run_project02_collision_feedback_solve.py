#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "apps/demo-backend/src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.layout_preview import solve_case_preview
from demo_backend.project02_ablation import build_ablation_request
from demo_backend.project02_collision_feedback import (
    apply_collision_feedback,
    build_collision_feedback,
    evaluate_feedback_gate,
)


BASE_REQUEST = ROOT / "demo/FL9A24D062A000_real_process_request.json"
GEOMETRY_OCCUPANCY = (
    ROOT
    / "demo/layout_previews/project02_dependency_ablation/project02_geometry_only_occupancy_v1.json"
)
REJECTED_PREVIEW = (
    ROOT / "demo/layout_previews/project02_dependency_ablation/variant_c_preview.json"
)
EXACT_BATCH = (
    ROOT
    / "demo/interference_dependency_C_rank1_20260908/functional_pairs/"
    "FL9A24D062A000_dependency_C_rank1_direct_20260908_leaf_details_batch.json"
)
OUTPUT_DIR = ROOT / "demo/layout_previews/project02_collision_feedback"
FEEDBACK_PATH = OUTPUT_DIR / "collision_feedback_v1.json"
REQUEST_PATH = OUTPUT_DIR / "feedback_hardened_request.json"
PREVIEW_PATH = OUTPUT_DIR / "feedback_hardened_preview.json"
REPORT_PATH = OUTPUT_DIR / "feedback_hardened_report.json"


def main() -> int:
    started_at = datetime.now(timezone.utc)
    pipeline_started = time.perf_counter()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    load_started = time.perf_counter()
    base_request = json.loads(BASE_REQUEST.read_text(encoding="utf-8-sig"))
    rejected_preview = json.loads(REJECTED_PREVIEW.read_text(encoding="utf-8-sig"))
    load_seconds = time.perf_counter() - load_started

    feedback_started = time.perf_counter()
    feedback = build_collision_feedback(
        EXACT_BATCH,
        rejected_preview=rejected_preview,
        forbidden_rotations_by_code={"A700": [180]},
    )
    FEEDBACK_PATH.write_text(
        json.dumps(feedback, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    feedback_seconds = time.perf_counter() - feedback_started

    request_started = time.perf_counter()
    request, ablation_metadata = build_ablation_request(
        base_request,
        "C",
        geometry_occupancy_path=str(GEOMETRY_OCCUPANCY),
    )
    request, feedback_metadata = apply_collision_feedback(request, feedback)
    REQUEST_PATH.write_text(
        json.dumps(request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    request_seconds = time.perf_counter() - request_started

    solve_started = time.perf_counter()
    preview = solve_case_preview(
        ROOT,
        "project02",
        persist=False,
        profile="reduced-prototype",
        request_override=request,
    )
    solve_seconds = time.perf_counter() - solve_started
    PREVIEW_PATH.write_text(
        json.dumps(preview, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    gate_started = time.perf_counter()
    gate = evaluate_feedback_gate(preview, feedback)
    gate_seconds = time.perf_counter() - gate_started
    finished_at = datetime.now(timezone.utc)
    report = {
        "schemaVersion": "project02-collision-feedback-solve/v1",
        "startedAt": started_at.isoformat(),
        "finishedAt": finished_at.isoformat(),
        "success": bool((preview.get("solutions") or [])) and gate["passed"],
        "profile": "reduced-prototype",
        "sourceVariant": "C",
        "solidWorksUsed": False,
        "exactBrepUsedDuringThisSolve": False,
        "paths": {
            "feedback": str(FEEDBACK_PATH),
            "request": str(REQUEST_PATH),
            "preview": str(PREVIEW_PATH),
            "exactEvidence": str(EXACT_BATCH),
        },
        "feedbackMetadata": feedback_metadata,
        "ablationMetadata": ablation_metadata,
        "compatibilityGate": gate,
        "solutionCount": len(preview.get("solutions") or []),
        "timing": {
            "loadInputsSeconds": load_seconds,
            "buildFeedbackSeconds": feedback_seconds,
            "buildRequestSeconds": request_seconds,
            "solveSeconds": solve_seconds,
            "evaluateGateSeconds": gate_seconds,
            "totalSeconds": time.perf_counter() - pipeline_started,
        },
        "nextGate": (
            "visual review before SolidWorks replay; exact B-rep remains final acceptance"
            if gate["passed"]
            else "do not replay; revise candidate constraints"
        ),
    }
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["success"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
