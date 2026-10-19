#!/usr/bin/env python3
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

from demo_backend.layout_preview import apply_project02_solve_profile, solve_case_preview
from demo_backend.project02_ablation import (
    VARIANTS,
    build_ablation_request,
    build_frozen_baseline_manifest,
    build_geometry_only_occupancy,
    compare_rank1_poses,
    evaluate_reference_preview_interactions,
)


REQUEST_PATH = ROOT / "demo/FL9A24D062A000_real_process_request.json"
REFERENCE_PREVIEW_PATH = ROOT / "demo/layout_previews/project02_preview.json"
OUTPUT_DIR = ROOT / "demo/layout_previews/project02_dependency_ablation"
REPORT_PATH = ROOT / "demo/layout_previews/project02_dependency_ablation_report.json"
FROZEN_PATH = ROOT / "demo/layout_previews/project02_v22_frozen_baseline_manifest.json"
GEOMETRY_OCCUPANCY_PATH = OUTPUT_DIR / "project02_geometry_only_occupancy_v1.json"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run or refresh the Project02 dependency-ablation report."
    )
    parser.add_argument(
        "--reuse-experiments",
        action="store_true",
        help=(
            "Reuse the existing A/B/C solve rows while refreshing frozen hashes, "
            "geometry occupancy and the reference-pose geometry audit."
        ),
    )
    parser.add_argument(
        "--variants",
        nargs="+",
        choices=VARIANTS,
        default=list(VARIANTS),
        help="Run only the selected ablation variants (for example: --variants B C).",
    )
    args = parser.parse_args()
    base_request = json.loads(REQUEST_PATH.read_text(encoding="utf-8"))
    reference_preview = json.loads(REFERENCE_PREVIEW_PATH.read_text(encoding="utf-8-sig"))
    geometry_path = ROOT / str(base_request["geometryCapturePath"])
    geometry = json.loads(geometry_path.read_text(encoding="utf-8"))
    capture_specs = [
        (
            ROOT / "demo/FL9A24D062A000_interaction_v8_leaf_body_envelopes.json",
            ROOT / "demo/FL9A24D062A000_interaction_v8_replay_result.json",
        ),
        (
            ROOT / "demo/FL9A24D062A800_leaf_body_envelopes.json",
            geometry_path,
        ),
        (
            ROOT / "demo/FL9A24D062A000_prototype_A300_A800_leaf_body_envelopes_v15.json",
            geometry_path,
        ),
        (
            ROOT / "demo/FL9A24D062A000_v16_T401_leaf_body_envelopes.json",
            ROOT / "demo/FL9A24D062A000_joint_v16_replay_result.json",
        ),
    ]
    capture_documents = [
        (
            json.loads(capture_path.read_text(encoding="utf-8")),
            json.loads(layout_path.read_text(encoding="utf-8")),
            str(capture_path),
        )
        for capture_path, layout_path in capture_specs
    ]
    geometry_occupancy = build_geometry_only_occupancy(geometry, capture_documents)
    GEOMETRY_OCCUPANCY_PATH.parent.mkdir(parents=True, exist_ok=True)
    GEOMETRY_OCCUPANCY_PATH.write_text(
        json.dumps(geometry_occupancy, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    geometry_reference_request, _ = build_ablation_request(
        base_request,
        "B",
        geometry_occupancy_path=str(GEOMETRY_OCCUPANCY_PATH),
    )
    geometry_reference_request, _ = apply_project02_solve_profile(
        geometry_reference_request,
        "reduced-prototype",
    )
    reference_geometry_validation = evaluate_reference_preview_interactions(
        ROOT,
        geometry_reference_request,
        geometry,
        reference_preview,
    )
    frozen_paths = [
        ROOT / "demo/layout_previews/project02_v22_full_leaf_a100_a300_selected.json",
        ROOT / "demo/layout_previews/project02_v22_incremental_brep_closure.json",
        ROOT / "demo/FL9A24D062A000_9modules_direct_solved_v22_full_leaf_candidate.SLDASM",
        ROOT / "demo/FL9A24D062A000_structural_occupancy_v42.json",
    ]
    missing = [str(path) for path in frozen_paths if not path.is_file()]
    if missing:
        raise SystemExit("Cannot freeze Project02 v22; missing: " + ", ".join(missing))
    FROZEN_PATH.write_text(
        json.dumps(build_frozen_baseline_manifest(frozen_paths), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    previous_report = None
    if REPORT_PATH.is_file():
        previous_report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    selected_variants = tuple(args.variants)
    previous_experiments = list((previous_report or {}).get("experiments") or [])
    if args.reuse_experiments and len(previous_experiments) != len(VARIANTS):
        raise SystemExit(
            "--reuse-experiments requires an existing report with all A/B/C rows"
        )
    experiments = previous_experiments if args.reuse_experiments else [
        item
        for item in previous_experiments
        if item.get("variant") not in selected_variants
    ]
    for variant in (() if args.reuse_experiments else selected_variants):
        request, metadata = build_ablation_request(
            base_request,
            variant,
            geometry_occupancy_path=str(GEOMETRY_OCCUPANCY_PATH),
        )
        request_path = OUTPUT_DIR / f"variant_{variant.lower()}_request.json"
        preview_path = OUTPUT_DIR / f"variant_{variant.lower()}_preview.json"
        request_path.write_text(
            json.dumps(request, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        started = time.perf_counter()
        try:
            preview = solve_case_preview(
                ROOT,
                "project02",
                persist=False,
                profile="reduced-prototype",
                request_override=request,
            )
            duration = time.perf_counter() - started
            preview_path.write_text(
                json.dumps(preview, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            rank1 = (preview.get("solutions") or [{}])[0]
            metrics = preview.get("metrics") or {}
            experiments.append(
                {
                    **metadata,
                    "success": bool((preview.get("solutions") or []) and metrics.get("hardFeasible")),
                    "durationSeconds": duration,
                    "requestPath": str(request_path),
                    "previewPath": str(preview_path),
                    "solutionCount": len(preview.get("solutions") or []),
                    "rank1Score": rank1.get("score"),
                    "rank1PredictedConditionalBrepPairCount": rank1.get(
                        "predictedConditionalBrepPairCount"
                    ),
                    "rank1PredictedConditionalLeafAabbHitCount": rank1.get(
                        "predictedConditionalLeafAabbHitCount"
                    ),
                    "hardConstraintMetrics": metrics,
                    "rank1DifferenceFromV22": compare_rank1_poses(preview, reference_preview),
                    "jointSearchDiagnostics": (
                        preview.get("jointSearchSummary") or {}
                    ),
                }
            )
        except Exception as exc:
            experiments.append(
                {
                    **metadata,
                    "success": False,
                    "durationSeconds": time.perf_counter() - started,
                    "requestPath": str(request_path),
                    "previewPath": None,
                    "error": f"{type(exc).__name__}: {exc}",
                    "jointSearchDiagnostics": getattr(exc, "report", None),
                }
            )

    experiments.sort(
        key=lambda item: VARIANTS.index(item.get("variant"))
        if item.get("variant") in VARIANTS
        else len(VARIANTS)
    )

    candidates = [
        item
        for item in experiments
        if item.get("success")
        and (item.get("rank1DifferenceFromV22") or {}).get("materiallyDifferent")
    ]
    candidates.sort(
        key=lambda item: (
            int(item.get("rank1PredictedConditionalLeafAabbHitCount") or 0),
            int(item.get("rank1PredictedConditionalBrepPairCount") or 0),
            float(item.get("rank1Score") or 0.0),
        )
    )
    recommended_for_visual_review = candidates[0]["variant"] if candidates else None
    report = {
        "schemaVersion": "project02-dependency-ablation/v3",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "profile": "reduced-prototype",
        "referencePreviewPath": str(REFERENCE_PREVIEW_PATH),
        "frozenBaselineManifestPath": str(FROZEN_PATH),
        "geometryOnlyOccupancyPath": str(GEOMETRY_OCCUPANCY_PATH),
        "geometryOnlyOccupancyBoxCount": sum(
            int(item.get("boxCount") or 0)
            for item in geometry_occupancy.get("components", {}).values()
        ),
        "referenceV22UnderGeometryOnlyValidation": reference_geometry_validation,
        "currentSelectionWasNotModified": True,
        "solveRowsReused": bool(args.reuse_experiments),
        "solidWorksWasNotUsed": True,
        "brepWasNotUsed": True,
        "experiments": experiments,
        "recommendedVariantForVisualReview": recommended_for_visual_review,
        "recommendedVariantForCadValidation": None,
        "cadValidationBlockedPendingVisualApproval": bool(recommended_for_visual_review),
        "recommendationReason": (
            "Among materially different hard-feasible rank-1 candidates, select the lowest "
            "predicted leaf-AABB/conditional-B-Rep risk for visual review first; CAD validation "
            "remains blocked until direction, boundary and obvious contact are approved."
            if recommended_for_visual_review
            else "No materially different hard-feasible rank-1 was found; do not enter CAD yet."
        ),
    }
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "success": all(item.get("success") for item in experiments),
                "reportPath": str(REPORT_PATH),
                "recommendedVariantForVisualReview": recommended_for_visual_review,
                "recommendedVariantForCadValidation": None,
                "experiments": [
                    {
                        "variant": item["variant"],
                        "success": item.get("success"),
                        "durationSeconds": item.get("durationSeconds"),
                        "solutionCount": item.get("solutionCount"),
                        "rank1Score": item.get("rank1Score"),
                        "maxDeltaMeters": (item.get("rank1DifferenceFromV22") or {}).get(
                            "maximumCenterDistanceMeters"
                        ),
                        "error": item.get("error"),
                    }
                    for item in experiments
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
