from __future__ import annotations

import copy
import itertools
import json
import math
from pathlib import Path
from typing import Any


class Project02FixedEnvironmentError(ValueError):
    pass


def attach_project02_fixed_environment(
    workspace: Path,
    request: dict[str, Any],
    generated: dict[str, Any],
) -> dict[str, Any]:
    """Add A600 as a fixed, constraining environment to a solved Project 02 layout.

    A600 is deliberately not a free search variable.  The movable layout is solved
    first, then every Top-K candidate is hard-gated against the A600 installation
    frame.  This mirrors the engineering order: enclosure -> transport -> process
    modules -> gantry coverage.
    """
    policy = request.get("fixedEnvironment") or {}
    if not bool(policy.get("enabled", False)):
        return generated

    pose_capture = _load_json(workspace, policy.get("geometryCapturePath"), "geometryCapturePath")
    frame = _load_json(workspace, policy.get("installationFramePath"), "installationFramePath")
    geometry = _load_json(
        workspace,
        policy.get("installationGeometryPath"),
        "installationGeometryPath",
    )
    pose = pose_capture.get("a600Pose")
    if not isinstance(pose, dict):
        raise Project02FixedEnvironmentError("A600 geometry capture has no a600Pose.")
    if frame.get("success") is not True or geometry.get("success") is not True:
        raise Project02FixedEnvironmentError(
            "A600 installation-frame or installation-geometry evidence is not successful."
        )

    component_name = str(pose.get("Name") or "").strip()
    component_path = str(pose.get("Path") or "").strip()
    world_box = _numbers(pose.get("BoundingBoxWorld"), 6, "A600 BoundingBoxWorld")
    transform = _numbers(pose.get("Transform"), 16, "A600 Transform")
    expected_code = str(policy.get("componentCode") or "A600").upper()
    if expected_code not in component_name.upper():
        raise Project02FixedEnvironmentError(
            f"Fixed environment expected {expected_code}, got '{component_name}'."
        )
    if any(
        str(item.get("componentName") or "").lower() == component_name.lower()
        for item in generated.get("components") or []
    ):
        raise Project02FixedEnvironmentError(
            f"Fixed environment '{component_name}' is already present in the layout."
        )

    base_frame = generated.get("baseFrame") or {}
    projected_bounds, height_range = _project_world_box(world_box, base_frame)
    center = [
        (projected_bounds[0] + projected_bounds[2]) / 2.0,
        (projected_bounds[1] + projected_bounds[3]) / 2.0,
    ]
    fixed_component = {
        "componentName": component_name,
        "filePath": component_path,
        "bottomFaceName": "A600_INSTALLATION_FRAME",
        "bottomCenterWorld": list(frame.get("originWorldMeters") or [0.0, 0.0, 0.0]),
        "bottomNormalWorld": list((frame.get("axesWorld") or {}).get("zUp") or [0.0, 1.0, 0.0]),
        "boundingBoxWorld": world_box,
        "fixedWorldTransform": transform,
        "layout2d": {
            "x": center[0],
            "y": center[1],
            "thetaDegrees": 0.0,
            "thetaAxis": "fixed-world",
            "normalOffsetMeters": height_range[0],
        },
        "role": "fixed",
        "roleReason": "A600 enclosure is the immutable installation datum and environment root.",
        "moduleSemantic": {
            "moduleType": "frame",
            "points": {},
            "regions": {},
            "preferredSide": "auto",
            "allowedRotationDegrees": [0],
            "parameters": {
                "fixedEnvironment": True,
                "degreesOfFreedom": 0,
                "installationFrameName": frame.get("frameName"),
                "installationGeometryStatus": geometry.get("status"),
                "authoritativeForFinalCollision": bool(
                    geometry.get("authoritativeForFinalCollision", False)
                ),
                "provisional": not bool(
                    geometry.get("authoritativeForFinalCollision", False)
                ),
            },
        },
        "projectedFootprint": {
            "minU": projected_bounds[0],
            "minV": projected_bounds[1],
            "maxU": projected_bounds[2],
            "maxV": projected_bounds[3],
        },
        "constraintPlacement": {
            "rotationQuarters": 0,
            "sourceThetaDegrees": 0.0,
            "containmentRelaxed": False,
            "fixedEnvironment": True,
            "degreesOfFreedom": 0,
            "replayPolicy": "preserve-source-world-transform",
        },
    }
    generated.setdefault("components", []).insert(0, fixed_component)

    plan = generated.setdefault("constraintPlan", {})
    roles = plan.setdefault("roles", {})
    role_reasons = plan.setdefault("roleReasons", {})
    semantics = plan.setdefault("moduleSemantics", {})
    roles[component_name] = "fixed"
    role_reasons[component_name] = fixed_component["roleReason"]
    semantics[component_name] = copy.deepcopy(fixed_component["moduleSemantic"])

    external_codes = {
        str(value).upper() for value in policy.get("externalModuleCodes") or []
    }
    validations: list[dict[str, Any]] = []
    rank_one_components = generated.get("components") or []
    validations.append(
        _validate_candidate(
            rank=1,
            components=rank_one_components,
            base_frame=base_frame,
            installation_frame=frame,
            geometry=geometry,
            fixed_name=component_name,
            external_codes=external_codes,
        )
    )

    joint_search = plan.get("jointSearch") or {}
    for solution in joint_search.get("solutions") or []:
        placements = solution.setdefault("placements", [])
        placements.insert(
            0,
            {
                "componentName": component_name,
                "role": "fixed",
                "x": center[0],
                "y": center[1],
                "thetaDegrees": 0.0,
                "rotationQuarters": 0,
                "bounds": projected_bounds,
                "fixedEnvironment": True,
                "degreesOfFreedom": 0,
            },
        )
        rank = int(solution.get("rank", len(validations)))
        if rank == 1:
            solution_validation = validations[0]
        else:
            candidate_components = _components_at_solution(
                generated.get("components") or [], placements
            )
            solution_validation = _validate_candidate(
                rank=rank,
                components=candidate_components,
                base_frame=base_frame,
                installation_frame=frame,
                geometry=geometry,
                fixed_name=component_name,
                external_codes=external_codes,
            )
            validations.append(solution_validation)
        solution["fixedEnvironmentValidation"] = solution_validation

    failures = [
        diagnostic
        for validation in validations
        for diagnostic in validation["diagnostics"]
        if diagnostic.get("hard") and not diagnostic.get("success")
    ]
    if failures:
        messages = "; ".join(str(item.get("message")) for item in failures[:4])
        raise Project02FixedEnvironmentError(
            "A600 fixed-environment hard constraint failed: " + messages
        )

    primary_validation = validations[0]
    plan["fixedEnvironment"] = {
        "componentName": component_name,
        "componentCode": expected_code,
        "role": "fixed",
        "degreesOfFreedom": 0,
        "worldTransformPreserved": True,
        "searchVariable": False,
        "installationFrameName": frame.get("frameName"),
        "geometryEvidencePath": str(
            _resolve_path(workspace, policy.get("installationGeometryPath"))
        ),
        "geometryAuthoritativeForFinalCollision": bool(
            geometry.get("authoritativeForFinalCollision", False)
        ),
        "candidateValidationCount": len(validations),
    }
    plan["fixedEnvironmentValidation"] = primary_validation
    candidate_counts = joint_search.setdefault("candidateCounts", {})
    accepted_counts = joint_search.setdefault("acceptedCandidateCounts", {})
    candidate_counts[component_name] = 1
    accepted_counts[component_name] = 1
    return generated


