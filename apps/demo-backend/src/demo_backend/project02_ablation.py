from __future__ import annotations

import copy
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VARIANTS = ("A", "B", "C")

SERVICE_POSITION_WINDOW_IDS = {
    "a700-a200-operation-side-partition-window",
    "a300-a700-coarse-service-cluster-envelope",
    "a500-a700-calibration-cleaning-relative-window",
}

SERVICE_POSITION_BIAS_FIELDS = {
    "sourceIndependentAnchorBiasU",
    "sourceIndependentAnchorBiasV",
    "prioritizeSourceIndependentAnchorBias",
}

SERVICE_COMPONENT_CODES = {"A300", "A500", "A700"}

# Frames and portals must preserve their real openings.  A direct-child union
# turns the gantry/CCD structure into a solid slab and creates false clearance
# failures.  Transport remains at direct-child resolution because its moving
# corridor is already represented separately by process keep-outs.
OPEN_STRUCTURE_COMPONENT_CODES = {"A100", "A200"}
LEAF_RESOLUTION_COMPONENT_CODES = (
    SERVICE_COMPONENT_CODES | OPEN_STRUCTURE_COMPONENT_CODES
)


def load_dependency_ablation_bundle(workspace: Path) -> dict[str, Any]:
    report_path = workspace / "demo/layout_previews/project02_dependency_ablation_report.json"
    if not report_path.is_file():
        raise FileNotFoundError(f"Project02 dependency-ablation report not found: {report_path}")
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    variants: dict[str, Any] = {}
    for variant in ("B", "C"):
        preview_path = (
            workspace
            / f"demo/layout_previews/project02_dependency_ablation/variant_{variant.lower()}_preview.json"
        )
        if preview_path.is_file():
            variants[variant] = json.loads(preview_path.read_text(encoding="utf-8-sig"))
    if not variants:
        raise FileNotFoundError("Project02 dependency-ablation B/C previews are missing")
    feedback_report_path = (
        workspace
        / "demo/layout_previews/project02_collision_feedback/feedback_hardened_report.json"
    )
    feedback_preview_path = (
        workspace
        / "demo/layout_previews/project02_collision_feedback/feedback_hardened_preview.json"
    )
    collision_feedback = None
    if feedback_report_path.is_file() and feedback_preview_path.is_file():
        collision_feedback = {
            "reportPath": str(feedback_report_path),
            "previewPath": str(feedback_preview_path),
            "report": json.loads(feedback_report_path.read_text(encoding="utf-8-sig")),
            "preview": json.loads(feedback_preview_path.read_text(encoding="utf-8-sig")),
        }
    return {
        "schemaVersion": "project02-dependency-ablation-display/v2",
        "readOnly": True,
        "reportPath": str(report_path),
        "report": report,
        "variants": variants,
        "collisionFeedback": collision_feedback,
    }


def _component_code(component_name: str) -> str:
    upper = component_name.upper()
    if upper.startswith("T401"):
        return "T401"
    if "D062A" in upper:
        return "A" + upper.split("D062A", 1)[1].split(".", 1)[0]
    return component_name


def _remove_geometry_policy_contradictions(
    request: dict[str, Any],
    removed_fields: list[str],
) -> None:
    """Let conditional B-Rep own pairs that were also forced hard by history."""

    collision_policy = request.get("staticCollisionPolicy") or {}
    conditional_pairs = {
        frozenset(str(value) for value in pair)
        for pair in collision_policy.get("brepOnAabbOverlapPairs") or []
        if isinstance(pair, list) and len(pair) == 2
    }
    if not conditional_pairs:
        return
    for component_name, semantic in (request.get("moduleSemantics") or {}).items():
        parameters = semantic.get("parameters") if isinstance(semantic, dict) else None
        if not isinstance(parameters, dict):
            continue
        raw_targets = parameters.get("hardOccupancyClearanceWith")
        if not isinstance(raw_targets, list):
            continue
        source_code = _component_code(component_name)
        retained = [
            target
            for target in raw_targets
            if frozenset((source_code, _component_code(str(target))))
            not in conditional_pairs
        ]
        if retained == raw_targets:
            continue
        parameters["hardOccupancyClearanceWith"] = retained
        removed_fields.append(
            f"moduleSemantics.{component_name}.parameters."
            "hardOccupancyClearanceWith:conditional-brep-conflicts-removed"
        )


