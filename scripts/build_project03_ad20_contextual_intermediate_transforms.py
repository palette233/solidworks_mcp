#!/usr/bin/env python3
"""Build AD20 local rigid samples from full-context 0/25-degree endpoint poses."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "demo-backend" / "src"))

from demo_backend.rigid_transform_interpolation import (
    build_endpoint_error,
    build_rigid_interpolation,
    relative_transform,
)


def pick(value: dict, name: str, default=None):
    return value.get(name, value.get(name[0].lower() + name[1:], default))


def occurrence_name(row: dict) -> str:
    return str(pick(row, "Name", "")).replace("\\", "/").rsplit("/", 1)[-1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--endpoints",
        type=Path,
        default=ROOT / "demo/semantic_ports/project03_ad20_contextual_endpoint_poses_v1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "demo/semantic_ports/project03_ad20_contextual_intermediate_transforms_v1.json",
    )
    args = parser.parse_args()
    endpoints_path = args.endpoints.resolve()
    output_path = args.output.resolve()
    if not endpoints_path.is_file():
        raise FileNotFoundError(endpoints_path)
    if output_path.exists():
        raise FileExistsError(output_path)

    endpoints = json.loads(endpoints_path.read_text(encoding="utf-8-sig"))
    states = {row["state"]: row for row in endpoints["states"]}
    zero_state = states["zero"]
    end_state = states["twenty-five"]
    zero_parent = list(pick(zero_state["ad20"], "Transform", []))
    end_parent = list(pick(end_state["ad20"], "Transform", []))
    zero_rows = {occurrence_name(row): row for row in zero_state["directChildren"]}
    end_rows = {occurrence_name(row): row for row in end_state["directChildren"]}
    if len(zero_rows) != len(zero_state["directChildren"]) or len(end_rows) != len(end_state["directChildren"]):
        raise RuntimeError("AD20 contextual child occurrence names are not unique.")
    if set(zero_rows) != set(end_rows):
        raise RuntimeError("AD20 contextual endpoint occurrence sets differ.")

    sample_angles = [0.0, 5.0, 10.0, 15.0, 20.0, 25.0]
    components = []
    moving_count = 0
    max_rotation_error = 0.0
    max_translation_error = 0.0
    for name in sorted(zero_rows):
        start = zero_rows[name]
        end = end_rows[name]
        if str(pick(start, "Path", "")).casefold() != str(pick(end, "Path", "")).casefold():
            raise RuntimeError(f"AD20 contextual child source differs between endpoints: {name}")
        # Nested Transform2 is reported in the active top-level assembly frame.
        # Convert each endpoint back into AD20-local coordinates before creating
        # a standalone static snapshot.
        start_transform = relative_transform(zero_parent, list(pick(start, "Transform", [])))
        end_transform = relative_transform(end_parent, list(pick(end, "Transform", [])))
        raw_delta = max(abs(float(a) - float(b)) for a, b in zip(start_transform, end_transform))
        row = {
            "componentName": name,
            "componentPath": pick(start, "Path", ""),
            "startReferencedConfiguration": pick(start, "ReferencedConfiguration", ""),
            "endReferencedConfiguration": pick(end, "ReferencedConfiguration", ""),
            "maxRawTransformElementDelta": raw_delta,
            "sourceWorldTransforms": {"zero": pick(start, "Transform", []), "twentyFive": pick(end, "Transform", [])},
        }
        if raw_delta <= 1e-9:
            row.update(
                motionType="static",
                samples=[
                    {"mechanismParameterDegrees": angle, "fraction": angle / 25.0, "transform": start_transform}
                    for angle in sample_angles
                ],
                endpointError=build_endpoint_error(start_transform, end_transform),
            )
        else:
            moving_count += 1
            row.update(build_rigid_interpolation(
                start_transform,
                end_transform,
                sample_angles_degrees=sample_angles,
                endpoint_parameter_degrees=25.0,
            ))
        error = row["endpointError"]
        max_rotation_error = max(max_rotation_error, error["maxRotationElementError"])
        max_translation_error = max(max_translation_error, error["translationErrorMeters"])
        components.append(row)

    passed = max_rotation_error <= 1e-9 and max_translation_error <= 1e-9 and len(components) == 29
    result = {
        "schemaVersion": "project03-ad20-contextual-rigid-interpolation/v1",
        "projectId": "project03",
        "moduleId": "AD20",
        "authority": "inferred-from-full-context-zero-and-twenty-five-degree-component-poses",
        "engineeringConfirmed": False,
        "sourceEndpointEvidence": str(endpoints_path),
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
            "maxRotationElementError": max_rotation_error,
            "translationErrorMeters": max_translation_error,
        },
        "components": components,
        "productionReady": False,
        "status": (
            "PASSED_PROJECT03_AD20_CONTEXTUAL_ENDPOINT_DERIVED_INTERPOLATION"
            if passed
            else "FAILED_PROJECT03_AD20_CONTEXTUAL_ENDPOINT_DERIVED_INTERPOLATION"
        ),
    }
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output_path)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
