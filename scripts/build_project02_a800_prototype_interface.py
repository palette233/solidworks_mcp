from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CAPTURE = ROOT / "demo/layout_previews/project02_a600_installation_geometry_capture.json"
DEFAULT_FRAME = ROOT / "demo/layout_previews/project02_a600_installation_frame.json"
DEFAULT_OUTPUT = ROOT / "demo/layout_previews/project02_a600_a800_prototype_interface.json"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Express the Project02 prototype A800 pose in the A600 engineering frame."
    )
    parser.add_argument("--capture", type=Path, default=DEFAULT_CAPTURE)
    parser.add_argument("--frame", type=Path, default=DEFAULT_FRAME)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    capture = _load(args.capture)
    frame = _load(args.frame)
    origin = [float(value) for value in frame["originWorldMeters"]]
    frame_axes = frame["axesWorld"]
    axes = [
        [float(value) for value in frame_axes["xIntoMachine"]],
        [float(value) for value in frame_axes["yTransportLateral"]],
        [float(value) for value in frame_axes["zUp"]],
    ]
    a800 = capture["a800Pose"]
    translation_world = _numbers(a800, "Translation", 3)
    translation_frame = _point_to_frame(translation_world, origin, axes)
    a800_world_axes = [
        _numbers(a800, "XAxis", 3),
        _numbers(a800, "YAxis", 3),
        _numbers(a800, "ZAxis", 3),
    ]
    orientation = [
        [_dot(world_axis, frame_axis) for world_axis in a800_world_axes]
        for frame_axis in axes
    ]
    bounds = _project_box(_numbers(a800, "BoundingBoxWorld", 6), origin, axes)
    center = [(bounds[index] + bounds[index + 3]) / 2 for index in range(3)]
    orthogonality_residual = max(
        abs(_dot(a800_world_axes[first], a800_world_axes[second]))
        for first, second in ((0, 1), (0, 2), (1, 2))
    )
    determinant = _det3(orientation)
    checks = [
        _check("a600-frame-valid", frame.get("success") is True),
        _check("a800-orientation-orthogonal", orthogonality_residual < 1e-6),
        _check("a800-orientation-right-handed", abs(determinant - 1.0) < 1e-6),
        _check("a800-bounding-box-spans-center-plane", bounds[1] <= 0.0 <= bounds[4]),
    ]
    success = all(item["passed"] for item in checks)
    result = {
        "schemaVersion": "project02-a600-a800-prototype-interface/v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "success": success,
        "status": "PASS_PROTOTYPE_INTERFACE_SEED" if success else "FAIL_PROTOTYPE_INTERFACE_SEED",
        "baseModuleCode": "A600",
        "transportModuleCode": "A800",
        "frameName": frame.get("frameName"),
        "sourceCapture": str(args.capture.resolve()),
        "sourceFrame": str(args.frame.resolve()),
        "prototypeTranslationFrameMeters": translation_frame,
        "prototypeOrientationFrame": orientation,
        "prototypeBoundingBoxFrameMeters": bounds,
        "prototypeBoundingBoxCenterFrameMeters": center,
        "transportCenterPlaneOffsetMeters": center[1],
        "orientationDeterminant": determinant,
        "orientationOrthogonalityResidual": orthogonality_residual,
        "usableAsPrototypeSeed": success,
        "confirmedAsVendorInterface": False,
        "interpretation": (
            "This is an exact measurement of the prototype assembly pose in the A600 engineering frame. "
            "It may seed or audit a coarse layout, but it must not be relabeled as a vendor-specified XYZ interface."
        ),
        "checks": checks,
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": result["status"],
                "output": str(output),
                "prototypeTranslationFrameMeters": translation_frame,
                "transportCenterPlaneOffsetMeters": center[1],
            },
            ensure_ascii=False,
        )
    )
    return 0 if success else 2


def _point_to_frame(point: list[float], origin: list[float], axes: list[list[float]]) -> list[float]:
    delta = [point[index] - origin[index] for index in range(3)]
    return [_dot(delta, axis) for axis in axes]


def _project_box(box: list[float], origin: list[float], axes: list[list[float]]) -> list[float]:
    points = [
        _point_to_frame([x, y, z], origin, axes)
        for x in (box[0], box[3])
        for y in (box[1], box[4])
        for z in (box[2], box[5])
    ]
    return [
        min(point[index] for point in points)
        for index in range(3)
    ] + [
        max(point[index] for point in points)
        for index in range(3)
    ]


def _det3(matrix: list[list[float]]) -> float:
    return (
        matrix[0][0] * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1])
        - matrix[0][1] * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0])
        + matrix[0][2] * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0])
    )


def _dot(first: list[float], second: list[float]) -> float:
    return sum(first[index] * second[index] for index in range(3))


def _numbers(item: dict[str, Any], name: str, length: int) -> list[float]:
    value = item.get(name, item.get(name[0].lower() + name[1:]))
    if not isinstance(value, list) or len(value) != length:
        raise SystemExit(f"Missing {length}-value {name}")
    return [float(number) for number in value]


def _check(name: str, passed: bool) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed)}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.resolve().read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
