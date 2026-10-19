#!/usr/bin/env python3
"""Finalize the Project 03 full static assembly and collision evidence chain."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from capture_leaf_interference_details import (  # noqa: E402
    baseline_acceptance,
    module_pair_key,
)


DEFAULT_DIR = ROOT / "demo/semantic_ports/project03_full_hybrid_static_v1"
PROTOTYPE_DIR = DEFAULT_DIR / "prototype_installation_baseline"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def integrity_manifest(paths: list[Path]) -> dict[str, Any]:
    unique = list(dict.fromkeys(path.resolve() for path in paths))
    return {
        "algorithm": "sha256",
        "artifactCount": len(unique),
        "artifacts": [
            {
                "path": str(path),
                "sizeBytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in unique
        ],
        "reuseRule": (
            "Reuse this static closure only while every registered artifact exists "
            "with the same SHA-256. Any assembly, pose, exact-check, baseline, or "
            "official-confirmation change invalidates the closure."
        ),
    }


def exact_rows(payload: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        module_pair_key(*row["pair"]): row
        for row in payload.get("exactChecks", [])
    }


def positive_count(result: dict[str, Any]) -> int:
    return int(
        result.get(
            "InterferingBodyPairCount",
            result.get("interferingBodyPairCount", 0),
        )
        or 0
    )


def build_closure(
    *,
    broadphase: dict[str, Any],
    exact: dict[str, Any],
    insertion: dict[str, Any],
    context_comparison: dict[str, Any],
    baselines: dict[tuple[str, str], tuple[dict[str, Any], str]],
    candidate_fallbacks: dict[tuple[str, str], tuple[dict[str, Any], str]],
    baseline_fallbacks: dict[tuple[str, str], tuple[dict[str, Any], str]],
    candidate_confirmations: dict[
        tuple[str, str], tuple[dict[str, Any], dict[str, Any], str]
    ] | None = None,
) -> dict[str, Any]:
    candidate_confirmations = candidate_confirmations or {}
    rows = exact_rows(exact)
    comparisons: list[dict[str, Any]] = []
    unresolved: list[list[str]] = []
    new_interference: list[list[str]] = []
    positive_pairs: list[list[str]] = []

    for key, row in sorted(rows.items()):
        pair = list(row["pair"])
        result = row["result"]
        if positive_count(result) > 0:
            positive_pairs.append(pair)
        baseline_entry = baselines.get(key)
        candidate_fallback_entry = candidate_fallbacks.get(key)
        baseline_fallback_entry = baseline_fallbacks.get(key)
        acceptance = baseline_acceptance(
            result,
            baseline_entry[0] if baseline_entry else None,
            candidate_fallback=(
                candidate_fallback_entry[0] if candidate_fallback_entry else None
            ),
            baseline_fallback=(
                baseline_fallback_entry[0] if baseline_fallback_entry else None
            ),
        )
        confirmation_entry = candidate_confirmations.get(key)
        if confirmation_entry:
            request, confirmation, confirmation_path = confirmation_entry
            confirmation_rows = confirmation.get("results", [])
            requested_count = int(
                request.get("requestedLeafComponentPairCount", 0) or 0
            )
            confirmation_complete = (
                confirmation.get("success") is True
                and requested_count > 0
                and len(confirmation_rows) == requested_count
                and all(row.get("success") is True for row in confirmation_rows)
            )
            confirmed_positive = [
                row for row in confirmation_rows if row.get("hasInterference") is True
            ]
            provisional_added = list(acceptance.get("addedInterferingPairs", []))
            acceptance["officialCandidateConfirmation"] = {
                "complete": confirmation_complete,
                "requestedLeafComponentPairCount": requested_count,
                "completedLeafComponentPairCount": len(confirmation_rows),
                "confirmedInterferingLeafComponentPairCount": len(
                    confirmed_positive
                ),
                "provisionalAddedInterferingPairs": provisional_added,
                "resultPath": confirmation_path,
            }
            if confirmation_complete and not confirmed_positive and provisional_added:
                acceptance["addedInterferingPairs"] = []
                acceptance["accepted"] = (
                    acceptance.get("effectiveExactCheckComplete") is True
                    and (
                        baseline_entry is None
                        or acceptance.get("baselineEffectiveExactCheckComplete") is True
                    )
                )
        if acceptance.get("effectiveExactCheckComplete") is not True:
            unresolved.append(pair)
        if acceptance.get("accepted") is not True:
            new_interference.append(pair)
        comparisons.append(
            {
                "pair": pair,
                "candidateIndex": row.get("candidateIndex"),
                "candidateInterferingBodyPairCount": positive_count(result),
                "classification": (
                    "PROTOTYPE_BASELINE_NO_NEW_INTERFERENCE"
                    if baseline_entry and acceptance.get("accepted") is True
                    else "ZERO_INTERFERENCE"
                    if not baseline_entry and acceptance.get("accepted") is True
                    else "REJECTED_OR_UNRESOLVED"
                ),
                "acceptance": acceptance,
                "evidence": {
                    "prototypeBaseline": baseline_entry[1] if baseline_entry else None,
                    "candidateFallback": (
                        candidate_fallback_entry[1]
                        if candidate_fallback_entry
                        else None
                    ),
                    "prototypeFallback": (
                        baseline_fallback_entry[1]
                        if baseline_fallback_entry
                        else None
                    ),
                    "candidateOfficialConfirmation": (
                        confirmation_entry[2] if confirmation_entry else None
                    ),
                },
                "timing": row.get("timing"),
            }
        )

    pair_count = int(exact.get("allTopLevelPairCount", 0) or 0)
    aabb_count = int(exact.get("aabbProvenPairCount", 0) or 0)
    exact_count = len(rows)
    coverage_complete = pair_count == aabb_count + exact_count
    insertion_success = bool(
        insertion.get("success", insertion.get("Success")) is True
    )
    context_error = context_comparison.get(
        "maximumTransformElementError",
        context_comparison.get("maxTransformAbsError"),
    )
    stable_context = (
        context_comparison.get("stable") is True
        and context_error is not None
        and float(context_error) <= 1e-9
    )
    success = (
        insertion_success
        and stable_context
        and coverage_complete
        and not unresolved
        and not new_interference
    )
    exact_duration = float(
        exact.get("timing", {}).get(
            "totalDurationSeconds",
            exact.get("timing", {}).get("durationSeconds", 0.0),
        )
        or 0.0
    )
    baseline_duration = 0.0
    for baseline, _ in baselines.values():
        baseline_duration += float(
            baseline.get("timing", {}).get("durationSeconds", 0.0) or 0.0
        )
    fallback_duration = sum(
        float(payload.get("durationSeconds", 0.0) or 0.0)
        for payload, _ in [
            *candidate_fallbacks.values(),
            *baseline_fallbacks.values(),
        ]
    )
    return {
        "schemaVersion": "project03-full-static-collision-closure/v1",
        "projectId": "project03",
        "status": (
            "PASSED_FULL_STATIC_GEOMETRY_NO_NEW_INTERFERENCE"
            if success
            else "FAILED_OR_INCOMPLETE"
        ),
        "success": success,
        "absoluteZeroInterference": not positive_pairs,
        "acceptancePolicy": (
            "Every top-level module pair must be AABB-proven separated or have "
            "effective complete exact evidence. Prototype-existing installation "
            "contacts are accepted only when the candidate adds no leaf contact."
        ),
        "scopeBoundary": {
            "staticGeometryClosed": success,
            "originalHierarchyReconstructed": False,
            "originalMateSemanticsReconstructed": False,
            "dynamicMotionValidated": False,
            "productionReleased": False,
        },
        "assembly": {
            "path": insertion.get(
                "outputAssemblyPath",
                insertion.get("targetAssemblyPath", insertion.get("assemblyPath")),
            ),
            "topLevelObjectCount": exact.get("componentCount"),
            "insertionSuccess": insertion_success,
            "contextStableAfterInsertion": stable_context,
            "maxContextTransformAbsError": context_error,
        },
        "coverage": {
            "topLevelPairCount": pair_count,
            "aabbProvenPairCount": aabb_count,
            "exactCandidatePairCount": exact_count,
            "effectiveExactCompletePairCount": exact_count - len(unresolved),
            "coverageComplete": coverage_complete and not unresolved,
            "unresolvedPairs": unresolved,
        },
        "collisionResult": {
            "prototypeExistingPositiveModulePairCount": len(positive_pairs),
            "prototypeExistingPositiveModulePairs": positive_pairs,
            "newInterferenceModulePairCount": len(new_interference),
            "newInterferenceModulePairs": new_interference,
            "pairComparisons": comparisons,
        },
        "timingSeconds": {
            "finalInsertion": insertion.get("durationSeconds"),
            "candidateExact": exact_duration,
            "prototypeBaselinesUsed": baseline_duration,
            "officialFallbacksUsed": fallback_duration,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_DIR / "interference_closure.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    broadphase_path = DEFAULT_DIR / "interference_broadphase.json"
    exact_path = DEFAULT_DIR / "interference_exact.json"
    insertion_path = DEFAULT_DIR / "project03_full_10_object_hybrid_static_v1.result.json"
    context_path = DEFAULT_DIR / "context_pose_comparison.json"

    baseline_paths = {
        module_pair_key("FL9A24D063AD00.001-1", "FL9A24D063AE00.001-1"):
            ROOT / "demo/interference_project03_prototype/conditional_hits/FL9A24D063A000.001_leaf_details_FL9A24D063AE00_FL9A24D063AD00.json",
        module_pair_key("FL9A24D063AA00.001-1", "FL9A24D063AI00.001-1"):
            PROTOTYPE_DIR / "FL9A24D063A000.001_leaf_details_FL9A24D063AA00_FL9A24D063AI00.json",
        module_pair_key("FL9A24D063AA00.001-1", "FL9A24D063AE00.001-1"):
            PROTOTYPE_DIR / "FL9A24D063A000.001_leaf_details_FL9A24D063AA00_FL9A24D063AE00.json",
        module_pair_key("FL9A24D063AA00.001-1", "FL9A24D063AD00.001-1"):
            PROTOTYPE_DIR / "FL9A24D063A000.001_leaf_details_FL9A24D063AA00_FL9A24D063AD00.json",
        module_pair_key("FL9A24D063AA00.001-1", "FL9A24D063AJ00.001-1"):
            PROTOTYPE_DIR / "FL9A24D063A000.001_leaf_details_FL9A24D063AA00_FL9A24D063AJ00.json",
        module_pair_key("FL9A24D063AA00.001-1", "FL9A24D063AB00.001-1"):
            PROTOTYPE_DIR / "FL9A24D063A000.001_leaf_details_FL9A24D063AA00_FL9A24D063AB00.json",
    }
    candidate_fallback_paths = {
        module_pair_key("FL9A24D063AA00.001-1", "FL9A24D063AE00.001-1"):
            DEFAULT_DIR / "fallback_candidate_AA00_AE00.json",
    }
    baseline_fallback_paths = {
        module_pair_key("FL9A24D063AA00.001-1", "FL9A24D063AE00.001-1"):
            PROTOTYPE_DIR / "fallback_prototype_AA00_AE00.json",
        module_pair_key("FL9A24D063AA00.001-1", "FL9A24D063AJ00.001-1"):
            PROTOTYPE_DIR / "fallback_prototype_AA00_AJ00.json",
    }
    candidate_confirmation_paths = {
        module_pair_key("FL9A24D063AA00.001-1", "FL9A24D063AE00.001-1"): (
            DEFAULT_DIR / "official_confirm_candidate_new_AA00_AE00.request.json",
            DEFAULT_DIR / "official_confirm_candidate_new_AA00_AE00.result.json",
        ),
        module_pair_key("FL9A24D063AA00.001-1", "FL9A24D063AJ00.001-1"): (
            DEFAULT_DIR / "official_confirm_candidate_new_AA00_AJ00.request.json",
            DEFAULT_DIR / "official_confirm_candidate_new_AA00_AJ00.result.json",
        ),
    }
    required = [
        broadphase_path,
        exact_path,
        insertion_path,
        context_path,
        *baseline_paths.values(),
        *candidate_fallback_paths.values(),
        *baseline_fallback_paths.values(),
        *[path for paths in candidate_confirmation_paths.values() for path in paths],
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing closure evidence:\n" + "\n".join(missing))

    payload = build_closure(
        broadphase=load(broadphase_path),
        exact=load(exact_path),
        insertion=load(insertion_path),
        context_comparison=load(context_path),
        baselines={key: (load(path), str(path)) for key, path in baseline_paths.items()},
        candidate_fallbacks={
            key: (load(path), str(path)) for key, path in candidate_fallback_paths.items()
        },
        baseline_fallbacks={
            key: (load(path), str(path)) for key, path in baseline_fallback_paths.items()
        },
        candidate_confirmations={
            key: (load(paths[0]), load(paths[1]), str(paths[1]))
            for key, paths in candidate_confirmation_paths.items()
        },
    )
    assembly_path = Path(str(payload["assembly"]["path"])).resolve()
    payload["integrity"] = integrity_manifest(
        [
            assembly_path,
            broadphase_path,
            exact_path,
            insertion_path,
            context_path,
            *baseline_paths.values(),
            *candidate_fallback_paths.values(),
            *baseline_fallback_paths.values(),
            *[path for paths in candidate_confirmation_paths.values() for path in paths],
        ]
    )
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "success": payload["success"],
                "status": payload["status"],
                "output": str(output),
            },
            ensure_ascii=False,
        )
    )
    return 0 if payload["success"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