def _downgrade_unconfirmed_maintenance_spaces(
    request: dict[str, Any],
    removed_fields: list[str],
) -> None:
    """Keep estimated operator access visible without treating it as vendor truth."""

    for component_name, semantic in (request.get("moduleSemantics") or {}).items():
        parameters = semantic.get("parameters") if isinstance(semantic, dict) else None
        if not isinstance(parameters, dict) or parameters.get("serviceAccessLaneConfirmed") is True:
            continue
        for space in parameters.get("protectedSpaceBoxesLocal") or []:
            if not isinstance(space, dict):
                continue
            identifier = str(space.get("id") or "").lower()
            purpose = str(space.get("purpose") or "").lower()
            if not any(
                token in f"{identifier} {purpose}"
                for token in ("operator", "maintenance", "维护", "工具", "耗材")
            ):
                continue
            space["enforcement"] = "advisory"
            space["confirmed"] = False
            space["evidenceStatus"] = (
                "prototype-derived coarse estimate; pending engineer/vendor confirmation"
            )
            removed_fields.append(
                f"moduleSemantics.{component_name}.parameters.protectedSpaceBoxesLocal."
                f"{space.get('id')}:hard-to-advisory"
            )


def _route_protected_spaces_to_conditional_brep(
    request: dict[str, Any],
    removed_fields: list[str],
) -> None:
    collision_policy = request.get("staticCollisionPolicy") or {}
    conditional_pairs = {
        frozenset(str(value) for value in pair)
        for pair in collision_policy.get("brepOnAabbOverlapPairs") or []
        if isinstance(pair, list) and len(pair) == 2
    }
    for component_name, semantic in (request.get("moduleSemantics") or {}).items():
        parameters = semantic.get("parameters") if isinstance(semantic, dict) else None
        if not isinstance(parameters, dict):
            continue
        source_code = _component_code(component_name)
        for space in parameters.get("protectedSpaceBoxesLocal") or []:
            if not isinstance(space, dict):
                continue
            targets = space.get("hardClearanceWith") or []
            if isinstance(targets, str):
                targets = [targets]
            conditional_targets = [
                str(target)
                for target in targets
                if frozenset((source_code, _component_code(str(target))))
                in conditional_pairs
            ]
            if not conditional_targets:
                continue
            space["conditionalBrepWith"] = conditional_targets
            removed_fields.append(
                f"moduleSemantics.{component_name}.parameters.protectedSpaceBoxesLocal."
                f"{space.get('id')}:leaf-aabb-to-conditional-brep"
            )


