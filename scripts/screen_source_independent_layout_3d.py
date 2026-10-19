"""Broad-phase all top-level pairs in the saved source-independent assembly."""

from __future__ import annotations

import argparse
import itertools
import json
import math
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.pipeline_timing import PipelineTiming  # noqa: E402
LAYOUT = ROOT / "demo" / "FL9A24D062A000_source_independent_replay_layout2d.json"
POSES = ROOT / "demo" / "FL9A24D062A000_source_independent_corrected_component_poses.json"
OUTPUT = ROOT / "demo" / "FL9A24D062A000_source_independent_corrected_3d_screening.json"
SEPARATION_TOLERANCE_METERS = 1e-6


def pose_rows(payload: object) -> list[dict]:
    """Accept both the historical bare list and the versioned pose catalog."""

    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        rows = payload.get("components")
        if isinstance(rows, list):
            return [item for item in rows if isinstance(item, dict)]
    raise ValueError("Pose evidence must be a list or an object with a components list.")


def module_token(name: str) -> str:
    upper = str(name).upper()
    marker = "D062A"
    if marker in upper:
        suffix = upper.split(marker, 1)[1]
        return "A" + suffix.split(".", 1)[0]
    for token in ("A100", "A180", "A200", "A300", "A500", "A600", "A700", "A800"):
        if upper.startswith(token):
            return token
    if upper.startswith("T401"):
        return "T401"
    return upper


def boxes_by_layout_name(rows: list[dict], layout: dict) -> dict[str, list[float]]:
    """Map static replacement occurrence names back to their module policy name."""

    expected_names = [
        str(item.get("componentName") or "")
        for item in layout.get("components") or []
        if item.get("componentName")
    ]
    expected_by_token: dict[str, list[str]] = {}
    for name in expected_names:
        expected_by_token.setdefault(module_token(name), []).append(name)

    boxes: dict[str, list[float]] = {}
    for item in rows:
        actual_name = str(item.get("Name") or "")
        bounds = item.get("BoundingBoxWorld")
        if not actual_name or not isinstance(bounds, list) or len(bounds) != 6:
            continue
        policy_name = actual_name
        if policy_name not in expected_names:
            matches = expected_by_token.get(module_token(actual_name), [])
            if len(matches) == 1:
                policy_name = matches[0]
        boxes[policy_name] = bounds
    return boxes


def _pair_key(first: str, second: str) -> frozenset[str]:
    return frozenset((first, second))


def classify_world_aabb_pairs(
    boxes: dict[str, list[float]],
    collision_policy: dict,
    *,
    separation_tolerance_meters: float = SEPARATION_TOLERANCE_METERS,
) -> list[dict]:
    """Apply the exhaustive pair policy without invoking SolidWorks B-Rep."""
    strict_pairs = {
        frozenset(pair) for pair in collision_policy.get("strictAabbPairs") or []
    }
    conditional_pairs = {
        frozenset(pair)
        for pair in collision_policy.get("brepOnAabbOverlapPairs") or []
    }
    installation_pairs = {
        frozenset(pair)
        for pair in collision_policy.get("installationContactPairs") or []
    }
    inflation = float(collision_policy.get("aabbInflationPerSideMeters", 0.0))
    required_strict_gap = inflation * 2.0
    diagnostics: list[dict] = []
    for first, second in itertools.combinations(sorted(boxes), 2):
        first_box = boxes[first]
        second_box = boxes[second]
        overlaps = [
            min(first_box[axis + 3], second_box[axis + 3])
            - max(first_box[axis], second_box[axis])
            for axis in range(3)
        ]
        gaps = [
            max(
                first_box[axis] - second_box[axis + 3],
                second_box[axis] - first_box[axis + 3],
                0.0,
            )
            for axis in range(3)
        ]
        pair_key = _pair_key(first, second)
        if pair_key in strict_pairs:
            policy_name = "strict_aabb"
            separated = any(
                value + separation_tolerance_meters >= required_strict_gap
                for value in gaps
            )
            status = "passed_by_strict_inflated_aabb" if separated else "failed_strict_inflated_aabb"
            requires_brep = False
        elif pair_key in conditional_pairs:
            policy_name = "brep_on_aabb_overlap"
            separated = any(value > separation_tolerance_meters for value in gaps)
            status = "passed_by_world_aabb" if separated else "needs_exact_brep_check"
            requires_brep = not separated
            requires_installation_review = False
        elif pair_key in installation_pairs:
            policy_name = "installation_contact"
            separated = any(value > separation_tolerance_meters for value in gaps)
            status = (
                "passed_by_world_aabb"
                if separated
                else "needs_installation_contact_review"
            )
            requires_brep = False
            requires_installation_review = not separated
        else:
            policy_name = "unclassified"
            separated = False
            status = "failed_unclassified_pair"
            requires_brep = False
            requires_installation_review = False
        if pair_key in strict_pairs:
            requires_installation_review = False
        overlaps_3d = all(value > 0 for value in overlaps)
        diagnostics.append(
            {
                "components": [first, second],
                "collisionPolicy": policy_name,
                "status": status,
                "success": (
                    status.startswith("passed_")
                    or requires_brep
                    or requires_installation_review
                ),
                "requiresExactBrep": requires_brep,
                "requiresInstallationContactReview": requires_installation_review,
                "aabbOverlaps3d": overlaps_3d,
                "broadPhaseSeparated": separated,
                "requiredStrictGapMeters": required_strict_gap if policy_name == "strict_aabb" else None,
                "axisOverlapMeters": overlaps,
                "axisGapMeters": gaps,
                "minimumAabbDistanceMeters": math.sqrt(sum(value * value for value in gaps)),
                "intersectionBoxVolumeCubicMeters": math.prod(overlaps) if overlaps_3d else 0.0,
            }
        )
    return diagnostics


