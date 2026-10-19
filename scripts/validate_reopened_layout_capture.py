"""Validate a disk-reopened common-base capture and export screening inputs."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def angle_error(first: float, second: float) -> float:
    return abs((first - second + 180.0) % 360.0 - 180.0)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--layout", type=Path, required=True)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument(
        "--replay-result",
        type=Path,
        help="Replay evidence containing list_component_poses. Used when the reopened capture has no face mappings/layout2d.",
    )
    parser.add_argument("--poses-output", type=Path, required=True)
    parser.add_argument("--probes-output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    parser.add_argument("--transform-tolerance", type=float, default=1e-9)
    parser.add_argument("--bounding-box-tolerance-meters", type=float, default=1e-8)
    args = parser.parse_args()

    layout = json.loads(args.layout.resolve().read_text(encoding="utf-8"))
    capture = json.loads(args.capture.resolve().read_text(encoding="utf-8"))
    expected = {item["componentName"]: item for item in layout["components"]}
    actual = {item["componentName"]: item for item in capture["components"]}
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    diagnostics = []
    validation_mode = "layout2d"
    reopened_has_layout = all(item.get("layout2d") is not None for item in actual.values())
    if reopened_has_layout:
        for name in sorted(set(expected) & set(actual)):
            target = expected[name]["layout2d"]
            measured = actual[name]["layout2d"]
            xy = math.dist(
                (float(target["x"]), float(target["y"])),
                (float(measured["x"]), float(measured["y"])),
            )
            theta = angle_error(float(target["thetaDegrees"]), float(measured["thetaDegrees"]))
            diagnostics.append(
                {
                    "componentName": name,
                    "xyErrorMeters": xy,
                    "thetaErrorDegrees": theta,
                    "success": xy <= 1e-6 and theta <= 1e-4,
                }
            )
    else:
        if args.replay_result is None:
            raise SystemExit("The reopened capture has no layout2d data; pass --replay-result for transform validation.")
        validation_mode = "saved-world-transform"
        replay = json.loads(args.replay_result.resolve().read_text(encoding="utf-8"))
        pose_step = next(
            (
                step
                for step in replay.get("steps", [])
                if step.get("tool") == "list_component_poses"
            ),
            None,
        )
        if pose_step is None:
            raise SystemExit("Replay result does not contain a list_component_poses step.")
        # Replay records every top-level prototype-context component, while a
        # reopen capture may intentionally request only the target module set.
        # Scope validation to the layout components instead of reporting all
        # unrelated prototype-context components as missing.
        expected_names = set(expected)
        expected_poses = {
            item["Name"]: item
            for item in pose_step["payload"]
            if item["Name"] in expected_names
        }
        missing = sorted(set(expected_poses) - set(actual))
        extra = sorted(set(actual) - set(expected_poses))
        for name in sorted(set(expected_poses) & set(actual)):
            target_transform = [float(value) for value in expected_poses[name]["Transform"]]
            measured_transform = [float(value) for value in actual[name]["sourceTransform"]]
            max_transform_error = max(
                abs(first - second)
                for first, second in zip(target_transform, measured_transform, strict=True)
            )
            target_box = [float(value) for value in expected_poses[name]["BoundingBoxWorld"]]
            measured_box = [float(value) for value in actual[name]["boundingBoxWorld"]]
            max_box_error = max(
                abs(first - second)
                for first, second in zip(target_box, measured_box, strict=True)
            )
            diagnostics.append(
                {
                    "componentName": name,
                    "maxTransformElementError": max_transform_error,
                    "maxBoundingBoxElementErrorMeters": max_box_error,
                    "success": (
                        max_transform_error <= args.transform_tolerance
                        and max_box_error <= args.bounding_box_tolerance_meters
                    ),
                }
            )

    poses = [
        {
            "Name": item["componentName"],
            "BoundingBoxWorld": item["boundingBoxWorld"],
            "Transform": item.get("sourceTransform"),
        }
        for item in capture["components"]
    ]
    probes = [
        {
            "ComponentName": item["componentName"],
            "FaceProbe": item.get("faceProbe"),
        }
        for item in capture["components"]
    ]
    report = {
        "success": not missing and not extra and all(item["success"] for item in diagnostics),
        "validationMode": validation_mode,
        "layoutPath": str(args.layout.resolve()),
        "capturePath": str(args.capture.resolve()),
        "componentCount": len(diagnostics),
        "missingComponents": missing,
        "extraComponents": extra,
        "maxXyErrorMeters": max((item.get("xyErrorMeters") for item in diagnostics if "xyErrorMeters" in item), default=None),
        "maxThetaErrorDegrees": max((item.get("thetaErrorDegrees") for item in diagnostics if "thetaErrorDegrees" in item), default=None),
        "maxTransformElementError": max((item.get("maxTransformElementError") for item in diagnostics if "maxTransformElementError" in item), default=None),
        "maxBoundingBoxElementErrorMeters": max((item.get("maxBoundingBoxElementErrorMeters") for item in diagnostics if "maxBoundingBoxElementErrorMeters" in item), default=None),
        "transformTolerance": args.transform_tolerance,
        "boundingBoxToleranceMeters": args.bounding_box_tolerance_meters,
        "diagnostics": diagnostics,
    }
    args.poses_output.resolve().write_text(json.dumps(poses, ensure_ascii=False, indent=2), encoding="utf-8")
    args.probes_output.resolve().write_text(json.dumps(probes, ensure_ascii=False, indent=2), encoding="utf-8")
    args.report_output.resolve().write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["success"] else 1)


if __name__ == "__main__":
    main()
