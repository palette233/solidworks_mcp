"""Validate persisted top-level SolidWorks poses against the corrected target transforms."""

from __future__ import annotations

import json
import math
import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "demo" / "FL9A24D062A000_real_process_layout2d.json"
POSES = ROOT / "demo" / "FL9A24D062A000_corrected_component_poses.json"
PROBES = ROOT / "demo" / "FL9A24D062A000_corrected_bottom_face_probes.json"
OUTPUT = ROOT / "demo" / "FL9A24D062A000_corrected_pose_validation.json"
TRANSLATION_TOLERANCE_METERS = 1e-9
ROTATION_TOLERANCE_DEGREES = 1e-8


def dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def axis_error_degrees(actual: list[float], expected: list[float]) -> float:
    actual_length = math.sqrt(dot(actual, actual))
    expected_length = math.sqrt(dot(expected, expected))
    if actual_length == 0.0 or expected_length == 0.0:
        return math.inf
    cosine = dot(actual, expected) / (actual_length * expected_length)
    cosine = max(-1.0, min(1.0, cosine))
    return math.degrees(math.acos(cosine))


def add_scaled(origin: list[float], axes: list[list[float]], local: list[float]) -> list[float]:
    return [
        origin[index] + sum(local[axis] * axes[axis][index] for axis in range(3))
        for index in range(3)
    ]


def normalize_angle(angle: float) -> float:
    value = angle % 360.0
    if value <= -180.0:
        value += 360.0
    if value > 180.0:
        value -= 360.0
    return value


