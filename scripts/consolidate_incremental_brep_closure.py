#!/usr/bin/env python3
"""Consolidate current and reusable exact B-Rep evidence into one closure report."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


def canonical_pair(values: list[str]) -> tuple[str, str]:
    if len(values) != 2:
        raise ValueError(f"Expected two component names, got {values!r}")
    return tuple(sorted(str(value) for value in values))


def read_json(path: Path) -> Any:
    return json.loads(path.resolve().read_text(encoding="utf-8"))


def pose_mapping(payload: Any) -> dict[str, dict[str, Any]]:
    rows = payload if isinstance(payload, list) else payload.get("components")
    if not isinstance(rows, list):
        for step in payload.get("steps") or []:
            if step.get("tool") == "list_component_poses":
                rows = step.get("payload")
                break
    if not isinstance(rows, list):
        raise ValueError("Pose artifact contains no component pose array.")
    return {str(row["Name"]): row for row in rows}


def dot(first: list[float], second: list[float]) -> float:
    return sum(float(a) * float(b) for a, b in zip(first, second, strict=True))


def pair_signature(first: dict[str, Any], second: dict[str, Any]) -> list[float]:
    first_axes = [[float(value) for value in first[name]] for name in ("XAxis", "YAxis", "ZAxis")]
    second_axes = [[float(value) for value in second[name]] for name in ("XAxis", "YAxis", "ZAxis")]
    delta = [
        float(first["Translation"][index]) - float(second["Translation"][index])
        for index in range(3)
    ]
    return [
        *(dot(first_axis, second_axis) for first_axis in first_axes for second_axis in second_axes),
        *(dot(delta, axis) for axis in second_axes),
    ]


def pair_values(item: dict[str, Any]) -> list[str]:
    values = item.get("pair", item.get("Components"))
    if not isinstance(values, list):
        raise ValueError(f"B-Rep pair row contains no pair: {item!r}")
    return [str(value) for value in values]


def exact_acceptance(item: dict[str, Any]) -> tuple[bool, str]:
    complete = item.get("exactCheckComplete", item.get("ExactCheckComplete")) is True
    interference = item.get("hasInterference", item.get("HasInterference")) is True
    failed = int(item.get("failedBodyPairCount", item.get("FailedBodyPairCount", 0)) or 0)
    acceptance = item.get("acceptance", item.get("Acceptance")) or {}
    accepted_baseline = acceptance.get("accepted", acceptance.get("Accepted")) is True
    if not complete or failed:
        return False, "incomplete_or_failed_exact_check"
    if not interference:
        return True, "raw_zero_interference"
    if accepted_baseline:
        return True, "accepted_prototype_baseline_no_new_interference"
    return False, "unaccepted_interference"


def build_report(
    screening: dict[str, Any],
    current_batches: list[tuple[Path, dict[str, Any]]],
    baseline_batches: list[tuple[Path, dict[str, Any], Path, dict[str, dict[str, Any]]]],
    current_poses_path: Path,
    current_poses: dict[str, dict[str, Any]],
    tolerance: float,
) -> dict[str, Any]:
    current: dict[tuple[str, str], tuple[Path, dict[str, Any]]] = {}
    for path, batch in current_batches:
        for item in batch.get("pairs") or []:
            current[canonical_pair(pair_values(item))] = (path, item)

    reusable: dict[
        tuple[str, str], tuple[Path, dict[str, Any], Path, dict[str, dict[str, Any]]]
    ] = {}
    for batch_path, batch, poses_path, poses in baseline_batches:
        for item in batch.get("pairs") or []:
            reusable[canonical_pair(pair_values(item))] = (
                batch_path,
                item,
                poses_path,
                poses,
            )

    expected = [canonical_pair(pair) for pair in screening.get("candidatePairs") or []]
    rows: list[dict[str, Any]] = []
    for pair in expected:
        if pair in current:
            batch_path, item = current[pair]
            accepted, acceptance = exact_acceptance(item)
            rows.append(
                {
                    "pair": list(pair),
                    "source": "current_exact_check",
                    "sourceBatch": str(batch_path.resolve()),
                    "accepted": accepted,
                    "acceptance": acceptance,
                    "relativeTransformMaximumElementError": 0.0,
                    "rawHasInterference": bool(
                        item.get("hasInterference", item.get("HasInterference", False))
                    ),
                    "detailPath": item.get("outputPath", item.get("OutputPath")),
                }
            )
            continue
        if pair not in reusable:
            rows.append(
                {
                    "pair": list(pair),
                    "source": "missing",
                    "accepted": False,
                    "acceptance": "missing_exact_evidence",
                }
            )
            continue
        batch_path, item, poses_path, poses = reusable[pair]
        exact_accepted, acceptance = exact_acceptance(item)
        missing_pose = [name for name in pair if name not in poses or name not in current_poses]
        maximum_error = math.inf
        if not missing_pose:
            old_signature = pair_signature(poses[pair[0]], poses[pair[1]])
            new_signature = pair_signature(current_poses[pair[0]], current_poses[pair[1]])
            maximum_error = max(
                abs(old - new)
                for old, new in zip(old_signature, new_signature, strict=True)
            )
        transform_unchanged = math.isfinite(maximum_error) and maximum_error <= tolerance
        rows.append(
            {
                "pair": list(pair),
                "source": "reused_exact_check",
                "sourceBatch": str(batch_path.resolve()),
                "sourcePoses": str(poses_path.resolve()),
                "accepted": exact_accepted and transform_unchanged,
                "acceptance": (
                    acceptance
                    if transform_unchanged
                    else "relative_transform_changed_recheck_required"
                ),
                "relativeTransformMaximumElementError": maximum_error,
                "relativeTransformTolerance": tolerance,
                "rawHasInterference": bool(
                    item.get("hasInterference", item.get("HasInterference", False))
                ),
                "detailPath": item.get("outputPath", item.get("OutputPath")),
            }
        )

    failures = [row for row in rows if not row["accepted"]]
    raw_interferences = [row for row in rows if row.get("rawHasInterference")]
    accepted_baseline = [
        row
        for row in raw_interferences
        if row["accepted"]
        and row["acceptance"] == "accepted_prototype_baseline_no_new_interference"
    ]
    strict_failures = int(screening.get("strictAabbFailureCount", 0) or 0)
    success = not failures and strict_failures == 0 and len(rows) == len(expected)
    return {
        "success": success,
        "policyClosurePassed": success,
        "literalZeroInterference": success and not raw_interferences,
        "currentPosePath": str(current_poses_path.resolve()),
        "screeningStrictAabbFailureCount": strict_failures,
        "expectedExactPairCount": len(expected),
        "coveredExactPairCount": len(rows) - sum(row["source"] == "missing" for row in rows),
        "currentExactPairCount": sum(row["source"] == "current_exact_check" for row in rows),
        "reusedExactPairCount": sum(row["source"] == "reused_exact_check" for row in rows),
        "unacceptedFailureCount": len(failures),
        "rawInterferingModulePairCount": len(raw_interferences),
        "acceptedPrototypeBaselinePairCount": len(accepted_baseline),
        "interpretation": (
            "All strict-AABB and conditional exact gates pass. Raw exact interference may "
            "remain only where a prototype baseline explicitly permits no-new-contact reuse."
        ),
        "failures": failures,
        "acceptedPrototypeBaselinePairs": accepted_baseline,
        "pairs": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screening", required=True, type=Path)
    parser.add_argument("--current-batch", required=True, action="append", type=Path)
    parser.add_argument("--current-poses", required=True, type=Path)
    parser.add_argument("--baseline-batch", required=True, action="append", type=Path)
    parser.add_argument("--baseline-poses", required=True, action="append", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--tolerance", type=float, default=1e-8)
    args = parser.parse_args()
    if len(args.baseline_batch) != len(args.baseline_poses):
        parser.error("--baseline-batch and --baseline-poses must have the same count.")

    current_poses_path = args.current_poses.resolve()
    current_poses = pose_mapping(read_json(current_poses_path))
    report = build_report(
        screening=read_json(args.screening),
        current_batches=[(path, read_json(path)) for path in args.current_batch],
        baseline_batches=[
            (batch_path, read_json(batch_path), poses_path, pose_mapping(read_json(poses_path)))
            for batch_path, poses_path in zip(args.baseline_batch, args.baseline_poses, strict=True)
        ],
        current_poses_path=current_poses_path,
        current_poses=current_poses,
        tolerance=args.tolerance,
    )
    report.update(
        {
            "screeningPath": str(args.screening.resolve()),
            "currentAssemblyPath": read_json(args.screening).get("assemblyPath"),
            "currentBatchPaths": [str(path.resolve()) for path in args.current_batch],
            "baselineBatchPaths": [str(path.resolve()) for path in args.baseline_batch],
        }
    )
    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.output.resolve().write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
