#!/usr/bin/env python3
"""Build the final Project 02 reconstruction/interference closure report."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from compare_reconstructed_interference_to_prototype import (  # noqa: E402
    expanded,
    leaf_pair_counter,
    module_pair_key,
)


RECONSTRUCTION = ROOT / "demo/mate_reconstruction_pipeline/non_source_minimal_anchor_v3_flex_reopen_fix/project02_mate_reconstruction_C_residual_anchors_v20_flex_reopen_fix.result.json"
FULL_V6 = ROOT / "demo/mate_reconstruction_pipeline/non_source_minimal_anchor_v1/project02_mate_reconstruction_C_residual_anchors_v6.interference.json"
FLEX_BATCH = ROOT / "demo/mate_reconstruction_pipeline/non_source_minimal_anchor_v3_flex_reopen_fix/targeted_interference/project02_mate_reconstruction_C_residual_anchors_v20_flex_reopen_fix_leaf_details_batch.json"
FALLBACK = ROOT / "demo/mate_reconstruction_pipeline/non_source_minimal_anchor_v3_flex_reopen_fix/A600_A800_failed_leaf_fallback.json"
OUTPUT = ROOT / "demo/mate_reconstruction_pipeline/non_source_minimal_anchor_v3_flex_reopen_fix/project02_mate_reconstruction_v20_interference_closure.json"

FLEXIBLE = {
    "FL9A24D062A100.001-1",
    "FL9A24D062A200.001-1",
    "FL9A24D062A700.001-1",
}

BASELINES = {
    module_pair_key("FL9A24D062A300.001-1", "FL9A24D062A800.001-1"): ROOT / "demo/interference_prototype_reference/FL9A24D062A000.001_leaf_details_A300_A800.json",
    module_pair_key("FL9A24D062A700.001-1", "FL9A24D062A800.001-1"): ROOT / "demo/interference_project02_prototype_reference_a800_a700/FL9A24D062A000.001_leaf_details_A800_A700.json",
    module_pair_key("FL9A24D062A500.001-1", "FL9A24D062A800.001-1"): ROOT / "demo/mate_reconstruction_pipeline/prototype_positive_pair_baseline_v1/FL9A24D062A000.001_leaf_details_A500_A800.json",
    module_pair_key("FL9A24D062A600.001-1", "T401AA-07388-0-2"): ROOT / "demo/mate_reconstruction_pipeline/prototype_positive_pair_baseline_v1/FL9A24D062A000.001_leaf_details_A600_T401AA-07388-0-2.json",
    module_pair_key("FL9A24D062A600.001-1", "FL9A24D062A700.001-1"): ROOT / "demo/mate_reconstruction_pipeline/prototype_positive_pair_baseline_v1/FL9A24D062A000.001_leaf_details_A600_A700.json",
    module_pair_key("FL9A24D062A600.001-1", "FL9A24D062A800.001-1"): ROOT / "demo/mate_reconstruction_pipeline/prototype_positive_pair_baseline_v1/FL9A24D062A000.001_leaf_details_A600_A800.json",
    module_pair_key("FL9A24D062A100.001-1", "FL9A24D062A600.001-1"): ROOT / "demo/mate_reconstruction_pipeline/prototype_positive_pair_baseline_v1/FL9A24D062A000.001_leaf_details_A100_A600.json",
    module_pair_key("FL9A24D062A200.001-1", "FL9A24D062A600.001-1"): ROOT / "demo/mate_reconstruction_pipeline/prototype_positive_pair_baseline_v1/FL9A24D062A000.001_leaf_details_A200_A600.json",
}


def pick(item: dict, pascal: str, camel: str):
    return item.get(pascal, item.get(camel))


def summary(result: dict) -> dict:
    return {
        "exactCheckComplete": pick(result, "ExactCheckComplete", "exactCheckComplete") is True,
        "failedBodyPairCount": int(pick(result, "FailedBodyPairCount", "failedBodyPairCount") or 0),
        "interferingBodyPairCount": int(pick(result, "InterferingBodyPairCount", "interferingBodyPairCount") or 0),
    }


def main() -> int:
    reconstruction = json.loads(RECONSTRUCTION.read_text(encoding="utf-8-sig"))
    full = json.loads(FULL_V6.read_text(encoding="utf-8-sig"))
    flex_batch = json.loads(FLEX_BATCH.read_text(encoding="utf-8-sig"))
    fallback = json.loads(FALLBACK.read_text(encoding="utf-8-sig"))

    rigid_results = {
        module_pair_key(*row["pair"]): (row["pair"], row["result"], str(FULL_V6), "reused-rigid-v6")
        for row in full["exactChecks"]
    }
    flex_results = {}
    for row in flex_batch["pairs"]:
        pair = list(row["pair"])
        path = Path(row["outputPath"])
        flex_results[module_pair_key(*pair)] = (pair, json.loads(path.read_text(encoding="utf-8-sig")), str(path), "v20-flexible-recheck")

    candidate_keys = {module_pair_key(*row["pair"]): list(row["pair"]) for row in full["broadPhase"] if row["requiresExactLeafBrep"]}
    evidence = {}
    for key, pair in candidate_keys.items():
        evidence[key] = flex_results[key] if any(name in FLEXIBLE for name in pair) else rigid_results[key]

    comparisons = []
    positive_pairs = []
    unresolved = []
    for key, (pair, result, result_path, evidence_kind) in sorted(evidence.items()):
        result_summary = summary(result)
        fallback_resolved = False
        if not result_summary["exactCheckComplete"] and key == module_pair_key("FL9A24D062A600.001-1", "FL9A24D062A800.001-1"):
            fallback_resolved = (
                fallback.get("success") is True
                and fallback.get("completedFallbackPairCount") == result_summary["failedBodyPairCount"]
            )
        if not result_summary["exactCheckComplete"] and not fallback_resolved:
            unresolved.append(pair)
        if result_summary["interferingBodyPairCount"] <= 0:
            continue
        positive_pairs.append(pair)
        baseline_path = BASELINES.get(key)
        if baseline_path is None:
            comparisons.append({"pair": pair, "status": "MISSING_PROTOTYPE_BASELINE", "addedMultiplicity": None})
            continue
        baseline = json.loads(baseline_path.read_text(encoding="utf-8-sig"))
        added = leaf_pair_counter(result) - leaf_pair_counter(baseline)
        missing = leaf_pair_counter(baseline) - leaf_pair_counter(result)
        comparisons.append(
            {
                "pair": pair,
                "status": "NO_NEW_INTERFERENCE" if not added else "NEW_INTERFERENCE_DETECTED",
                "evidenceKind": evidence_kind,
                "targetResultPath": result_path,
                "prototypeResultPath": str(baseline_path),
                "target": result_summary,
                "prototype": summary(baseline),
                "addedMultiplicity": sum(added.values()),
                "missingMultiplicity": sum(missing.values()),
                "addedLeafComponentPairs": expanded(added),
                "missingLeafComponentPairs": expanded(missing),
                "fallbackResolvedFailedPairs": fallback_resolved,
            }
        )

    new_interference = [row for row in comparisons if (row.get("addedMultiplicity") or 0) > 0]
    missing_baselines = [row for row in comparisons if row["status"] == "MISSING_PROTOTYPE_BASELINE"]
    pair_count = int(full["allTopLevelPairCount"])
    aabb_count = int(full["aabbProvenPairCount"])
    exact_count = len(evidence)
    coverage_complete = pair_count == aabb_count + exact_count
    success = (
        reconstruction.get("Success") is True
        and coverage_complete
        and not unresolved
        and not new_interference
        and not missing_baselines
    )
    payload = {
        "schemaVersion": "project02-mate-reconstruction-interference-closure/v1",
        "status": "PASSED_NO_NEW_INTERFERENCE_RELATIVE_TO_PROTOTYPE" if success else "FAILED",
        "success": success,
        "absoluteZeroInterference": not positive_pairs,
        "acceptancePolicy": "No reconstructed leaf interference may be added beyond the prototype baseline; prototype-existing installation/interpenetration pairs are reported, not hidden.",
        "reconstruction": {
            "resultPath": str(RECONSTRUCTION),
            "success": reconstruction.get("Success"),
            "moduleCount": reconstruction.get("SourceModuleCount"),
            "createdMateCount": reconstruction.get("CreatedMateCount"),
            "reopenedMateCount": reconstruction.get("ReopenedMateCount"),
            "poseMatchCount": reconstruction.get("PoseMatchCount"),
            "timing": reconstruction.get("RunTiming"),
        },
        "coverage": {
            "topLevelPairCount": pair_count,
            "aabbProvenSeparatedOrContactOnlyCount": aabb_count,
            "exactCandidatePairCount": exact_count,
            "v20FlexiblePairRecheckCount": len(flex_results),
            "reusedRigidPairResultCount": exact_count - len(flex_results),
            "fallbackResolvedLeafPairCount": fallback.get("completedFallbackPairCount"),
            "complete": coverage_complete and not unresolved,
            "unresolvedPairs": unresolved,
        },
        "prototypeExistingInterferencePairCount": len(positive_pairs),
        "prototypeExistingInterferencePairs": positive_pairs,
        "newInterferencePairCount": len(new_interference),
        "newInterferencePairs": [row["pair"] for row in new_interference],
        "baselineComparisons": comparisons,
        "evidence": {
            "broadPhaseAndRigidExact": str(FULL_V6),
            "v20FlexibleExactBatch": str(FLEX_BATCH),
            "failedLeafFallback": str(FALLBACK),
        },
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"success": success, "status": payload["status"], "pairCount": pair_count, "newInterferencePairCount": len(new_interference), "output": str(OUTPUT)}, ensure_ascii=False))
    return 0 if success else 2


if __name__ == "__main__":
    raise SystemExit(main())
