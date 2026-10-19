"""Project saved SolidWorks poses to a new planar rigid layout.

This is a deterministic fallback for broad-phase review when SolidWorks COM is
temporarily unavailable.  It never claims to replace a saved Replay or an exact
B-Rep interference check.  When a module rotates, its saved world AABB is rotated
as a box around the layout anchor, producing a conservative replacement AABB.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.pipeline_timing import PipelineTiming  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-layout", type=Path, required=True)
    parser.add_argument("--baseline-replay", type=Path, required=True)
    parser.add_argument("--baseline-poses", type=Path, required=True)
    parser.add_argument("--output-poses", type=Path, required=True)
    parser.add_argument("--output-report", type=Path, required=True)
    return parser.parse_args()


def layouts(components: list[dict]) -> dict[str, dict]:
    return {item["componentName"]: item["layout2d"] for item in components}


def load_layouts_from_replay_artifact(
    path: Path,
    seen: set[Path] | None = None,
) -> dict[str, dict]:
    """Recover planar layouts from either a Replay snapshot or a projection report.

    Iterative collision closure often starts from a previously saved SolidWorks
    assembly whose planar target was produced by this script.  Such a projection
    report stores the prior baseline plus per-component deltas instead of copying
    the full component payload.  Reconstructing that target here lets the next
    iteration reuse the already-loaded CAD assembly rather than reinsert all
    heavyweight subassemblies.
    """

    resolved = path.resolve()
    visited = set() if seen is None else seen
    if resolved in visited:
        raise ValueError(f"Projection baseline cycle detected at: {resolved}")
    visited.add(resolved)
    document = json.loads(resolved.read_text(encoding="utf-8"))
    components = document.get("components")
    if isinstance(components, list):
        return layouts(components)

    baseline_value = document.get("baselineReplay")
    diagnostics = document.get("diagnostics")
    if not baseline_value or not isinstance(diagnostics, list):
        raise ValueError(
            f"Baseline artifact has neither components nor projection deltas: {resolved}"
        )
    baseline_path = Path(str(baseline_value))
    if not baseline_path.is_absolute():
        baseline_path = resolved.parent / baseline_path
    recovered = copy.deepcopy(load_layouts_from_replay_artifact(baseline_path, visited))
    for diagnostic in diagnostics:
        name = diagnostic.get("componentName")
        delta = diagnostic.get("deltaLayoutMeters")
        if name not in recovered or not isinstance(delta, list) or len(delta) < 2:
            continue
        recovered[name]["x"] = float(recovered[name]["x"]) + float(delta[0])
        recovered[name]["y"] = float(recovered[name]["y"]) + float(delta[1])
        recovered[name]["thetaDegrees"] = float(
            recovered[name].get("thetaDegrees", 0.0)
        ) + float(diagnostic.get("thetaDeltaDegrees") or 0.0)
    return recovered


def _dot(first: list[float], second: list[float]) -> float:
    return sum(float(a) * float(b) for a, b in zip(first, second))


def _normal_coordinate(
    point: list[float],
    origin: list[float],
    normal: list[float],
) -> float:
    return _dot(
        [float(point[index]) - float(origin[index]) for index in range(3)],
        normal,
    )


def _target_normal_delta(
    current_point: list[float],
    target_component: dict,
    target_layout: dict,
    origin: list[float],
    normal: list[float],
) -> tuple[float, float | None]:
    """Return the absolute normal correction and captured source bottom height.

    Project02's captured installation convention is::

        solved top transform = source top transform
            + (target bottom height - captured source bottom height) * normal

    ``installationNormalOffsetMeters`` is therefore an absolute bottom-face
    height in the common installation frame, not a translation to subtract from
    the source component transform.  A saved baseline assembly may already
    contain an earlier height correction, so the desired top coordinate is
    reconstructed from the captured source top and bottom instead of inferred
    from the current saved pose.
    """

    source_transform = target_component.get("sourceTransform")
    source_bottom_center = target_component.get("bottomCenterWorld")
    if (
        not isinstance(source_transform, list)
        or len(source_transform) < 12
        or not isinstance(source_bottom_center, list)
        or len(source_bottom_center) < 3
    ):
        return 0.0, None
    source_point = [float(value) for value in source_transform[9:12]]
    source_top_n = _normal_coordinate(source_point, origin, normal)
    source_bottom_n = _normal_coordinate(source_bottom_center, origin, normal)
    current_n = _normal_coordinate(current_point, origin, normal)
    target_offset = float(target_layout.get("normalOffsetMeters") or 0.0)
    desired_top_n = source_top_n + target_offset - source_bottom_n
    return desired_top_n - current_n, source_bottom_n


def _project_point(
    point: list[float],
    origin: list[float],
    u_axis: list[float],
    v_axis: list[float],
    normal: list[float],
    before: dict,
    after: dict,
    theta_delta_degrees: float,
) -> list[float]:
    relative = [float(point[index]) - float(origin[index]) for index in range(3)]
    u = _dot(relative, u_axis)
    v = _dot(relative, v_axis)
    n = _dot(relative, normal)
    radians = math.radians(theta_delta_degrees)
    cosine, sine = math.cos(radians), math.sin(radians)
    local_u = u - float(before["x"])
    local_v = v - float(before["y"])
    projected_u = float(after["x"]) + cosine * local_u - sine * local_v
    projected_v = float(after["y"]) + sine * local_u + cosine * local_v
    return [
        float(origin[index])
        + projected_u * float(u_axis[index])
        + projected_v * float(v_axis[index])
        + n * float(normal[index])
        for index in range(3)
    ]


def _box_corners(box: list[float]) -> list[list[float]]:
    return [
        [x, y, z]
        for x in (float(box[0]), float(box[3]))
        for y in (float(box[1]), float(box[4]))
        for z in (float(box[2]), float(box[5]))
    ]


def main() -> None:
    args = parse_args()
    timer = PipelineTiming("project02.offline-pose-projection")
    with timer.stage("load-input-artifacts"):
        target = json.loads(args.target_layout.resolve().read_text(encoding="utf-8"))
        baseline_poses = json.loads(
            args.baseline_poses.resolve().read_text(encoding="utf-8")
        )
    with timer.stage("prepare-projection-frame-and-components"):
        target_components = {
            item["componentName"]: item for item in target["components"]
        }
        target_layouts = layouts(target["components"])
        baseline_layouts = load_layouts_from_replay_artifact(args.baseline_replay)
        frame = target["baseFrame"]
        u_axis = frame["uAxis"]
        v_axis = frame["vAxis"]
        normal = frame["normal"]
        origin = frame["origin"]
        fixed_environment_names = {
            name
            for name, component in target_components.items()
            if bool((component.get("constraintPlacement") or {}).get("fixedEnvironment"))
        }
        projected = [
            copy.deepcopy(pose)
            for pose in baseline_poses
            if pose.get("Name") in target_layouts
            and pose.get("Name") in baseline_layouts
            and pose.get("Name") not in fixed_environment_names
        ]
        skipped_baseline_components = sorted(
            str(pose.get("Name"))
            for pose in baseline_poses
            if pose.get("Name") not in target_layouts
            or pose.get("Name") not in baseline_layouts
        )
        fixed_environment_poses = []
        for name, component in target_components.items():
            placement = component.get("constraintPlacement") or {}
            if not bool(placement.get("fixedEnvironment")):
                continue
            transform = component.get("fixedWorldTransform")
            box = component.get("boundingBoxWorld")
            if not isinstance(transform, list) or len(transform) != 16:
                raise SystemExit(f"Fixed environment '{name}' has no 16-value fixedWorldTransform.")
            if not isinstance(box, list) or len(box) != 6:
                raise SystemExit(f"Fixed environment '{name}' has no six-value boundingBoxWorld.")
            fixed_environment_poses.append(
                {
                    "Name": name,
                    "Path": component.get("filePath"),
                    "Transform": [float(value) for value in transform],
                    "Translation": [float(value) for value in transform[9:12]],
                    "XAxis": [float(value) for value in transform[0:3]],
                    "YAxis": [float(value) for value in transform[3:6]],
                    "ZAxis": [float(value) for value in transform[6:9]],
                    "BoundingBoxWorld": [float(value) for value in box],
                    "FixedEnvironment": True,
                }
            )
    diagnostics = []

    with timer.stage("project-component-poses", componentCount=len(projected)):
        for pose in projected:
            name = pose["Name"]
            before = baseline_layouts[name]
            after = target_layouts[name]
            theta_delta = float(after.get("thetaDegrees", 0.0)) - float(
                before.get("thetaDegrees", 0.0)
            )
            du = float(after["x"]) - float(before["x"])
            dv = float(after["y"]) - float(before["y"])
            source_translation = pose.get("Translation")
            if not isinstance(source_translation, list) or len(source_translation) < 3:
                source_translation = pose["Transform"][9:12]
            normal_delta, inferred_baseline_normal_offset = _target_normal_delta(
                source_translation,
                target_components[name],
                after,
                origin,
                normal,
            )
            delta = [
                du * u_axis[i] + dv * v_axis[i] + normal_delta * normal[i]
                for i in range(3)
            ]
            pose["Translation"] = _project_point(
                source_translation,
                origin,
                u_axis,
                v_axis,
                normal,
                before,
                after,
                theta_delta,
            )
            pose["Translation"] = [
                float(pose["Translation"][index])
                + normal_delta * float(normal[index])
                for index in range(3)
            ]
            pose["Transform"][9:12] = list(pose["Translation"])
            box = pose["BoundingBoxWorld"]
            projected_corners = [
                [
                    projected_coordinate + normal_delta * float(normal[index])
                    for index, projected_coordinate in enumerate(
                        _project_point(
                            point,
                            origin,
                            u_axis,
                            v_axis,
                            normal,
                            before,
                            after,
                            theta_delta,
                        )
                    )
                ]
                for point in _box_corners(box)
            ]
            pose["BoundingBoxWorld"] = [
                min(point[index] for point in projected_corners) for index in range(3)
            ] + [
                max(point[index] for point in projected_corners) for index in range(3)
            ]
            target_component = target_components[name]
            target_axes = (
                target_component.get("targetXAxisWorld"),
                target_component.get("targetYAxisWorld"),
                target_component.get("targetZAxisWorld"),
            )
            if all(isinstance(axis, list) and len(axis) == 3 for axis in target_axes):
                pose["XAxis"], pose["YAxis"], pose["ZAxis"] = (
                    list(target_axes[0]),
                    list(target_axes[1]),
                    list(target_axes[2]),
                )
                pose["Transform"][0:9] = [
                    *pose["XAxis"],
                    *pose["YAxis"],
                    *pose["ZAxis"],
                ]
            diagnostics.append(
                {
                    "componentName": name,
                    "deltaLayoutMeters": [du, dv],
                    "deltaWorldMeters": delta,
                    "translationMagnitudeMeters": math.sqrt(
                        sum(x * x for x in delta)
                    ),
                    "thetaDeltaDegrees": theta_delta,
                    "targetNormalOffsetMeters": float(
                        after.get("normalOffsetMeters") or 0.0
                    ),
                    "inferredBaselineNormalOffsetMeters": inferred_baseline_normal_offset,
                    "normalDeltaMeters": normal_delta,
                }
            )
        projected.extend(fixed_environment_poses)
        diagnostics.extend(
            {
                "componentName": pose["Name"],
                "deltaLayoutMeters": [0.0, 0.0],
                "deltaWorldMeters": [0.0, 0.0, 0.0],
                "translationMagnitudeMeters": 0.0,
                "thetaDeltaDegrees": 0.0,
                "fixedEnvironmentPreserved": True,
            }
            for pose in fixed_environment_poses
        )

    with timer.stage("persist-projected-poses"):
        args.output_poses.resolve().parent.mkdir(parents=True, exist_ok=True)
        args.output_poses.resolve().write_text(
            json.dumps(projected, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    report = {
        "success": True,
        "kind": "planar-rigid-projection-from-saved-solidworks-poses",
        "isSavedSolidWorksReplay": False,
        "isExactBrepEvidence": False,
        "targetLayout": str(args.target_layout.resolve()),
        "baselineReplay": str(args.baseline_replay.resolve()),
        "baselinePoses": str(args.baseline_poses.resolve()),
        "outputPoses": str(args.output_poses.resolve()),
        "maximumTranslationMeters": max(
            item["translationMagnitudeMeters"] for item in diagnostics
        ),
        "changedComponentCount": sum(
            item["translationMagnitudeMeters"] > 1e-12
            or abs(item["thetaDeltaDegrees"]) > 1e-12
            for item in diagnostics
        ),
        "rotatedComponentCount": sum(
            abs(item["thetaDeltaDegrees"]) > 1e-12 for item in diagnostics
        ),
        "projectedComponentCount": len(projected),
        "fixedEnvironmentComponentCount": len(fixed_environment_poses),
        "skippedBaselineComponents": skipped_baseline_components,
        "diagnostics": diagnostics,
        "limitation": (
            "Rotated world AABBs are conservative projections of saved world AABBs and may "
            "create false-positive broad-phase overlaps. Use only for world-AABB screening; "
            "perform SolidWorks Replay and exact B-Rep checks for final closure."
        ),
    }
    with timer.stage("persist-projection-report"):
        args.output_report.resolve().parent.mkdir(parents=True, exist_ok=True)
        args.output_report.resolve().write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    report["timing"] = timer.finish()
    report["timing"]["note"] = (
        "The final report rewrite that embeds this timing object is excluded from the "
        "persist-projection-report stage."
    )
    args.output_report.resolve().write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
