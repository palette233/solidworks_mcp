#!/usr/bin/env python3
"""Compare standalone and AD10-nested AD20 snapshot transforms against intended 5-degree poses."""

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


def delta(first: list[float], second: list[float]) -> float:
    if len(first) != len(second):
        return float("inf")
    return max((abs(float(a) - float(b)) for a, b in zip(first, second)), default=0.0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--capture",
        type=Path,
        default=ROOT
        / "demo/semantic_ports/project03_ad20_5deg_ad10_parent_pilot_v2/project03_ad20_snapshot_stage_transforms_v1.json",
    )
    parser.add_argument(
        "--interpolation",
        type=Path,
        default=ROOT / "demo/semantic_ports/project03_ad20_intermediate_transforms_v1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "demo/semantic_ports/project03_ad20_5deg_ad10_parent_pilot_v2/project03_ad20_snapshot_stage_assessment_v1.json",
    )
    args = parser.parse_args()
    capture_path, interpolation_path, output_path = (
        args.capture.resolve(), args.interpolation.resolve(), args.output.resolve()
    )
    for path in (capture_path, interpolation_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    if output_path.exists():
        raise FileExistsError(output_path)
    capture = json.loads(capture_path.read_text(encoding="utf-8-sig"))
    interpolation = json.loads(interpolation_path.read_text(encoding="utf-8-sig"))
    expected = {}
    for component in interpolation["components"]:
        sample = next(
            row for row in component["samples"]
            if abs(float(row["mechanismParameterDegrees"]) - 5.0) <= 1e-9
        )
        expected[str(component["componentName"])] = list(sample["transform"])
    stages = []
    for stage in capture["stages"]:
        parent = stage.get("parent")
        comparisons = []
        for child in stage["directChildren"]:
            occurrence = str(pick(child, "Name", "")).split("/")[-1]
            total = list(pick(child, "TotalTransform", []))
            actual = (
                total
                if parent is None
                else relative_transform(list(pick(parent, "TotalTransform", [])), total)
            )
            target = expected.get(occurrence)
            comparisons.append(
                {
                    "occurrenceName": occurrence,
                    "sourcePath": pick(child, "Path"),
                    "actualLocalTransform": actual,
                    "expectedLocalTransform": target,
                    "maxTransformElementError": delta(actual, target or []),
                }
            )
        failed = [row for row in comparisons if row["maxTransformElementError"] > 1e-8]
        stages.append(
            {
                "stage": stage["stage"],
                "componentCount": len(comparisons),
                "failedPoseCount": len(failed),
                "maximumTransformElementError": max(
                    (row["maxTransformElementError"] for row in comparisons), default=float("inf")
                ),
                "comparisons": sorted(comparisons, key=lambda row: row["occurrenceName"].casefold()),
            }
        )
    result = {
        "schemaVersion": "project03-ad20-snapshot-stage-assessment/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "sourceCapture": str(capture_path),
        "sourceInterpolation": str(interpolation_path),
        "stages": stages,
        "status": "PASSED_AD20_SNAPSHOT_STAGE_ASSESSMENT"
        if stages
        and all(row["componentCount"] == len(expected) and row["failedPoseCount"] == 0 for row in stages)
        else "FAILED_AD20_SNAPSHOT_STAGE_ASSESSMENT",
        "productionReady": False,
    }
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output_path)
    return 0 if result["status"].startswith("PASSED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