def augment_project02_collision_policy(
    policy: dict[str, Any],
    generated: dict[str, Any],
) -> dict[str, Any]:
    """Classify A600 pairs as installation-contact/structural-envelope relations."""
    result = copy.deepcopy(policy)
    fixed = (generated.get("constraintPlan") or {}).get("fixedEnvironment") or {}
    fixed_name = str(fixed.get("componentName") or "")
    if not fixed_name:
        return result
    names = [str(item.get("componentName")) for item in generated.get("components") or []]
    installation_pairs = [
        sorted((fixed_name, name)) for name in names if name != fixed_name
    ]
    result["installationContactPairs"] = installation_pairs
    all_pairs = list(itertools.combinations(sorted(names), 2))
    covered = (
        len(result.get("strictAabbPairs") or [])
        + len(result.get("brepOnAabbOverlapPairs") or [])
        + len(installation_pairs)
    )
    result.update(
        {
            "pairCount": len(all_pairs),
            "coveredPairCount": covered,
            "installationContactPairCount": len(installation_pairs),
            "maximumBrepReductionPairCount": len(result.get("strictAabbPairs") or []),
            "maximumBrepReductionRatio": (
                len(result.get("strictAabbPairs") or []) / max(1, len(all_pairs))
            ),
            "fixedEnvironmentPairPolicy": (
                "Validate the A600 installation frame and safe-boundary anchors during solve; "
                "after Replay, inspect illegal penetration without requiring zero nominal mounting contact."
            ),
        }
    )
    if result.get("requireCompletePairCoverage") and covered != len(all_pairs):
        raise Project02FixedEnvironmentError(
            f"Nine-object collision policy covers {covered}/{len(all_pairs)} pairs."
        )
    return result


