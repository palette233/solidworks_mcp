#!/usr/bin/env python3
"""Rebase native AD20 0-25 degree motion onto the full-context zero pose."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "demo-backend" / "src"))

from demo_backend.rigid_transform_interpolation import (
    rebase_parent_frame_motion,
    relative_transform,
)


def pick(value: dict, name: str, default=None):
    return value.get(name, value.get(name[0].lower() + name[1:], default))


def leaf_name(value: str) -> str:
    return value.replace("\\", "/").rsplit("/", 1)[-1]


def max_error(first: list[float], second: list[float]) -> float:
    return max(abs(float(a) - float(b)) for a, b in zip(first, second))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--native-interpolation",
        type=Path,
        default=ROOT / "demo/semantic_ports/project03_ad20_intermediate_transforms_v1.json",
    )
    parser.add_argument(
        "--contextual-endpoints",
        type=Path,
        default=ROOT / "demo/semantic_ports/project03_ad20_contextual_endpoint_poses_v1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "demo/semantic_ports/project03_ad20_context_rebased_intermediate_transforms_v1.json",
    )
    args = parser.parse_args()
    native_path = args.native_interpolation.resolve()
    contextual_path = args.contextual_endpoints.resolve()
    output_path = args.output.resolve()
    for path in (native_path, contextual_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    if output_path.exists():
        raise FileExistsError(output_path)

    native = json.loads(native_path.read_text(encoding="utf-8-sig"))
    contextual = json.loads(contextual_path.read_text(encoding="utf-8-sig"))
    zero_state = next(row for row in contextual["states"] if row["state"] == "zero")
    parent_world = list(pick(zero_state["ad20"], "Transform", []))
    contextual_children = {
        leaf_name(str(pick(row, "Name", ""))): row for row in zero_state["directChildren"]
    }
    native_components = {row["componentName"]: row for row in native["components"]}
    if set(contextual_children) != set(native_components):
        missing_context = sorted(set(native_components) - set(contextual_children))
        missing_native = sorted(set(contextual_children) - set(native_components))
        raise RuntimeError(
            f"Context/native occurrence mismatch: missingContext={missing_context}, missingNative={missing_native}"
        )

    components = []
    zero_errors = []
    for name in sorted(native_components):
        source = native_components[name]
        native_samples = list(source["samples"])
        original_start = list(native_samples[0]["transform"])
        corrected_start = relative_transform(
            parent_world,
            list(pick(contextual_children[name], "Transform", [])),
        )
        samples = []
        for sample in native_samples:
            transform = rebase_parent_frame_motion(
                original_start,
                list(sample["transform"]),
                corrected_start,
            )
            samples.append({**sample, "transform": transform})
        zero_errors.append(max_error(samples[0]["transform"], corrected_start))
        components.append(
            {
                **source,
                "contextualZeroTransform": corrected_start,
                "nativeZeroTransform": original_start,
                "samples": samples,
                "motionRebase": "native-parent-frame-delta-on-full-context-zero-pose",
            }
        )

    maximum_zero_error = max(zero_errors, default=float("inf"))
    passed = len(components) == 29 and maximum_zero_error <= 1e-9
    result = {
        "schemaVersion": "project03-ad20-context-rebased-interpolation/v1",
        "projectId": "project03",
        "moduleId": "AD20",
        "authority": "full-context-zero-pose-plus-native-0-to-25-degree-motion-delta",
        "engineeringConfirmed": False,
        "sourceNativeInterpolation": str(native_path),
        "sourceContextualEndpointEvidence": str(contextual_path),
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "sampleAnglesDegrees": native["sampleAnglesDegrees"],
        "componentCount": len(components),
        "movingComponentCount": sum(row["motionType"] != "static" for row in components),
        "staticComponentCount": sum(row["motionType"] == "static" for row in components),
        "maximumContextualZeroTransformError": maximum_zero_error,
        "components": components,
        "productionReady": False,
        "status": (
            "PASSED_PROJECT03_AD20_CONTEXT_REBASED_INTERPOLATION"
            if passed
            else "FAILED_PROJECT03_AD20_CONTEXT_REBASED_INTERPOLATION"
        ),
        "blockers": [
            "The 0-to-25-degree motion delta is inferred from native endpoint configurations, not vendor kinematics.",
            "Intermediate and endpoint full-context B-rep gates remain required.",
        ],
    }
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output_path)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