def dot(first: list[float], second: list[float]) -> float:
    return sum(a * b for a, b in zip(first, second, strict=True))


def projected_bounds(box: list[float], frame: dict) -> list[float]:
    origin = frame["origin"]
    corners = [
        [x, y, z]
        for x in (box[0], box[3])
        for y in (box[1], box[4])
        for z in (box[2], box[5])
    ]
    projected = [
        [
            dot([point[index] - origin[index] for index in range(3)], frame["uAxis"]),
            dot([point[index] - origin[index] for index in range(3)], frame["vAxis"]),
        ]
        for point in corners
    ]
    return [
        min(point[0] for point in projected),
        min(point[1] for point in projected),
        max(point[0] for point in projected),
        max(point[1] for point in projected),
    ]


def overlap_ratio(inner: list[float], outer: list[float]) -> float:
    width = max(0.0, min(inner[2], outer[2]) - max(inner[0], outer[0]))
    height = max(0.0, min(inner[3], outer[3]) - max(inner[1], outer[1]))
    area = max(0.0, inner[2] - inner[0]) * max(0.0, inner[3] - inner[1])
    return width * height / max(area, 1e-12)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run world-AABB broad-phase screening for a saved Replay assembly."
    )
    parser.add_argument("--layout", type=Path, default=LAYOUT)
    parser.add_argument("--poses", type=Path, default=POSES)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument(
        "--assembly",
        type=Path,
        default=ROOT
        / "demo"
        / "FL9A24D062A000_8components_source_independent_corrected.SLDASM",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    timer = PipelineTiming("project02.world-aabb-screening")
    with timer.stage("load-layout-and-projected-poses"):
        layout_path = args.layout.resolve()
        poses_path = args.poses.resolve()
        output_path = args.output.resolve()
        assembly_path = args.assembly.resolve()
        layout = json.loads(layout_path.read_text(encoding="utf-8"))
        poses = pose_rows(json.loads(poses_path.read_text(encoding="utf-8")))
        boxes = boxes_by_layout_name(poses, layout)
        allowed = {
            frozenset(pair)
            for pair in layout["constraintPlan"]["validation"][
                "allowedAabbOverlapPairs"
            ]
        }

    plan = layout["constraintPlan"]
    collision_policy = plan.get("staticCollisionPolicy") or {}
    with timer.stage("classify-all-module-pairs", pairCount=math.comb(len(boxes), 2)):
        if collision_policy.get("enabled"):
            diagnostics = classify_world_aabb_pairs(boxes, collision_policy)
        else:
            diagnostics = []
            for first, second in itertools.combinations(sorted(boxes), 2):
                first_box = boxes[first]
                second_box = boxes[second]
                overlaps = [
                    min(first_box[axis + 3], second_box[axis + 3])
                    - max(first_box[axis], second_box[axis])
                    for axis in range(3)
                ]
                gaps = [
                    max(
                        first_box[axis] - second_box[axis + 3],
                        second_box[axis] - first_box[axis + 3],
                        0.0,
                    )
                    for axis in range(3)
                ]
                separated = any(
                    value > SEPARATION_TOLERANCE_METERS for value in gaps
                )
                diagnostics.append(
                    {
                        "components": [first, second],
                        "collisionPolicy": "legacy_all_overlap_to_brep",
                        "status": (
                            "passed_by_world_aabb"
                            if separated
                            else "needs_exact_brep_check"
                        ),
                        "success": True,
                        "requiresExactBrep": not separated,
                        "aabbOverlaps3d": all(value > 0 for value in overlaps),
                        "broadPhaseSeparated": separated,
                        "axisOverlapMeters": overlaps,
                        "axisGapMeters": gaps,
                        "minimumAabbDistanceMeters": math.sqrt(
                            sum(value * value for value in gaps)
                        ),
                        "intersectionBoxVolumeCubicMeters": (
                            math.prod(overlaps)
                            if all(value > 0 for value in overlaps)
                            else 0.0
                        ),
                    }
                )
        for item in diagnostics:
            item["projectedOverlapAllowed"] = (
                frozenset(item["components"]) in allowed
            )
    pending = [item for item in diagnostics if item.get("requiresExactBrep")]
    installation_pending = [
        item for item in diagnostics if item.get("requiresInstallationContactReview")
    ]
    strict_failures = [
        item for item in diagnostics if item["status"] == "failed_strict_inflated_aabb"
    ]
    unclassified = [
        item for item in diagnostics if item["status"] == "failed_unclassified_pair"
    ]
    with timer.stage("validate-spatial-coverage"):
        gantry_name = plan["gantryComponentName"]
        actual_projected = {
            name: projected_bounds(box, layout["baseFrame"])
            for name, box in boxes.items()
        }
        gantry_bounds = actual_projected[gantry_name]
        minimum_by_component = {
            item["componentName"]: float(item["minimumOverlapRatio"])
            for item in plan["spatialValidation"]["diagnostics"]
            if "minimumOverlapRatio" in item
        }
        actual_spatial = []
        for name, minimum in minimum_by_component.items():
            ratio = overlap_ratio(actual_projected[name], gantry_bounds)
            actual_spatial.append(
                {
                    "componentName": name,
                    "success": ratio >= minimum - 1e-9,
                    "actualOverlapRatio": ratio,
                    "minimumOverlapRatio": minimum,
                    "actualComponentBounds": actual_projected[name],
                    "actualGantryBounds": gantry_bounds,
                }
            )

    transports = [name for name, role in plan["roles"].items() if role == "transport"]
    policy = plan.get("sourceIndependentPolicy", {})
    required_pairs = [
        [name, transport]
        for name in policy.get("forbidTransportProjectionOverlapComponents", [])
        for transport in transports
    ]
    by_pair = {frozenset(item["components"]): item for item in diagnostics}
    required_separation = []
    for pair in required_pairs:
        check = by_pair[frozenset(pair)]
        required_separation.append(
            {
                "components": pair,
                "success": check["broadPhaseSeparated"],
                "minimumAabbDistanceMeters": check["minimumAabbDistanceMeters"],
                "axisGapMeters": check["axisGapMeters"],
            }
        )
    interaction_validation = plan.get("interactionValidation", {})
    targeted_success = (
        all(item["success"] for item in actual_spatial)
        and all(item["success"] for item in required_separation)
        and interaction_validation.get("hardFeasible", True)
        and not strict_failures
        and not unclassified
    )
    result = {
        "success": targeted_success,
        "broadPhaseSuccess": targeted_success,
        "staticInterferenceClosed": targeted_success and not pending and not installation_pending,
        "assemblyPath": str(assembly_path),
        "poseSource": str(poses_path),
        "componentCount": len(boxes),
        "pairCount": len(diagnostics),
        "separationToleranceMeters": SEPARATION_TOLERANCE_METERS,
        "excludedBy3dAabbCount": (
            len(diagnostics)
            - len(pending)
            - len(installation_pending)
            - len(strict_failures)
            - len(unclassified)
        ),
        "needsExactBrepCheckCount": len(pending),
        "candidatePairs": [item["components"] for item in pending],
        "installationContactReviewCount": len(installation_pending),
        "installationContactPairs": [item["components"] for item in installation_pending],
        "strictAabbPairCount": sum(item["collisionPolicy"] == "strict_aabb" for item in diagnostics),
        "strictAabbFailureCount": len(strict_failures),
        "unclassifiedPairCount": len(unclassified),
        "brepAvoidedPairCount": len(diagnostics) - len(pending),
        "brepAvoidedRatio": (len(diagnostics) - len(pending)) / max(1, len(diagnostics)),
        "actualSpatialValidation": {
            "success": all(item["success"] for item in actual_spatial),
            "diagnostics": actual_spatial,
        },
        "requiredTransportSeparationValidation": {
            "success": all(item["success"] for item in required_separation),
            "diagnostics": required_separation,
        },
        "solverInteractionValidation": interaction_validation,
        "interpretation": (
            "Strict ordinary-module pairs pass only when their inflated world AABBs are separated. "
            "Structural pairs invoke exact B-Rep only when their world AABBs still overlap. "
            "A600 pairs preserve nominal mounting contact and are reviewed separately for illegal penetration."
        ),
        "diagnostics": diagnostics,
    }
    with timer.stage("persist-screening-report"):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    result["timing"] = timer.finish()
    result["timing"]["note"] = (
        "The final report rewrite that embeds this timing object is excluded from the "
        "persist-screening-report stage."
    )
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
