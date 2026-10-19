#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "demo-backend" / "src"))

from demo_backend.rigid_transform_interpolation import build_endpoint_error, build_rigid_interpolation


def pick(value: dict, name: str, default=None):
    return value.get(name, value.get(name[0].lower() + name[1:], default))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--endpoints",
        type=Path,
        default=ROOT / "demo/semantic_ports/project03_ad20_internal_endpoint_poses_v1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "demo/semantic_ports/project03_ad20_intermediate_transforms_v1.json",
    )
    parser.add_argument(
        "--sample-angles",
        type=float,
        nargs="+",
        default=[0.0, 5.0, 10.0, 15.0, 20.0, 25.0],
        help="Mechanism parameters in degrees, each within the 0-25 endpoint interval.",
    )
    args = parser.parse_args()
    endpoints = json.loads(args.endpoints.resolve().read_text(encoding="utf-8-sig"))
    states = {row["state"]: row for row in endpoints["states"]}
    zero_rows = {
        pick(row, "Name"): row for row in states["zero"]["topLevelComponentPoses"]
    }
    end_rows = {
        pick(row, "Name"): row for row in states["twenty-five"]["topLevelComponentPoses"]
    }
    if set(zero_rows) != set(end_rows):
        raise RuntimeError("AD20 endpoint component occurrence sets differ.")

    sample_angles = sorted(set(float(value) for value in args.sample_angles))
    if not sample_angles or sample_angles[0] < 0.0 or sample_angles[-1] > 25.0:
        raise ValueError("Sample angles must lie inside the 0-25 degree endpoint interval.")
    if 0.0 not in sample_angles or 25.0 not in sample_angles:
        raise ValueError("Sample angles must include both 0 and 25 degrees for endpoint audit.")
    components = []
    moving_count = 0
    maximum_rotation_error = 0.0
    maximum_translation_error = 0.0
    for name in sorted(zero_rows):
        start = zero_rows[name]
        end = end_rows[name]
        if pick(start, "Path", "").casefold() != pick(end, "Path", "").casefold():
            raise RuntimeError(f"AD20 component source differs between endpoints: {name}")
        start_transform = list(pick(start, "Transform", []))
        end_transform = list(pick(end, "Transform", []))
        raw_delta = max(abs(float(a) - float(b)) for a, b in zip(start_transform, end_transform))
        row = {
            "componentName": name,
            "componentPath": pick(start, "Path", ""),
            "startReferencedConfiguration": pick(start, "ReferencedConfiguration", ""),
            "endReferencedConfiguration": pick(end, "ReferencedConfiguration", ""),
            "maxRawTransformElementDelta": raw_delta,
        }
        if raw_delta <= 1e-9:
            row.update(
                motionType="static",
                samples=[
                    {
                        "mechanismParameterDegrees": angle,
                        "fraction": angle / 25.0,
                        "transform": start_transform,
                    }
                    for angle in sample_angles
                ],
                endpointError=build_endpoint_error(start_transform, end_transform),
            )
        else:
            moving_count += 1
            interpolation = build_rigid_interpolation(
                start_transform,
                end_transform,
                sample_angles_degrees=sample_angles,
                endpoint_parameter_degrees=25.0,
            )
            row.update(interpolation)
        error = row["endpointError"]
        maximum_rotation_error = max(maximum_rotation_error, error["maxRotationElementError"])
        maximum_translation_error = max(maximum_translation_error, error["translationErrorMeters"])
        components.append(row)

    result = {
        "schemaVersion": "project03-ad20-internal-rigid-interpolation/v1",
        "projectId": "project03",
        "moduleId": "AD20",
        "authority": "inferred-from-native-ad20-0-and-25-degree-configuration-component-poses",
        "engineeringConfirmed": False,
        "sourceEndpointEvidence": str(args.endpoints.resolve()),
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "sampleAnglesDegrees": sample_angles,
        "componentCount": len(components),
        "movingComponentCount": moving_count,
        "staticComponentCount": len(components) - moving_count,
        "motionTypeCounts": {
            kind: sum(1 for row in components if row["motionType"] == kind)
            for kind in sorted({row["motionType"] for row in components})
        },
        "maximumEndpointError": {
            "maxRotationElementError": maximum_rotation_error,
            "translationErrorMeters": maximum_translation_error,
        },
        "components": components,
        "productionReady": False,
    }
    passed = maximum_rotation_error <= 1e-9 and maximum_translation_error <= 1e-9
    result["status"] = (
        "PASSED_PROJECT03_AD20_ENDPOINT_DERIVED_INTERPOLATION"
        if passed
        else "FAILED_PROJECT03_AD20_ENDPOINT_DERIVED_INTERPOLATION"
    )
    args.output.resolve().write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(args.output.resolve())
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