def _validate_candidate(
    *,
    rank: int,
    components: list[dict[str, Any]],
    base_frame: dict[str, Any],
    installation_frame: dict[str, Any],
    geometry: dict[str, Any],
    fixed_name: str,
    external_codes: set[str],
) -> dict[str, Any]:
    safe = ((geometry.get("installationPlatform") or {}).get("safeBoundary") or {})
    support = geometry.get("transportSupportRegion") or {}
    required = ("minX", "minY", "maxX", "maxY")
    if any(key not in safe for key in required) or any(key not in support for key in required):
        raise Project02FixedEnvironmentError(
            "A600 safeBoundary or transportSupportRegion is incomplete."
        )

    diagnostics: list[dict[str, Any]] = [
        {
            "id": "a600-fixed-zero-dof",
            "type": "fixedEnvironment",
            "hard": True,
            "success": True,
            "message": "A600 is fixed at its captured world transform with zero solve DOF.",
            "measured": {"componentName": fixed_name, "degreesOfFreedom": 0},
        }
    ]
    for component in components:
        name = str(component.get("componentName") or "")
        if not name or name == fixed_name:
            continue
        code = _component_code(name)
        layout = component.get("layout2d") or {}
        xy = _solver_point_to_installation(
            [float(layout.get("x", 0.0)), float(layout.get("y", 0.0))],
            base_frame,
            installation_frame,
        )
        module_type = str((component.get("moduleSemantic") or {}).get("moduleType") or "")
        external = code.upper() in external_codes or module_type == "glue_supply"
        region = support if module_type == "transport" else safe
        success = external or _inside_xy(xy, region)
        diagnostics.append(
            {
                "id": (
                    f"a600-transport-anchor-{code.lower()}"
                    if module_type == "transport"
                    else f"a600-safe-anchor-{code.lower()}"
                ),
                "type": (
                    "transportAnchorInA600Support"
                    if module_type == "transport"
                    else "moduleAnchorInA600SafeBoundary"
                ),
                "hard": not external,
                "success": success,
                "message": (
                    f"{code} installation anchor is inside the A600 "
                    + ("transport support region." if module_type == "transport" else "safe platform boundary.")
                    if success and not external
                    else (
                        f"{code} is an explicitly external utility module; A600 platform containment is not required."
                        if external
                        else f"{code} installation anchor is outside its allowed A600 region."
                    )
                ),
                "measured": {
                    "componentName": name,
                    "componentCode": code,
                    "installationFrameXYMeters": xy,
                    "allowedRegion": {key: float(region[key]) for key in required},
                    "externalModule": external,
                },
            }
        )
    hard_items = [item for item in diagnostics if item["hard"]]
    passed = sum(bool(item["success"]) for item in hard_items)
    return {
        "rank": rank,
        "success": passed == len(hard_items),
        "hardFeasible": passed == len(hard_items),
        "constraintCount": len(hard_items),
        "passedCount": passed,
        "hardFailureCount": len(hard_items) - passed,
        "diagnostics": diagnostics,
    }


