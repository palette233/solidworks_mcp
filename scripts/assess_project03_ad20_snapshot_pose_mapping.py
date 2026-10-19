#!/usr/bin/env python3
"""Assess whether each AD20 snapshot occurrence retained its intended local pose."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "demo-backend" / "src"))

from demo_backend.rigid_transform_interpolation import relative_transform


def pick(value: dict[str, Any], name: str, default: Any = None) -> Any:
    return value.get(name, value.get(name[0].lower() + name[1:], default))


def max_delta(first: list[float], second: list[float]) -> float:
    if len(first) != len(second):
        return float("inf")
    return max((abs(float(a) - float(b)) for a, b in zip(first, second)), default=0.0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--diagnostic",
        type=Path,
        default=ROOT
        / "demo/semantic_ports/project03_ad00_full_context_left5_v4/project03_nested_total_transform_diagnostic_v1.json",
    )
    parser.add_argument(
        "--interpolation",
        type=Path,
        default=ROOT / "demo/semantic_ports/project03_ad20_intermediate_transforms_v1.json",
    )
    parser.add_argument(
        "--snapshot-manifest",
        type=Path,
        default=ROOT
        / "demo/semantic_ports/project03_ad20_intermediate_5deg_snapshot_v1/project03_ad20_intermediate_snapshot_closure.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "demo/semantic_ports/project03_ad00_full_context_left5_v4/project03_ad20_snapshot_pose_mapping_assessment_v1.json",
    )
    parser.add_argument("--angle", type=float, default=5.0)
    args = parser.parse_args()
    diagnostic_path = args.diagnostic.resolve()
    interpolation_path = args.interpolation.resolve()
    manifest_path = args.snapshot_manifest.resolve()
    output_path = args.output.resolve()
    for path in (diagnostic_path, interpolation_path, manifest_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    if output_path.exists():
        raise FileExistsError(output_path)

    diagnostic = json.loads(diagnostic_path.read_text(encoding="utf-8-sig"))
    interpolation = json.loads(interpolation_path.read_text(encoding="utf-8-sig"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    candidate = next(row for row in diagnostic["assemblies"] if row["label"] == "candidate")
    rows = candidate["selectedPoses"]
    snapshot_file_name = Path(manifest["assemblyPath"]).name.casefold()
    parent_matches = [
        row
        for row in rows
        if Path(str(pick(row, "Path", ""))).name.casefold() == snapshot_file_name
    ]
    if not parent_matches:
        raise RuntimeError("Static AD20 parent resolved to 0 rows.")
    expected_by_occurrence: dict[str, list[float]] = {}
    for component in interpolation["components"]:
        sample = next(
            row
            for row in component["samples"]
            if abs(float(row["mechanismParameterDegrees"]) - args.angle) <= 1e-9
        )
        expected_by_occurrence[str(component["componentName"])] = list(sample["transform"])
    source_to_snapshot = {
        str(row["sourceOccurrenceName"]): str(row["snapshotOccurrenceName"])
        for row in manifest["componentInstances"]
    }
    snapshot_to_source = {value: key for key, value in source_to_snapshot.items()}

    comparisons = []
    captured_child_count = 0
    for parent in parent_matches:
        parent_hierarchy = str(pick(parent, "HierarchyPath", ""))
        children = [
            row
            for row in rows
            if int(pick(row, "Depth", -1)) == int(pick(parent, "Depth", 0)) + 1
            and str(pick(row, "HierarchyPath", "")).startswith(parent_hierarchy + "/")
        ]
        captured_child_count += len(children)
        for child in children:
            snapshot_name = str(pick(child, "Name", "")).replace("\\", "/").split("/")[-1]
            source_name = snapshot_to_source.get(snapshot_name)
            actual_local = relative_transform(
                list(pick(parent, "TotalTransform", [])),
                list(pick(child, "TotalTransform", [])),
            )
            expected = expected_by_occurrence.get(source_name or "")
            comparisons.append(
                {
                    "parentHierarchyPath": pick(parent, "HierarchyPath"),
                    "snapshotOccurrenceName": snapshot_name,
                    "sourceOccurrenceName": source_name,
                    "sourcePath": pick(child, "Path"),
                    "actualLocalTransform": actual_local,
                    "expectedLocalTransform": expected,
                    "maxTransformElementError": max_delta(actual_local, expected or []),
                }
            )
    comparisons.sort(key=lambda row: row["snapshotOccurrenceName"].casefold())
    unmatched = [row for row in comparisons if row["sourceOccurrenceName"] is None]
    failed = [row for row in comparisons if row["maxTransformElementError"] > 1e-8]
    result = {
        "schemaVersion": "project03-ad20-snapshot-pose-mapping-assessment/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "sourceDiagnostic": str(diagnostic_path),
        "sourceInterpolation": str(interpolation_path),
        "sourceSnapshotManifest": str(manifest_path),
        "parents": parent_matches,
        "parentCount": len(parent_matches),
        "expectedComponentCount": len(expected_by_occurrence) * len(parent_matches),
        "capturedDirectChildCount": captured_child_count,
        "unmatchedOccurrenceCount": len(unmatched),
        "failedPoseCount": len(failed),
        "maximumTransformElementError": max(
            (row["maxTransformElementError"] for row in comparisons), default=float("inf")
        ),
        "comparisons": comparisons,
        "status": "PASSED_AD20_SNAPSHOT_POSE_MAPPING"
        if captured_child_count == len(expected_by_occurrence) * len(parent_matches) and not unmatched and not failed
        else "FAILED_AD20_SNAPSHOT_POSE_MAPPING",
        "productionReady": False,
    }
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output_path)
    return 0 if result["status"].startswith("PASSED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
