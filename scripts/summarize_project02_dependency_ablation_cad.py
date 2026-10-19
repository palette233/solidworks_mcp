#!/usr/bin/env python3
"""Summarize solve, CAD preparation and direct-build timings for B/C."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CAD_DIR = ROOT / "demo/layout_previews/project02_dependency_ablation/cad"
OUTPUT = CAD_DIR / "project02_dependency_ablation_cad_timing_summary.json"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def optional_json(path: Path) -> Any | None:
    return read_json(path) if path.is_file() else None


def grouped_tool_timings(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups = {
        "connect-solidworks": {"solid_works_connect"},
        "create-or-clone-assembly": {
            "initialize_common_base_assembly",
            "save_document_as",
        },
        "apply-final-orientation-and-translation": {
            "set_component_orientation",
            "move_component",
        },
        "component-and-pose-audit": {
            "list_components",
            "list_component_poses",
            "get_active_document_rebuild_state",
        },
        "force-rebuild": {"force_rebuild_active_document"},
        "save-close-reopen": {"save_document", "close_document", "open_document"},
        "export-review-images": {
            "export_current_view_png",
            "export_standard_view_png_set",
        },
    }
    rows = []
    for name, tools in groups.items():
        matching = [item for item in steps if item.get("tool") in tools]
        rows.append(
            {
                "name": name,
                "durationSeconds": round(
                    sum(float((item.get("timing") or {}).get("durationSeconds") or 0.0) for item in matching),
                    6,
                ),
                "toolCallCount": len(matching),
                "tools": [item.get("tool") for item in matching],
            }
        )
    return sorted(rows, key=lambda item: item["durationSeconds"], reverse=True)


def main() -> int:
    ablation = read_json(
        ROOT / "demo/layout_previews/project02_dependency_ablation_report.json"
    )
    solve_rows = {
        item["variant"]: item for item in ablation.get("experiments") or []
    }
    internal_review = read_json(CAD_DIR / "internal_review_views_result.json")
    internal_review_rows = {
        item["variant"]: item for item in internal_review.get("results") or []
    }
    variants = []
    for variant in ("B", "C"):
        lower = variant.lower()
        prepare = read_json(CAD_DIR / f"variant_{lower}_rank1_cad_prepare_result.json")
        build = read_json(CAD_DIR / f"variant_{lower}_rank1_direct_build_result.json")
        screening = read_json(CAD_DIR / f"variant_{lower}_rank1_world_aabb_screening.json")
        functional_brep_path = (
            ROOT
            / f"demo/interference_dependency_{variant}_rank1_20260908/functional_pairs"
            / f"FL9A24D062A000_dependency_{variant}_rank1_direct_20260908_leaf_details_batch.json"
        )
        functional_brep = optional_json(functional_brep_path)
        review = internal_review_rows.get(variant) or {}
        solve_seconds = float(solve_rows[variant]["durationSeconds"])
        prepare_seconds = float(prepare["timing"]["durationSeconds"])
        cad_seconds = float(build["timing"]["durationSeconds"])
        assembly_path = Path(build["targetAssemblyPath"])
        variants.append(
            {
                "variant": variant,
                "solutionRank": 1,
                "success": bool(build.get("success")),
                "generationMode": build.get("generationMode"),
                "prototypeAssemblyCopied": bool(build.get("prototypeAssemblyCopied")),
                "replayLayoutToolUsed": bool(build.get("replayLayoutToolUsed")),
                "orientationChangedComponents": prepare.get("orientationChangedComponents") or [],
                "assemblyPath": str(assembly_path),
                "assemblyBytes": assembly_path.stat().st_size if assembly_path.is_file() else None,
                "screenshotPath": build.get("screenshotPath"),
                "internalReviewScreenshotPath": review.get("outputPath"),
                "savedPosePath": build.get("savedPosePath"),
                "fullyRebuilt": (build.get("rebuildState") or {}).get("RawStatus") == 0,
                "topLevelAuditPassed": bool((build.get("reopenedTopLevelAudit") or {}).get("success")),
                "poseAuditPassed": bool((build.get("reopenedPoseAudit") or {}).get("success")),
                "phaseTimings": [
                    {
                        "name": "constraint-solve",
                        "durationSeconds": solve_seconds,
                        "source": "project02_dependency_ablation_report.json",
                    },
                    {
                        "name": "candidate-materialization-and-3d-pose-projection",
                        "durationSeconds": prepare_seconds,
                        "source": prepare.get("timing", {}).get("runId"),
                    },
                    {
                        "name": "solidworks-direct-build-save-reopen-verify-and-export",
                        "durationSeconds": cad_seconds,
                        "source": build.get("timing", {}).get("runId"),
                    },
                ],
                "recordedEndToEndSeconds": round(
                    solve_seconds + prepare_seconds + cad_seconds, 6
                ),
                "worldAabbScreening": {
                    "durationSeconds": (screening.get("timing") or {}).get("durationSeconds"),
                    "pairCount": screening.get("pairCount"),
                    "strictAabbPairCount": screening.get("strictAabbPairCount"),
                    "strictAabbFailureCount": screening.get("strictAabbFailureCount"),
                    "strictAabbFailurePairs": [
                        item.get("components")
                        for item in screening.get("diagnostics") or []
                        if item.get("collisionPolicy") == "strict_aabb"
                        and not item.get("success")
                    ],
                    "needsExactBrepCheckCount": screening.get("needsExactBrepCheckCount"),
                    "excludedBy3dAabbCount": screening.get("excludedBy3dAabbCount"),
                    "installationContactReviewCount": screening.get("installationContactReviewCount"),
                    "eligibleForConditionalBrep": (
                        int(screening.get("strictAabbFailureCount") or 0) == 0
                    ),
                },
                "functionalModuleExactBrep": (
                    {
                        "resultPath": str(functional_brep_path),
                        "durationSeconds": (functional_brep.get("timing") or {}).get(
                            "durationSeconds"
                        ),
                        "requestedPairCount": functional_brep.get("requestedPairCount"),
                        "completedPairCount": functional_brep.get("completedPairCount"),
                        "acceptedPairCount": functional_brep.get("acceptedPairCount"),
                        "hardFailureCount": functional_brep.get("hardFailureCount"),
                        "pairs": [
                            {
                                "components": item.get("pair"),
                                "hasInterference": item.get("hasInterference"),
                                "interferingBodyPairCount": item.get(
                                    "interferingBodyPairCount"
                                ),
                                "failedBodyPairCount": item.get("failedBodyPairCount"),
                                "exactCheckComplete": item.get("exactCheckComplete"),
                                "accepted": (item.get("acceptance") or {}).get("accepted"),
                                "durationSeconds": (item.get("timing") or {}).get(
                                    "durationSeconds"
                                ),
                            }
                            for item in functional_brep.get("pairs") or []
                        ],
                    }
                    if functional_brep is not None
                    else None
                ),
                "cadToolTimingRanking": grouped_tool_timings(build.get("steps") or []),
                "toolTimeline": [
                    {
                        "tool": item.get("tool"),
                        "startedAtUtc": (item.get("timing") or {}).get("startedAtUtc"),
                        "finishedAtUtc": (item.get("timing") or {}).get("finishedAtUtc"),
                        "durationSeconds": (item.get("timing") or {}).get("durationSeconds"),
                        "businessFailed": item.get("businessFailed"),
                    }
                    for item in build.get("steps") or []
                ],
            }
        )

    report = {
        "success": all(item["success"] for item in variants),
        "schemaVersion": 3,
        "kind": "project02-dependency-ablation-b-c-cad-timing-summary",
        "solidWorksRecovery": {
            "rootCause": (
                "Two stale windowless SLDWORKS processes were present; a stale "
                "SolidWorksMcpApp --headless-hub respawned an -Embedding instance."
            ),
            "remediation": (
                "Terminated the two exact windowless processes and the stale headless hub, "
                "then launched one visible SolidWorks 2024 SP5 session."
            ),
            "healthVerification": (
                "MCP reused the visible current-session COM server; certified 2024 baseline, "
                "Premium license, 123 tools."
            ),
            "initialBuildAttempt": {
                "status": "failed-before-cad-mutation-completed",
                "durationSeconds": 48.242909,
                "failedTool": "initialize_common_base_assembly",
                "interpretation": (
                    "Transient first initialization after session recovery; no target assembly "
                    "was left on disk. The instrumented retry succeeded."
                ),
            },
        },
        "variants": variants,
        "comparison": {
            "blankBuildVariant": "B",
            "incrementalVariant": "C",
            "cadSecondsSavedByIncrementalUpdate": round(
                variants[0]["phaseTimings"][2]["durationSeconds"]
                - variants[1]["phaseTimings"][2]["durationSeconds"],
                6,
            ),
            "cadRelativeReduction": round(
                1.0
                - variants[1]["phaseTimings"][2]["durationSeconds"]
                / variants[0]["phaseTimings"][2]["durationSeconds"],
                6,
            ),
            "interpretation": (
                "C reuses the independently generated B module set and saves it as a distinct "
                "assembly before applying C poses. This measures fast candidate switching, not "
                "a second blank-assembly insertion benchmark."
            ),
        },
        "validationBoundary": {
            "shared": (
                "Both assemblies passed save/reopen pose and rebuild checks. Exact leaf-body "
                "B-Rep was subsequently executed for the priority functional-module pairs; "
                "this is not a complete check of every conditional pair in either assembly."
            ),
            "B": (
                "A180 versus A700 has zero exact body interference, but it still violates the "
                "configured 20 mm strict engineering clearance. B remains rejected by the "
                "clearance policy rather than by literal body penetration."
            ),
            "C": (
                "Six functional-module pairs were checked exactly. A180-A200, A300-A700 and "
                "A500-A700 contain 5, 57 and 34 interfering leaf-body pairs respectively. "
                "C is rejected and must return to constraint/pose generation; the remaining "
                "conditional pairs need not be checked before that correction."
            ),
        },
    }
    OUTPUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