def in_plane_angle(axis: list[float], frame: dict) -> float:
    normal = frame["normal"]
    projected = [axis[index] - dot(axis, normal) * normal[index] for index in range(3)]
    length = math.sqrt(dot(projected, projected))
    unit = [value / length for value in projected]
    return normalize_angle(
        math.degrees(math.atan2(dot(unit, frame["vAxis"]), dot(unit, frame["uAxis"])))
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--layout", type=Path, default=LAYOUT)
    parser.add_argument("--poses", type=Path, default=POSES)
    parser.add_argument("--probes", type=Path, default=PROBES)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--translation-tolerance", type=float, default=TRANSLATION_TOLERANCE_METERS)
    parser.add_argument("--rotation-tolerance", type=float, default=ROTATION_TOLERANCE_DEGREES)
    return parser.parse_args()


def probe_payload(item: dict) -> dict:
    """Accept both legacy flat probes and reopened-capture wrapper probes."""
    nested = item.get("FaceProbe")
    return nested if isinstance(nested, dict) else item


def probe_value(probe: dict, pascal_name: str, camel_name: str):
    if pascal_name in probe:
        return probe[pascal_name]
    return probe.get(camel_name)


def pose_axes(pose: dict) -> dict[str, list[float]]:
    explicit = {
        "x": pose.get("XAxis"),
        "y": pose.get("YAxis"),
        "z": pose.get("ZAxis"),
    }
    if all(isinstance(axis, list) and len(axis) >= 3 for axis in explicit.values()):
        return explicit

    transform = pose.get("Transform")
    if not isinstance(transform, list) or len(transform) < 9:
        raise ValueError(f"Pose '{pose.get('Name')}' has neither explicit axes nor a valid Transform.")
    return {
        "x": transform[0:3],
        "y": transform[3:6],
        "z": transform[6:9],
    }


def main() -> None:
    args = parse_args()
    layout = json.loads(args.layout.read_text(encoding="utf-8"))
    poses = json.loads(args.poses.read_text(encoding="utf-8"))
    probes = json.loads(args.probes.read_text(encoding="utf-8"))
    expected = {item["componentName"]: item for item in layout["components"]}
    actual = {item["Name"]: item for item in poses}
    actual_probes = {item["ComponentName"]: probe_payload(item) for item in probes}
    frame = layout["baseFrame"]
    base_name = layout["baseComponentName"]
    actual_base_origin = probe_value(actual_probes[base_name], "WorldCenter", "worldCenter")
    actual_base_normal = probe_value(actual_probes[base_name], "WorldNormal", "worldNormal")

    diagnostics: list[dict] = []
    for name, target in expected.items():
        pose = actual.get(name)
        probe = actual_probes.get(name)
        probe_success = probe_value(probe, "Success", "success") if probe is not None else False
        if pose is None or probe is None or not probe_success:
            diagnostics.append({"componentName": name, "success": False, "reason": "missing pose"})
            continue
        actual_bottom_center = probe_value(probe, "WorldCenter", "worldCenter")
        base_delta = [actual_bottom_center[index] - actual_base_origin[index] for index in range(3)]
        actual_x = dot(base_delta, frame["uAxis"])
        actual_y = dot(base_delta, frame["vAxis"])
        plane_error = abs(dot(base_delta, actual_base_normal))
        normal_dot = dot(probe_value(probe, "WorldNormal", "worldNormal"), actual_base_normal)
        normal_alignment = abs(normal_dot)
        target_layout = target["layout2d"]
        translation_error = math.hypot(actual_x - target_layout["x"], actual_y - target_layout["y"])
        theta_axis = target_layout.get("thetaAxis")
        axis_by_name = pose_axes(pose)
        actual_theta = in_plane_angle(axis_by_name[theta_axis], frame) if theta_axis else None
        rotation_error = (
            abs(normalize_angle(actual_theta - target_layout["thetaDegrees"]))
            if actual_theta is not None and target_layout.get("thetaDegrees") is not None
            else 0.0
        )
        target_axes = {
            "x": target.get("targetXAxisWorld"),
            "y": target.get("targetYAxisWorld"),
            "z": target.get("targetZAxisWorld"),
        }
        full_axis_errors = {
            axis: axis_error_degrees(axis_by_name[axis], expected_axis)
            for axis, expected_axis in target_axes.items()
            if isinstance(expected_axis, list) and len(expected_axis) >= 3
        }
        full_orientation_error = max(full_axis_errors.values(), default=rotation_error)
        diagnostics.append(
            {
                "componentName": name,
                "success": (
                    translation_error <= args.translation_tolerance
                    and rotation_error <= args.rotation_tolerance
                    and full_orientation_error <= args.rotation_tolerance
                    and plane_error <= args.translation_tolerance
                    and normal_alignment >= 0.999999
                ),
                "translationErrorMeters": translation_error,
                "rotationErrorDegrees": rotation_error,
                "bottomPlaneErrorMeters": plane_error,
                "bottomNormalDot": normal_dot,
                "bottomNormalAlignment": normal_alignment,
                "fullOrientationErrorDegrees": full_orientation_error,
                "axisOrientationErrorsDegrees": full_axis_errors,
                "actualLayout2d": {
                    "x": actual_x,
                    "y": actual_y,
                    "thetaDegrees": actual_theta,
                    "thetaAxis": theta_axis,
                },
                "targetLayout2d": target_layout,
            }
        )

    result = {
        "success": len(diagnostics) == len(expected) and all(item["success"] for item in diagnostics),
        "componentCount": len(expected),
        "capturedPoseCount": len(actual),
        "capturedBottomProbeCount": len(actual_probes),
        "translationToleranceMeters": args.translation_tolerance,
        "rotationToleranceDegrees": args.rotation_tolerance,
        "maxTranslationErrorMeters": max(
            (item.get("translationErrorMeters", math.inf) for item in diagnostics),
            default=math.inf,
        ),
        "maxRotationErrorDegrees": max(
            (item.get("rotationErrorDegrees", math.inf) for item in diagnostics),
            default=math.inf,
        ),
        "maxFullOrientationErrorDegrees": max(
            (item.get("fullOrientationErrorDegrees", math.inf) for item in diagnostics),
            default=math.inf,
        ),
        "maxBottomPlaneErrorMeters": max(
            (item.get("bottomPlaneErrorMeters", math.inf) for item in diagnostics),
            default=math.inf,
        ),
        "minimumBottomNormalAlignment": min(
            (item.get("bottomNormalAlignment", -math.inf) for item in diagnostics),
            default=-math.inf,
        ),
        "diagnostics": diagnostics,
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["success"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