def build_ablation_request(
    base_request: dict[str, Any],
    variant: str,
    *,
    geometry_occupancy_path: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build a Project02 dependency-ablation request without mutating its source."""

    variant = variant.upper()
    if variant not in VARIANTS:
        raise ValueError(f"Unknown Project02 ablation variant: {variant}")
    request = copy.deepcopy(base_request)
    removed_fields: list[str] = []
    removed_constraints: list[str] = []
    occupancy_path = request.get("structuralOccupancyPath")

    if variant in {"B", "C"}:
        if not geometry_occupancy_path:
            raise ValueError("Variants B/C require a geometry-only occupancy path")
        request["structuralOccupancyPath"] = geometry_occupancy_path
        removed_fields.append("structuralOccupancyPath:v42-history-overlay-replaced")
        _remove_geometry_policy_contradictions(request, removed_fields)
        _downgrade_unconfirmed_maintenance_spaces(request, removed_fields)
        _route_protected_spaces_to_conditional_brep(request, removed_fields)

    if variant == "C":
        kept_constraints = []
        for constraint in request.get("processConstraints") or []:
            constraint_id = str(constraint.get("id") or "")
            if constraint_id in SERVICE_POSITION_WINDOW_IDS:
                removed_constraints.append(constraint_id)
            else:
                kept_constraints.append(constraint)
        request["processConstraints"] = kept_constraints

        for component_name, semantic in (request.get("moduleSemantics") or {}).items():
            code = (
                "T401"
                if component_name.upper().startswith("T401")
                else "A" + component_name.split("D062A", 1)[1].split(".", 1)[0]
                if "D062A" in component_name
                else component_name
            )
            if code not in SERVICE_COMPONENT_CODES:
                continue
            parameters = semantic.get("parameters") if isinstance(semantic, dict) else None
            if not isinstance(parameters, dict):
                continue
            for field in sorted(SERVICE_POSITION_BIAS_FIELDS):
                if field in parameters:
                    parameters.pop(field, None)
                    removed_fields.append(f"moduleSemantics.{component_name}.parameters.{field}")

    metadata = {
        "variant": variant,
        "structuralOccupancyMode": (
            "v42-history-feedback-overlay"
            if variant == "A"
            else "geometry-only-open-structure-leaf-resolution"
        ),
        "sourceStructuralOccupancyPath": occupancy_path,
        "removedFields": removed_fields,
        "removedConstraintIds": removed_constraints,
        "retainedInterfaceConstraintIds": [
            "a200-a800-ccd-transport-process-window",
            "a180-a200-scanner-ccd-channel-window",
        ],
        "interpretation": {
            "A": "Current v42 baseline, including accumulated pair-specific collision feedback.",
            "B": "CAD geometry with leaf-level open structures/service modules plus process constraints, without the v42 history overlay.",
            "C": "Variant B with nonessential service-cluster pose windows and candidate biases removed.",
        }[variant],
    }
    return request, metadata


def _dot(first: list[float], second: list[float]) -> float:
    return sum(float(a) * float(b) for a, b in zip(first, second))


def _subtract(first: list[float], second: list[float]) -> list[float]:
    return [float(a) - float(b) for a, b in zip(first, second)]


def _corners(box: list[float]) -> list[list[float]]:
    return [
        [x, y, z]
        for x in (float(box[0]), float(box[3]))
        for y in (float(box[1]), float(box[4]))
        for z in (float(box[2]), float(box[5]))
    ]


def _rotate(u: float, v: float, quarters: int) -> tuple[float, float]:
    radians = math.radians((quarters % 4) * 90.0)
    cosine, sine = math.cos(radians), math.sin(radians)
    return cosine * u - sine * v, sine * u + cosine * v


def _layout_rows(document: dict[str, Any]) -> list[dict[str, Any]]:
    direct = document.get("components")
    if isinstance(direct, list) and direct:
        return direct
    for step in document.get("steps") or []:
        payload = step.get("payload") or {}
        rows = payload.get("components")
        if step.get("tool") == "apply_captured_common_base_layout" and isinstance(rows, list):
            return rows
    raise ValueError("Layout document has no component rows")


def build_geometry_only_occupancy(
    geometry: dict[str, Any],
    capture_layout_documents: list[tuple[dict[str, Any], dict[str, Any], str]],
) -> dict[str, Any]:
    """Build history-independent mixed-resolution boxes from leaf CAD captures."""

    frame = geometry["baseFrame"]
    origin = [float(value) for value in frame["origin"]]
    axes = {
        "u": [float(value) for value in frame["uAxis"]],
        "v": [float(value) for value in frame["vAxis"]],
        "n": [float(value) for value in frame["normal"]],
    }
    geometry_layouts = {
        str(item["componentName"]): item["layout2d"]
        for item in geometry.get("components") or []
    }
    components: dict[str, Any] = {}
    for capture, layout_document, source_label in capture_layout_documents:
        layouts = {
            str(item["componentName"]): item["layout2d"]
            for item in _layout_rows(layout_document)
        }
        for captured in capture.get("captures") or []:
            top_name = str((captured.get("TopLevelComponent") or {}).get("Name") or "")
            if not top_name or top_name in components:
                continue
            if top_name not in layouts or top_name not in geometry_layouts:
                raise ValueError(f"No layout anchor for captured component {top_name}")
            layout = layouts[top_name]
            anchor_u = float(layout["x"])
            anchor_v = float(layout["y"])
            source_theta = float(geometry_layouts[top_name].get("thetaDegrees", 0.0))
            capture_theta = float(layout.get("thetaDegrees", source_theta))
            quarters = int(round((capture_theta - source_theta) / 90.0))
            groups: dict[str, dict[str, Any]] = {}
            for body in captured.get("Bodies") or []:
                world_box = body.get("BoundingBoxWorld")
                if not isinstance(world_box, list) or len(world_box) != 6:
                    continue
                component_name = str((body.get("Component") or {}).get("Name") or "")
                parts = component_name.split("/")
                code = (
                    "T401"
                    if top_name.upper().startswith("T401")
                    else "A" + top_name.split("D062A", 1)[1].split(".", 1)[0]
                )
                # Service modules and open structures need leaf-instance
                # resolution.  Merging A710/A720/A730 closes their real gaps;
                # merging gantry/CCD children fills real door openings.  The
                # transport stays at direct-child resolution for speed because
                # its moving corridor has separate process keep-outs.
                group_name = (
                    component_name
                    if code in LEAF_RESOLUTION_COMPONENT_CODES
                    else parts[1]
                    if len(parts) > 1
                    else parts[0]
                )
                projected = {
                    axis: [
                        _dot(_subtract(point, origin), vector)
                        for point in _corners(world_box)
                    ]
                    for axis, vector in axes.items()
                }
                local_points = [
                    _rotate(u - anchor_u, v - anchor_v, -quarters)
                    for u in (min(projected["u"]), max(projected["u"]))
                    for v in (min(projected["v"]), max(projected["v"]))
                ]
                incoming = {
                    "bounds": [
                        min(point[0] for point in local_points),
                        min(point[1] for point in local_points),
                        max(point[0] for point in local_points),
                        max(point[1] for point in local_points),
                    ],
                    "heightRangeMeters": [
                        max(0.0, min(projected["n"])),
                        max(1e-6, max(projected["n"])),
                    ],
                }
                current = groups.get(group_name)
                if current is None:
                    groups[group_name] = incoming
                    continue
                left, right = current["bounds"], incoming["bounds"]
                current["bounds"] = [
                    min(left[0], right[0]),
                    min(left[1], right[1]),
                    max(left[2], right[2]),
                    max(left[3], right[3]),
                ]
                first_height, second_height = current["heightRangeMeters"], incoming["heightRangeMeters"]
                current["heightRangeMeters"] = [
                    min(first_height[0], second_height[0]),
                    max(first_height[1], second_height[1]),
                ]
            boxes = [
                {
                    "id": f"{code}-geometry-child-{index}",
                    "bounds": item["bounds"],
                    "heightRangeMeters": item["heightRangeMeters"],
                    "componentCode": code,
                    "occupancyScope": (
                        "geometry-only-leaf-instance-union"
                        if code in LEAF_RESOLUTION_COMPONENT_CODES
                        else "geometry-only-direct-child-union"
                    ),
                    "sourceChild": group_name,
                    "minimumClearanceMeters": 0.0001,
                }
                for index, (group_name, item) in enumerate(sorted(groups.items()))
            ]
            if not boxes:
                raise ValueError(f"No usable CAD bodies for {top_name}")
            components[top_name] = {
                "code": code,
                "hardClearance": True,
                "source": source_label,
                "boxCount": len(boxes),
                "capturedBodyCount": int(captured.get("BodyCount") or 0),
                "boxMergeMode": (
                    "leaf-instance-union-without-collision-history"
                    if code in LEAF_RESOLUTION_COMPONENT_CODES
                    else "direct-child-union-without-collision-history"
                ),
                "boxes": boxes,
            }
    return {
        "schemaVersion": 1,
        "coordinateFrame": "component bottom-centre local U/V plus Common Base normal height",
        "conservative": True,
        "occupancyMode": "geometry-only-open-structure-leaf-resolution",
        "historicalCollisionFeedbackUsed": False,
        "components": components,
    }


def _module_map(preview: dict[str, Any], rank: int = 1) -> dict[str, dict[str, Any]]:
    solution = next(
        (item for item in preview.get("solutions") or [] if int(item.get("rank", -1)) == rank),
        None,
    )
    if solution is None:
        return {}
    return {
        str(module.get("componentName")): module
        for module in solution.get("modules") or []
        if module.get("componentName")
    }


def compare_rank1_poses(
    preview: dict[str, Any],
    reference_preview: dict[str, Any],
) -> dict[str, Any]:
    current = _module_map(preview)
    reference = _module_map(reference_preview)
    rows = []
    for name in sorted(set(current).intersection(reference)):
        if name.endswith("A600.001-1"):
            continue
        first = current[name]
        second = reference[name]
        first_center = [float(value) for value in first.get("center") or (0.0, 0.0)]
        second_center = [float(value) for value in second.get("center") or (0.0, 0.0)]
        distance = math.dist(first_center, second_center)
        angle = abs(
            ((float(first.get("thetaDegrees", 0.0)) - float(second.get("thetaDegrees", 0.0)) + 180.0) % 360.0)
            - 180.0
        )
        rows.append(
            {
                "componentName": name,
                "centerDistanceMeters": distance,
                "angleDifferenceDegrees": angle,
            }
        )
    distances = [row["centerDistanceMeters"] for row in rows]
    return {
        "matchedMovableComponentCount": len(rows),
        "maximumCenterDistanceMeters": max(distances, default=0.0),
        "rmsCenterDistanceMeters": (
            math.sqrt(sum(value * value for value in distances) / len(distances))
            if distances
            else 0.0
        ),
        "maximumAngleDifferenceDegrees": max(
            (row["angleDifferenceDegrees"] for row in rows),
            default=0.0,
        ),
        "materiallyDifferent": any(
            row["centerDistanceMeters"] > 0.02
            or row["angleDifferenceDegrees"] > 1.0
            for row in rows
        ),
        "components": rows,
    }


def evaluate_reference_preview_interactions(
    workspace: Path,
    request: dict[str, Any],
    geometry: dict[str, Any],
    preview: dict[str, Any],
) -> dict[str, Any]:
    """Re-evaluate an existing rank-1 pose with the request's current geometry model.

    This control separates search failure from model incompatibility.  If a
    previously accepted pose fails after replacing historical occupancy with
    complete geometry, a longer search alone cannot establish that the two
    formulations are equivalent.
    """

    from .constraint_layout import (
        Placement,
        _apply_semantic_footprint_override,
        _evaluate_interaction_hard_constraints,
        _infer_roles,
        _normalize_portal_constraints,
        _read_footprints,
    )
    from .layout_preview import build_source_independent_options
    from .process_constraints import normalize_module_semantics, role_overrides_from_semantics

    options = build_source_independent_options(request, workspace)
    raw_footprints = _read_footprints(geometry)
    semantics = normalize_module_semantics(
        [item.component_name for item in raw_footprints],
        options.module_semantics,
    )
    footprints = [
        _apply_semantic_footprint_override(item, semantics.get(item.component_name))
        for item in raw_footprints
    ]
    footprint_map = {item.component_name: item for item in footprints}
    roles, _ = _infer_roles(
        footprints,
        {**role_overrides_from_semantics(semantics), **options.role_overrides},
    )
    portal_pass_through = _normalize_portal_constraints(
        footprints,
        roles,
        options.portal_pass_through,
    )
    modules = (preview.get("solutions") or [{}])[0].get("modules") or []
    placements: list[Placement] = []
    for module in modules:
        name = str(module.get("componentName") or "")
        if name not in footprint_map:
            continue
        center = module.get("center") or []
        bounds = module.get("bounds") or []
        if len(center) != 2 or len(bounds) != 4:
            raise ValueError(f"Preview module {name} has incomplete center/bounds")
        theta = float(module.get("thetaDegrees", 0.0))
        source_theta = footprint_map[name].source_theta
        placements.append(
            Placement(
                component_name=name,
                role=roles[name],
                anchor_u=float(center[0]),
                anchor_v=float(center[1]),
                theta_degrees=theta,
                rotation_quarters=int(round((theta - source_theta) / 90.0)) % 4,
                bounds=tuple(float(value) for value in bounds),
            )
        )
    gantry = next((item for item in placements if item.role == "gantry"), None)
    if gantry is None:
        raise ValueError("Reference preview has no gantry placement")
    long_axis = (
        "u"
        if gantry.bounds[2] - gantry.bounds[0]
        >= gantry.bounds[3] - gantry.bounds[1]
        else "v"
    )
    validation = _evaluate_interaction_hard_constraints(
        placements,
        footprint_map,
        semantics,
        portal_pass_through,
        long_axis,
        options.minimum_clearance_meters,
        allow_post_solve_projection_overlaps=True,
    )
    failures = [
        diagnostic
        for diagnostic in validation.get("diagnostics") or []
        if diagnostic.get("hard") and not diagnostic.get("success")
    ]
    advisory_warnings = [
        diagnostic
        for diagnostic in validation.get("diagnostics") or []
        if not diagnostic.get("hard", True) and not diagnostic.get("success")
    ]
    conditional_brep_risks = [
        diagnostic
        for diagnostic in validation.get("diagnostics") or []
        if diagnostic.get("conditionalBrepPair") and diagnostic.get("collisionDetected")
    ]
    by_type: dict[str, int] = {}
    for failure in failures:
        key = str(failure.get("type") or "unknown")
        by_type[key] = by_type.get(key, 0) + 1
    return {
        "hardFeasible": bool(validation.get("hardFeasible")),
        "message": validation.get("message"),
        "hardFailureCount": len(failures),
        "hardFailureCountByType": by_type,
        "hardFailures": [
            {
                "id": item.get("id"),
                "type": item.get("type"),
                "firstComponent": item.get("firstComponent"),
                "secondComponent": item.get("secondComponent"),
                "protectedSpaceOwner": item.get("protectedSpaceOwner"),
                "protectedSpaceId": (item.get("protectedSpace") or {}).get("id"),
                "resolution": item.get("resolution"),
                "collidingBoxPairCount": item.get("collidingBoxPairCount"),
                "collidingBoxPairs": (item.get("collidingBoxPairs") or [])[:10],
            }
            for item in failures
        ],
        "advisoryWarningCount": len(advisory_warnings),
        "advisoryWarnings": [
            {
                "id": item.get("id"),
                "type": item.get("type"),
                "firstComponent": item.get("firstComponent"),
                "secondComponent": item.get("secondComponent"),
                "protectedSpaceOwner": item.get("protectedSpaceOwner"),
                "protectedSpaceId": (item.get("protectedSpace") or {}).get("id"),
                "enforcement": item.get("enforcement"),
                "evidenceStatus": (item.get("protectedSpace") or {}).get("evidenceStatus"),
                "resolution": item.get("resolution"),
                "collidingBoxPairCount": item.get("collidingBoxPairCount"),
            }
            for item in advisory_warnings
        ],
        "conditionalBrepRiskCount": len(conditional_brep_risks),
        "conditionalBrepRisks": [
            {
                "id": item.get("id"),
                "firstComponent": item.get("firstComponent"),
                "secondComponent": item.get("secondComponent"),
                "resolution": item.get("resolution"),
                "collidingBoxPairCount": item.get("collidingBoxPairCount"),
            }
            for item in conditional_brep_risks
        ],
        "compatibilityGate": {
            "passedConfirmedHardConstraints": not failures,
            "requiresEngineeringReview": bool(advisory_warnings),
            "requiresConditionalCadValidation": bool(conditional_brep_risks),
        },
        "interpretation": (
            "The frozen v22 pose remains feasible under confirmed hard geometry constraints; advisory maintenance-space warnings and conditional B-Rep risks are reported separately."
            if not failures
            else "The frozen v22 pose itself violates the geometry-only formulation; B/C search timeouts therefore mix search cost with a model-equivalence failure."
        ),
    }


def file_fingerprint(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    stat = path.stat()
    return {
        "path": str(path.resolve()),
        "bytes": stat.st_size,
        "modifiedAt": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        "sha256": digest.hexdigest(),
    }


def build_frozen_baseline_manifest(paths: list[Path]) -> dict[str, Any]:
    return {
        "schemaVersion": "project02-v22-frozen-baseline/v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "immutableByConvention": True,
        "artifacts": [file_fingerprint(path) for path in paths],
    }
