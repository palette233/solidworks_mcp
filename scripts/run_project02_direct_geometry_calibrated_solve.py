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
from demo_backend.project02_collision_feedback import evaluate_feedback_gate
from demo_backend.project02_direct_geometry import (
    apply_direct_geometry_calibration,
    build_direct_geometry_calibration,
    build_direct_major_subassembly_occupancy,
)


SOURCE_REQUEST = ROOT / "demo/layout_previews/project02_collision_feedback/feedback_hardened_request.json"
SOURCE_LAYOUT = ROOT / "demo/layout_previews/project02_dependency_ablation/cad/variant_f_rank1_cad_layout.json"
SOURCE_POSES = ROOT / "demo/layout_previews/project02_dependency_ablation/cad/variant_f_rank1_clean_saved_poses.json"
SOURCE_LEAF_CAPTURE = ROOT / "demo/layout_previews/project02_direct_geometry_calibration/A700_direct_leaf_body_envelopes.json"
FEEDBACK = ROOT / "demo/layout_previews/project02_collision_feedback/collision_feedback_v1.json"
OUTPUT_DIR = ROOT / "demo/layout_previews/project02_direct_geometry_calibration"


def main() -> int:
    started = datetime.now(timezone.utc)
    clock = time.perf_counter()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    request = json.loads(SOURCE_REQUEST.read_text(encoding="utf-8-sig"))
    source_layout = json.loads(SOURCE_LAYOUT.read_text(encoding="utf-8-sig"))
    source_poses = json.loads(SOURCE_POSES.read_text(encoding="utf-8-sig"))
    source_leaf_capture = json.loads(SOURCE_LEAF_CAPTURE.read_text(encoding="utf-8-sig"))
    feedback = json.loads(FEEDBACK.read_text(encoding="utf-8-sig"))

    calibration = build_direct_geometry_calibration(
        source_layout,
        source_poses,
        component_codes=["A700"],
        evidence_path=str(SOURCE_POSES),
    )
    calibration["entries"][0]["occupancyBoxesLocal"] = (
        build_direct_major_subassembly_occupancy(
            source_layout,
            source_leaf_capture,
            component_code="A700",
            collision_partner_codes=["A300", "A500"],
        )
    )
    request, applied = apply_direct_geometry_calibration(
        request,
        calibration,
        promote_strict_pairs=[],
    )
    request.setdefault("sourceIndependentPolicy", {})[
        "solverGeneratedWarmStartReplayResultPath"
    ] = str(SOURCE_LAYOUT)
    request["sourceIndependentPolicy"]["jointSearchTimeLimitSeconds"] = 120
    calibration_path = OUTPUT_DIR / "direct_module_geometry_calibration_v1.json"
    request_path = OUTPUT_DIR / "cad_calibrated_request.json"
    preview_path = OUTPUT_DIR / "cad_calibrated_preview.json"
    report_path = OUTPUT_DIR / "cad_calibrated_report.json"
    calibration_path.write_text(json.dumps(calibration, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    request_path.write_text(json.dumps(request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    solve_started = time.perf_counter()
    preview = solve_case_preview(
        ROOT,
        "project02",
        persist=False,
        profile="reduced-prototype",
        request_override=request,
    )
    solve_seconds = time.perf_counter() - solve_started
    preview_path.write_text(json.dumps(preview, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    gate = evaluate_feedback_gate(preview, feedback)
    report = {
        "schemaVersion": "project02-direct-geometry-calibrated-solve/v1",
        "startedAt": started.isoformat(),
        "finishedAt": datetime.now(timezone.utc).isoformat(),
        "success": bool(preview.get("solutions")) and gate["passed"],
        "profile": "reduced-prototype",
        "variant": "G",
        "solidWorksUsedDuringSolve": False,
        "calibrationApplied": applied,
        "compatibilityGate": gate,
        "solutionCount": len(preview.get("solutions") or []),
        "timing": {
            "solveSeconds": solve_seconds,
            "totalSeconds": time.perf_counter() - clock,
        },
        "paths": {
            "calibration": str(calibration_path),
            "request": str(request_path),
            "preview": str(preview_path),
        },
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["success"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