def _components_at_solution(
    components: list[dict[str, Any]], placements: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_name = {str(item.get("componentName")): item for item in placements}
    result: list[dict[str, Any]] = []
    for source in components:
        item = copy.deepcopy(source)
        placement = by_name.get(str(item.get("componentName")))
        if placement:
            item["layout2d"] = {
                **(item.get("layout2d") or {}),
                "x": float(placement["x"]),
                "y": float(placement["y"]),
                "thetaDegrees": float(placement.get("thetaDegrees", 0.0)),
            }
        result.append(item)
    return result


def _solver_point_to_installation(
    point: list[float],
    base_frame: dict[str, Any],
    installation_frame: dict[str, Any],
) -> list[float]:
    base_origin = _numbers(base_frame.get("origin"), 3, "baseFrame.origin")
    base_u = _unit(_numbers(base_frame.get("uAxis"), 3, "baseFrame.uAxis"))
    base_v = _unit(_numbers(base_frame.get("vAxis"), 3, "baseFrame.vAxis"))
    world = [
        base_origin[index] + point[0] * base_u[index] + point[1] * base_v[index]
        for index in range(3)
    ]
    install_origin = _numbers(
        installation_frame.get("originWorldMeters"), 3, "installationFrame.originWorldMeters"
    )
    axes = installation_frame.get("axesWorld") or {}
    install_x = _unit(_numbers(axes.get("xIntoMachine"), 3, "installationFrame.xIntoMachine"))
    install_y = _unit(
        _numbers(axes.get("yTransportLateral"), 3, "installationFrame.yTransportLateral")
    )
    relative = [world[index] - install_origin[index] for index in range(3)]
    return [_dot(relative, install_x), _dot(relative, install_y)]


def _project_world_box(
    box: list[float], frame: dict[str, Any]
) -> tuple[list[float], list[float]]:
    origin = _numbers(frame.get("origin"), 3, "baseFrame.origin")
    axes = [
        _unit(_numbers(frame.get("uAxis"), 3, "baseFrame.uAxis")),
        _unit(_numbers(frame.get("vAxis"), 3, "baseFrame.vAxis")),
        _unit(_numbers(frame.get("normal"), 3, "baseFrame.normal")),
    ]
    corners = [
        [x, y, z]
        for x in (box[0], box[3])
        for y in (box[1], box[4])
        for z in (box[2], box[5])
    ]
    projected = [
        [_dot([point[i] - origin[i] for i in range(3)], axis) for axis in axes]
        for point in corners
    ]
    return (
        [
            min(value[0] for value in projected),
            min(value[1] for value in projected),
            max(value[0] for value in projected),
            max(value[1] for value in projected),
        ],
        [min(value[2] for value in projected), max(value[2] for value in projected)],
    )


def _inside_xy(point: list[float], region: dict[str, Any]) -> bool:
    tolerance = 1e-9
    return (
        float(region["minX"]) - tolerance <= point[0] <= float(region["maxX"]) + tolerance
        and float(region["minY"]) - tolerance <= point[1] <= float(region["maxY"]) + tolerance
    )


def _load_json(workspace: Path, value: Any, label: str) -> dict[str, Any]:
    if not value:
        raise Project02FixedEnvironmentError(f"fixedEnvironment.{label} is required.")
    path = _resolve_path(workspace, value)
    if not path.is_file():
        raise Project02FixedEnvironmentError(f"A600 evidence does not exist: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _resolve_path(workspace: Path, value: Any) -> Path:
    path = Path(str(value))
    return path.resolve() if path.is_absolute() else (workspace / path).resolve()


def _numbers(value: Any, count: int, label: str) -> list[float]:
    if not isinstance(value, list) or len(value) != count:
        raise Project02FixedEnvironmentError(f"{label} must contain {count} numbers.")
    try:
        result = [float(item) for item in value]
    except (TypeError, ValueError) as exc:
        raise Project02FixedEnvironmentError(f"{label} contains non-numeric values.") from exc
    if not all(math.isfinite(item) for item in result):
        raise Project02FixedEnvironmentError(f"{label} contains non-finite values.")
    return result


def _unit(vector: list[float]) -> list[float]:
    length = math.sqrt(sum(value * value for value in vector))
    if length <= 1e-12:
        raise Project02FixedEnvironmentError("Coordinate-frame axis has zero length.")
    return [value / length for value in vector]


def _dot(first: list[float], second: list[float]) -> float:
    return sum(a * b for a, b in zip(first, second, strict=True))


def _component_code(name: str) -> str:
    upper = str(name).upper()
    for code in ("A100", "A180", "A200", "A300", "A500", "A600", "A700", "A800", "T401"):
        if code in upper:
            return code
    return str(name)
