#!/usr/bin/env python3
"""Run one evidence-driven Project02 collision-feedback solve iteration."""

from __future__ import annotations

import argparse
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
from demo_backend.constraint_layout import ConstraintLayoutError
from demo_backend.project02_collision_feedback import (
    apply_collision_feedback,
    build_collision_feedback,
    evaluate_feedback_gate,
)
from demo_backend.project02_direct_geometry import (
    apply_direct_geometry_calibration,
    build_direct_geometry_calibration,
    derive_common_axis_clearance_offsets,
)


def read(path: Path) -> dict:
    return json.loads(path.resolve().read_text(encoding="utf-8-sig"))


def write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", required=True)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--exact-batch", required=True, type=Path)
    parser.add_argument("--rejected-preview", required=True, type=Path)
    parser.add_argument("--structural-occupancy", required=True, type=Path)
    parser.add_argument("--warm-start", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--time-limit", type=float, default=120.0)
    parser.add_argument("--repair-component")
    parser.add_argument("--direct-layout", type=Path)
    parser.add_argument("--direct-poses", type=Path)
    parser.add_argument(
        "--calibrate-component",
        action="append",
        default=[],
        help="Component code whose direct-CAD footprint should replace the capture footprint.",
    )
    parser.add_argument(
        "--defer-component",
        action="append",
        default=[],
        help="Move this functional component behind the repair component in placement order.",
    )
    args = parser.parse_args()

    clock = time.perf_counter()
    started = datetime.now(timezone.utc)
    request = read(args.request)
    rejected = read(args.rejected_preview)
    warm_layout = read(args.warm_start)
    direct_calibration = None
    direct_calibration_metadata = None
    if args.calibrate_component:
        if not args.direct_layout or not args.direct_poses:
            parser.error(
                "--calibrate-component requires --direct-layout and --direct-poses"
            )
        direct_calibration = build_direct_geometry_calibration(
            read(args.direct_layout),
            read(args.direct_poses),
            component_codes=[code.upper() for code in args.calibrate_component],
            evidence_path=str(args.direct_poses.resolve()),
        )
        request, direct_calibration_metadata = apply_direct_geometry_calibration(
            request, direct_calibration
        )
    feedback = build_collision_feedback(
        args.exact_batch,
        rejected_preview=rejected,
        forbidden_rotations_by_code={},
        request=request,
        base_frame=warm_layout.get("baseFrame") or {},
    )
    request["structuralOccupancyPath"] = str(args.structural_occupancy.resolve())
    request, metadata = apply_collision_feedback(request, feedback)
    policy = request.setdefault("sourceIndependentPolicy", {})
    policy["solverGeneratedWarmStartReplayResultPath"] = str(args.warm_start.resolve())
    policy["jointSearchTimeLimitSeconds"] = float(args.time_limit)
    directional_offsets = []
    placement_priority_changes = []
    if args.repair_component:
        batch = read(args.exact_batch)
        pair_row = next(
            (row for row in batch.get("pairs") or [] if row.get("outputPath")), None
        )
        if pair_row is None:
            raise ValueError("Exact batch has no detailed pair output for directional repair.")
        detail = read(Path(str(pair_row["outputPath"])))
        directional_offsets = derive_common_axis_clearance_offsets(
            detail,
            warm_layout.get("baseFrame") or {},
            moving_component_code=args.repair_component.upper(),
            clearance_meters=float(request.get("minimumClearanceMeters", 0.01)),
        )
        semantic_name = next(
            name
            for name in request["moduleSemantics"]
            if args.repair_component.upper() in name.upper()
        )
        request["moduleSemantics"][semantic_name].setdefault("parameters", {})[
            "candidateDirectionalOffsetsMeters"
        ] = directional_offsets
        repair_parameters = request["moduleSemantics"][semantic_name].setdefault(
            "parameters", {}
        )
        repair_priority = int(repair_parameters.get("placementPriority", 100))
        for deferred_code in args.defer_component:
            deferred_name = next(
                name
                for name in request["moduleSemantics"]
                if deferred_code.upper() in name.upper()
            )
            deferred_parameters = request["moduleSemantics"][deferred_name].setdefault(
                "parameters", {}
            )
            deferred_priority = int(
                deferred_parameters.get("placementPriority", repair_priority + 1)
            )
            repair_parameters["placementPriority"] = min(
                repair_priority, deferred_priority
            )
            deferred_parameters["placementPriority"] = max(
                repair_priority, deferred_priority
            )
            if deferred_parameters["placementPriority"] == repair_parameters["placementPriority"]:
                deferred_parameters["placementPriority"] += 1
            placement_priority_changes.append(
                {
                    "repairComponent": semantic_name,
                    "repairPriority": repair_parameters["placementPriority"],
                    "deferredComponent": deferred_name,
                    "deferredPriority": deferred_parameters["placementPriority"],
                }
            )

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    feedback_path = output_dir / "collision_feedback.json"
    calibration_path = output_dir / "direct_geometry_calibration.json"
    request_path = output_dir / "hardened_request.json"
    preview_path = output_dir / "preview.json"
    report_path = output_dir / "report.json"
    write(feedback_path, feedback)
    if direct_calibration is not None:
        write(calibration_path, direct_calibration)
    write(request_path, request)
    solve_started = time.perf_counter()
    solve_error = None
    try:
        preview = solve_case_preview(
            ROOT,
            "project02",
            persist=False,
            profile="reduced-prototype",
            request_override=request,
        )
    except ConstraintLayoutError as exc:
        solve_error = str(exc)
        preview = {
            "caseId": "project02",
            "success": False,
            "status": "NO_FEASIBLE_LAYOUT",
            "message": solve_error,
            "solveProfile": "reduced-prototype",
            "solutions": [],
        }
    solve_seconds = time.perf_counter() - solve_started
    write(preview_path, preview)
    gate = evaluate_feedback_gate(preview, feedback)
    report = {
        "schemaVersion": "project02-collision-iteration/v1",
        "variant": args.variant.upper(),
        "startedAt": started.isoformat(),
        "finishedAt": datetime.now(timezone.utc).isoformat(),
        "success": bool(preview.get("solutions")) and gate["passed"],
        "status": (
            "SOLVED_AND_FEEDBACK_GATE_PASSED"
            if preview.get("solutions") and gate["passed"]
            else "NO_FEASIBLE_LAYOUT"
            if solve_error
            else "FEEDBACK_GATE_REJECTED"
        ),
        "solveError": solve_error,
        "solutionCount": len(preview.get("solutions") or []),
        "feedbackMetadata": metadata,
        "directGeometryCalibration": direct_calibration_metadata,
        "directionalRepairOffsetsMeters": directional_offsets,
        "placementPriorityChanges": placement_priority_changes,
        "compatibilityGate": gate,
        "paths": {
            "feedback": str(feedback_path),
            "request": str(request_path),
            "preview": str(preview_path),
            "exactEvidence": str(args.exact_batch.resolve()),
            "structuralOccupancy": str(args.structural_occupancy.resolve()),
            "warmStart": str(args.warm_start.resolve()),
            "directGeometryCalibration": (
                str(calibration_path) if direct_calibration is not None else None
            ),
        },
        "timing": {
            "solveSeconds": solve_seconds,
            "totalSeconds": time.perf_counter() - clock,
        },
    }
    write(report_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["success"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
