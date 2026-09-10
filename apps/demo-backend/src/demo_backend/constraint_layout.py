from __future__ import annotations

import math
import time
from dataclasses import dataclass, field, replace
from typing import Any, Literal

from .process_constraints import (
    ModuleSemantic,
    ProcessConstraintConfigurationError,
    compile_process_constraints,
    evaluate_process_constraints,
    normalize_module_semantics,
    role_overrides_from_semantics,
    semantic_point_height_meters,
)

# Maintenance rule: every layout-constraint or solver-order change must update
# docs/layout_constraints_and_solver_principles-CN.md and its change log.


ComponentRole = Literal["gantry", "transport", "glue", "functional"]


class ConstraintLayoutError(ValueError):
    pass


class ConstraintLayoutSearchTimeout(ConstraintLayoutError):
    def __init__(self, message: str, report: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.report = dict(report or {})


@dataclass(frozen=True)
class ConstraintLayoutOptions:
    role_overrides: dict[str, ComponentRole]
    margin_ratios: tuple[float, ...] = (0.05, 0.03, 0.01, 0.0)
    minimum_clearance_meters: float = 0.01
    glue_distance_meters: float = 0.05
    allow_rotation: bool = False
    portal_pass_through: dict[str, tuple[str, ...]] = field(default_factory=dict)
    portal_opening_width_ratio: float = 0.8
    portal_opening_height_ratio: float = 0.75
    module_semantics: dict[str, dict[str, Any]] = field(default_factory=dict)
    process_constraints: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    auto_generate_process_constraints: bool = True
    provisional_components: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    prefer_source_layout: bool = False
    source_position_independent: bool = False
    allowed_projected_overlap_pairs: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    minimum_transport_gantry_overlap_ratio: float = 0.5
    minimum_portal_gantry_overlap_ratio: float = 0.5
    minimum_functional_gantry_overlap_ratio: float = 0.0
    minimum_functional_gantry_boundary_clearance_meters: float = 0.0
    maximum_transport_gantry_center_offset_meters: float | None = None
    maximum_portal_gantry_center_offset_meters: float | None = None
    maximum_portal_gantry_overhang_meters: float | None = None
    require_reach_inside_gantry: bool = True
    joint_candidate_search: bool = False
    joint_candidate_limit: int = 18
    maximum_layout_solutions: int = 3
    warm_start_placements: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    warm_start_locked_components: tuple[str, ...] = field(default_factory=tuple)
    joint_search_time_limit_seconds: float | None = None
    case_anchor_component_name: str | None = None
    case_anchor_target_world: tuple[float, float, float] | None = None
    case_anchor_target_kind: str = "sourceCapture"
    case_anchor_target_source: str | None = None
    case_anchor_target_prototype_derived: bool = False
    case_anchor_scope: str = "caseSpecific"


@dataclass(frozen=True)
class Footprint:
    component_name: str
    file_path: str
    bottom_face_name: str
    source_theta: float
    theta_axis: str
    anchor_u: float
    anchor_v: float
    min_u_offset: float
    min_v_offset: float
    max_u_offset: float
    max_v_offset: float
    height_normal: float
    volume: float
    source: dict[str, Any]


@dataclass(frozen=True)
class Placement:
    component_name: str
    role: ComponentRole
    anchor_u: float
    anchor_v: float
    theta_degrees: float
    rotation_quarters: int
    bounds: tuple[float, float, float, float]
    containment_relaxed: bool = False


def _apply_semantic_footprint_override(
    item: Footprint,
    semantic: ModuleSemantic | None,
) -> Footprint:
    """Replace a coarse projected AABB with a rotation-frame CAD-calibrated footprint.

    The override stays local to the component bottom-center anchor, so it remains
    source-position independent while preserving asymmetric assemblies such as A700.
    """
    configured = semantic.parameters.get("layoutFootprintBoundsLocal") if semantic else None
    if configured is None:
        return item
    if not isinstance(configured, list) or len(configured) != 4:
        raise ConstraintLayoutError(
            f"Component '{item.component_name}' layoutFootprintBoundsLocal must contain four numbers."
        )
    try:
        bounds = tuple(float(value) for value in configured)
    except (TypeError, ValueError) as exc:
        raise ConstraintLayoutError(
            f"Component '{item.component_name}' layoutFootprintBoundsLocal must contain four numbers."
        ) from exc
    if not all(math.isfinite(value) for value in bounds) or bounds[0] >= bounds[2] or bounds[1] >= bounds[3]:
        raise ConstraintLayoutError(
            f"Component '{item.component_name}' layoutFootprintBoundsLocal is invalid: {bounds}."
        )
    return replace(
        item,
        min_u_offset=bounds[0],
        min_v_offset=bounds[1],
        max_u_offset=bounds[2],
        max_v_offset=bounds[3],
    )


def generate_constraint_layout(
    capture: dict[str, Any],
    options: ConstraintLayoutOptions,
) -> dict[str, Any]:
    """Generate an existing-Replay-compatible Layout2D document without changing CAD."""
    if options.prefer_source_layout and options.source_position_independent:
        raise ConstraintLayoutError(
            "prefer_source_layout and source_position_independent cannot both be enabled."
        )
    for label, value in (
        (
            "maximumTransportGantryCenterOffsetMeters",
            options.maximum_transport_gantry_center_offset_meters,
        ),
        (
            "maximumPortalGantryCenterOffsetMeters",
            options.maximum_portal_gantry_center_offset_meters,
        ),
        (
            "maximumPortalGantryOverhangMeters",
            options.maximum_portal_gantry_overhang_meters,
        ),
    ):
        if value is not None and (not math.isfinite(value) or value < 0):
            raise ConstraintLayoutError(f"{label} must be a finite non-negative number.")
    capture, provisional_warnings = _inject_provisional_components(
        capture,
        options.provisional_components,
    )
    footprints = _read_footprints(capture)
    if len(footprints) < 2:
        raise ConstraintLayoutError("Constraint layout requires at least two components with bounding boxes.")

    try:
        semantics = normalize_module_semantics(
            [item.component_name for item in footprints],
            options.module_semantics,
        )
    except ProcessConstraintConfigurationError as exc:
        raise ConstraintLayoutError(str(exc)) from exc
    footprints = [
        _apply_semantic_footprint_override(item, semantics.get(item.component_name))
        for item in footprints
    ]
    semantic_roles = role_overrides_from_semantics(semantics)
    semantic_names_by_lower = {name.lower(): name for name in semantics}
    for component_name, role in options.role_overrides.items():
        semantic_name = semantic_names_by_lower.get(component_name.lower())
        semantic_role = semantic_roles.get(semantic_name or "")
        if semantic_role and semantic_role != role:
            raise ConstraintLayoutError(
                f"Component '{component_name}' has conflicting role '{role}' and semantic module type "
                f"'{semantics[semantic_name].module_type}'."
            )
    effective_role_overrides = {**semantic_roles, **options.role_overrides}
    roles, role_reasons = _infer_roles(footprints, effective_role_overrides)
    explicit_overlap_pairs = _normalize_allowed_projected_overlap_pairs(
        footprints,
        options.allowed_projected_overlap_pairs,
    )
    semantic_overlap_pairs = (
        _semantic_projected_overlap_pairs(semantics, roles) | explicit_overlap_pairs
    )
    post_solve_overlap_pairs = _post_solve_projected_overlap_pairs(semantics)
    portal_pass_through = _normalize_portal_constraints(
        footprints,
        roles,
        options.portal_pass_through,
    )
    gantries = [item for item in footprints if roles[item.component_name] == "gantry"]
    if len(gantries) != 1:
        raise ConstraintLayoutError(f"Exactly one gantry component is required; found {len(gantries)}.")

    gantry = gantries[0]
    gantry_placement = _placement_at_source(gantry, "gantry")
    if options.source_position_independent:
        gantry_placement = _translate_placement(
            gantry_placement,
            -gantry_placement.anchor_u,
            -gantry_placement.anchor_v,
        )
    gantry_bounds = gantry_placement.bounds
    long_axis = "u" if _width(gantry_bounds) >= _height(gantry_bounds) else "v"
    reach_validation = _validate_gantry_reach_regions(
        gantry_placement,
        semantics.get(gantry.component_name),
        require_contained=options.require_reach_inside_gantry,
    )
    if not reach_validation["hardFeasible"]:
        raise ConstraintLayoutError(reach_validation["message"])
    try:
        process_constraints = compile_process_constraints(
            [item.component_name for item in footprints],
            semantics,
            roles,
            gantry.component_name,
            long_axis,
            options.process_constraints,
            options.auto_generate_process_constraints,
            options.minimum_clearance_meters,
        )
    except ProcessConstraintConfigurationError as exc:
        raise ConstraintLayoutError(str(exc)) from exc

    attempts: list[dict[str, Any]] = []
    solved: tuple[list[Placement], float, dict[str, Any]] | None = None
    for margin_ratio in options.margin_ratios:
        try:
            joint_search_report: dict[str, Any] = {}
            placements = _solve_with_margin(
                footprints,
                roles,
                gantry_placement,
                long_axis,
                max(0.0, margin_ratio),
                max(0.0, options.minimum_clearance_meters),
                max(0.0, options.glue_distance_meters),
                allow_outside_functional=False,
                allow_rotation=options.allow_rotation,
                portal_pass_through=portal_pass_through,
                portal_opening_width_ratio=options.portal_opening_width_ratio,
                portal_opening_height_ratio=options.portal_opening_height_ratio,
                semantics=semantics,
                process_constraints=process_constraints,
                semantic_overlap_pairs=semantic_overlap_pairs,
                prefer_source_layout=options.prefer_source_layout,
                source_position_independent=options.source_position_independent,
                minimum_transport_gantry_overlap_ratio=options.minimum_transport_gantry_overlap_ratio,
                minimum_portal_gantry_overlap_ratio=options.minimum_portal_gantry_overlap_ratio,
                minimum_functional_gantry_overlap_ratio=options.minimum_functional_gantry_overlap_ratio,
                minimum_functional_gantry_boundary_clearance_meters=options.minimum_functional_gantry_boundary_clearance_meters,
                maximum_transport_gantry_center_offset_meters=options.maximum_transport_gantry_center_offset_meters,
                maximum_portal_gantry_center_offset_meters=options.maximum_portal_gantry_center_offset_meters,
                maximum_portal_gantry_overhang_meters=options.maximum_portal_gantry_overhang_meters,
                joint_candidate_search=options.joint_candidate_search,
                joint_candidate_limit=options.joint_candidate_limit,
                maximum_layout_solutions=options.maximum_layout_solutions,
                warm_start_placements=options.warm_start_placements,
                warm_start_locked_components=options.warm_start_locked_components,
                joint_search_time_limit_seconds=options.joint_search_time_limit_seconds,
                joint_search_report=joint_search_report,
            )
            attempts.append({"marginRatio": margin_ratio, "success": True, "message": "feasible"})
            solved = placements, margin_ratio, joint_search_report
            break
        except ConstraintLayoutSearchTimeout:
            raise
        except ConstraintLayoutError as exc:
            attempts.append({"marginRatio": margin_ratio, "success": False, "message": str(exc)})

    # ``allow_outside_functional`` only belongs to the legacy band placer.  The
    # joint solver applies its explicit overlap/boundary hard constraints and
    # does not consume that flag, so replaying it here would run the identical
    # search a second time and could misleadingly double an interactive timeout.
    if solved is None and not options.joint_candidate_search:
        try:
            joint_search_report = {}
            placements = _solve_with_margin(
                footprints,
                roles,
                gantry_placement,
                long_axis,
                0.0,
                max(0.0, options.minimum_clearance_meters),
                max(0.0, options.glue_distance_meters),
                allow_outside_functional=True,
                allow_rotation=options.allow_rotation,
                portal_pass_through=portal_pass_through,
                portal_opening_width_ratio=options.portal_opening_width_ratio,
                portal_opening_height_ratio=options.portal_opening_height_ratio,
                semantics=semantics,
                process_constraints=process_constraints,
                semantic_overlap_pairs=semantic_overlap_pairs,
                prefer_source_layout=options.prefer_source_layout,
                source_position_independent=options.source_position_independent,
                minimum_transport_gantry_overlap_ratio=options.minimum_transport_gantry_overlap_ratio,
                minimum_portal_gantry_overlap_ratio=options.minimum_portal_gantry_overlap_ratio,
                minimum_functional_gantry_overlap_ratio=options.minimum_functional_gantry_overlap_ratio,
                minimum_functional_gantry_boundary_clearance_meters=options.minimum_functional_gantry_boundary_clearance_meters,
                maximum_transport_gantry_center_offset_meters=options.maximum_transport_gantry_center_offset_meters,
                maximum_portal_gantry_center_offset_meters=options.maximum_portal_gantry_center_offset_meters,
                maximum_portal_gantry_overhang_meters=options.maximum_portal_gantry_overhang_meters,
                joint_candidate_search=options.joint_candidate_search,
                joint_candidate_limit=options.joint_candidate_limit,
                maximum_layout_solutions=options.maximum_layout_solutions,
                warm_start_placements=options.warm_start_placements,
                warm_start_locked_components=options.warm_start_locked_components,
                joint_search_time_limit_seconds=options.joint_search_time_limit_seconds,
                joint_search_report=joint_search_report,
            )
            attempts.append(
                {
                    "marginRatio": 0.0,
                    "success": True,
                    "containmentRelaxed": True,
                    "message": "feasible after allowing oversized functional modules outside the gantry envelope",
                }
            )
            solved = placements, 0.0, joint_search_report
        except ConstraintLayoutSearchTimeout:
            raise
        except ConstraintLayoutError as exc:
            attempts.append(
                {
                    "marginRatio": 0.0,
                    "success": False,
                    "containmentRelaxed": True,
                    "message": str(exc),
                }
            )

    if solved is None:
        detail = attempts[-1]["message"] if attempts else "no solver attempt"
        raise ConstraintLayoutError(f"No feasible constraint layout was found: {detail}")

    placements, used_margin, joint_search_report = solved
    pinned_name = (
        ""
        if options.source_position_independent
        else str(capture.get("baseComponentName") or "").strip()
    )
    pinned_source = next((item for item in footprints if item.component_name == pinned_name), None)
    pinned_target = next((item for item in placements if item.component_name == pinned_name), None)
    if pinned_source and pinned_target:
        if pinned_target.rotation_quarters != 0:
            raise ConstraintLayoutError(
                f"Pinned base component '{pinned_name}' would be rotated. Disable rotation or choose another base component."
            )
        delta_u = pinned_source.anchor_u - pinned_target.anchor_u
        delta_v = pinned_source.anchor_v - pinned_target.anchor_v
        placements = [_translate_placement(item, delta_u, delta_v) for item in placements]

    if options.source_position_independent:
        placements = [
            _translate_placement(
                placement,
                float(
                    (semantics.get(placement.component_name).parameters if semantics.get(placement.component_name) else {}).get(
                        "postSolveAnchorBiasU",
                        0.0,
                    )
                ),
                float(
                    (semantics.get(placement.component_name).parameters if semantics.get(placement.component_name) else {}).get(
                        "postSolveAnchorBiasV",
                        0.0,
                    )
                ),
            )
            for placement in placements
        ]
        _apply_post_solve_bias_to_joint_search_solutions(
            joint_search_report,
            semantics,
        )

    case_anchor_report: dict[str, Any] | None = None
    case_anchor_name = str(options.case_anchor_component_name or "").strip()
    if case_anchor_name:
        anchor_source = next(
            (item for item in footprints if item.component_name == case_anchor_name),
            None,
        )
        anchor_target = next(
            (item for item in placements if item.component_name == case_anchor_name),
            None,
        )
        if anchor_source is None or anchor_target is None:
            raise ConstraintLayoutError(
                f"Case anchor component '{case_anchor_name}' was not found in the solved layout."
            )
        if anchor_target.rotation_quarters != 0:
            raise ConstraintLayoutError(
                f"Case anchor component '{case_anchor_name}' would be rotated; exact source-pose reuse "
                "requires rotationQuarters = 0."
            )
        target_kind = str(options.case_anchor_target_kind or "sourceCapture")
        if options.case_anchor_target_world is None:
            target_u = anchor_source.anchor_u
            target_v = anchor_source.anchor_v
            target_kind = "sourceCapture"
        else:
            frame = capture.get("baseFrame") or {}
            origin = _vector3(frame.get("origin"), "baseFrame.origin")
            u_axis = _unit(_vector3(frame.get("uAxis"), "baseFrame.uAxis"))
            v_axis = _unit(_vector3(frame.get("vAxis"), "baseFrame.vAxis"))
            target_world = tuple(float(value) for value in options.case_anchor_target_world)
            if len(target_world) != 3 or not all(math.isfinite(value) for value in target_world):
                raise ConstraintLayoutError("Case anchor target world point must contain three finite numbers.")
            relative = _subtract(target_world, origin)
            target_u = _dot(relative, u_axis)
            target_v = _dot(relative, v_axis)
        delta_u = target_u - anchor_target.anchor_u
        delta_v = target_v - anchor_target.anchor_v
        placements = [
            _translate_placement(item, delta_u, delta_v) for item in placements
        ]
        _anchor_joint_search_solutions(
            joint_search_report,
            case_anchor_name,
            target_u,
            target_v,
        )
        exact_source_pose_reuse = (
            target_kind == "sourceCapture"
            and math.isclose(target_u, anchor_source.anchor_u, abs_tol=1e-12)
            and math.isclose(target_v, anchor_source.anchor_v, abs_tol=1e-12)
        )
        case_anchor_report = {
            "componentName": case_anchor_name,
            "targetKind": target_kind,
            "targetSource": options.case_anchor_target_source,
            "scope": options.case_anchor_scope,
            "targetAnchor": [target_u, target_v],
            "targetWorld": (
                list(options.case_anchor_target_world)
                if options.case_anchor_target_world is not None
                else None
            ),
            "preTranslationAnchor": [anchor_target.anchor_u, anchor_target.anchor_v],
            "appliedTranslation": [delta_u, delta_v],
            "achievedAnchor": [target_u, target_v],
            "exactSourcePoseReuse": exact_source_pose_reuse,
            "sourceCapturePoseReadForAnchor": options.case_anchor_target_world is None,
            "prototypeDerivedParameter": options.case_anchor_target_prototype_derived,
            "relativeConstraintsRemainSourceIndependent": options.source_position_independent,
        }

    by_name = {item.component_name: item for item in placements}
    footprint_by_name = {item.component_name: item for item in footprints}
    spatial_validation = _evaluate_spatial_hard_constraints(
        placements,
        footprint_by_name,
        roles,
        semantics,
        gantry.component_name,
        portal_pass_through,
        minimum_transport_gantry_overlap_ratio=options.minimum_transport_gantry_overlap_ratio,
        minimum_portal_gantry_overlap_ratio=options.minimum_portal_gantry_overlap_ratio,
        minimum_functional_gantry_overlap_ratio=options.minimum_functional_gantry_overlap_ratio,
        minimum_functional_gantry_boundary_clearance_meters=options.minimum_functional_gantry_boundary_clearance_meters,
        maximum_transport_gantry_center_offset_meters=options.maximum_transport_gantry_center_offset_meters,
        maximum_portal_gantry_center_offset_meters=options.maximum_portal_gantry_center_offset_meters,
        maximum_portal_gantry_overhang_meters=options.maximum_portal_gantry_overhang_meters,
    )
    if not spatial_validation["hardFeasible"]:
        raise ConstraintLayoutError(spatial_validation["message"])
    interaction_validation = _evaluate_interaction_hard_constraints(
        placements,
        footprint_by_name,
        semantics,
        portal_pass_through,
        long_axis,
        options.minimum_clearance_meters,
        allow_post_solve_projection_overlaps=True,
    )
    if not interaction_validation["hardFeasible"]:
        raise ConstraintLayoutError(interaction_validation["message"])
    try:
        process_validation = evaluate_process_constraints(
            process_constraints,
            semantics,
            footprint_by_name,
            placements,
            roles,
            long_axis,
        )
    except ProcessConstraintConfigurationError as exc:
        raise ConstraintLayoutError(str(exc)) from exc
    inverse_gantry_coverage = _inverse_gantry_anchor_report(
        placements,
        semantics,
        process_constraints,
        gantry.component_name,
    )
    output_components: list[dict[str, Any]] = []
    for footprint in footprints:
        placement = by_name[footprint.component_name]
        source_component = dict(footprint.source)
        semantic = semantics.get(footprint.component_name)
        source_layout = source_component.get("layout2d")
        if not isinstance(source_layout, dict):
            source_layout = {}
        normal_offset_meters = float(
            (semantic.parameters if semantic else {}).get(
                "installationNormalOffsetMeters",
                source_layout.get("normalOffsetMeters", 0.0),
            )
        )
        source_component["layout2d"] = {
            "x": placement.anchor_u,
            "y": placement.anchor_v,
            "thetaDegrees": placement.theta_degrees,
            "thetaAxis": footprint.theta_axis,
            "normalOffsetMeters": normal_offset_meters,
        }
        source_component["role"] = placement.role
        source_component["roleReason"] = role_reasons[footprint.component_name]
        if footprint.component_name in semantics:
            source_component["moduleSemantic"] = semantics[footprint.component_name].to_json()
        source_component["projectedFootprint"] = {
            "minU": placement.bounds[0],
            "minV": placement.bounds[1],
            "maxU": placement.bounds[2],
            "maxV": placement.bounds[3],
        }
        source_component["constraintPlacement"] = {
            "rotationQuarters": placement.rotation_quarters,
            "sourceThetaDegrees": footprint.source_theta,
            "containmentRelaxed": placement.containment_relaxed,
        }
        interaction = _interaction_envelope(
            placement,
            footprint,
            semantics.get(footprint.component_name),
        )
        source_component["interactionEnvelope"] = {
            "bounds": list(interaction["bounds"]),
            "heightRangeMeters": list(interaction["heightRangeMeters"]),
            "source": interaction["source"],
        }
        hard_body = _hard_body_envelope(
            placement,
            footprint,
            semantics.get(footprint.component_name),
        )
        source_component["hardBodyEnvelope"] = {
            "bounds": list(hard_body["bounds"]),
            "heightRangeMeters": list(hard_body["heightRangeMeters"]),
            "source": hard_body["source"],
        }
        transport_sweep = _transport_sweep_envelope(
            placement,
            footprint,
            semantics.get(footprint.component_name),
        )
        if transport_sweep is not None:
            source_component["transportSweepEnvelope"] = {
                "bounds": list(transport_sweep["bounds"]),
                "heightRangeMeters": list(transport_sweep["heightRangeMeters"]),
                "source": transport_sweep["source"],
            }
        transport_static_keepout = _transport_static_keepout_envelope(
            placement,
            footprint,
            semantics.get(footprint.component_name),
        )
        if transport_static_keepout is not None:
            source_component["transportStaticKeepoutEnvelope"] = {
                "bounds": list(transport_static_keepout["bounds"]),
                "heightRangeMeters": list(transport_static_keepout["heightRangeMeters"]),
                "source": transport_static_keepout["source"],
            }
        target_frame = _target_orientation_frame(
            source_component,
            capture.get("baseFrame") or {},
            placement.rotation_quarters,
        )
        if target_frame is not None:
            source_component.update(target_frame)
        output_components.append(source_component)

    result = dict(capture)
    provisional_count = len(options.provisional_components)
    semantic_warnings = _semantic_assumption_warnings(semantics)
    assumption_warnings = [*provisional_warnings, *semantic_warnings]
    result.update(
        {
            "success": True,
            "message": (
                "Provisional constraint layout generated. Review assumptions before Replay Layout."
                if assumption_warnings
                else "Constraint layout generated. Review roles and diagnostics before Replay Layout."
            ),
            "layoutKind": "constraintGenerated",
            "provisional": bool(assumption_warnings),
            "components": output_components,
            "constraintPlan": {
                "roles": roles,
                "roleReasons": role_reasons,
                "gantryComponentName": gantry.component_name,
                "pinnedComponentName": pinned_name or None,
                "longAxis": long_axis,
                "usedMarginRatio": used_margin,
                "minimumClearanceMeters": options.minimum_clearance_meters,
                "glueDistanceMeters": options.glue_distance_meters,
                "allowRotation": options.allow_rotation,
                "solverMode": (
                    "bounded-joint-backtracking-top-k"
                    if options.joint_candidate_search
                    else "deterministic-first-feasible"
                ),
                "jointSearch": joint_search_report,
                "preferSourceLayout": options.prefer_source_layout,
                "sourcePositionIndependent": options.source_position_independent,
                "requiresAnchorTranslationBeforeReplay": (
                    options.source_position_independent and case_anchor_report is None
                ),
                "keepTopLevelMatesSuppressed": options.source_position_independent,
                "caseAnchor": case_anchor_report,
                "inverseGantryCoverage": inverse_gantry_coverage,
                "allowedProjectedOverlapPairs": [
                    sorted(pair) for pair in sorted(explicit_overlap_pairs, key=lambda item: sorted(item))
                ],
                "postSolveAllowedProjectedOverlapPairs": [
                    sorted(pair)
                    for pair in sorted(post_solve_overlap_pairs, key=lambda item: sorted(item))
                ],
                "spatialValidation": spatial_validation,
                "interactionValidation": interaction_validation,
                "reachValidation": reach_validation,
                "moduleSemantics": {
                    name: item.to_json() for name, item in semantics.items()
                },
                "processConstraints": process_constraints,
                "processValidation": process_validation,
                "provisionalPlaceholderCount": provisional_count,
                "provisionalSemanticCount": len(semantic_warnings),
                "assumptionWarnings": assumption_warnings,
                "portalConstraints": _portal_constraint_diagnostics(
                    placements,
                    footprint_by_name,
                    portal_pass_through,
                    long_axis,
                    options.minimum_clearance_meters,
                    options.portal_opening_width_ratio,
                    options.portal_opening_height_ratio,
                    semantics,
                ),
                "attempts": attempts,
                "containmentRelaxedComponents": [
                    item.component_name for item in placements if item.containment_relaxed
                ],
                "validation": _combined_validation(
                    placements,
                    gantry.component_name,
                    portal_pass_through,
                    process_validation,
                    semantic_overlap_pairs | post_solve_overlap_pairs,
                    explicit_overlap_pairs,
                    spatial_validation,
                    interaction_validation,
                ),
            },
        }
    )
    result["constraintPlan"]["validation"]["productionReady"] = not assumption_warnings
    return result


def _anchor_joint_search_solutions(
    joint_search_report: dict[str, Any],
    component_name: str,
    target_u: float,
    target_v: float,
) -> None:
    """Normalize every Top-K record to the same case-specific anchor frame."""
    for solution in joint_search_report.get("solutions") or []:
        records = solution.get("placements") or []
        anchor = next(
            (
                item
                for item in records
                if item.get("componentName") == component_name
            ),
            None,
        )
        if anchor is None:
            raise ConstraintLayoutError(
                f"Joint-search solution is missing case anchor component '{component_name}'."
            )
        if int(anchor.get("rotationQuarters", 0)) != 0:
            raise ConstraintLayoutError(
                f"Joint-search case anchor component '{component_name}' is rotated."
            )
        delta_u = target_u - float(anchor["x"])
        delta_v = target_v - float(anchor["y"])
        for item in records:
            item["x"] = float(item["x"]) + delta_u
            item["y"] = float(item["y"]) + delta_v
            bounds = item.get("bounds")
            if isinstance(bounds, list) and len(bounds) == 4:
                item["bounds"] = [
                    float(bounds[0]) + delta_u,
                    float(bounds[1]) + delta_v,
                    float(bounds[2]) + delta_u,
                    float(bounds[3]) + delta_v,
                ]
        solution["caseAnchor"] = {
            "componentName": component_name,
            "targetAnchor": [target_u, target_v],
            "appliedTranslation": [delta_u, delta_v],
        }


def _apply_post_solve_bias_to_joint_search_solutions(
    joint_search_report: dict[str, Any],
    semantics: dict[str, ModuleSemantic],
) -> None:
    """Keep persisted Top-K candidates aligned with post-solve module biases.

    Candidate approval materializes a layout from ``jointSearch.solutions``.
    Therefore every bias applied to the primary placement list must also be
    applied to those records before case-anchor normalization.
    """
    for solution in joint_search_report.get("solutions") or []:
        applied: list[dict[str, Any]] = []
        for item in solution.get("placements") or []:
            component_name = str(item.get("componentName") or "")
            semantic = semantics.get(component_name)
            parameters = semantic.parameters if semantic else {}
            delta_u = float(parameters.get("postSolveAnchorBiasU", 0.0))
            delta_v = float(parameters.get("postSolveAnchorBiasV", 0.0))
            if math.isclose(delta_u, 0.0, abs_tol=1e-15) and math.isclose(
                delta_v,
                0.0,
                abs_tol=1e-15,
            ):
                continue
            item["x"] = float(item["x"]) + delta_u
            item["y"] = float(item["y"]) + delta_v
            bounds = item.get("bounds")
            if isinstance(bounds, list) and len(bounds) == 4:
                item["bounds"] = [
                    float(bounds[0]) + delta_u,
                    float(bounds[1]) + delta_v,
                    float(bounds[2]) + delta_u,
                    float(bounds[3]) + delta_v,
                ]
            applied.append(
                {
                    "componentName": component_name,
                    "delta": [delta_u, delta_v],
                }
            )
        if applied:
            solution["postSolveAnchorBiases"] = applied


def _inverse_gantry_anchor_report(
    placements: list[Placement],
    semantics: dict[str, ModuleSemantic],
    constraints: list[dict[str, Any]],
    gantry_name: str,
) -> dict[str, Any]:
    """Report the gantry-anchor domain implied by all valve-reach point constraints.

    The joint solver works in a gantry-relative frame for search efficiency.  This
    report expresses the same hard constraints in the engineer's assembly order:
    after transport and service targets are placed, intersect the gantry anchor
    intervals that make every target enter its configured reach region.
    """
    placement_by_name = {item.component_name: item for item in placements}
    gantry_placement = placement_by_name[gantry_name]
    gantry_semantic = semantics.get(gantry_name)
    intervals: list[dict[str, Any]] = []
    min_anchor_u = -math.inf
    min_anchor_v = -math.inf
    max_anchor_u = math.inf
    max_anchor_v = math.inf

    for constraint in constraints:
        if (
            constraint.get("type") != "pointInRegion"
            or constraint.get("regionComponent") != gantry_name
            or not bool(constraint.get("hard", True))
        ):
            continue
        point_component = str(constraint.get("pointComponent") or "")
        point_name = str(constraint.get("point") or "")
        region_name = str(constraint.get("region") or "")
        point_semantic = semantics.get(point_component)
        point_placement = placement_by_name.get(point_component)
        region = gantry_semantic.regions.get(region_name) if gantry_semantic else None
        point = point_semantic.points.get(point_name) if point_semantic else None
        if point_placement is None or point is None or region is None:
            continue

        point_offset = _rotate_local_point(
            point.u,
            point.v,
            point_placement.rotation_quarters,
        )
        point_u = point_placement.anchor_u + point_offset[0]
        point_v = point_placement.anchor_v + point_offset[1]
        region_corners = [
            _rotate_local_point(u, v, gantry_placement.rotation_quarters)
            for u in (region.min_u, region.max_u)
            for v in (region.min_v, region.max_v)
        ]
        region_min_u = min(item[0] for item in region_corners)
        region_min_v = min(item[1] for item in region_corners)
        region_max_u = max(item[0] for item in region_corners)
        region_max_v = max(item[1] for item in region_corners)
        interval = {
            "constraintId": str(constraint.get("id") or ""),
            "targetComponentName": point_component,
            "targetPoint": point_name,
            "region": region_name,
            "worldPoint": [point_u, point_v],
            "anchorRegion": [
                point_u - region_max_u,
                point_v - region_max_v,
                point_u - region_min_u,
                point_v - region_min_v,
            ],
        }
        intervals.append(interval)
        min_anchor_u = max(min_anchor_u, interval["anchorRegion"][0])
        min_anchor_v = max(min_anchor_v, interval["anchorRegion"][1])
        max_anchor_u = min(max_anchor_u, interval["anchorRegion"][2])
        max_anchor_v = min(max_anchor_v, interval["anchorRegion"][3])

    feasible = bool(intervals) and min_anchor_u <= max_anchor_u and min_anchor_v <= max_anchor_v
    selected_inside = bool(
        feasible
        and min_anchor_u - 1e-9 <= gantry_placement.anchor_u <= max_anchor_u + 1e-9
        and min_anchor_v - 1e-9 <= gantry_placement.anchor_v <= max_anchor_v + 1e-9
    )
    unique_targets = {
        (item["targetComponentName"], item["targetPoint"]) for item in intervals
    }
    return {
        "method": "intersectionOfPointInReachAnchorIntervals",
        "gantryComponentName": gantry_name,
        "constraintCount": len(intervals),
        "targetPointCount": len(unique_targets),
        "requiredTargets": intervals,
        "feasibleAnchorRegion": (
            [min_anchor_u, min_anchor_v, max_anchor_u, max_anchor_v]
            if feasible
            else None
        ),
        "selectedAnchor": [gantry_placement.anchor_u, gantry_placement.anchor_v],
        "nonEmpty": feasible,
        "selectedInside": selected_inside,
        "interpretation": (
            "A100 is positioned last by selecting an anchor in the intersection that covers all transport work points and service points."
        ),
    }


def _semantic_assumption_warnings(semantics: dict[str, ModuleSemantic]) -> list[str]:
    warnings: list[str] = []
    for name, semantic in semantics.items():
        if not bool(semantic.parameters.get("provisional", False)):
            continue
        reason = str(
            semantic.parameters.get("assumptionReason")
            or "module points, reach, working distance, or orientation still use coarse estimates"
        ).strip()
        warnings.append(f"{name}: provisional semantic parameters ({reason}); production validation is disabled.")
    return warnings


def _inject_provisional_components(
    capture: dict[str, Any],
    requested: tuple[dict[str, Any], ...],
) -> tuple[dict[str, Any], list[str]]:
    if not requested:
        return capture, []

    components = capture.get("components")
    if not isinstance(components, list):
        raise ConstraintLayoutError("Capture JSON does not contain a components array.")
    frame = capture.get("baseFrame") or {}
    origin = _vector3(frame.get("origin"), "baseFrame.origin")
    u_axis = _unit(_vector3(frame.get("uAxis"), "baseFrame.uAxis"))
    v_axis = _unit(_vector3(frame.get("vAxis"), "baseFrame.vAxis"))
    normal = _unit(_vector3(frame.get("normal"), "baseFrame.normal"))
    existing = {
        str(item.get("componentName") or "").strip().lower()
        for item in components
        if isinstance(item, dict)
    }
    merged = [dict(item) if isinstance(item, dict) else item for item in components]
    warnings: list[str] = []

    for index, raw in enumerate(requested):
        if not isinstance(raw, dict):
            raise ConstraintLayoutError(f"Provisional component #{index + 1} must be a JSON object.")
        name = str(raw.get("componentName") or "").strip()
        if not name:
            raise ConstraintLayoutError(f"Provisional component #{index + 1} has no componentName.")
        if name.lower() in existing:
            raise ConstraintLayoutError(
                f"Provisional component '{name}' conflicts with an existing geometry component."
            )
        width = _positive_placeholder_dimension(raw, "widthMeters", name)
        depth = _positive_placeholder_dimension(raw, "depthMeters", name)
        height = _positive_placeholder_dimension(raw, "heightMeters", name)
        anchor_u = float(raw.get("anchorU") or 0.0)
        anchor_v = float(raw.get("anchorV") or 0.0)
        reason = str(raw.get("reason") or "User-approved provisional component for coarse reconstruction.")
        replayable = bool(raw.get("replayable", False))
        file_path = str(raw.get("filePath") or "")
        center = tuple(
            origin[axis] + anchor_u * u_axis[axis] + anchor_v * v_axis[axis]
            for axis in range(3)
        )
        corners = [
            tuple(
                center[axis]
                + du * u_axis[axis]
                + dv * v_axis[axis]
                + dn * normal[axis]
                for axis in range(3)
            )
            for du in (-width / 2.0, width / 2.0)
            for dv in (-depth / 2.0, depth / 2.0)
            for dn in (0.0, height)
        ]
        bbox = [
            min(point[axis] for point in corners)
            for axis in range(3)
        ] + [
            max(point[axis] for point in corners)
            for axis in range(3)
        ]
        merged.append(
            {
                "componentName": name,
                "filePath": file_path,
                "bottomFaceName": str(raw.get("bottomFaceName") or "底面"),
                "bottomCenterWorld": list(center),
                "bottomNormalWorld": list(normal),
                "boundingBoxWorld": bbox,
                "layout2d": {
                    "x": anchor_u,
                    "y": anchor_v,
                    "thetaDegrees": 0.0,
                    "thetaAxis": "x",
                },
                "faceMappingFound": False,
                "isProvisionalPlaceholder": True,
                "provisionalPlaceholder": {
                    "reason": reason,
                    "replayable": replayable,
                    "widthMeters": width,
                    "depthMeters": depth,
                    "heightMeters": height,
                },
            }
        )
        existing.add(name.lower())
        replay_note = "has a replay file" if replayable and file_path else "is geometry-only and cannot be replayed into CAD"
        warnings.append(
            f"{name}: provisional placeholder ({reason}); {replay_note}; production validation is disabled."
        )

    result = dict(capture)
    result["components"] = merged
    return result, warnings


def _positive_placeholder_dimension(raw: dict[str, Any], key: str, name: str) -> float:
    try:
        value = float(raw.get(key))
    except (TypeError, ValueError) as exc:
        raise ConstraintLayoutError(
            f"Provisional component '{name}' {key} must be a positive number."
        ) from exc
    if not math.isfinite(value) or value <= 0:
        raise ConstraintLayoutError(
            f"Provisional component '{name}' {key} must be a positive number."
        )
    return value


def _read_footprints(capture: dict[str, Any]) -> list[Footprint]:
    frame = capture.get("baseFrame") or {}
    origin = _vector3(frame.get("origin"), "baseFrame.origin")
    u_axis = _unit(_vector3(frame.get("uAxis"), "baseFrame.uAxis"))
    v_axis = _unit(_vector3(frame.get("vAxis"), "baseFrame.vAxis"))
    normal = _unit(_vector3(frame.get("normal"), "baseFrame.normal"))
    components = capture.get("components")
    if not isinstance(components, list):
        raise ConstraintLayoutError("Capture JSON does not contain a components array.")

    result: list[Footprint] = []
    for component in components:
        if not isinstance(component, dict):
            continue
        name = str(component.get("componentName") or "").strip()
        if not name:
            continue
        box = component.get("boundingBoxWorld")
        if not isinstance(box, list) or len(box) < 6:
            raise ConstraintLayoutError(f"Component '{name}' has no boundingBoxWorld. Publish the updated MCP and capture again.")
        values = [float(value) for value in box[:6]]
        min_x, min_y, min_z = values[:3]
        max_x, max_y, max_z = values[3:]
        corners = [
            (x, y, z)
            for x in (min_x, max_x)
            for y in (min_y, max_y)
            for z in (min_z, max_z)
        ]
        projected = [
            (_dot(_subtract(point, origin), u_axis), _dot(_subtract(point, origin), v_axis))
            for point in corners
        ]
        projected_normal = [_dot(_subtract(point, origin), normal) for point in corners]
        layout = component.get("layout2d") or {}
        anchor_u = float(layout.get("x", 0.0))
        anchor_v = float(layout.get("y", 0.0))
        theta = float(layout.get("thetaDegrees") or 0.0)
        result.append(
            Footprint(
                component_name=name,
                file_path=str(component.get("filePath") or ""),
                bottom_face_name=str(component.get("bottomFaceName") or "底面"),
                source_theta=theta,
                theta_axis=str(layout.get("thetaAxis") or "x"),
                anchor_u=anchor_u,
                anchor_v=anchor_v,
                min_u_offset=min(item[0] for item in projected) - anchor_u,
                min_v_offset=min(item[1] for item in projected) - anchor_v,
                max_u_offset=max(item[0] for item in projected) - anchor_u,
                max_v_offset=max(item[1] for item in projected) - anchor_v,
                height_normal=max(projected_normal) - min(projected_normal),
                volume=max(0.0, max_x - min_x) * max(0.0, max_y - min_y) * max(0.0, max_z - min_z),
                source=component,
            )
        )
    return result


def _infer_roles(
    footprints: list[Footprint],
    overrides: dict[str, ComponentRole],
) -> tuple[dict[str, ComponentRole], dict[str, str]]:
    roles: dict[str, ComponentRole] = {}
    reasons: dict[str, str] = {}
    by_lower = {name.lower(): role for name, role in overrides.items()}
    keywords: tuple[tuple[ComponentRole, tuple[str, ...]], ...] = (
        ("gantry", ("龙门", "gantry")),
        ("transport", ("传输", "transport", "conveyor")),
        ("glue", ("供胶", "点胶", "glue", "dispens")),
        ("functional", ("功能", "function")),
    )
    for item in footprints:
        override = overrides.get(item.component_name) or by_lower.get(item.component_name.lower())
        if override:
            roles[item.component_name] = override
            reasons[item.component_name] = "explicit role override"
            continue
        lowered = item.component_name.lower()
        for role, tokens in keywords:
            if any(token.lower() in lowered for token in tokens):
                roles[item.component_name] = role
                reasons[item.component_name] = f"name keyword matched {role}"
                break

    gantry_names = [name for name, role in roles.items() if role == "gantry"]
    if len(gantry_names) > 1:
        raise ConstraintLayoutError("Role mapping contains more than one gantry component.")
    if not gantry_names:
        gantry = max(footprints, key=lambda item: item.volume)
        roles[gantry.component_name] = "gantry"
        reasons[gantry.component_name] = "largest world bounding-box volume"
    else:
        gantry = next(item for item in footprints if item.component_name == gantry_names[0])

    gantry_bounds = _source_bounds(gantry)
    long_axis = "u" if _width(gantry_bounds) >= _height(gantry_bounds) else "v"
    remaining = [item for item in footprints if item.component_name not in roles]

    if not any(role == "transport" for role in roles.values()) and remaining:
        scored: list[tuple[float, Footprint]] = []
        for item in remaining:
            bounds = _source_bounds(item)
            overlap = _intersection_area(bounds, gantry_bounds) / max(_area(bounds), 1e-12)
            overhang = _axis_overhang(bounds, gantry_bounds, long_axis)
            long_coverage = _axis_size(bounds, long_axis) / max(_axis_size(gantry_bounds, long_axis), 1e-12)
            center_short_inside = _axis_min(gantry_bounds, _other_axis(long_axis)) <= _axis_center(bounds, _other_axis(long_axis)) <= _axis_max(gantry_bounds, _other_axis(long_axis))
            score = overlap * 2.0 + min(long_coverage, 2.0) + (0.6 if 0 < overhang <= 0.5 else 0.0) + (0.3 if center_short_inside else 0.0)
            scored.append((score, item))
        transport = max(scored, key=lambda entry: entry[0])[1]
        roles[transport.component_name] = "transport"
        reasons[transport.component_name] = "best geometric transport score: central overlap and long-axis coverage/overhang"
        remaining = [item for item in remaining if item.component_name != transport.component_name]

    for item in remaining:
        bounds = _source_bounds(item)
        overlap_ratio = _intersection_area(bounds, gantry_bounds) / max(_area(bounds), 1e-12)
        center_inside = _contains_point(gantry_bounds, _center(bounds))
        if overlap_ratio < 0.35 or not center_inside:
            roles[item.component_name] = "glue"
            reasons[item.component_name] = "source footprint is primarily outside the gantry envelope"
        else:
            roles[item.component_name] = "functional"
            reasons[item.component_name] = "remaining component inside the gantry envelope"

    return roles, reasons


def _normalize_allowed_projected_overlap_pairs(
    footprints: list[Footprint],
    requested: tuple[tuple[str, str], ...],
) -> set[frozenset[str]]:
    canonical = {item.component_name.lower(): item.component_name for item in footprints}
    normalized: set[frozenset[str]] = set()
    for index, raw_pair in enumerate(requested):
        if len(raw_pair) != 2:
            raise ConstraintLayoutError(
                f"Allowed projected overlap pair #{index + 1} must contain exactly two component names."
            )
        names: list[str] = []
        for requested_name in raw_pair:
            name = canonical.get(str(requested_name).strip().lower())
            if not name:
                raise ConstraintLayoutError(
                    f"Allowed projected overlap component '{requested_name}' was not found in the capture."
                )
            names.append(name)
        if names[0] == names[1]:
            raise ConstraintLayoutError("A component cannot overlap itself.")
        normalized.add(frozenset(names))
    return normalized


def _normalize_portal_constraints(
    footprints: list[Footprint],
    roles: dict[str, ComponentRole],
    requested: dict[str, tuple[str, ...]],
) -> dict[str, tuple[str, ...]]:
    """Resolve case-insensitive names and reject portal definitions the solver cannot honor."""
    canonical = {item.component_name.lower(): item.component_name for item in footprints}
    normalized: dict[str, tuple[str, ...]] = {}
    for requested_portal, requested_pass_through in requested.items():
        portal_name = canonical.get(requested_portal.strip().lower())
        if not portal_name:
            raise ConstraintLayoutError(f"Portal component '{requested_portal}' was not found in the capture.")
        if roles.get(portal_name) != "functional":
            raise ConstraintLayoutError(
                f"Portal component '{portal_name}' must use the functional role."
            )

        pass_through_names: list[str] = []
        for requested_name in requested_pass_through:
            component_name = canonical.get(requested_name.strip().lower())
            if not component_name:
                raise ConstraintLayoutError(
                    f"Pass-through component '{requested_name}' was not found in the capture."
                )
            if component_name == portal_name:
                raise ConstraintLayoutError(
                    f"Portal component '{portal_name}' cannot pass through itself."
                )
            if roles.get(component_name) not in {"transport", "functional"}:
                raise ConstraintLayoutError(
                    f"Pass-through/portal-overlap component '{component_name}' must use the transport or functional role."
                )
            if component_name not in pass_through_names:
                pass_through_names.append(component_name)

        if not pass_through_names:
            raise ConstraintLayoutError(
                f"Portal component '{portal_name}' must name at least one pass-through component."
            )
        normalized[portal_name] = tuple(pass_through_names)
    return normalized


def _solve_with_margin(
    footprints: list[Footprint],
    roles: dict[str, ComponentRole],
    gantry: Placement,
    long_axis: str,
    margin_ratio: float,
    clearance: float,
    glue_distance: float,
    allow_outside_functional: bool,
    allow_rotation: bool,
    portal_pass_through: dict[str, tuple[str, ...]],
    portal_opening_width_ratio: float,
    portal_opening_height_ratio: float,
    semantics: dict[str, ModuleSemantic],
    process_constraints: list[dict[str, Any]],
    semantic_overlap_pairs: set[frozenset[str]],
    prefer_source_layout: bool,
    source_position_independent: bool,
    minimum_transport_gantry_overlap_ratio: float,
    minimum_portal_gantry_overlap_ratio: float,
    minimum_functional_gantry_overlap_ratio: float,
    minimum_functional_gantry_boundary_clearance_meters: float,
    maximum_transport_gantry_center_offset_meters: float | None,
    maximum_portal_gantry_center_offset_meters: float | None,
    maximum_portal_gantry_overhang_meters: float | None,
    joint_candidate_search: bool,
    joint_candidate_limit: int,
    maximum_layout_solutions: int,
    warm_start_placements: tuple[dict[str, Any], ...],
    warm_start_locked_components: tuple[str, ...],
    joint_search_time_limit_seconds: float | None,
    joint_search_report: dict[str, Any],
) -> list[Placement]:
    by_name = {item.component_name: item for item in footprints}
    gantry_bounds = gantry.bounds
    long_size = _axis_size(gantry_bounds, long_axis)
    short_axis = _other_axis(long_axis)
    short_size = _axis_size(gantry_bounds, short_axis)
    margin_long = long_size * margin_ratio
    margin_short = short_size * margin_ratio

    placements: list[Placement] = [gantry]
    warm_start_by_name = {
        str(item.get("componentName")): item
        for item in warm_start_placements
        if isinstance(item, dict) and item.get("componentName")
    }
    locked_warm_start_names = {
        str(name) for name in warm_start_locked_components if str(name)
    }
    transports = [item for item in footprints if roles[item.component_name] == "transport"]
    transport_placements: list[Placement] = []
    if transports:
        variants = [
            _best_long_variant(item, long_axis, allow_rotation, semantics.get(item.component_name))
            for item in transports
        ]
        total_long = sum(_axis_size(bounds, long_axis) for _, bounds in variants) + clearance * max(0, len(variants) - 1)
        cursor = _axis_center(gantry_bounds, long_axis) - total_long / 2.0
        for item, (quarters, offsets) in zip(transports, variants):
            length = _axis_size(offsets, long_axis)
            source_candidate = _placement_at_source(item, "transport")
            locked_warm_start = (
                warm_start_by_name.get(item.component_name)
                if item.component_name in locked_warm_start_names
                else None
            )
            if locked_warm_start is not None:
                try:
                    warm_theta = float(locked_warm_start["thetaDegrees"])
                    warm_quarters = int(
                        round((warm_theta - item.source_theta) / 90.0)
                    ) % 4
                    allowed_quarters = _rotation_candidates(
                        item,
                        allow_rotation,
                        semantics.get(item.component_name),
                    )
                    if warm_quarters not in allowed_quarters:
                        raise ConstraintLayoutError(
                            f"Locked transport warm-start orientation is not allowed for "
                            f"'{item.component_name}'."
                        )
                    placement = _placement_at_anchor(
                        item,
                        "transport",
                        warm_quarters,
                        gantry.anchor_u + float(locked_warm_start["x"]),
                        gantry.anchor_v + float(locked_warm_start["y"]),
                    )
                except (KeyError, TypeError, ValueError) as exc:
                    raise ConstraintLayoutError(
                        f"Locked transport warm-start placement is invalid for "
                        f"'{item.component_name}'."
                    ) from exc
            elif (
                prefer_source_layout
                and _overlap_ratio(source_candidate.bounds, gantry_bounds)
                >= minimum_transport_gantry_overlap_ratio - 1e-9
                and _candidate_process_feasible(
                    source_candidate,
                    placements,
                    process_constraints,
                    semantics,
                    by_name,
                    roles,
                    long_axis,
                )
            ):
                placement = source_candidate
            else:
                desired_long = cursor + length / 2.0
                desired_short = _axis_center(gantry_bounds, short_axis)
                placement = _place_by_bounds_center(item, "transport", quarters, long_axis, desired_long, desired_short)
                placement = _align_transport_work_points_to_reach(
                    placement,
                    item,
                    semantics.get(item.component_name),
                    gantry,
                    semantics.get(gantry.component_name),
                )
            overlap_ratio = _overlap_ratio(placement.bounds, gantry_bounds)
            if overlap_ratio < minimum_transport_gantry_overlap_ratio - 1e-9:
                raise ConstraintLayoutError(
                    f"Transport component '{item.component_name}' overlaps only {overlap_ratio:.3f} "
                    f"of the gantry envelope; minimum is {minimum_transport_gantry_overlap_ratio:.3f}."
                )
            transport_placements.append(placement)
            cursor += length + clearance
        placements.extend(transport_placements)

    if transport_placements:
        corridor_min = min(_axis_min(item.bounds, short_axis) for item in transport_placements) - clearance
        corridor_max = max(_axis_max(item.bounds, short_axis) for item in transport_placements) + clearance
    else:
        center = _axis_center(gantry_bounds, short_axis)
        corridor_min = center - clearance / 2.0
        corridor_max = center + clearance / 2.0

    functional = sorted(
        (item for item in footprints if roles[item.component_name] == "functional"),
        key=lambda item: (
            _semantic_order(semantics.get(item.component_name)),
            -_area(_source_bounds(item)),
        ),
    )
    long_min = _axis_min(gantry_bounds, long_axis) + margin_long
    long_max = _axis_max(gantry_bounds, long_axis) - margin_long
    bands = [
        [_axis_min(gantry_bounds, short_axis) + margin_short, corridor_min, long_min],
        [corridor_max, _axis_max(gantry_bounds, short_axis) - margin_short, long_min],
    ]
    if joint_candidate_search:
        placements.extend(
            _joint_place_functionals(
                functional,
                placements,
                by_name,
                roles,
                gantry,
                long_axis,
                clearance,
                allow_rotation,
                portal_pass_through,
                semantics,
                process_constraints,
                semantic_overlap_pairs,
                source_position_independent,
                minimum_portal_gantry_overlap_ratio,
                minimum_functional_gantry_overlap_ratio,
                minimum_functional_gantry_boundary_clearance_meters,
                maximum_portal_gantry_center_offset_meters,
                maximum_portal_gantry_overhang_meters,
                max(1, joint_candidate_limit),
                max(1, maximum_layout_solutions),
                warm_start_placements,
                warm_start_locked_components,
                joint_search_time_limit_seconds,
                joint_search_report,
            )
        )
        functional = []
    for item in functional:
        placed = None
        pass_through_names = portal_pass_through.get(item.component_name, ())
        semantic = semantics.get(item.component_name)
        required_overlap = (
            minimum_portal_gantry_overlap_ratio
            if pass_through_names
            else float(
                semantic.parameters.get(
                    "minimumGantryOverlapRatio",
                    minimum_functional_gantry_overlap_ratio,
                )
            )
            if semantic
            else minimum_functional_gantry_overlap_ratio
        )
        source_candidate = _placement_at_source(item, "functional")
        if (
            prefer_source_layout
            and _overlap_ratio(source_candidate.bounds, gantry_bounds) >= required_overlap - 1e-9
            and not _candidate_has_disallowed_overlap(
                source_candidate,
                placements[1:],
                clearance,
                portal_pass_through,
                semantic_overlap_pairs,
            )
            and _candidate_process_feasible(
                source_candidate,
                placements,
                process_constraints,
                semantics,
                by_name,
                roles,
                long_axis,
            )
            and _candidate_interaction_feasible(
                source_candidate,
                placements,
                by_name,
                semantics,
                portal_pass_through,
                long_axis,
                clearance,
            )
        ):
            placements.append(source_candidate)
            continue

        if pass_through_names:
            opening_pass_through_names = tuple(
                name for name in pass_through_names if roles.get(name) == "transport"
            )
            pass_through_placements = [
                placement
                for placement in placements
                if placement.component_name in opening_pass_through_names
            ]
            if len(pass_through_placements) != len(opening_pass_through_names):
                unresolved = sorted(
                    set(opening_pass_through_names)
                    - {placement.component_name for placement in pass_through_placements}
                )
                raise ConstraintLayoutError(
                    f"Portal component '{item.component_name}' references components that were not placed first: "
                    f"{', '.join(unresolved)}"
                )

            portal_offsets = _rotated_offsets(item, 0)
            portal_short = _axis_size(portal_offsets, short_axis)
            desired_long = _axis_center(gantry_bounds, long_axis)
            desired_short = (
                min(_axis_min(candidate.bounds, short_axis) for candidate in pass_through_placements)
                + max(_axis_max(candidate.bounds, short_axis) for candidate in pass_through_placements)
            ) / 2.0
            candidate = _place_by_bounds_center(
                item,
                "functional",
                0,
                long_axis,
                desired_long,
                desired_short,
            )
            candidate = _align_portal_process_region(
                candidate,
                item,
                semantics.get(item.component_name),
                pass_through_placements,
                semantics,
            )
            inner_gantry_bounds = _inset_bounds(
                gantry_bounds,
                margin_long,
                margin_short,
                long_axis,
            )
            if _overlap_ratio(candidate.bounds, inner_gantry_bounds) < minimum_portal_gantry_overlap_ratio - 1e-9:
                raise ConstraintLayoutError(
                    f"Portal component '{item.component_name}' does not sufficiently overlap the gantry envelope "
                    f"at margin ratio {margin_ratio:.3f}; gantry={inner_gantry_bounds}, "
                    f"portal={candidate.bounds}."
                )

            opening_short = portal_short * _ratio(portal_opening_width_ratio, "portal opening width")
            opening_height = item.height_normal * _ratio(
                portal_opening_height_ratio,
                "portal opening height",
            )
            opening_min = desired_short - opening_short / 2.0
            opening_max = desired_short + opening_short / 2.0
            for pass_through in pass_through_placements:
                pass_footprint = by_name[pass_through.component_name]
                if (
                    _axis_min(pass_through.bounds, short_axis) < opening_min + clearance - 1e-9
                    or _axis_max(pass_through.bounds, short_axis) > opening_max - clearance + 1e-9
                ):
                    raise ConstraintLayoutError(
                        f"Pass-through component '{pass_through.component_name}' is wider than the estimated "
                        f"opening of portal '{item.component_name}'."
                    )
                if pass_footprint.height_normal + clearance > opening_height + 1e-9:
                    raise ConstraintLayoutError(
                        f"Pass-through component '{pass_through.component_name}' is taller than the estimated "
                        f"opening of portal '{item.component_name}'."
                    )

            if any(
                _rectangles_touch_or_overlap(candidate.bounds, other.bounds, clearance)
                for other in placements[1:]
                if not _is_allowed_portal_overlap(
                    candidate.component_name,
                    other.component_name,
                    portal_pass_through,
                )
            ):
                raise ConstraintLayoutError(
                    f"Portal component '{item.component_name}' collides with a non-pass-through component."
                )
            if not _candidate_process_feasible(
                candidate,
                placements,
                process_constraints,
                semantics,
                by_name,
                roles,
                long_axis,
            ):
                validation = _candidate_process_validation(
                    candidate,
                    placements,
                    process_constraints,
                    semantics,
                    by_name,
                    roles,
                    long_axis,
                )
                failures = [
                    item for item in validation.get("diagnostics", [])
                    if item.get("hard") and not item.get("success")
                ]
                raise ConstraintLayoutError(
                    f"Portal component '{item.component_name}' cannot satisfy its process coverage constraints; "
                    f"failures={failures}."
                )
            if not _candidate_interaction_feasible(
                candidate,
                placements,
                by_name,
                semantics,
                portal_pass_through,
                long_axis,
                clearance,
            ):
                raise ConstraintLayoutError(
                    f"Portal component '{item.component_name}' cannot satisfy its hard interaction constraints."
                )
            placed = candidate

        if placed:
            placements.append(placed)
            continue

        for quarters in _rotation_candidates(item, allow_rotation, semantic):
            for anchor_u, anchor_v in _point_in_region_anchor_candidates(
                item,
                quarters,
                process_constraints,
                semantics,
                placements,
                portal_pass_through,
                clearance,
                source_position_independent=source_position_independent,
            ):
                candidate = _placement_at_anchor(
                    item,
                    "functional",
                    quarters,
                    anchor_u,
                    anchor_v,
                    containment_relaxed=not _contains_bounds(gantry_bounds, _translated_offsets(_rotated_offsets(item, quarters), anchor_u, anchor_v)),
                )
                if _overlap_ratio(candidate.bounds, gantry_bounds) < required_overlap - 1e-9:
                    continue
                if (
                    minimum_functional_gantry_boundary_clearance_meters > 0
                    and not pass_through_names
                    and not _contains_bounds(
                        _inset_bounds(
                            gantry_bounds,
                            minimum_functional_gantry_boundary_clearance_meters,
                            minimum_functional_gantry_boundary_clearance_meters,
                            long_axis,
                        ),
                        candidate.bounds,
                    )
                ):
                    continue
                if any(
                    _rectangles_touch_or_overlap(candidate.bounds, other.bounds, clearance)
                    and not _is_allowed_portal_overlap(
                        candidate.component_name,
                        other.component_name,
                        portal_pass_through,
                    )
                    and frozenset((candidate.component_name, other.component_name)) not in semantic_overlap_pairs
                    and not _uses_multi_box_clearance(candidate, other, semantics)
                    for other in placements[1:]
                ):
                    continue
                if not _candidate_process_feasible(
                    candidate,
                    placements,
                    process_constraints,
                    semantics,
                    by_name,
                    roles,
                    long_axis,
                ):
                    continue
                if not _candidate_interaction_feasible(
                    candidate,
                    placements,
                    by_name,
                    semantics,
                    portal_pass_through,
                    long_axis,
                    clearance,
                ):
                    continue
                placed = candidate
                break
            if placed:
                break
        if placed:
            placements.append(placed)
            continue

        for band_index in _band_order(semantic, bands):
            band_min, band_max, cursor = bands[band_index]
            for quarters in _rotation_candidates(item, allow_rotation, semantic):
                offsets = _rotated_offsets(item, quarters)
                item_long = _axis_size(offsets, long_axis)
                item_short = _axis_size(offsets, short_axis)
                if item_short > band_max - band_min + 1e-9 or cursor + item_long > long_max + 1e-9:
                    continue
                last_cursor = long_max - item_long
                for candidate_cursor in _candidate_cursors(cursor, last_cursor):
                    desired_long = candidate_cursor + item_long / 2.0
                    desired_short = (band_min + band_max) / 2.0
                    candidate = _place_by_bounds_center(item, "functional", quarters, long_axis, desired_long, desired_short)
                    if _overlap_ratio(candidate.bounds, gantry_bounds) < required_overlap - 1e-9:
                        continue
                    if (
                        minimum_functional_gantry_boundary_clearance_meters > 0
                        and not pass_through_names
                        and not _contains_bounds(
                            _inset_bounds(
                                gantry_bounds,
                                minimum_functional_gantry_boundary_clearance_meters,
                                minimum_functional_gantry_boundary_clearance_meters,
                                long_axis,
                            ),
                            candidate.bounds,
                        )
                    ):
                        continue
                    if any(
                        _rectangles_touch_or_overlap(candidate.bounds, other.bounds, clearance)
                        and not _is_allowed_portal_overlap(
                            candidate.component_name,
                            other.component_name,
                            portal_pass_through,
                        )
                        and frozenset((candidate.component_name, other.component_name)) not in semantic_overlap_pairs
                        and not _uses_multi_box_clearance(candidate, other, semantics)
                        for other in placements[1:]
                    ):
                        continue
                    if not _candidate_process_feasible(
                        candidate,
                        placements,
                        process_constraints,
                        semantics,
                        by_name,
                        roles,
                        long_axis,
                    ):
                        continue
                    if not _candidate_interaction_feasible(
                        candidate,
                        placements,
                        by_name,
                        semantics,
                        portal_pass_through,
                        long_axis,
                        clearance,
                    ):
                        continue
                    placed = candidate
                    bands[band_index][2] = candidate_cursor + item_long + clearance
                    break
                if placed:
                    break
            if placed:
                break
        if not placed:
            if not allow_outside_functional:
                raise ConstraintLayoutError(f"Functional component '{item.component_name}' does not fit inside gantry side bands.")
            quarters, offsets = _best_long_variant(item, long_axis, allow_rotation, semantic)
            item_long = _axis_size(offsets, long_axis)
            item_short = _axis_size(offsets, short_axis)
            desired_long = _axis_min(gantry_bounds, long_axis) + item_long / 2.0
            desired_short = _axis_max(gantry_bounds, short_axis) + clearance + item_short / 2.0
            candidate = _place_by_bounds_center(
                item,
                "functional",
                quarters,
                long_axis,
                desired_long,
                desired_short,
                containment_relaxed=True,
            )
            while any(_rectangles_touch_or_overlap(candidate.bounds, other.bounds, clearance) for other in placements):
                desired_long += item_long + clearance
                candidate = _place_by_bounds_center(
                    item,
                    "functional",
                    quarters,
                    long_axis,
                    desired_long,
                    desired_short,
                    containment_relaxed=True,
                )
            if not _candidate_process_feasible(
                candidate,
                placements,
                process_constraints,
                semantics,
                by_name,
                roles,
                long_axis,
            ):
                raise ConstraintLayoutError(
                    f"Functional component '{item.component_name}' cannot satisfy its hard process "
                    "constraints outside the gantry envelope."
                )
            if not _candidate_interaction_feasible(
                candidate,
                placements,
                by_name,
                semantics,
                portal_pass_through,
                long_axis,
                clearance,
            ):
                raise ConstraintLayoutError(
                    f"Functional component '{item.component_name}' cannot satisfy its hard interaction "
                    "constraints outside the gantry envelope."
                )
            placed = candidate
        placements.append(placed)

    glue_items = [item for item in footprints if roles[item.component_name] == "glue"]
    glue_cursor = _axis_min(gantry_bounds, long_axis)
    for item in glue_items:
        source_candidate = _placement_at_source(item, "glue")
        locked_warm_start = (
            warm_start_by_name.get(item.component_name)
            if item.component_name in locked_warm_start_names
            else None
        )
        if locked_warm_start is not None:
            try:
                warm_theta = float(locked_warm_start["thetaDegrees"])
                warm_quarters = int(
                    round((warm_theta - item.source_theta) / 90.0)
                ) % 4
                allowed_quarters = _rotation_candidates(
                    item,
                    allow_rotation,
                    semantics.get(item.component_name),
                )
                if warm_quarters not in allowed_quarters:
                    raise ConstraintLayoutError(
                        f"Locked glue warm-start orientation is not allowed for "
                        f"'{item.component_name}'."
                    )
                candidate = _placement_at_anchor(
                    item,
                    "glue",
                    warm_quarters,
                    gantry.anchor_u + float(locked_warm_start["x"]),
                    gantry.anchor_v + float(locked_warm_start["y"]),
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ConstraintLayoutError(
                    f"Locked glue warm-start placement is invalid for "
                    f"'{item.component_name}'."
                ) from exc
            if _candidate_has_disallowed_overlap(
                candidate,
                placements,
                clearance,
                portal_pass_through,
                semantic_overlap_pairs,
            ):
                raise ConstraintLayoutError(
                    f"Locked glue warm-start placement overlaps another component for "
                    f"'{item.component_name}'."
                )
            if not _candidate_interaction_feasible(
                candidate,
                placements,
                by_name,
                semantics,
                portal_pass_through,
                long_axis,
                clearance,
            ):
                raise ConstraintLayoutError(
                    f"Locked glue warm-start placement violates an interaction constraint for "
                    f"'{item.component_name}'."
                )
            placements.append(candidate)
            glue_cursor = _axis_max(candidate.bounds, long_axis) + clearance
            continue
        if (
            prefer_source_layout
            and not _candidate_has_disallowed_overlap(
                source_candidate,
                placements,
                clearance,
                portal_pass_through,
                semantic_overlap_pairs,
            )
        ):
            placements.append(source_candidate)
            continue
        quarters, offsets = _best_long_variant(
            item,
            long_axis,
            allow_rotation,
            semantics.get(item.component_name),
        )
        item_long = _axis_size(offsets, long_axis)
        item_short = _axis_size(offsets, short_axis)
        semantic = semantics.get(item.component_name)
        if source_position_independent:
            source_side_high = bool(semantic and semantic.preferred_side == "high")
        else:
            source_side_high = (
                _axis_center(_source_bounds(item), short_axis)
                >= _axis_center(gantry_bounds, short_axis)
            )
        desired_short = (
            _axis_max(gantry_bounds, short_axis) + glue_distance + item_short / 2.0
            if source_side_high
            else _axis_min(gantry_bounds, short_axis) - glue_distance - item_short / 2.0
        )
        preferred_fraction = (
            float(semantic.parameters.get("preferredLongAxisFraction"))
            if semantic and semantic.parameters.get("preferredLongAxisFraction") is not None
            else None
        )
        if preferred_fraction is not None and not 0.0 <= preferred_fraction <= 1.0:
            raise ConstraintLayoutError(
                f"Glue component '{item.component_name}' preferredLongAxisFraction must be in [0, 1]."
            )
        desired_long = (
            _axis_min(gantry_bounds, long_axis)
            + preferred_fraction * _axis_size(gantry_bounds, long_axis)
            if source_position_independent and preferred_fraction is not None
            else glue_cursor + item_long / 2.0
        )
        candidate = _place_by_bounds_center(item, "glue", quarters, long_axis, desired_long, desired_short)
        if source_position_independent:
            # Glue equipment is placed after the joint functional-module search,
            # but it must obey the same measured multi-box clearance gate. Search
            # relative-process window anchors first, then locally around the
            # preferred service location.  This lets a glue/CCD B-Rep failure feed
            # back into a coordinated relative pose instead of keeping a stale
            # warm-start glue pose while only the CCD moves.
            search_step = max(clearance, 0.025)
            minimum_long = _axis_min(gantry_bounds, long_axis) + item_long / 2.0
            maximum_long = _axis_max(gantry_bounds, long_axis) - item_long / 2.0
            candidate_centers = [desired_long]
            maximum_steps = max(
                1,
                int(math.ceil(_axis_size(gantry_bounds, long_axis) / search_step)),
            )
            for step_index in range(1, maximum_steps + 1):
                candidate_centers.extend(
                    (desired_long + step_index * search_step, desired_long - step_index * search_step)
                )
            trial_candidates = [
                _placement_at_anchor(item, "glue", quarters, anchor_u, anchor_v)
                for anchor_u, anchor_v in _relative_anchor_window_anchors(
                    item.component_name,
                    process_constraints,
                    placements,
                )
            ]
            for candidate_long in candidate_centers:
                if candidate_long < minimum_long - 1e-9 or candidate_long > maximum_long + 1e-9:
                    continue
                trial_candidates.append(
                    _place_by_bounds_center(
                        item,
                        "glue",
                        quarters,
                        long_axis,
                        candidate_long,
                        desired_short,
                    )
                )

            deduplicated_trials: list[Placement] = []
            seen_trial_keys: set[tuple[int, int, int]] = set()
            for trial in trial_candidates:
                key = (
                    trial.rotation_quarters,
                    round(trial.anchor_u * 1_000_000),
                    round(trial.anchor_v * 1_000_000),
                )
                if key in seen_trial_keys:
                    continue
                seen_trial_keys.add(key)
                deduplicated_trials.append(trial)

            feasible_trials: list[Placement] = []
            for trial in deduplicated_trials:
                if _candidate_has_disallowed_overlap(
                    trial,
                    placements,
                    clearance,
                    portal_pass_through,
                    semantic_overlap_pairs,
                ):
                    continue
                if not _candidate_interaction_feasible(
                    trial,
                    placements,
                    by_name,
                    semantics,
                    portal_pass_through,
                    long_axis,
                    clearance,
                ):
                    continue
                if not _candidate_process_feasible(
                    trial,
                    placements,
                    process_constraints,
                    semantics,
                    by_name,
                    roles,
                    long_axis,
                ):
                    continue
                feasible_trials.append(trial)

            feasible_trials.sort(
                key=lambda trial: (
                    _conditional_brep_overlap_count(trial, placements, semantics),
                    _conditional_brep_leaf_hit_count(
                        trial,
                        placements,
                        by_name,
                        semantics,
                        clearance,
                    ),
                    _relative_anchor_window_target_distance(
                        trial,
                        placements,
                        process_constraints,
                    ),
                    math.dist(
                        (trial.anchor_u, trial.anchor_v),
                        (candidate.anchor_u, candidate.anchor_v),
                    ),
                )
            )
            selected = feasible_trials[0] if feasible_trials else None
            if selected is None:
                raise ConstraintLayoutError(
                    f"Glue component '{item.component_name}' cannot satisfy measured occupancy, "
                    "process-window, and interaction clearance along the gantry service side."
                )
            candidate = selected
        else:
            while _candidate_has_disallowed_overlap(
                candidate,
                placements,
                clearance,
                portal_pass_through,
                semantic_overlap_pairs,
            ):
                desired_long += item_long + clearance
                candidate = _place_by_bounds_center(
                    item, "glue", quarters, long_axis, desired_long, desired_short
                )
        placements.append(candidate)
        glue_cursor = desired_long + item_long / 2.0 + clearance

    if joint_search_report.get("solutions"):
        glue_summaries = [
            _placement_summary(value) for value in placements if value.role == "glue"
        ]
        for solution in joint_search_report["solutions"]:
            present = {
                value.get("componentName") for value in solution.get("placements", [])
            }
            solution.setdefault("placements", []).extend(
                value for value in glue_summaries if value["componentName"] not in present
            )

    if set(by_name) != {item.component_name for item in placements}:
        missing = sorted(set(by_name) - {item.component_name for item in placements})
        raise ConstraintLayoutError(f"Solver did not place all components: {', '.join(missing)}")
    validation = _validate_placements(
        placements,
        gantry.component_name,
        portal_pass_through,
        semantic_overlap_pairs,
    )
    if validation["overlapPairs"]:
        raise ConstraintLayoutError(f"Generated placements overlap: {validation['overlapPairs']}")
    try:
        process_validation = evaluate_process_constraints(
            process_constraints,
            semantics,
            by_name,
            placements,
            roles,
            long_axis,
        )
    except ProcessConstraintConfigurationError as exc:
        raise ConstraintLayoutError(str(exc)) from exc
    if not process_validation["hardFeasible"]:
        failures = [
            f"{item['id']}: {item['message']} measured={item.get('measured')}"
            for item in process_validation["diagnostics"]
            if item["hard"] and not item["success"]
        ]
        raise ConstraintLayoutError(
            "Process hard constraints failed: " + "; ".join(failures[:5])
        )
    spatial_validation = _evaluate_spatial_hard_constraints(
        placements,
        by_name,
        roles,
        semantics,
        gantry.component_name,
        portal_pass_through,
        minimum_transport_gantry_overlap_ratio=minimum_transport_gantry_overlap_ratio,
        minimum_portal_gantry_overlap_ratio=minimum_portal_gantry_overlap_ratio,
        minimum_functional_gantry_overlap_ratio=minimum_functional_gantry_overlap_ratio,
        minimum_functional_gantry_boundary_clearance_meters=minimum_functional_gantry_boundary_clearance_meters,
        maximum_transport_gantry_center_offset_meters=maximum_transport_gantry_center_offset_meters,
        maximum_portal_gantry_center_offset_meters=maximum_portal_gantry_center_offset_meters,
        maximum_portal_gantry_overhang_meters=maximum_portal_gantry_overhang_meters,
    )
    if not spatial_validation["hardFeasible"]:
        raise ConstraintLayoutError(spatial_validation["message"])
    return placements


def _joint_place_functionals(
    items: list[Footprint],
    fixed_placements: list[Placement],
    footprints: dict[str, Footprint],
    roles: dict[str, ComponentRole],
    gantry: Placement,
    long_axis: str,
    clearance: float,
    allow_rotation: bool,
    portal_pass_through: dict[str, tuple[str, ...]],
    semantics: dict[str, ModuleSemantic],
    process_constraints: list[dict[str, Any]],
    semantic_overlap_pairs: set[frozenset[str]],
    source_position_independent: bool,
    minimum_portal_gantry_overlap_ratio: float,
    minimum_functional_gantry_overlap_ratio: float,
    minimum_boundary_clearance: float,
    maximum_portal_gantry_center_offset_meters: float | None,
    maximum_portal_gantry_overhang_meters: float | None,
    candidate_limit: int,
    maximum_solutions: int,
    warm_start_placements: tuple[dict[str, Any], ...],
    warm_start_locked_components: tuple[str, ...],
    search_time_limit_seconds: float | None,
    report: dict[str, Any],
) -> list[Placement]:
    """Place all functional modules with bounded DFS instead of greedy pair repair.

    Candidate generation is local to module semantics.  Collision checks always
    include the fixed gantry/transport skeleton and every earlier candidate, so a
    later dead end backtracks to the responsible upstream choice.
    """
    candidate_counts: dict[str, int] = {}
    accepted_counts: dict[str, int] = {}
    rejection_counts: dict[str, dict[str, int]] = {}
    collision_matrix: dict[str, int] = {}
    explored_nodes = 0
    maximum_search_nodes = max(500, candidate_limit * candidate_limit * max(1, len(items)))
    solutions: list[tuple[float, list[Placement], list[int]]] = []
    geometry_candidate_cache: dict[
        tuple[str, tuple[tuple[str, int, int, int], ...]], list[Placement]
    ] = {}
    occupancy_envelope_cache: dict[
        tuple[str, int, int, int], list[dict[str, Any]]
    ] = {}
    accepted_candidate_cache: dict[
        tuple[str, tuple[tuple[str, int, int, int], ...]], list[Placement]
    ] = {}
    candidate_interaction_cache: dict[
        tuple[
            tuple[str, int, int, int],
            tuple[tuple[str, int, int, int], ...],
        ],
        dict[str, Any],
    ] = {}
    candidate_process_cache: dict[
        tuple[
            tuple[str, int, int, int],
            tuple[tuple[str, int, int, int], ...],
        ],
        dict[str, Any],
    ] = {}
    process_constraint_failure_counts: dict[str, dict[str, int]] = {}
    candidate_cache_hits = 0
    candidate_cache_misses = 0
    interaction_cache_hits = 0
    interaction_cache_misses = 0
    process_cache_hits = 0
    process_cache_misses = 0
    responsibility_pruned_candidate_count = 0
    warm_start_candidate_count = 0
    candidate_pipeline_seconds: dict[str, float] = {}
    candidate_generation_calls: dict[str, int] = {}
    candidate_cache_hit_counts: dict[str, int] = {}
    warm_start_by_name = {
        str(item.get("componentName")): item
        for item in warm_start_placements
        if isinstance(item, dict) and item.get("componentName")
    }
    locked_warm_start_names = {
        str(name) for name in warm_start_locked_components if str(name)
    }
    missing_locked_warm_starts = sorted(locked_warm_start_names - set(warm_start_by_name))
    if missing_locked_warm_starts:
        raise ConstraintLayoutError(
            "Locked warm-start components have no warm-start placement: "
            + ", ".join(missing_locked_warm_starts)
        )
    if search_time_limit_seconds is not None:
        if (
            not math.isfinite(search_time_limit_seconds)
            or search_time_limit_seconds <= 0
            or search_time_limit_seconds > 600
        ):
            raise ConstraintLayoutError(
                "jointSearchTimeLimitSeconds must be greater than 0 and no more than 600."
            )
    search_started = time.perf_counter()
    search_deadline = (
        search_started + search_time_limit_seconds
        if search_time_limit_seconds is not None
        else None
    )

    def elapsed_seconds() -> float:
        return max(0.0, time.perf_counter() - search_started)

    def module_stage_diagnostics() -> dict[str, dict[str, Any]]:
        names = {
            *candidate_counts,
            *accepted_counts,
            *rejection_counts,
            *process_constraint_failure_counts,
            *candidate_pipeline_seconds,
            *candidate_generation_calls,
            *candidate_cache_hit_counts,
        }
        return {
            name: {
                "candidateCount": candidate_counts.get(name, 0),
                "acceptedCandidateCount": accepted_counts.get(name, 0),
                "candidateGenerationCalls": candidate_generation_calls.get(name, 0),
                "candidateCacheHitCount": candidate_cache_hit_counts.get(name, 0),
                "candidatePipelineSeconds": round(candidate_pipeline_seconds.get(name, 0.0), 6),
                "rejectionCounts": dict(rejection_counts.get(name, {})),
                "processConstraintFailureCounts": dict(
                    process_constraint_failure_counts.get(name, {})
                ),
            }
            for name in sorted(names)
        }

    def check_search_time(stage: str) -> None:
        if search_deadline is None or time.perf_counter() <= search_deadline:
            return
        report.update(
            {
                "success": False,
                "timedOut": True,
                "timeoutStage": stage,
                "elapsedSeconds": elapsed_seconds(),
                "timeLimitSeconds": search_time_limit_seconds,
                "candidateCounts": candidate_counts,
                "acceptedCandidateCounts": accepted_counts,
                "rejectionCounts": rejection_counts,
                "processConstraintFailureCounts": process_constraint_failure_counts,
                "collisionMatrix": collision_matrix,
                "exploredNodeCount": explored_nodes,
                "candidateStateCache": {
                    "hits": candidate_cache_hits,
                    "misses": candidate_cache_misses,
                    "entryCount": len(accepted_candidate_cache),
                },
                "processValidationCache": {
                    "hits": process_cache_hits,
                    "misses": process_cache_misses,
                    "entryCount": len(candidate_process_cache),
                },
                "interactionValidationCache": {
                    "hits": interaction_cache_hits,
                    "misses": interaction_cache_misses,
                    "entryCount": len(candidate_interaction_cache),
                },
                "occupancyEnvelopeCacheEntryCount": len(occupancy_envelope_cache),
                "responsibilityPrunedCandidateCount": responsibility_pruned_candidate_count,
                "moduleStageDiagnostics": module_stage_diagnostics(),
                "timeoutModule": stage.split(":", 1)[1] if ":" in stage else None,
            }
        )
        raise ConstraintLayoutSearchTimeout(
            "Bounded joint search exceeded its time budget; "
            f"stage={stage}, elapsedSeconds={elapsed_seconds():.3f}, "
            f"timeLimitSeconds={search_time_limit_seconds}, "
            f"acceptedCandidateCounts={accepted_counts}, collisionMatrix={collision_matrix}. "
            "Timeout is an indeterminate search result, not proof that the layout is infeasible.",
            report=report,
        )

    def pose_key(placement: Placement) -> tuple[str, int, int, int]:
        return (
            placement.component_name,
            placement.rotation_quarters,
            round(placement.anchor_u * 1_000_000),
            round(placement.anchor_v * 1_000_000),
        )

    def placed_state_key(
        placed: list[Placement],
    ) -> tuple[tuple[str, int, int, int], ...]:
        return tuple(pose_key(value) for value in placed)

    def process_validation_cached(
        candidate: Placement,
        placed: list[Placement],
    ) -> dict[str, Any]:
        nonlocal process_cache_hits, process_cache_misses
        key = (pose_key(candidate), placed_state_key(placed))
        cached = candidate_process_cache.get(key)
        if cached is not None:
            process_cache_hits += 1
            return cached
        process_cache_misses += 1
        result = _candidate_process_validation(
            candidate,
            placed,
            process_constraints,
            semantics,
            footprints,
            roles,
            long_axis,
        )
        candidate_process_cache[key] = result
        return result

    def process_feasible_cached(
        candidate: Placement,
        placed: list[Placement],
    ) -> bool:
        return bool(process_validation_cached(candidate, placed)["hardFeasible"])

    def interaction_validation_cached(
        candidate: Placement,
        placed: list[Placement],
    ) -> dict[str, Any]:
        nonlocal interaction_cache_hits, interaction_cache_misses
        key = (pose_key(candidate), placed_state_key(placed))
        cached = candidate_interaction_cache.get(key)
        if cached is not None:
            interaction_cache_hits += 1
            return cached
        interaction_cache_misses += 1
        result = _evaluate_interaction_hard_constraints(
            [*placed, candidate],
            footprints,
            semantics,
            portal_pass_through,
            long_axis,
            clearance,
            collision_pair_limit=1,
            focus_component_name=candidate.component_name,
            occupancy_envelope_cache=occupancy_envelope_cache,
        )
        candidate_interaction_cache[key] = result
        return result

    def reject(name: str, reason: str) -> None:
        bucket = rejection_counts.setdefault(name, {})
        bucket[reason] = bucket.get(reason, 0) + 1

    def record_process_failures(
        candidate: Placement,
        validation: dict[str, Any],
    ) -> None:
        bucket = process_constraint_failure_counts.setdefault(
            candidate.component_name,
            {},
        )
        failed = [
            item
            for item in validation.get("diagnostics", [])
            if item.get("hard", True) and not item.get("success", False)
        ]
        if not failed:
            bucket["unknown-process-constraint"] = (
                bucket.get("unknown-process-constraint", 0) + 1
            )
            return
        for diagnostic in failed:
            constraint_id = str(
                diagnostic.get("id")
                or diagnostic.get("type")
                or "unknown-process-constraint"
            )
            bucket[constraint_id] = bucket.get(constraint_id, 0) + 1

    def record_interaction_failures(candidate: Placement, validation: dict[str, Any]) -> None:
        failed = [
            item for item in validation.get("diagnostics", [])
            if item.get("hard", True) and not item.get("success", False)
        ]
        if not failed:
            reject(candidate.component_name, "interaction")
            return
        for diagnostic in failed[:1]:
            first = str(diagnostic.get("firstComponent") or diagnostic.get("portalComponent") or "unknown")
            second = str(diagnostic.get("secondComponent") or diagnostic.get("passThroughComponent") or candidate.component_name)
            rule = str(diagnostic.get("resolution") or diagnostic.get("type") or "interaction")
            key = " | ".join((*sorted((first, second)), rule))
            collision_matrix[key] = collision_matrix.get(key, 0) + 1
        reject(candidate.component_name, "interaction")

    def raw_candidates(item: Footprint, placed: list[Placement]) -> list[Placement]:
        nonlocal candidate_cache_hits, candidate_cache_misses
        nonlocal responsibility_pruned_candidate_count
        nonlocal warm_start_candidate_count
        pipeline_started = time.perf_counter()
        candidate_generation_calls[item.component_name] = (
            candidate_generation_calls.get(item.component_name, 0) + 1
        )
        check_search_time(f"candidate-generation:{item.component_name}")
        accepted_cache_key = (item.component_name, placed_state_key(placed))
        cached_accepted = accepted_candidate_cache.get(accepted_cache_key)
        if cached_accepted is not None:
            candidate_cache_hits += 1
            candidate_cache_hit_counts[item.component_name] = (
                candidate_cache_hit_counts.get(item.component_name, 0) + 1
            )
            accepted_counts[item.component_name] = max(
                accepted_counts.get(item.component_name, 0),
                len(cached_accepted),
            )
            candidate_pipeline_seconds[item.component_name] = (
                candidate_pipeline_seconds.get(item.component_name, 0.0)
                + time.perf_counter()
                - pipeline_started
            )
            return list(cached_accepted)
        candidate_cache_misses += 1
        semantic = semantics.get(item.component_name)
        pass_names = portal_pass_through.get(item.component_name, ())
        required_overlap = (
            minimum_portal_gantry_overlap_ratio
            if pass_names
            else float(
                semantic.parameters.get("minimumGantryOverlapRatio", minimum_functional_gantry_overlap_ratio)
                if semantic
                else minimum_functional_gantry_overlap_ratio
            )
        )
        component_boundary_clearance = float(
            semantic.parameters.get(
                "minimumGantryBoundaryClearanceMeters",
                minimum_boundary_clearance,
            )
            if semantic
            else minimum_boundary_clearance
        )
        if not math.isfinite(component_boundary_clearance) or component_boundary_clearance < 0:
            raise ConstraintLayoutError(
                f"Functional component '{item.component_name}' minimumGantryBoundaryClearanceMeters "
                "must be a finite non-negative number."
            )
        portal_dependency = next(
            (value for value in placed if value.component_name in portal_pass_through),
            None,
        )
        process_dependency_names = {
            name
            for constraint in process_constraints
            if item.component_name in _constraint_component_names(constraint)
            for name in _constraint_component_names(constraint)
        }
        generation_dependencies = [
            value
            for value in placed
            if value.component_name in process_dependency_names
            or value is portal_dependency
        ]
        cache_key = (
            item.component_name,
            placed_state_key(generation_dependencies),
        )
        ordered = geometry_candidate_cache.get(cache_key)
        if ordered is None:
            generation_placements = list(fixed_placements)
            fixed_names = {value.component_name for value in generation_placements}
            generation_placements.extend(
                value
                for value in generation_dependencies
                if value.component_name != item.component_name
                and value.component_name not in fixed_names
            )
            result: list[Placement] = []
            if pass_names:
                opening_pass_names = tuple(
                    name for name in pass_names if roles.get(name) == "transport"
                )
                pass_through = [
                    value for value in generation_placements
                    if value.component_name in opening_pass_names
                ]
                if len(pass_through) != len(opening_pass_names):
                    candidate_pipeline_seconds[item.component_name] = (
                        candidate_pipeline_seconds.get(item.component_name, 0.0)
                        + time.perf_counter()
                        - pipeline_started
                    )
                    return result
                for quarters in _rotation_candidates(item, allow_rotation, semantic):
                    baseline = _place_by_bounds_center(
                        item,
                        "functional",
                        quarters,
                        long_axis,
                        _axis_center(gantry.bounds, long_axis),
                        (
                            min(_axis_min(value.bounds, _other_axis(long_axis)) for value in pass_through)
                            + max(_axis_max(value.bounds, _other_axis(long_axis)) for value in pass_through)
                        ) / 2.0,
                    )
                    baseline = _align_portal_process_region(
                        baseline, item, semantic, pass_through, semantics
                    )
                    span_u = min(0.36, _width(gantry.bounds) * 0.28)
                    span_v = min(0.36, _height(gantry.bounds) * 0.28)
                    offsets = [
                        (u, v)
                        for u in _grid_values(-span_u, span_u, 7)
                        for v in _grid_values(-span_v, span_v, 7)
                    ]
                    opening_region = semantic.regions.get("portalOpening") if semantic else None
                    if opening_region is not None:
                        for passed in pass_through:
                            passed_semantic = semantics.get(passed.component_name)
                            raw_pass_bodies = (
                                passed_semantic.parameters.get("portalPassBodyBoxesLocal", [])
                                if passed_semantic
                                else []
                            )
                            interval = _portal_long_axis_anchor_interval(
                                baseline,
                                opening_region,
                                passed,
                                raw_pass_bodies,
                                long_axis,
                                clearance,
                            )
                            if interval is None or interval[0] > interval[1] + 1e-9:
                                continue
                            current_long = (
                                baseline.anchor_u if long_axis == "u" else baseline.anchor_v
                            )
                            event_long_offsets = _grid_values(interval[0], interval[1], 3)
                            short_span = span_v if long_axis == "u" else span_u
                            for event_anchor in event_long_offsets:
                                long_offset = event_anchor - current_long
                                for short_offset in _grid_values(-short_span, short_span, 7):
                                    offsets.append(
                                        (long_offset, short_offset)
                                        if long_axis == "u"
                                        else (short_offset, long_offset)
                                    )
                    offsets.sort(key=lambda value: (math.hypot(*value), abs(value[1]), abs(value[0]), value))
                    result.extend(
                        _translate_placement(baseline, offset_u, offset_v)
                        for offset_u, offset_v in offsets
                    )
                    result.extend(
                        _placement_at_anchor(
                            item,
                            "functional",
                            quarters,
                            anchor_u,
                            anchor_v,
                        )
                        for anchor_u, anchor_v in _relative_anchor_window_anchors(
                            item.component_name,
                            process_constraints,
                            generation_placements,
                        )
                    )
            else:
                for quarters in _rotation_candidates(item, allow_rotation, semantic):
                    candidate_grid_count = int(
                        semantic.parameters.get("candidateGridCount", 13)
                        if semantic
                        else 13
                    )
                    if candidate_grid_count < 3 or candidate_grid_count > 41:
                        raise ConstraintLayoutError(
                            f"Functional component '{item.component_name}' candidateGridCount "
                            "must be between 3 and 41."
                        )
                    anchors = list(
                        _point_in_region_anchor_candidates(
                            item,
                            quarters,
                            process_constraints,
                            semantics,
                            generation_placements,
                            portal_pass_through,
                            clearance,
                            source_position_independent=source_position_independent,
                            grid_count=candidate_grid_count,
                        )
                    )
                    if not anchors:
                        offsets = _rotated_offsets(item, quarters)
                        min_u = gantry.bounds[0] + minimum_boundary_clearance - offsets[0]
                        max_u = gantry.bounds[2] - minimum_boundary_clearance - offsets[2]
                        min_v = gantry.bounds[1] + minimum_boundary_clearance - offsets[1]
                        max_v = gantry.bounds[3] - minimum_boundary_clearance - offsets[3]
                        if min_u <= max_u and min_v <= max_v:
                            anchors = [
                                (u, v)
                                for u in _grid_values(min_u, max_u, 9)
                                for v in _grid_values(min_v, max_v, 9)
                            ]
                    result.extend(
                        _placement_at_anchor(item, "functional", quarters, anchor_u, anchor_v)
                        for anchor_u, anchor_v in anchors
                    )
            warm_start = warm_start_by_name.get(item.component_name)
            if warm_start is not None:
                try:
                    warm_theta = float(warm_start["thetaDegrees"])
                    warm_quarters = int(
                        round((warm_theta - item.source_theta) / 90.0)
                    ) % 4
                    allowed_quarters = _rotation_candidates(
                        item,
                        allow_rotation,
                        semantic,
                    )
                    if warm_quarters in allowed_quarters:
                        warm_candidate = _placement_at_anchor(
                            item,
                            "functional",
                            warm_quarters,
                            gantry.anchor_u + float(warm_start["x"]),
                            gantry.anchor_v + float(warm_start["y"]),
                        )
                        warm_candidates: list[Placement] = []
                        raw_directional_offsets = (
                            semantic.parameters.get(
                                "candidateDirectionalOffsetsMeters", []
                            )
                            if semantic
                            else []
                        )
                        if isinstance(raw_directional_offsets, list):
                            for raw_offset in raw_directional_offsets:
                                if not isinstance(raw_offset, list) or len(raw_offset) != 2:
                                    continue
                                offset_u, offset_v = (float(raw_offset[0]), float(raw_offset[1]))
                                if (
                                    not math.isfinite(offset_u)
                                    or not math.isfinite(offset_v)
                                    or math.hypot(offset_u, offset_v) > 1.0
                                ):
                                    continue
                                warm_candidates.append(
                                    _translate_placement(warm_candidate, offset_u, offset_v)
                                )
                        raw_local_refinements = (
                            semantic.parameters.get(
                                "candidateLocalRefinementMeters", []
                            )
                            if semantic
                            else []
                        )
                        if isinstance(raw_local_refinements, (int, float)):
                            raw_local_refinements = [raw_local_refinements]
                        if isinstance(raw_local_refinements, list):
                            for raw_refinement in raw_local_refinements:
                                refinement = float(raw_refinement)
                                if (
                                    not math.isfinite(refinement)
                                    or refinement <= 0
                                    or refinement > 0.05
                                ):
                                    continue
                                # Prefer a positive short-axis shift first:
                                # service clusters commonly need to move away
                                # from a transport keepout while preserving
                                # their calibrated internal relation.
                                warm_candidates.extend(
                                    (
                                        _translate_placement(
                                            warm_candidate, 0.0, refinement
                                        ),
                                        _translate_placement(
                                            warm_candidate, 0.0, -refinement
                                        ),
                                        _translate_placement(
                                            warm_candidate, refinement, 0.0
                                        ),
                                        _translate_placement(
                                            warm_candidate, -refinement, 0.0
                                        ),
                                    )
                                )
                        warm_candidates.append(warm_candidate)
                        result[0:0] = warm_candidates
                        warm_start_candidate_count += 1
                except (KeyError, TypeError, ValueError):
                    pass

            unique: dict[tuple[int, int, int], Placement] = {}
            for candidate in result:
                key = (
                    candidate.rotation_quarters,
                    round(candidate.anchor_u * 1_000_000),
                    round(candidate.anchor_v * 1_000_000),
                )
                unique.setdefault(key, candidate)
            ordered = list(unique.values())
            geometry_candidate_cache[cache_key] = ordered
        if item.component_name in locked_warm_start_names:
            warm_start = warm_start_by_name[item.component_name]
            try:
                warm_theta = float(warm_start["thetaDegrees"])
                warm_quarters = int(round((warm_theta - item.source_theta) / 90.0)) % 4
                allowed_quarters = _rotation_candidates(item, allow_rotation, semantic)
                if warm_quarters not in allowed_quarters:
                    raise ConstraintLayoutError(
                        f"Locked warm-start orientation is not allowed for '{item.component_name}'."
                    )
                ordered = [
                    _placement_at_anchor(
                        item,
                        "functional",
                        warm_quarters,
                        gantry.anchor_u + float(warm_start["x"]),
                        gantry.anchor_v + float(warm_start["y"]),
                    )
                ]
            except (KeyError, TypeError, ValueError) as exc:
                raise ConstraintLayoutError(
                    f"Locked warm-start placement is invalid for '{item.component_name}'."
                ) from exc
        candidate_counts[item.component_name] = max(candidate_counts.get(item.component_name, 0), len(ordered))

        search_candidates = list(ordered)
        repair_seed_limit = (
            0
            if item.component_name in locked_warm_start_names
            else int(
                semantic.parameters.get("collisionRepairSeedLimit", 0)
                if semantic
                else 0
            )
        )
        repair_depth = int(
            semantic.parameters.get("collisionRepairDepth", 0)
            if semantic
            else 0
        )
        repair_candidate_limit = int(
            semantic.parameters.get("collisionRepairCandidateLimit", 4096)
            if semantic
            else 4096
        )
        if repair_seed_limit < 0 or repair_seed_limit > 1024:
            raise ConstraintLayoutError(
                f"Functional component '{item.component_name}' collisionRepairSeedLimit "
                "must be between 0 and 1024."
            )
        if repair_depth < 0 or repair_depth > 6:
            raise ConstraintLayoutError(
                f"Functional component '{item.component_name}' collisionRepairDepth "
                "must be between 0 and 6."
            )
        if repair_candidate_limit < 1 or repair_candidate_limit > 20000:
            raise ConstraintLayoutError(
                f"Functional component '{item.component_name}' collisionRepairCandidateLimit "
                "must be between 1 and 20000."
            )
        if item.component_name in warm_start_by_name and repair_seed_limit:
            warm_seed_limit = int(
                semantic.parameters.get("warmStartRepairSeedLimit", 1)
                if semantic
                else 1
            )
            if warm_seed_limit < 1 or warm_seed_limit > repair_seed_limit:
                raise ConstraintLayoutError(
                    f"Functional component '{item.component_name}' warmStartRepairSeedLimit "
                    f"must be between 1 and collisionRepairSeedLimit ({repair_seed_limit})."
                )
            repair_seed_limit = warm_seed_limit

        # Boundary repair exists to recover narrow feasible cells missed by the
        # semantic grid.  When explicitly requested, do not generate hundreds of
        # repaired locations if that grid already contains a hard-feasible one.
        # The normal accepted-candidate loop below remains authoritative.
        repair_only_when_grid_infeasible = bool(
            semantic
            and semantic.parameters.get(
                "collisionRepairOnlyWhenGridInfeasible",
                False,
            )
        )
        if (
            source_position_independent
            and repair_seed_limit
            and repair_depth
            and repair_only_when_grid_infeasible
        ):
            inset = _inset_bounds(
                gantry.bounds,
                component_boundary_clearance,
                component_boundary_clearance,
                long_axis,
            )
            for candidate in search_candidates:
                if _overlap_ratio(candidate.bounds, gantry.bounds) < required_overlap - 1e-9:
                    continue
                if component_boundary_clearance > 0 and not pass_names and not _contains_bounds(
                    inset,
                    candidate.bounds,
                ):
                    continue
                if any(
                    _rectangles_touch_or_overlap(candidate.bounds, other.bounds, clearance)
                    and not _is_allowed_portal_overlap(
                        candidate.component_name,
                        other.component_name,
                        portal_pass_through,
                    )
                    and frozenset((candidate.component_name, other.component_name))
                    not in semantic_overlap_pairs
                    and not _uses_multi_box_clearance(candidate, other, semantics)
                    for other in placed[1:]
                ):
                    continue
                if not process_feasible_cached(candidate, placed):
                    continue
                validation = interaction_validation_cached(candidate, placed)
                if validation["hardFeasible"]:
                    repair_seed_limit = 0
                    break

        # A uniform Cartesian grid can miss a narrow free cell between measured
        # leaf-body boxes.  For explicitly enabled modules, walk a bounded set of
        # analytic collision events: move the candidate just beyond the blocking
        # box along one axis, then repeat for the next blocker.  This uses only
        # semantic/process geometry and never the prototype component position.
        if source_position_independent and repair_seed_limit and repair_depth:
            repair_seen = {
                (
                    candidate.rotation_quarters,
                    round(candidate.anchor_u * 1_000_000),
                    round(candidate.anchor_v * 1_000_000),
                )
                for candidate in search_candidates
            }
            frontier: list[Placement] = []
            for candidate in search_candidates:
                if _overlap_ratio(candidate.bounds, gantry.bounds) < required_overlap - 1e-9:
                    continue
                if component_boundary_clearance > 0 and not pass_names and not _contains_bounds(
                    _inset_bounds(
                        gantry.bounds,
                        component_boundary_clearance,
                        component_boundary_clearance,
                        long_axis,
                    ),
                    candidate.bounds,
                ):
                    continue
                if not process_feasible_cached(candidate, placed):
                    continue
                frontier.append(candidate)
                if len(frontier) >= repair_seed_limit:
                    break

            repaired_feasible: list[Placement] = []
            generated_repair_count = 0
            for _ in range(repair_depth):
                check_search_time(f"collision-repair:{item.component_name}")
                next_frontier_by_responsibility: dict[
                    tuple[Any, ...], Placement
                ] = {}
                for candidate in frontier:
                    check_search_time(f"collision-repair:{item.component_name}")
                    for repaired in _candidate_collision_boundary_repairs(
                        candidate,
                        placed,
                        footprints,
                        semantics,
                        portal_pass_through,
                        clearance,
                        occupancy_envelope_cache,
                    ):
                        check_search_time(f"collision-repair:{item.component_name}")
                        key = (
                            repaired.rotation_quarters,
                            round(repaired.anchor_u * 1_000_000),
                            round(repaired.anchor_v * 1_000_000),
                        )
                        if key in repair_seen:
                            continue
                        repair_seen.add(key)
                        generated_repair_count += 1
                        if generated_repair_count > repair_candidate_limit:
                            break
                        if _overlap_ratio(repaired.bounds, gantry.bounds) < required_overlap - 1e-9:
                            continue
                        if component_boundary_clearance > 0 and not pass_names and not _contains_bounds(
                            _inset_bounds(
                                gantry.bounds,
                                component_boundary_clearance,
                                component_boundary_clearance,
                                long_axis,
                            ),
                            repaired.bounds,
                        ):
                            continue
                        if not process_feasible_cached(repaired, placed):
                            continue
                        interaction_validation = interaction_validation_cached(
                            repaired,
                            placed,
                        )
                        if interaction_validation["hardFeasible"]:
                            repaired_feasible.append(repaired)
                            if len(repaired_feasible) >= candidate_limit:
                                break
                        else:
                            responsibility = _collision_responsibility_key(
                                interaction_validation,
                                candidate,
                                repaired,
                            )
                            if responsibility in next_frontier_by_responsibility:
                                responsibility_pruned_candidate_count += 1
                            else:
                                next_frontier_by_responsibility[responsibility] = repaired
                    if generated_repair_count > repair_candidate_limit or len(repaired_feasible) >= candidate_limit:
                        break
                frontier = list(next_frontier_by_responsibility.values())
                if not frontier or generated_repair_count > repair_candidate_limit or len(repaired_feasible) >= candidate_limit:
                    break
            if repaired_feasible:
                search_candidates = [*repaired_feasible, *search_candidates]

        # Prefer candidates that avoid a future exact CAD check altogether.
        # When two candidates need the same number of conditional B-Rep pairs,
        # prefer the one with fewer measured leaf-AABB broad-phase hits.  This
        # remains a soft ordering key: non-convex false positives are not turned
        # into hard failures and the candidate set is not enlarged.
        search_candidates = sorted(
            enumerate(search_candidates),
            key=lambda item_with_index: (
                _conditional_brep_overlap_count(
                    item_with_index[1],
                    placed,
                    semantics,
                ),
                _conditional_brep_leaf_hit_count(
                    item_with_index[1],
                    placed,
                    footprints,
                    semantics,
                    clearance,
                    occupancy_envelope_cache,
                ),
                _relative_anchor_window_target_distance(
                    item_with_index[1],
                    placed,
                    process_constraints,
                ),
                (
                    item_with_index[0]
                    if semantic
                    and bool(
                        semantic.parameters.get(
                            "prioritizeSourceIndependentAnchorBias", False
                        )
                    )
                    else 0
                ),
                item_with_index[0],
            ),
        )
        search_candidates = [item for _, item in search_candidates]

        accepted: list[Placement] = []
        inset = _inset_bounds(
            gantry.bounds,
            component_boundary_clearance,
            component_boundary_clearance,
            long_axis,
        )
        for candidate in search_candidates:
            check_search_time(f"candidate-validation:{item.component_name}")
            if _overlap_ratio(candidate.bounds, gantry.bounds) < required_overlap - 1e-9:
                reject(item.component_name, "gantry-overlap")
                continue
            if pass_names and maximum_portal_gantry_center_offset_meters is not None:
                portal_center_offset = abs(
                    _axis_center(candidate.bounds, _other_axis(long_axis))
                    - _axis_center(gantry.bounds, _other_axis(long_axis))
                )
                if portal_center_offset > maximum_portal_gantry_center_offset_meters + 1e-9:
                    reject(item.component_name, "portal-centerline")
                    continue
            if pass_names and maximum_portal_gantry_overhang_meters is not None:
                portal_overhang = _maximum_bounds_overhang(candidate.bounds, gantry.bounds)
                if portal_overhang > maximum_portal_gantry_overhang_meters + 1e-9:
                    reject(item.component_name, "portal-overhang")
                    continue
            if component_boundary_clearance > 0 and not pass_names and not _contains_bounds(inset, candidate.bounds):
                reject(item.component_name, "gantry-boundary")
                continue
            if any(
                _rectangles_touch_or_overlap(candidate.bounds, other.bounds, clearance)
                and not _is_allowed_portal_overlap(candidate.component_name, other.component_name, portal_pass_through)
                and frozenset((candidate.component_name, other.component_name)) not in semantic_overlap_pairs
                and not _uses_multi_box_clearance(candidate, other, semantics)
                for other in placed[1:]
            ):
                reject(item.component_name, "coarse-overlap")
                continue
            process_validation = process_validation_cached(candidate, placed)
            if not process_validation["hardFeasible"]:
                record_process_failures(candidate, process_validation)
                reject(item.component_name, "process")
                continue
            interaction_validation = interaction_validation_cached(candidate, placed)
            if not interaction_validation["hardFeasible"]:
                record_interaction_failures(candidate, interaction_validation)
                continue
            accepted.append(candidate)
            if len(accepted) >= candidate_limit:
                break
        accepted_counts[item.component_name] = max(accepted_counts.get(item.component_name, 0), len(accepted))
        accepted_candidate_cache[accepted_cache_key] = list(accepted)
        candidate_pipeline_seconds[item.component_name] = (
            candidate_pipeline_seconds.get(item.component_name, 0.0)
            + time.perf_counter()
            - pipeline_started
        )
        return accepted

    def search(index: int, placed: list[Placement], ranks: list[int]) -> None:
        nonlocal explored_nodes
        check_search_time("depth-first-search")
        if len(solutions) >= maximum_solutions or explored_nodes >= maximum_search_nodes:
            return
        if index >= len(items):
            compactness = sum(
                math.dist(
                    (_axis_center(value.bounds, "u"), _axis_center(value.bounds, "v")),
                    (_axis_center(gantry.bounds, "u"), _axis_center(gantry.bounds, "v")),
                )
                for value in placed[len(fixed_placements) :]
            )
            conditional_brep_candidates = _conditional_brep_pair_count(
                placed,
                semantics,
            )
            conditional_leaf_hit_count = _conditional_brep_leaf_hit_count_for_layout(
                placed,
                footprints,
                semantics,
                clearance,
                occupancy_envelope_cache,
            )
            solutions.append(
                (
                    sum(ranks)
                    + compactness * 0.01
                    + conditional_brep_candidates * 0.1
                    + conditional_leaf_hit_count * 0.01,
                    list(placed),
                    list(ranks),
                )
            )
            return
        item = items[index]
        for rank, candidate in enumerate(raw_candidates(item, placed)):
            check_search_time(f"depth-first-search:{item.component_name}")
            explored_nodes += 1
            search(index + 1, [*placed, candidate], [*ranks, rank])
            if len(solutions) >= maximum_solutions or explored_nodes >= maximum_search_nodes:
                return

    search(0, list(fixed_placements), [])
    if not solutions:
        report.update(
            {
                "success": False,
                "candidateLimitPerModule": candidate_limit,
                "candidateCounts": candidate_counts,
                "acceptedCandidateCounts": accepted_counts,
                "rejectionCounts": rejection_counts,
                "processConstraintFailureCounts": process_constraint_failure_counts,
                "collisionMatrix": collision_matrix,
                "exploredNodeCount": explored_nodes,
                "maximumSearchNodes": maximum_search_nodes,
                "candidateStateCache": {
                    "hits": candidate_cache_hits,
                    "misses": candidate_cache_misses,
                    "entryCount": len(accepted_candidate_cache),
                },
                "processValidationCache": {
                    "hits": process_cache_hits,
                    "misses": process_cache_misses,
                    "entryCount": len(candidate_process_cache),
                },
                "interactionValidationCache": {
                    "hits": interaction_cache_hits,
                    "misses": interaction_cache_misses,
                    "entryCount": len(candidate_interaction_cache),
                },
                "occupancyEnvelopeCacheEntryCount": len(occupancy_envelope_cache),
                "responsibilityPrunedCandidateCount": responsibility_pruned_candidate_count,
                "moduleStageDiagnostics": module_stage_diagnostics(),
                "warmStartConfiguredComponentCount": len(warm_start_by_name),
                "warmStartCandidateCount": warm_start_candidate_count,
                "warmStartLockedComponents": sorted(locked_warm_start_names),
                "timedOut": False,
                "elapsedSeconds": elapsed_seconds(),
                "timeLimitSeconds": search_time_limit_seconds,
            }
        )
        failed_name = next(
            (
                item.component_name
                for item in items
                if accepted_counts.get(item.component_name, 0) == 0
            ),
            items[-1].component_name if items else "unknown",
        )
        raise ConstraintLayoutError(
            f"Bounded joint search found no complete functional layout; lastModule={failed_name}, "
            f"acceptedCandidateCounts={accepted_counts}, rejectionCounts={rejection_counts}, "
            f"processConstraintFailureCounts={process_constraint_failure_counts}, "
            f"collisionMatrix={collision_matrix}, candidateCacheHits={candidate_cache_hits}, "
            f"processCacheHits={process_cache_hits}, interactionCacheHits={interaction_cache_hits}, "
            f"responsibilityPruned={responsibility_pruned_candidate_count}."
        )
    solutions.sort(key=lambda item: item[0])
    report.update(
        {
            "success": True,
            "candidateLimitPerModule": candidate_limit,
            "maximumSolutions": maximum_solutions,
            "solutionCount": len(solutions),
            "candidateCounts": candidate_counts,
            "acceptedCandidateCounts": accepted_counts,
            "rejectionCounts": rejection_counts,
            "processConstraintFailureCounts": process_constraint_failure_counts,
            "collisionMatrix": collision_matrix,
            "exploredNodeCount": explored_nodes,
            "maximumSearchNodes": maximum_search_nodes,
            "candidateStateCache": {
                "hits": candidate_cache_hits,
                "misses": candidate_cache_misses,
                "entryCount": len(accepted_candidate_cache),
            },
            "processValidationCache": {
                "hits": process_cache_hits,
                "misses": process_cache_misses,
                "entryCount": len(candidate_process_cache),
            },
            "interactionValidationCache": {
                "hits": interaction_cache_hits,
                "misses": interaction_cache_misses,
                "entryCount": len(candidate_interaction_cache),
            },
            "occupancyEnvelopeCacheEntryCount": len(occupancy_envelope_cache),
            "responsibilityPrunedCandidateCount": responsibility_pruned_candidate_count,
            "moduleStageDiagnostics": module_stage_diagnostics(),
            "warmStartConfiguredComponentCount": len(warm_start_by_name),
            "warmStartCandidateCount": warm_start_candidate_count,
            "warmStartLockedComponents": sorted(locked_warm_start_names),
            "timedOut": False,
            "elapsedSeconds": elapsed_seconds(),
            "timeLimitSeconds": search_time_limit_seconds,
            "solutions": [
                {
                    "rank": index + 1,
                    "score": score,
                    "candidateRanks": ranks,
                    "predictedConditionalBrepPairCount": _conditional_brep_pair_count(
                        placed,
                        semantics,
                    ),
                    "predictedConditionalLeafAabbHitCount": (
                        _conditional_brep_leaf_hit_count_for_layout(
                            placed,
                            footprints,
                            semantics,
                            clearance,
                            occupancy_envelope_cache,
                        )
                    ),
                    "placements": [_placement_summary(value) for value in placed],
                }
                for index, (score, placed, ranks) in enumerate(solutions)
            ],
        }
    )
    best = solutions[0][1]
    return best[len(fixed_placements) :]


def _placement_summary(placement: Placement) -> dict[str, Any]:
    return {
        "componentName": placement.component_name,
        "role": placement.role,
        "x": placement.anchor_u,
        "y": placement.anchor_v,
        "thetaDegrees": placement.theta_degrees,
        "rotationQuarters": placement.rotation_quarters,
        "bounds": list(placement.bounds),
    }


def _align_transport_work_points_to_reach(
    placement: Placement,
    footprint: Footprint,
    semantic: ModuleSemantic | None,
    gantry: Placement,
    gantry_semantic: ModuleSemantic | None,
) -> Placement:
    if not semantic or not gantry_semantic:
        return placement
    work_points = [
        point
        for name, point in semantic.points.items()
        if name.lower().startswith("workposition") or name.lower().startswith("fiducial")
    ]
    region = (
        gantry_semantic.regions.get("dualValveReach")
        or gantry_semantic.regions.get("leftValveReach")
    )
    if not work_points or region is None:
        return placement
    target_u = gantry.anchor_u + (region.min_u + region.max_u) / 2.0
    target_u += float(semantic.parameters.get("workEnvelopeBiasU", 0.0))
    target_v = (
        gantry.anchor_v
        + (region.min_v + region.max_v) / 2.0
        + float(semantic.parameters.get("workEnvelopeBiasV", 0.0))
    )
    local_u = sum(point.u for point in work_points) / len(work_points)
    local_v = sum(point.v for point in work_points) / len(work_points)
    rotated_u, rotated_v = _rotate_local_point(local_u, local_v, placement.rotation_quarters)
    return _placement_at_anchor(
        footprint,
        placement.role,
        placement.rotation_quarters,
        target_u - rotated_u,
        target_v - rotated_v,
        placement.containment_relaxed,
    )


def _align_portal_process_region(
    placement: Placement,
    footprint: Footprint,
    semantic: ModuleSemantic | None,
    pass_through: list[Placement],
    semantics: dict[str, ModuleSemantic],
) -> Placement:
    if not semantic or "fieldOfView" not in semantic.regions:
        return placement
    target_points: list[tuple[float, float]] = []
    for target in pass_through:
        target_semantic = semantics.get(target.component_name)
        if not target_semantic:
            continue
        for name, point in target_semantic.points.items():
            if name.lower().startswith("workposition") or name.lower().startswith("fiducial"):
                local_u, local_v = _rotate_local_point(point.u, point.v, target.rotation_quarters)
                target_points.append((target.anchor_u + local_u, target.anchor_v + local_v))
    if not target_points:
        return placement
    target_u = sum(point[0] for point in target_points) / len(target_points)
    target_v = sum(point[1] for point in target_points) / len(target_points)
    target_u += float(semantic.parameters.get("sourceIndependentProcessRegionBiasU", 0.0))
    target_v += float(semantic.parameters.get("sourceIndependentProcessRegionBiasV", 0.0))
    region = semantic.regions["fieldOfView"]
    local_u = (region.min_u + region.max_u) / 2.0
    local_v = (region.min_v + region.max_v) / 2.0
    rotated_u, rotated_v = _rotate_local_point(local_u, local_v, placement.rotation_quarters)
    return _placement_at_anchor(
        footprint,
        placement.role,
        placement.rotation_quarters,
        target_u - rotated_u,
        target_v - rotated_v,
        placement.containment_relaxed,
    )


def _placement_at_anchor(
    item: Footprint,
    role: ComponentRole,
    quarters: int,
    anchor_u: float,
    anchor_v: float,
    containment_relaxed: bool = False,
) -> Placement:
    bounds = _translated_offsets(_rotated_offsets(item, quarters), anchor_u, anchor_v)
    return Placement(
        item.component_name,
        role,
        anchor_u,
        anchor_v,
        _normalize_angle(item.source_theta + quarters * 90.0),
        quarters,
        bounds,
        containment_relaxed,
    )


def _rotate_local_point(u: float, v: float, quarters: int) -> tuple[float, float]:
    radians = math.radians((quarters % 4) * 90.0)
    cosine, sine = math.cos(radians), math.sin(radians)
    return cosine * u - sine * v, sine * u + cosine * v


def _candidate_cursors(first: float, last: float, count: int = 31) -> tuple[float, ...]:
    if last < first - 1e-9:
        return ()
    if math.isclose(first, last, abs_tol=1e-9):
        return (first,)
    return tuple(first + (last - first) * index / (count - 1) for index in range(count))


def _candidate_process_feasible(
    candidate: Placement,
    placed: list[Placement],
    constraints: list[dict[str, Any]],
    semantics: dict[str, ModuleSemantic],
    footprints: dict[str, Footprint],
    roles: dict[str, str],
    long_axis: str,
) -> bool:
    validation = _candidate_process_validation(
        candidate,
        placed,
        constraints,
        semantics,
        footprints,
        roles,
        long_axis,
    )
    return bool(validation["hardFeasible"])


def _candidate_process_validation(
    candidate: Placement,
    placed: list[Placement],
    constraints: list[dict[str, Any]],
    semantics: dict[str, ModuleSemantic],
    footprints: dict[str, Footprint],
    roles: dict[str, str],
    long_axis: str,
) -> dict[str, Any]:
    trial = [*placed, candidate]
    present = {item.component_name for item in trial}
    applicable: list[dict[str, Any]] = []
    for constraint in constraints:
        if constraint["type"] == "lineOfSight":
            required = {
                str(constraint[field])
                for field in ("sourceComponent", "targetComponent")
                if constraint.get(field)
            }
            if not required.issubset(present):
                continue
            configured_blockers = constraint.get("blockerComponents")
            candidate_is_endpoint = candidate.component_name in required
            candidate_is_configured_blocker = bool(
                configured_blockers
                and candidate.component_name
                in {str(name) for name in configured_blockers}
            )
            candidate_can_be_implicit_blocker = bool(
                not configured_blockers
                and candidate.component_name not in required
                and roles.get(candidate.component_name) != "gantry"
                and not bool(
                    semantics.get(candidate.component_name)
                    and semantics[candidate.component_name].parameters.get(
                        "lineOfSightTransparent",
                        False,
                    )
                )
            )
            if not (
                candidate_is_endpoint
                or candidate_is_configured_blocker
                or candidate_can_be_implicit_blocker
            ):
                continue
            if not configured_blockers:
                applicable.append(constraint)
                continue
            incremental = dict(constraint)
            incremental["blockerComponents"] = [
                str(name) for name in configured_blockers if str(name) in present
            ]
            applicable.append(incremental)
            continue
        involved = _constraint_component_names(constraint)
        if candidate.component_name not in involved:
            continue
        if involved.issubset(present):
            applicable.append(constraint)
    if not applicable:
        return {
            "success": True,
            "hardFeasible": True,
            "constraintCount": 0,
            "passedCount": 0,
            "hardFailureCount": 0,
            "softFailureCount": 0,
            "diagnostics": [],
        }
    return evaluate_process_constraints(
        applicable,
        semantics,
        footprints,
        trial,
        roles,
        long_axis,
    )


def _constraint_component_names(constraint: dict[str, Any]) -> set[str]:
    fields_by_type = {
        "pointDistance": ("sourceComponent", "targetComponent"),
        "pointInRegion": ("pointComponent", "regionComponent"),
        "sameSide": ("component", "referenceComponent"),
        "moduleClearance": ("firstComponent", "secondComponent"),
        "relativeAnchorWindow": ("component", "referenceComponent"),
        "lineOfSight": ("sourceComponent", "targetComponent"),
        "directedPointing": ("sourceComponent", "targetComponent"),
    }
    fields = fields_by_type.get(str(constraint.get("type")), ())
    names = {str(constraint[field]) for field in fields if constraint.get(field)}
    names.update(str(item) for item in constraint.get("blockerComponents") or [])
    return names


def _semantic_projected_overlap_pairs(
    semantics: dict[str, ModuleSemantic],
    roles: dict[str, str],
) -> set[frozenset[str]]:
    transports = [name for name, role in roles.items() if role == "transport"]
    pairs: set[frozenset[str]] = set()
    for name, semantic in semantics.items():
        if not bool(
            semantic.parameters.get("allowTransportProjectionOverlap", False)
            or semantic.parameters.get(
                "resolveTransportProjectionWithInteractionEnvelope", False
            )
        ):
            continue
        for transport_name in transports:
            if name != transport_name:
                pairs.add(frozenset((name, transport_name)))
    cluster_members: dict[str, list[str]] = {}
    for name, semantic in semantics.items():
        cluster_id = str(semantic.parameters.get("serviceClusterId") or "").strip()
        if not cluster_id or not semantic.parameters.get(
            "allowServiceClusterProjectionOverlap", False
        ):
            continue
        cluster_members.setdefault(cluster_id, []).append(name)
    for names in cluster_members.values():
        for index, first_name in enumerate(names):
            for second_name in names[index + 1 :]:
                pairs.add(frozenset((first_name, second_name)))
    semantic_names = tuple(semantics)
    for index, first_name in enumerate(semantic_names):
        for second_name in semantic_names[index + 1 :]:
            if bool(
                semantics[first_name].parameters.get("useOccupancyBoxesForClearance", False)
                or semantics[second_name].parameters.get("useOccupancyBoxesForClearance", False)
            ):
                # The coarse projected-overlap validator must defer these pairs to
                # the height-aware multi-box interaction validator.
                pairs.add(frozenset((first_name, second_name)))
    canonical = {name.lower(): name for name in semantics}
    for name, semantic in semantics.items():
        configured = semantic.parameters.get("allowProjectedOverlapWith", [])
        if isinstance(configured, str):
            configured = [configured]
        for requested_name in configured:
            other_name = canonical.get(str(requested_name).strip().lower())
            if other_name and other_name != name:
                pairs.add(frozenset((name, other_name)))
    return pairs


def _post_solve_projected_overlap_pairs(
    semantics: dict[str, ModuleSemantic],
) -> set[frozenset[str]]:
    pairs: set[frozenset[str]] = set()
    canonical = {name.lower(): name for name in semantics}
    for name, semantic in semantics.items():
        configured = semantic.parameters.get("allowPostSolveProjectedOverlapWith", [])
        if isinstance(configured, str):
            configured = [configured]
        for requested_name in configured:
            other_name = canonical.get(str(requested_name).strip().lower())
            if other_name and other_name != name:
                pairs.add(frozenset((name, other_name)))
    return pairs


def _candidate_has_disallowed_overlap(
    candidate: Placement,
    others: list[Placement],
    clearance: float,
    portal_pass_through: dict[str, tuple[str, ...]],
    allowed_overlap_pairs: set[frozenset[str]],
) -> bool:
    return any(
        _rectangles_touch_or_overlap(candidate.bounds, other.bounds, clearance)
        and not _is_allowed_portal_overlap(
            candidate.component_name,
            other.component_name,
            portal_pass_through,
        )
        and frozenset((candidate.component_name, other.component_name)) not in allowed_overlap_pairs
        for other in others
    )


def _relative_anchor_window_target_distance(
    candidate: Placement,
    placements: list[Placement],
    constraints: list[dict[str, Any]],
) -> float:
    """Return distance from active relative-window center targets.

    A hard relative process window is a feasibility range; either hard or soft
    windows can also encode a calibrated nominal relation. Candidate generation
    injects reachable centers, and this ordering term keeps candidates near the
    nominal pose without turning a soft preference into a hidden hard gate.
    """
    placed_by_name = {placement.component_name: placement for placement in placements}
    distances: list[float] = []
    for constraint in constraints:
        if constraint.get("type") != "relativeAnchorWindow":
            continue
        component_name = str(constraint.get("component") or "")
        reference_name = str(constraint.get("referenceComponent") or "")
        midpoint_u = (
            float(constraint["minDeltaU"]) + float(constraint["maxDeltaU"])
        ) / 2.0
        midpoint_v = (
            float(constraint["minDeltaV"]) + float(constraint["maxDeltaV"])
        ) / 2.0
        if candidate.component_name == component_name:
            reference = placed_by_name.get(reference_name)
            if reference is None:
                continue
            target = (
                reference.anchor_u + midpoint_u,
                reference.anchor_v + midpoint_v,
            )
        elif candidate.component_name == reference_name:
            component = placed_by_name.get(component_name)
            if component is None:
                continue
            target = (
                component.anchor_u - midpoint_u,
                component.anchor_v - midpoint_v,
            )
        else:
            continue
        distances.append(math.dist((candidate.anchor_u, candidate.anchor_v), target))
    return sum(distances)


def _relative_anchor_window_anchors(
    component_name: str,
    constraints: list[dict[str, Any]],
    placements: list[Placement],
) -> tuple[tuple[float, float], ...]:
    """Return exact edge/center anchors for active relative process windows.

    Portal candidates use a geometry-specific offset grid and therefore do not
    pass through ``_point_in_region_anchor_candidates``. Without this helper a
    narrow CCD/transport relative window can be feasible yet absent from the
    portal grid. Intersect active windows and emit a bounded 3 x 3 set.
    """
    placed_by_name = {placement.component_name: placement for placement in placements}
    intervals: list[tuple[float, float, float, float]] = []
    for constraint in constraints:
        if (
            constraint.get("type") != "relativeAnchorWindow"
            or not bool(constraint.get("hard", True))
        ):
            continue
        constrained_name = str(constraint.get("component") or "")
        reference_name = str(constraint.get("referenceComponent") or "")
        if component_name == constrained_name:
            reference = placed_by_name.get(reference_name)
            if reference is None:
                continue
            intervals.append(
                (
                    reference.anchor_u + float(constraint["minDeltaU"]),
                    reference.anchor_v + float(constraint["minDeltaV"]),
                    reference.anchor_u + float(constraint["maxDeltaU"]),
                    reference.anchor_v + float(constraint["maxDeltaV"]),
                )
            )
        elif component_name == reference_name:
            constrained = placed_by_name.get(constrained_name)
            if constrained is None:
                continue
            intervals.append(
                (
                    constrained.anchor_u - float(constraint["maxDeltaU"]),
                    constrained.anchor_v - float(constraint["maxDeltaV"]),
                    constrained.anchor_u - float(constraint["minDeltaU"]),
                    constrained.anchor_v - float(constraint["minDeltaV"]),
                )
            )
    if not intervals:
        return ()
    min_u = max(value[0] for value in intervals)
    min_v = max(value[1] for value in intervals)
    max_u = min(value[2] for value in intervals)
    max_v = min(value[3] for value in intervals)
    if min_u > max_u + 1e-9 or min_v > max_v + 1e-9:
        return ()
    u_values = (min_u, (min_u + max_u) / 2.0, max_u)
    v_values = (min_v, (min_v + max_v) / 2.0, max_v)
    return tuple(dict.fromkeys((u, v) for u in u_values for v in v_values))


def _point_in_region_anchor_candidates(
    item: Footprint,
    quarters: int,
    constraints: list[dict[str, Any]],
    semantics: dict[str, ModuleSemantic],
    placements: list[Placement],
    portal_pass_through: dict[str, tuple[str, ...]],
    clearance: float,
    source_position_independent: bool = False,
    grid_count: int = 11,
) -> tuple[tuple[float, float], ...]:
    placed_by_name = {placement.component_name: placement for placement in placements}
    intervals: list[tuple[float, float, float, float]] = []
    relative_target_anchors: list[tuple[float, float]] = []
    point_semantic = semantics.get(item.component_name)
    if point_semantic is None:
        return ()
    for constraint in constraints:
        kind = constraint.get("type")
        hard = bool(constraint.get("hard", True))
        if kind == "relativeAnchorWindow":
            component_name = str(constraint.get("component") or "")
            reference_name = str(constraint.get("referenceComponent") or "")
            if item.component_name == component_name:
                reference = placed_by_name.get(reference_name)
                if reference is not None:
                    midpoint_u = (
                        float(constraint["minDeltaU"])
                        + float(constraint["maxDeltaU"])
                    ) / 2.0
                    midpoint_v = (
                        float(constraint["minDeltaV"])
                        + float(constraint["maxDeltaV"])
                    ) / 2.0
                    if hard:
                        intervals.append(
                            (
                                reference.anchor_u + float(constraint["minDeltaU"]),
                                reference.anchor_v + float(constraint["minDeltaV"]),
                                reference.anchor_u + float(constraint["maxDeltaU"]),
                                reference.anchor_v + float(constraint["maxDeltaV"]),
                            )
                        )
                    relative_target_anchors.append(
                        (
                            reference.anchor_u + midpoint_u,
                            reference.anchor_v + midpoint_v,
                        )
                    )
            elif item.component_name == reference_name:
                component = placed_by_name.get(component_name)
                if component is not None:
                    midpoint_u = (
                        float(constraint["minDeltaU"])
                        + float(constraint["maxDeltaU"])
                    ) / 2.0
                    midpoint_v = (
                        float(constraint["minDeltaV"])
                        + float(constraint["maxDeltaV"])
                    ) / 2.0
                    if hard:
                        intervals.append(
                            (
                                component.anchor_u - float(constraint["maxDeltaU"]),
                                component.anchor_v - float(constraint["maxDeltaV"]),
                                component.anchor_u - float(constraint["minDeltaU"]),
                                component.anchor_v - float(constraint["minDeltaV"]),
                            )
                        )
                    relative_target_anchors.append(
                        (
                            component.anchor_u - midpoint_u,
                            component.anchor_v - midpoint_v,
                        )
                    )
            continue
        if kind == "pointDistance":
            if constraint.get("sourceComponent") == item.component_name:
                candidate_point_name = str(constraint.get("sourcePoint") or "")
                other_component = str(constraint.get("targetComponent") or "")
                other_point_name = str(constraint.get("targetPoint") or "")
            elif constraint.get("targetComponent") == item.component_name:
                candidate_point_name = str(constraint.get("targetPoint") or "")
                other_component = str(constraint.get("sourceComponent") or "")
                other_point_name = str(constraint.get("sourcePoint") or "")
            else:
                continue
            other_placement = placed_by_name.get(other_component)
            other_semantic = semantics.get(other_component)
            candidate_point = point_semantic.points.get(candidate_point_name)
            other_point = other_semantic.points.get(other_point_name) if other_semantic else None
            if other_placement is None or candidate_point is None or other_point is None:
                continue
            other_u, other_v = _rotate_local_point(
                other_point.u,
                other_point.v,
                other_placement.rotation_quarters,
            )
            target_u = other_placement.anchor_u + other_u
            target_v = other_placement.anchor_v + other_v
            point_u, point_v = _rotate_local_point(
                candidate_point.u,
                candidate_point.v,
                quarters,
            )
            if not hard:
                relative_target_anchors.append(
                    (target_u - point_u, target_v - point_v)
                )
                continue
            max_distance = float(constraint.get("maxDistanceMeters") or 0.0)
            source_height = constraint.get("sourceHeightMeters")
            target_height = constraint.get("targetHeightMeters")
            if source_height is None and target_height is None:
                candidate_height = semantic_point_height_meters(
                    point_semantic,
                    candidate_point_name,
                )
                other_height = semantic_point_height_meters(
                    other_semantic,
                    other_point_name,
                )
            elif source_height is None or target_height is None:
                raise ConstraintLayoutError(
                    f"Point-distance constraint '{constraint.get('id')}' requires both endpoint heights."
                )
            elif constraint.get("sourceComponent") == item.component_name:
                candidate_height = float(source_height)
                other_height = float(target_height)
            else:
                candidate_height = float(target_height)
                other_height = float(source_height)
            if candidate_height is not None and other_height is not None:
                vertical_distance = abs(candidate_height - other_height)
                if vertical_distance > max_distance + 1e-9:
                    return ()
                max_distance = math.sqrt(
                    max(0.0, max_distance * max_distance - vertical_distance * vertical_distance)
                )
            intervals.append(
                (
                    target_u - max_distance - point_u,
                    target_v - max_distance - point_v,
                    target_u + max_distance - point_u,
                    target_v + max_distance - point_v,
                )
            )
            continue
        if kind != "pointInRegion" or constraint.get("pointComponent") != item.component_name:
            continue
        region_component = str(constraint.get("regionComponent") or "")
        region_placement = placed_by_name.get(region_component)
        region_semantic = semantics.get(region_component)
        point = point_semantic.points.get(str(constraint.get("point") or ""))
        region = region_semantic.regions.get(str(constraint.get("region") or "")) if region_semantic else None
        if region_placement is None or point is None or region is None:
            continue
        world_region = _semantic_region_bounds(region, region_placement)
        point_u, point_v = _rotate_local_point(point.u, point.v, quarters)
        if not hard:
            relative_target_anchors.append(
                (
                    (world_region[0] + world_region[2]) / 2.0 - point_u,
                    (world_region[1] + world_region[3]) / 2.0 - point_v,
                )
            )
            continue
        intervals.append(
            (
                world_region[0] - point_u,
                world_region[1] - point_v,
                world_region[2] - point_u,
                world_region[3] - point_v,
            )
        )
    placed_by_name = {placement.component_name: placement for placement in placements}
    for portal_name, pass_names in portal_pass_through.items():
        if item.component_name not in pass_names:
            continue
        portal_placement = placed_by_name.get(portal_name)
        portal_semantic = semantics.get(portal_name)
        if portal_placement is None or portal_semantic is None:
            continue
        pass_modes = portal_semantic.parameters.get("portalPassModeByComponent", {})
        if str(pass_modes.get(item.component_name) or "") != "namedChannel":
            continue
        channel_names = portal_semantic.parameters.get("portalChannelByComponent", {})
        channels = portal_semantic.parameters.get("passageChannelsLocal", {})
        channel_name = str(channel_names.get(item.component_name) or "").strip()
        raw_channel = channels.get(channel_name) if isinstance(channels, dict) else None
        if not channel_name or not isinstance(raw_channel, dict):
            raise ConstraintLayoutError(
                f"Portal '{portal_name}' must define a named passage channel for '{item.component_name}'."
            )
        channel = _named_local_envelope(
            portal_placement,
            raw_channel,
            f"semanticPassageChannel:{channel_name}",
        )
        local_candidate = _placement_at_anchor(item, "functional", quarters, 0.0, 0.0)
        local_bodies = _channel_body_envelopes(
            local_candidate,
            item,
            point_semantic,
        )
        local_union = _union_envelopes(local_bodies)
        if not all(
            body["heightRangeMeters"][0]
            >= channel["heightRangeMeters"][0] + clearance - 1e-9
            and body["heightRangeMeters"][1]
            <= channel["heightRangeMeters"][1] - clearance + 1e-9
            for body in local_bodies
        ):
            return ()
        intervals.append(
            (
                channel["bounds"][0] + clearance - local_union["bounds"][0],
                channel["bounds"][1] + clearance - local_union["bounds"][1],
                channel["bounds"][2] - clearance - local_union["bounds"][2],
                channel["bounds"][3] - clearance - local_union["bounds"][3],
            )
        )
    if not intervals:
        return ()
    min_u = max(interval[0] for interval in intervals)
    min_v = max(interval[1] for interval in intervals)
    max_u = min(interval[2] for interval in intervals)
    max_v = min(interval[3] for interval in intervals)
    if min_u > max_u + 1e-9 or min_v > max_v + 1e-9:
        return ()
    interval_center = ((min_u + max_u) / 2.0, (min_v + max_v) / 2.0)
    target_center = (
        min(max(interval_center[0] + float(point_semantic.parameters.get("sourceIndependentAnchorBiasU", 0.0)), min_u), max_u),
        min(max(interval_center[1] + float(point_semantic.parameters.get("sourceIndependentAnchorBiasV", 0.0)), min_v), max_v),
    )
    u_seed_values = [*_grid_values(min_u, max_u, grid_count), target_center[0]]
    v_seed_values = [*_grid_values(min_v, max_v, grid_count), target_center[1]]
    local_refinements = point_semantic.parameters.get(
        "candidateLocalRefinementMeters", []
    )
    if isinstance(local_refinements, (int, float)):
        local_refinements = [local_refinements]
    if not isinstance(local_refinements, list):
        raise ConstraintLayoutError(
            f"Functional component '{item.component_name}' candidateLocalRefinementMeters "
            "must be a number or an array of positive numbers."
        )
    for raw_refinement in local_refinements:
        refinement = float(raw_refinement)
        if not math.isfinite(refinement) or refinement <= 0 or refinement > 0.05:
            raise ConstraintLayoutError(
                f"Functional component '{item.component_name}' candidateLocalRefinementMeters "
                "values must be greater than 0 and no more than 0.05 m."
            )
        for sign in (-1.0, 1.0):
            refined_u = target_center[0] + sign * refinement
            refined_v = target_center[1] + sign * refinement
            if min_u - 1e-9 <= refined_u <= max_u + 1e-9:
                u_seed_values.append(min(max(refined_u, min_u), max_u))
            if min_v - 1e-9 <= refined_v <= max_v + 1e-9:
                v_seed_values.append(min(max(refined_v, min_v), max_v))
    for target_u, target_v in relative_target_anchors:
        if (
            min_u - 1e-9 <= target_u <= max_u + 1e-9
            and min_v - 1e-9 <= target_v <= max_v + 1e-9
        ):
            u_seed_values.append(min(max(target_u, min_u), max_u))
            v_seed_values.append(min(max(target_v, min_v), max_v))
    if source_position_independent:
        gantry_placement = next(
            (placement for placement in placements if placement.role == "gantry"),
            None,
        )
        if gantry_placement is not None:
            offsets = _rotated_offsets(item, quarters)
            # Uniform grids can miss a narrow feasible strip next to the gantry
            # inset. Add exact event anchors where the measured module footprint
            # touches each safe inner boundary.
            for value in (
                gantry_placement.bounds[0] + clearance - offsets[0],
                gantry_placement.bounds[2] - clearance - offsets[2],
            ):
                if min_u - 1e-9 <= value <= max_u + 1e-9:
                    u_seed_values.append(min(max(value, min_u), max_u))
            for value in (
                gantry_placement.bounds[1] + clearance - offsets[1],
                gantry_placement.bounds[3] - clearance - offsets[3],
            ):
                if min_v - 1e-9 <= value <= max_v + 1e-9:
                    v_seed_values.append(min(max(value, min_v), max_v))
    u_values = tuple(sorted(set(u_seed_values)))
    v_values = tuple(sorted(set(v_seed_values)))
    candidates = [(u, v) for u in u_values for v in v_values]
    if source_position_independent:
        gantry_placement = next(
            (placement for placement in placements if placement.role == "gantry"),
            None,
        )
        cluster_id = str(point_semantic.parameters.get("serviceClusterId") or "").strip()
        cluster_placements = [
            placement
            for placement in placements
            if cluster_id
            and str(
                (semantics.get(placement.component_name).parameters if semantics.get(placement.component_name) else {}).get(
                    "serviceClusterId"
                )
                or ""
            ).strip()
            == cluster_id
        ]

        def source_independent_key(value: tuple[float, float]) -> tuple[float, float, float, float, float]:
            candidate = _placement_at_anchor(
                item,
                "functional",
                quarters,
                value[0],
                value[1],
            )
            cluster_distance = (
                min(_rectangle_distance(candidate.bounds, peer.bounds) for peer in cluster_placements)
                if cluster_placements
                else 0.0
            )
            gantry_rank = (
                -_overlap_ratio(candidate.bounds, gantry_placement.bounds)
                if gantry_placement
                else 0.0
            )
            target_distance = math.dist(value, target_center)
            if bool(point_semantic.parameters.get("prioritizeSourceIndependentAnchorBias")):
                return gantry_rank, target_distance, cluster_distance, value[0], value[1]
            return gantry_rank, cluster_distance, target_distance, value[0], value[1]

        candidates.sort(
            key=source_independent_key
        )
    else:
        candidates.sort(key=lambda value: math.dist(value, (item.anchor_u, item.anchor_v)))
    return tuple(candidates)


def _semantic_region_bounds(region: Any, placement: Placement) -> tuple[float, float, float, float]:
    corners = [
        _rotate_local_point(u, v, placement.rotation_quarters)
        for u in (region.min_u, region.max_u)
        for v in (region.min_v, region.max_v)
    ]
    return (
        placement.anchor_u + min(point[0] for point in corners),
        placement.anchor_v + min(point[1] for point in corners),
        placement.anchor_u + max(point[0] for point in corners),
        placement.anchor_v + max(point[1] for point in corners),
    )


def _portal_long_axis_anchor_interval(
    portal_placement: Placement,
    opening_region: Any,
    passed_placement: Placement,
    raw_pass_bodies: Any,
    long_axis: str,
    clearance: float,
) -> tuple[float, float] | None:
    """Return portal-anchor limits required by localized pass-through bodies.

    A rail can legitimately extend through both ends of a portal, while a
    localized motor or bracket cannot intersect either longitudinal wall.  A
    body opts into this stronger rule with ``requireLongAxisContainment``.
    """
    if not isinstance(raw_pass_bodies, list):
        return None
    constrained = [
        raw
        for raw in raw_pass_bodies
        if isinstance(raw, dict) and bool(raw.get("requireLongAxisContainment"))
    ]
    if not constrained:
        return None

    opening_bounds = _semantic_region_bounds(opening_region, portal_placement)
    portal_anchor = (
        portal_placement.anchor_u if long_axis == "u" else portal_placement.anchor_v
    )
    opening_offset_min = _axis_min(opening_bounds, long_axis) - portal_anchor
    opening_offset_max = _axis_max(opening_bounds, long_axis) - portal_anchor
    minimum_anchor = -math.inf
    maximum_anchor = math.inf
    for index, raw in enumerate(constrained):
        body = _named_local_envelope(
            passed_placement,
            raw,
            f"measuredPortalPassBody:{index + 1}",
        )
        minimum_anchor = max(
            minimum_anchor,
            _axis_max(body["bounds"], long_axis) + clearance - opening_offset_max,
        )
        maximum_anchor = min(
            maximum_anchor,
            _axis_min(body["bounds"], long_axis) - clearance - opening_offset_min,
        )
    return minimum_anchor, maximum_anchor


def _grid_values(minimum: float, maximum: float, count: int) -> tuple[float, ...]:
    if math.isclose(minimum, maximum, abs_tol=1e-9):
        return (minimum,)
    center = (minimum + maximum) / 2.0
    values = [center]
    for index in range(count):
        values.append(minimum + (maximum - minimum) * index / max(1, count - 1))
    return tuple(dict.fromkeys(values))


def _placement_at_source(item: Footprint, role: ComponentRole) -> Placement:
    bounds = _translated_offsets(_rotated_offsets(item, 0), item.anchor_u, item.anchor_v)
    return Placement(item.component_name, role, item.anchor_u, item.anchor_v, item.source_theta, 0, bounds)


def _place_by_bounds_center(
    item: Footprint,
    role: ComponentRole,
    quarters: int,
    long_axis: str,
    desired_long: float,
    desired_short: float,
    containment_relaxed: bool = False,
) -> Placement:
    offsets = _rotated_offsets(item, quarters)
    offset_center_u, offset_center_v = _center(offsets)
    desired_u = desired_long if long_axis == "u" else desired_short
    desired_v = desired_short if long_axis == "u" else desired_long
    anchor_u = desired_u - offset_center_u
    anchor_v = desired_v - offset_center_v
    bounds = _translated_offsets(offsets, anchor_u, anchor_v)
    return Placement(
        item.component_name,
        role,
        anchor_u,
        anchor_v,
        _normalize_angle(item.source_theta + quarters * 90.0),
        quarters,
        bounds,
        containment_relaxed,
    )


def _best_long_variant(
    item: Footprint,
    long_axis: str,
    allow_rotation: bool,
    semantic: ModuleSemantic | None = None,
) -> tuple[int, tuple[float, float, float, float]]:
    variants = [
        (quarters, _rotated_offsets(item, quarters))
        for quarters in _rotation_candidates(item, allow_rotation, semantic)
    ]
    return max(variants, key=lambda entry: _axis_size(entry[1], long_axis))


def _rotation_candidates(
    item: Footprint,
    allow_rotation: bool,
    semantic: ModuleSemantic | None,
) -> tuple[int, ...]:
    candidates = semantic.allowed_rotation_quarters if semantic else (0, 1)
    if not allow_rotation:
        candidates = tuple(item for item in candidates if item == 0)
    # 180/270 degree candidates have the same AABB as 0/90 but may encode a required
    # process-facing orientation, so retain them when explicitly configured.
    if not semantic:
        candidates = tuple(item for item in candidates if item in (0, 1))
    if not candidates:
        configured = [item * 90 for item in semantic.allowed_rotation_quarters] if semantic else [0, 90]
        raise ConstraintLayoutError(
            f"Component '{item.component_name}' has no allowed rotation candidate; "
            f"allowRotation={allow_rotation}, configured={configured}."
        )
    return candidates


def _semantic_order(semantic: ModuleSemantic | None) -> int:
    if semantic is None:
        return 50
    configured_priority = semantic.parameters.get("placementPriority")
    if configured_priority is not None:
        return int(configured_priority)
    return {
        "ccd": 10,
        "scanner": 20,
        "calibration": 30,
        "cleaning": 31,
        "weighing": 32,
    }.get(semantic.module_type, 50)


def _band_order(semantic: ModuleSemantic | None, bands: list[list[float]]) -> list[int]:
    if semantic and semantic.preferred_side == "low":
        return [0, 1]
    if semantic and semantic.preferred_side == "high":
        return [1, 0]
    return sorted(range(2), key=lambda index: bands[index][2])


def _rotated_offsets(item: Footprint, quarters: int) -> tuple[float, float, float, float]:
    radians = math.radians((quarters % 4) * 90.0)
    cosine, sine = math.cos(radians), math.sin(radians)
    corners = [
        (u, v)
        for u in (item.min_u_offset, item.max_u_offset)
        for v in (item.min_v_offset, item.max_v_offset)
    ]
    rotated = [(cosine * u - sine * v, sine * u + cosine * v) for u, v in corners]
    return (
        min(point[0] for point in rotated),
        min(point[1] for point in rotated),
        max(point[0] for point in rotated),
        max(point[1] for point in rotated),
    )


def _source_bounds(item: Footprint) -> tuple[float, float, float, float]:
    return _translated_offsets(_rotated_offsets(item, 0), item.anchor_u, item.anchor_v)


def _translated_offsets(bounds: tuple[float, float, float, float], u: float, v: float) -> tuple[float, float, float, float]:
    return bounds[0] + u, bounds[1] + v, bounds[2] + u, bounds[3] + v


def _translate_placement(item: Placement, delta_u: float, delta_v: float) -> Placement:
    return Placement(
        component_name=item.component_name,
        role=item.role,
        anchor_u=item.anchor_u + delta_u,
        anchor_v=item.anchor_v + delta_v,
        theta_degrees=item.theta_degrees,
        rotation_quarters=item.rotation_quarters,
        bounds=_translated_offsets(item.bounds, delta_u, delta_v),
        containment_relaxed=item.containment_relaxed,
    )


def _validate_gantry_reach_regions(
    gantry: Placement,
    semantic: ModuleSemantic | None,
    *,
    require_contained: bool,
) -> dict[str, Any]:
    diagnostics: list[dict[str, Any]] = []
    if semantic:
        for name in ("dualValveReach", "leftValveReach", "rightValveReach"):
            region = semantic.regions.get(name)
            if region is None:
                continue
            bounds = _semantic_region_bounds(region, gantry)
            overlap_ratio = _overlap_ratio(bounds, gantry.bounds)
            contained = _contains_bounds(gantry.bounds, bounds)
            diagnostics.append(
                {
                    "region": name,
                    "success": contained or not require_contained,
                    "containedInGantry": contained,
                    "overlapRatio": overlap_ratio,
                    "regionBounds": list(bounds),
                    "gantryBounds": list(gantry.bounds),
                }
            )
    failures = [item for item in diagnostics if not item["success"]]
    message = (
        "Configured valve reach extends outside the gantry envelope: "
        + "; ".join(
            f"{item['region']} overlap={item['overlapRatio']:.3f}, "
            f"reach={item['regionBounds']}, gantry={item['gantryBounds']}"
            for item in failures
        )
        if failures
        else "All configured valve reach regions are contained in the gantry envelope."
    )
    return {
        "success": not failures,
        "hardFeasible": not failures,
        "requireContained": require_contained,
        "diagnostics": diagnostics,
        "message": message,
    }


def _evaluate_spatial_hard_constraints(
    placements: list[Placement],
    footprints: dict[str, Footprint],
    roles: dict[str, str],
    semantics: dict[str, ModuleSemantic],
    gantry_name: str,
    portal_pass_through: dict[str, tuple[str, ...]],
    *,
    minimum_transport_gantry_overlap_ratio: float,
    minimum_portal_gantry_overlap_ratio: float,
    minimum_functional_gantry_overlap_ratio: float,
    minimum_functional_gantry_boundary_clearance_meters: float,
    maximum_transport_gantry_center_offset_meters: float | None,
    maximum_portal_gantry_center_offset_meters: float | None,
    maximum_portal_gantry_overhang_meters: float | None,
) -> dict[str, Any]:
    by_name = {item.component_name: item for item in placements}
    gantry = by_name[gantry_name]
    diagnostics: list[dict[str, Any]] = []
    for placement in placements:
        if placement.component_name == gantry_name or placement.role == "glue":
            continue
        semantic_minimum = minimum_functional_gantry_overlap_ratio
        if placement.role == "transport":
            semantic_minimum = minimum_transport_gantry_overlap_ratio
            constraint_type = "transportGantryOverlap"
        elif placement.component_name in portal_pass_through:
            semantic_minimum = minimum_portal_gantry_overlap_ratio
            constraint_type = "portalGantryOverlap"
        else:
            semantic = semantics.get(placement.component_name)
            if semantic and "minimumGantryOverlapRatio" in semantic.parameters:
                semantic_minimum = float(semantic.parameters["minimumGantryOverlapRatio"])
            constraint_type = "functionalGantryOverlap"
        ratio = _overlap_ratio(placement.bounds, gantry.bounds)
        diagnostics.append(
            {
                "id": f"spatial-{constraint_type}-{placement.component_name}",
                "type": constraint_type,
                "componentName": placement.component_name,
                "success": ratio >= semantic_minimum - 1e-9,
                "overlapRatio": ratio,
                "minimumOverlapRatio": semantic_minimum,
                "componentBounds": list(placement.bounds),
                "gantryBounds": list(gantry.bounds),
            }
        )
        effective_boundary_clearance = minimum_functional_gantry_boundary_clearance_meters
        if placement.role == "functional" and placement.component_name not in portal_pass_through:
            semantic = semantics.get(placement.component_name)
            if semantic and "minimumGantryBoundaryClearanceMeters" in semantic.parameters:
                effective_boundary_clearance = float(
                    semantic.parameters["minimumGantryBoundaryClearanceMeters"]
                )
            if not math.isfinite(effective_boundary_clearance) or effective_boundary_clearance < 0:
                raise ConstraintLayoutError(
                    f"Functional component '{placement.component_name}' "
                    "minimumGantryBoundaryClearanceMeters must be a finite non-negative number."
                )
        if (
            placement.role == "functional"
            and placement.component_name not in portal_pass_through
            and effective_boundary_clearance > 0
        ):
            inset = _inset_bounds(
                gantry.bounds,
                effective_boundary_clearance,
                effective_boundary_clearance,
                "u" if _width(gantry.bounds) >= _height(gantry.bounds) else "v",
            )
            contained = _contains_bounds(inset, placement.bounds)
            diagnostics.append(
                {
                    "id": f"spatial-functionalGantryBoundaryClearance-{placement.component_name}",
                    "type": "functionalGantryBoundaryClearance",
                    "componentName": placement.component_name,
                    "success": contained,
                    "minimumClearanceMeters": effective_boundary_clearance,
                    "componentBounds": list(placement.bounds),
                    "allowedBounds": list(inset),
                }
            )
    if maximum_transport_gantry_center_offset_meters is not None:
        long_axis = "u" if _width(gantry.bounds) >= _height(gantry.bounds) else "v"
        short_axis = _other_axis(long_axis)
        for placement in placements:
            if placement.role != "transport":
                continue
            offset = abs(
                _axis_center(placement.bounds, short_axis)
                - _axis_center(gantry.bounds, short_axis)
            )
            diagnostics.append(
                {
                    "id": f"spatial-transportGantryCenterOffset-{placement.component_name}",
                    "type": "transportGantryCenterOffset",
                    "componentName": placement.component_name,
                    "success": offset <= maximum_transport_gantry_center_offset_meters + 1e-9,
                    "centerOffsetMeters": offset,
                    "maximumCenterOffsetMeters": maximum_transport_gantry_center_offset_meters,
                }
            )
    if maximum_portal_gantry_center_offset_meters is not None or maximum_portal_gantry_overhang_meters is not None:
        long_axis = "u" if _width(gantry.bounds) >= _height(gantry.bounds) else "v"
        short_axis = _other_axis(long_axis)
        for placement in placements:
            if placement.component_name not in portal_pass_through:
                continue
            if maximum_portal_gantry_center_offset_meters is not None:
                offset = abs(
                    _axis_center(placement.bounds, short_axis)
                    - _axis_center(gantry.bounds, short_axis)
                )
                diagnostics.append(
                    {
                        "id": f"spatial-portalGantryCenterOffset-{placement.component_name}",
                        "type": "portalGantryCenterOffset",
                        "componentName": placement.component_name,
                        "success": offset <= maximum_portal_gantry_center_offset_meters + 1e-9,
                        "centerOffsetMeters": offset,
                        "maximumCenterOffsetMeters": maximum_portal_gantry_center_offset_meters,
                        "axis": short_axis,
                    }
                )
            if maximum_portal_gantry_overhang_meters is not None:
                overhang = _bounds_overhang(placement.bounds, gantry.bounds)
                maximum_overhang = max(overhang.values())
                diagnostics.append(
                    {
                        "id": f"spatial-portalGantryOverhang-{placement.component_name}",
                        "type": "portalGantryOverhang",
                        "componentName": placement.component_name,
                        "success": maximum_overhang <= maximum_portal_gantry_overhang_meters + 1e-9,
                        "overhangMeters": overhang,
                        "maximumObservedOverhangMeters": maximum_overhang,
                        "maximumAllowedOverhangMeters": maximum_portal_gantry_overhang_meters,
                    }
                )
    failures = [item for item in diagnostics if not item["success"]]
    message = (
        "Spatial hard constraints failed: "
        + "; ".join(
            f"{item['componentName']} {item['type']} failed"
            for item in failures
        )
        if failures
        else "All transport, portal, and functional gantry-overlap constraints passed."
    )
    return {
        "success": not failures,
        "hardFeasible": not failures,
        "constraintCount": len(diagnostics),
        "passedCount": len(diagnostics) - len(failures),
        "hardFailureCount": len(failures),
        "diagnostics": diagnostics,
        "message": message,
    }


def _validate_placements(
    placements: list[Placement],
    gantry_name: str,
    portal_pass_through: dict[str, tuple[str, ...]] | None = None,
    semantic_overlap_pairs: set[frozenset[str]] | None = None,
    explicit_overlap_pairs: set[frozenset[str]] | None = None,
) -> dict[str, Any]:
    portal_pass_through = portal_pass_through or {}
    semantic_overlap_pairs = semantic_overlap_pairs or set()
    explicit_overlap_pairs = explicit_overlap_pairs or set()
    overlap_pairs: list[list[str]] = []
    allowed_overlap_pairs: list[list[str]] = []
    explicit_allowed_overlap_pairs: list[list[str]] = []
    conditional_interaction_review_pairs: list[list[str]] = []
    for index, first in enumerate(placements):
        for second in placements[index + 1 :]:
            if gantry_name in (first.component_name, second.component_name):
                continue
            if _intersection_area(first.bounds, second.bounds) <= 1e-10:
                continue
            if _is_allowed_portal_overlap(
                first.component_name,
                second.component_name,
                portal_pass_through,
            ) or frozenset((first.component_name, second.component_name)) in semantic_overlap_pairs:
                pair = [first.component_name, second.component_name]
                allowed_overlap_pairs.append(pair)
                if frozenset(pair) in explicit_overlap_pairs:
                    explicit_allowed_overlap_pairs.append(pair)
                else:
                    conditional_interaction_review_pairs.append(pair)
            else:
                overlap_pairs.append([first.component_name, second.component_name])
    return {
        "success": not overlap_pairs,
        "overlapPairs": overlap_pairs,
        "allowedAabbOverlapPairs": allowed_overlap_pairs,
        "explicitAllowedAabbOverlapPairs": explicit_allowed_overlap_pairs,
        "conditionalInteractionReviewPairs": conditional_interaction_review_pairs,
        "requiresCadInterferenceValidation": bool(allowed_overlap_pairs),
        "componentCount": len(placements),
        "containmentRelaxedComponents": [
            item.component_name for item in placements if item.containment_relaxed
        ],
    }


def _combined_validation(
    placements: list[Placement],
    gantry_name: str,
    portal_pass_through: dict[str, tuple[str, ...]],
    process_validation: dict[str, Any],
    semantic_overlap_pairs: set[frozenset[str]],
    explicit_overlap_pairs: set[frozenset[str]],
    spatial_validation: dict[str, Any],
    interaction_validation: dict[str, Any],
) -> dict[str, Any]:
    result = _validate_placements(
        placements,
        gantry_name,
        portal_pass_through,
        semantic_overlap_pairs,
        explicit_overlap_pairs,
    )
    result["geometricSuccess"] = result["success"]
    result["processHardFeasible"] = process_validation["hardFeasible"]
    result["spatialHardFeasible"] = spatial_validation["hardFeasible"]
    result["interactionHardFeasible"] = interaction_validation["hardFeasible"]
    result["success"] = bool(
        result["success"]
        and process_validation["hardFeasible"]
        and spatial_validation["hardFeasible"]
        and interaction_validation["hardFeasible"]
    )
    return result


def _portal_constraint_diagnostics(
    placements: list[Placement],
    footprints: dict[str, Footprint],
    portal_pass_through: dict[str, tuple[str, ...]],
    long_axis: str,
    clearance: float,
    opening_width_ratio: float,
    opening_height_ratio: float,
    semantics: dict[str, ModuleSemantic],
) -> list[dict[str, Any]]:
    by_name = {item.component_name: item for item in placements}
    short_axis = _other_axis(long_axis)
    diagnostics: list[dict[str, Any]] = []
    for portal_name, pass_through_names in portal_pass_through.items():
        portal = by_name[portal_name]
        footprint = footprints[portal_name]
        semantic = semantics.get(portal_name)
        opening_region = semantic.regions.get("portalOpening") if semantic else None
        opening_bounds = (
            _semantic_region_bounds(opening_region, portal)
            if opening_region is not None
            else None
        )
        opening_height = _portal_opening_height_range(semantic, footprint)
        diagnostics.append(
            {
                "portalComponentName": portal_name,
                "passThroughComponentNames": list(pass_through_names),
                "openingWidthRatio": opening_width_ratio,
                "openingHeightRatio": opening_height_ratio,
                "estimatedOpeningWidth": _axis_size(portal.bounds, short_axis)
                * opening_width_ratio,
                "estimatedOpeningHeight": footprint.height_normal * opening_height_ratio,
                "openingBounds": list(opening_bounds) if opening_bounds else None,
                "openingHeightRangeMeters": list(opening_height) if opening_height else None,
                "openingSource": "semantic.portalOpening" if opening_bounds else "ratioEstimate",
                "minimumClearanceMeters": clearance,
                "aabbOverlapAllowed": True,
                "requiresCadInterferenceValidation": True,
            }
        )
    return diagnostics


def _evaluate_interaction_hard_constraints(
    placements: list[Placement],
    footprints: dict[str, Footprint],
    semantics: dict[str, ModuleSemantic],
    portal_pass_through: dict[str, tuple[str, ...]],
    long_axis: str,
    clearance: float,
    allow_post_solve_projection_overlaps: bool = False,
    collision_pair_limit: int | None = None,
    focus_component_name: str | None = None,
    occupancy_envelope_cache: dict[tuple[str, int, int, int], list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Resolve coarse AABB overlaps with simplified body envelopes and portal openings."""
    diagnostics: list[dict[str, Any]] = []
    fast_candidate_check = collision_pair_limit == 1 and focus_component_name is not None
    for index, first in enumerate(placements):
        for second in placements[index + 1 :]:
            if focus_component_name is not None and focus_component_name not in {
                first.component_name,
                second.component_name,
            }:
                continue
            portal_name, pass_name = _portal_pair(
                first.component_name,
                second.component_name,
                portal_pass_through,
            )
            transport = first if first.role == "transport" else second if second.role == "transport" else None
            body = second if transport is first else first if transport is second else None
            body_semantic = semantics.get(body.component_name) if body is not None else None
            avoid_transport_sweep = bool(
                body_semantic
                and body_semantic.parameters.get("avoidTransportSweep", False)
            )
            protected_failures = False
            for owner, partner in ((first, second), (second, first)):
                protected_spaces = _protected_space_envelopes_for_partner(
                    owner,
                    semantics.get(owner.component_name),
                    partner.component_name,
                )
                if not protected_spaces:
                    continue
                partner_boxes = _occupancy_envelopes(
                    partner,
                    footprints[partner.component_name],
                    semantics.get(partner.component_name),
                )
                for protected_space in protected_spaces:
                    enforcement = str(
                        protected_space.get("enforcement") or "hard"
                    ).strip().lower()
                    requested_hard_space = enforcement not in {
                        "soft", "advisory", "warning"
                    }
                    conditional_partners = protected_space.get("conditionalBrepWith") or []
                    if isinstance(conditional_partners, str):
                        conditional_partners = [conditional_partners]
                    conditional_brep_pair = any(
                        str(name).lower() == partner.component_name.lower()
                        for name in conditional_partners
                    )
                    hard_space = requested_hard_space and not conditional_brep_pair
                    protected_clearance = max(
                        clearance,
                        float(protected_space.get("minimumClearanceMeters") or 0.0),
                    )
                    collisions = _overlapping_envelope_pairs(
                        [protected_space],
                        partner_boxes,
                        protected_clearance,
                        maximum_collisions=collision_pair_limit,
                    )
                    collision_detected = bool(collisions)
                    success = (
                        not collision_detected
                        if not requested_hard_space
                        else not collision_detected or conditional_brep_pair
                    )
                    protected_failures = protected_failures or (hard_space and not success)
                    diagnostics.append(
                        {
                            "id": (
                                f"protected-space-{owner.component_name}-"
                                f"{protected_space['id']}-{partner.component_name}"
                            ),
                            "type": "protectedServiceSpaceClearance",
                            "firstComponent": owner.component_name,
                            "secondComponent": partner.component_name,
                            "protectedSpaceOwner": owner.component_name,
                            "protectedSpace": protected_space,
                            "success": success,
                            "hard": hard_space,
                            "semanticHard": requested_hard_space,
                            "enforcement": enforcement,
                            "resolution": (
                                "protectedServiceSpaceClear"
                                if not collision_detected
                                else "advisoryProtectedServiceSpaceObstructed"
                                if not requested_hard_space
                                else "conditionalBrepProtectedSpaceOverlapDeferredToCad"
                                if conditional_brep_pair
                                else "protectedServiceSpaceObstructed"
                            ),
                            "minimumClearanceMeters": protected_clearance,
                            "collidingBoxPairs": collisions[:100],
                            "collidingBoxPairCount": len(collisions),
                            "collisionDetected": collision_detected,
                            "conditionalBrepPair": conditional_brep_pair,
                            "requiresCadInterferenceValidation": (
                                requested_hard_space
                                and conditional_brep_pair
                                and collision_detected
                            ),
                            "requiresEngineeringReview": (
                                not requested_hard_space and collision_detected
                            ),
                        }
                    )
                    if fast_candidate_check and hard_space and not success:
                        return _interaction_validation_result(diagnostics)
            if protected_failures:
                continue
            strict_aabb_clearance = _strict_aabb_pair_clearance(
                first.component_name,
                second.component_name,
                semantics,
                clearance,
            )
            if strict_aabb_clearance is not None:
                first_envelope = _full_aabb_envelope(
                    first,
                    footprints[first.component_name],
                )
                second_envelope = _full_aabb_envelope(
                    second,
                    footprints[second.component_name],
                )
                planar_overlap = _rectangles_touch_or_overlap(
                    first_envelope["bounds"],
                    second_envelope["bounds"],
                    strict_aabb_clearance,
                )
                height_overlap = _intervals_touch_or_overlap(
                    first_envelope["heightRangeMeters"],
                    second_envelope["heightRangeMeters"],
                    strict_aabb_clearance,
                )
                success = not (planar_overlap and height_overlap)
                diagnostics.append(
                    {
                        "id": f"strict-aabb-{first.component_name}-{second.component_name}",
                        "type": "strictInflatedAabbSeparation",
                        "firstComponent": first.component_name,
                        "secondComponent": second.component_name,
                        "success": success,
                        "hard": True,
                        "resolution": (
                            "separatedInflatedFullAabbs"
                            if success
                            else "inflatedFullAabbCollision"
                        ),
                        "minimumSeparationMeters": strict_aabb_clearance,
                        "firstEnvelope": first_envelope,
                        "secondEnvelope": second_envelope,
                        "requiresCadInterferenceValidation": False,
                    }
                )
                if fast_candidate_check and not success:
                    return _interaction_validation_result(diagnostics)
                continue
            multi_box_checked = _uses_multi_box_clearance(first, second, semantics)
            if multi_box_checked:
                def cached_occupancy(placement: Placement) -> list[dict[str, Any]]:
                    if occupancy_envelope_cache is None:
                        return _occupancy_envelopes(
                            placement,
                            footprints[placement.component_name],
                            semantics.get(placement.component_name),
                        )
                    key = (
                        placement.component_name,
                        placement.rotation_quarters,
                        round(placement.anchor_u * 1_000_000),
                        round(placement.anchor_v * 1_000_000),
                    )
                    cached = occupancy_envelope_cache.get(key)
                    if cached is None:
                        cached = _occupancy_envelopes(
                            placement,
                            footprints[placement.component_name],
                            semantics.get(placement.component_name),
                        )
                        occupancy_envelope_cache[key] = cached
                    return cached

                first_boxes = cached_occupancy(first)
                second_boxes = cached_occupancy(second)
                pair_clearance = _occupancy_pair_clearance(
                    first.component_name,
                    second.component_name,
                    semantics,
                    clearance,
                )
                collisions = _overlapping_envelope_pairs(
                    first_boxes,
                    second_boxes,
                    pair_clearance,
                    maximum_collisions=collision_pair_limit,
                )
                compared_box_pair_count = (
                    1
                    if fast_candidate_check
                    and _has_eligible_envelope_pair(first_boxes, second_boxes)
                    else 0
                    if fast_candidate_check
                    else _eligible_envelope_pair_count(first_boxes, second_boxes)
                )
                occupancy_coverage_complete = compared_box_pair_count > 0
                structural_pair = first.role == "gantry" or second.role == "gantry" or portal_name is not None
                first_hard = bool(
                    (semantics.get(first.component_name).parameters if semantics.get(first.component_name) else {}).get(
                        "occupancyBoxesHardClearance", True
                    )
                )
                second_hard = bool(
                    (semantics.get(second.component_name).parameters if semantics.get(second.component_name) else {}).get(
                        "occupancyBoxesHardClearance", True
                    )
                )
                conditional_brep_pair = _is_conditional_brep_pair(
                    first.component_name,
                    second.component_name,
                    semantics,
                )
                forced_hard_occupancy_pair = _is_forced_hard_occupancy_pair(
                    first.component_name,
                    second.component_name,
                    semantics,
                )
                # A leaf AABB overlap is only a conservative broad-phase hit for
                # sparse frames, portals and other non-convex assemblies.  When
                # the pair policy explicitly assigns the pair to conditional
                # B-Rep, preserve the overlap as a CAD-review item and continue
                # into any configured portal/channel hard checks below.
                hard_pair = forced_hard_occupancy_pair or (
                    (structural_pair or (first_hard and second_hard))
                    and not conditional_brep_pair
                )
                success = not collisions or not hard_pair
                diagnostics.append(
                    {
                        "id": f"occupancy-clearance-{first.component_name}-{second.component_name}",
                        "type": "structuralOccupancyClearance" if structural_pair else "multiBoxClearance",
                        "firstComponent": first.component_name,
                        "secondComponent": second.component_name,
                        "success": success,
                        "hard": hard_pair,
                        "resolution": (
                            "insufficientOccupancyCoverageDeferredToCad"
                            if not occupancy_coverage_complete
                            else
                            "separatedLeafBodyOccupancyBoxes"
                            if not collisions
                            else "conditionalBrepLeafBodyOverlapDeferredToCad"
                            if conditional_brep_pair
                            else "approximateLeafBodyOverlapDeferredToCad"
                            if not hard_pair
                            else "leafBodyOccupancyBoxCollision"
                        ),
                        "minimumClearanceMeters": pair_clearance,
                        "firstOccupancyBoxCount": len(first_boxes),
                        "secondOccupancyBoxCount": len(second_boxes),
                        "comparedOccupancyBoxPairCount": compared_box_pair_count,
                        "occupancyCoverageComplete": occupancy_coverage_complete,
                        "collidingBoxPairs": collisions[:100],
                        "collidingBoxPairCount": len(collisions),
                        "collisionDetected": bool(collisions),
                        "conditionalBrepPair": conditional_brep_pair,
                        "forcedHardOccupancyPair": forced_hard_occupancy_pair,
                        "requiresCadInterferenceValidation": True,
                    }
                )
                if not success:
                    if fast_candidate_check:
                        return _interaction_validation_result(diagnostics)
                    continue
                if first.role == "gantry" or second.role == "gantry":
                    continue
                if portal_name is None and not (transport is not None and avoid_transport_sweep):
                    continue
            if (first.role == "gantry" or second.role == "gantry") and not multi_box_checked:
                # Sparse-frame occupancy cannot be inferred from a full gantry AABB.
                # Legacy/general cases without measured leaf boxes stay unmodelled
                # here and must use their existing CAD validation path.
                continue
            if allow_post_solve_projection_overlaps and _is_post_solve_projection_overlap_allowed(
                first.component_name,
                second.component_name,
                semantics,
            ):
                if _rectangles_touch_or_overlap(first.bounds, second.bounds, clearance):
                    diagnostics.append(
                        {
                            "id": f"post-solve-projection-overlap-{first.component_name}-{second.component_name}",
                            "type": "postSolveProjectionOverlap",
                            "firstComponent": first.component_name,
                            "secondComponent": second.component_name,
                            "success": True,
                            "resolution": "configuredPostSolveCadReview",
                            "minimumClearanceMeters": clearance,
                            "requiresCadInterferenceValidation": True,
                        }
                    )
                continue
            if _is_service_cluster_projection_overlap_allowed(
                first.component_name,
                second.component_name,
                semantics,
            ) and not _uses_multi_box_clearance(first, second, semantics):
                if _rectangles_touch_or_overlap(first.bounds, second.bounds, clearance):
                    diagnostics.append(
                        {
                            "id": f"service-cluster-overlap-{first.component_name}-{second.component_name}",
                            "type": "serviceClusterProjectionOverlap",
                            "firstComponent": first.component_name,
                            "secondComponent": second.component_name,
                            "success": True,
                            "resolution": "configuredInterleavedServiceCluster",
                            "minimumClearanceMeters": clearance,
                            "requiresCadInterferenceValidation": True,
                        }
                    )
                continue
            if _is_configured_projection_overlap_allowed(
                first.component_name,
                second.component_name,
                semantics,
            ):
                if _rectangles_touch_or_overlap(first.bounds, second.bounds, clearance):
                    diagnostics.append(
                        {
                            "id": f"configured-projection-overlap-{first.component_name}-{second.component_name}",
                            "type": "configuredProjectionOverlap",
                            "firstComponent": first.component_name,
                            "secondComponent": second.component_name,
                            "success": True,
                            "resolution": "configuredSparseFrameOverlap",
                            "minimumClearanceMeters": clearance,
                            "requiresCadInterferenceValidation": True,
                        }
                    )
                continue
            if transport is not None and body is not None and avoid_transport_sweep:
                sweep_envelope = _transport_sweep_envelope(
                    transport,
                    footprints[transport.component_name],
                    semantics.get(transport.component_name),
                )
                if sweep_envelope is None:
                    raise ConstraintLayoutError(
                        f"Transport '{transport.component_name}' must define transportSweepBoundsLocal "
                        f"before '{body.component_name}' can require avoidTransportSweep."
                    )
                body_envelope = _hard_body_envelope(
                    body,
                    footprints[body.component_name],
                    body_semantic,
                )
                clearance_envelopes = [
                    (
                        "transportSweepClearance",
                        "transport-sweep",
                        "transportSweepEnvelope",
                        sweep_envelope,
                        "separatedTransportSweepAndHardBody",
                        "transportSweepCollision",
                    )
                ]
                static_keepout = _transport_static_keepout_envelope(
                    transport,
                    footprints[transport.component_name],
                    semantics.get(transport.component_name),
                ) if body_semantic and body_semantic.parameters.get(
                    "avoidTransportStaticKeepout", False
                ) else None
                if static_keepout is not None:
                    clearance_envelopes.append(
                        (
                            "transportStaticKeepoutClearance",
                            "transport-static-keepout",
                            "transportStaticKeepoutEnvelope",
                            static_keepout,
                            "separatedTransportStaticKeepoutAndHardBody",
                            "transportStaticKeepoutCollision",
                        )
                    )
                for (
                    diagnostic_type,
                    diagnostic_id,
                    envelope_key,
                    transport_envelope,
                    success_resolution,
                    failure_resolution,
                ) in clearance_envelopes:
                    planar_overlap = _rectangles_touch_or_overlap(
                        transport_envelope["bounds"], body_envelope["bounds"], clearance
                    )
                    height_overlap = _intervals_touch_or_overlap(
                        transport_envelope["heightRangeMeters"],
                        body_envelope["heightRangeMeters"],
                        clearance,
                    )
                    success = not (planar_overlap and height_overlap)
                    diagnostics.append(
                        {
                            "id": f"{diagnostic_id}-{transport.component_name}-{body.component_name}",
                            "type": diagnostic_type,
                            "firstComponent": transport.component_name,
                            "secondComponent": body.component_name,
                            "success": success,
                            "resolution": success_resolution if success else failure_resolution,
                            "minimumClearanceMeters": clearance,
                            envelope_key: transport_envelope,
                            "hardBodyEnvelope": body_envelope,
                            "requiresCadInterferenceValidation": bool(
                                transport_envelope["source"].startswith("semantic")
                                or body_envelope["source"] != "fullAabbBody"
                            ),
                        }
                    )
                continue
            if (
                portal_name is None
                and not _rectangles_touch_or_overlap(first.bounds, second.bounds, clearance)
            ):
                continue
            first_envelope = _interaction_envelope(
                first,
                footprints[first.component_name],
                semantics.get(first.component_name),
            )
            second_envelope = _interaction_envelope(
                second,
                footprints[second.component_name],
                semantics.get(second.component_name),
            )
            planar_overlap = _rectangles_touch_or_overlap(
                first_envelope["bounds"], second_envelope["bounds"], clearance
            )
            height_overlap = _intervals_touch_or_overlap(
                first_envelope["heightRangeMeters"],
                second_envelope["heightRangeMeters"],
                clearance,
            )
            resolution = "separatedInteractionEnvelopes"
            success = not (planar_overlap and height_overlap)
            portal_check = None
            if portal_name:
                portal = first if first.component_name == portal_name else second
                passed = first if first.component_name == pass_name else second
                pass_envelope = (
                    first_envelope if first.component_name == pass_name else second_envelope
                )
                pass_semantic = semantics.get(pass_name)
                portal_semantic = semantics.get(portal_name)
                pass_mode_by_component = (
                    portal_semantic.parameters.get("portalPassModeByComponent", {})
                    if portal_semantic
                    else {}
                )
                pass_mode = str(
                    pass_mode_by_component.get(
                        pass_name,
                        "throughLongAxis" if passed.role == "transport" else "contained2d",
                    )
                )
                if pass_mode not in {"throughLongAxis", "contained2d", "namedChannel"}:
                    raise ConstraintLayoutError(
                        f"Portal '{portal_name}' has unsupported pass mode '{pass_mode}' for '{pass_name}'."
                    )
                pass_envelopes = [pass_envelope]
                if pass_mode == "throughLongAxis" and pass_semantic:
                    raw_pass_bodies = pass_semantic.parameters.get(
                        "portalPassBodyBoxesLocal"
                    )
                    if isinstance(raw_pass_bodies, list) and raw_pass_bodies:
                        pass_envelopes = [
                            {
                                **_named_local_envelope(
                                    passed,
                                    raw,
                                    "measuredPortalPassBody",
                                ),
                                "id": str(raw.get("id") or f"portal-pass-{index + 1}"),
                                "requireLongAxisContainment": bool(
                                    raw.get("requireLongAxisContainment", False)
                                ),
                            }
                            for index, raw in enumerate(raw_pass_bodies)
                            if isinstance(raw, dict)
                        ]
                        if not pass_envelopes:
                            raise ConstraintLayoutError(
                                f"Component '{pass_name}' portalPassBodyBoxesLocal has no valid boxes."
                            )
                        pass_envelope = _union_envelopes(pass_envelopes)
                    elif pass_semantic.parameters.get("portalPassBoundsLocal") is not None:
                        pass_envelope = _configured_local_envelope(
                            passed,
                            footprints[pass_name],
                            pass_semantic,
                            bounds_parameter="portalPassBoundsLocal",
                            height_parameter="portalPassHeightRangeMeters",
                            configured_source="measuredPortalPassEnvelope",
                            default_source="fullPortalPassEnvelope",
                        )
                        pass_envelopes = [pass_envelope]
                if pass_mode == "contained2d":
                    pass_envelopes = _occupancy_envelopes(
                        passed,
                        footprints[pass_name],
                        pass_semantic,
                    )
                    pass_envelope = _union_envelopes(pass_envelopes)
                if pass_mode == "namedChannel":
                    channel_by_component = (
                        portal_semantic.parameters.get("portalChannelByComponent", {})
                        if portal_semantic
                        else {}
                    )
                    channels = (
                        portal_semantic.parameters.get("passageChannelsLocal", {})
                        if portal_semantic
                        else {}
                    )
                    channel_name = str(channel_by_component.get(pass_name) or "").strip()
                    raw_channel = channels.get(channel_name) if isinstance(channels, dict) else None
                    if not channel_name or not isinstance(raw_channel, dict):
                        raise ConstraintLayoutError(
                            f"Portal '{portal_name}' must define a named passage channel for '{pass_name}'."
                        )
                    channel = _named_local_envelope(
                        portal,
                        raw_channel,
                        f"semanticPassageChannel:{channel_name}",
                    )
                    pass_envelopes = _channel_body_envelopes(
                        passed,
                        footprints[pass_name],
                        pass_semantic,
                    )
                    contained = [
                        _envelope_contained(channel, item, clearance)
                        for item in pass_envelopes
                    ]
                    success = bool(contained) and all(contained)
                    resolution = "namedStructureChannel" if success else "unresolvedNamedStructureChannel"
                    portal_check = {
                        "portalComponentName": portal_name,
                        "passThroughComponentName": pass_name,
                        "passMode": pass_mode,
                        "channelName": channel_name,
                        "channelEnvelope": channel,
                        "passEnvelopes": pass_envelopes,
                        "contained": contained,
                    }
                    diagnostics.append(
                        {
                            "id": f"interaction-{first.component_name}-{second.component_name}",
                            "type": "structureChannelContainment",
                            "firstComponent": first.component_name,
                            "secondComponent": second.component_name,
                            "success": success,
                            "resolution": resolution,
                            "minimumClearanceMeters": clearance,
                            "firstEnvelope": first_envelope,
                            "secondEnvelope": second_envelope,
                            "portalCheck": portal_check,
                            "requiresCadInterferenceValidation": True,
                        }
                    )
                    if fast_candidate_check and not success:
                        return _interaction_validation_result(diagnostics)
                    continue
                opening_region = (
                    portal_semantic.regions.get("portalOpening")
                    if portal_semantic
                    else None
                )
                opening_height = _portal_opening_height_range(
                    portal_semantic, footprints[portal_name]
                )
                if opening_region is not None and opening_height is not None:
                    opening_bounds = _semantic_region_bounds(opening_region, portal)
                    short_axis = _other_axis(long_axis)
                    short_contained = all(
                        _axis_min(item["bounds"], short_axis)
                        >= _axis_min(opening_bounds, short_axis) + clearance - 1e-9
                        and _axis_max(item["bounds"], short_axis)
                        <= _axis_max(opening_bounds, short_axis) - clearance + 1e-9
                        for item in pass_envelopes
                    )
                    long_contained = all(
                        _axis_min(item["bounds"], long_axis)
                        >= _axis_min(opening_bounds, long_axis) + clearance - 1e-9
                        and _axis_max(item["bounds"], long_axis)
                        <= _axis_max(opening_bounds, long_axis) - clearance + 1e-9
                        for item in pass_envelopes
                    )
                    long_requirement_satisfied = all(
                        not bool(item.get("requireLongAxisContainment"))
                        or (
                            _axis_min(item["bounds"], long_axis)
                            >= _axis_min(opening_bounds, long_axis) + clearance - 1e-9
                            and _axis_max(item["bounds"], long_axis)
                            <= _axis_max(opening_bounds, long_axis) - clearance + 1e-9
                        )
                        for item in pass_envelopes
                    )
                    height_contained = all(
                        item["heightRangeMeters"][0] >= opening_height[0] - 1e-9
                        and item["heightRangeMeters"][1]
                        <= opening_height[1] - clearance + 1e-9
                        for item in pass_envelopes
                    )
                    success = (
                        short_contained
                        and height_contained
                        and (
                            (pass_mode == "throughLongAxis" and long_requirement_satisfied)
                            or (pass_mode != "throughLongAxis" and long_contained)
                        )
                    )
                    resolution = "portalOpening" if success else "unresolvedPortalOverlap"
                    portal_check = {
                        "portalComponentName": portal_name,
                        "passThroughComponentName": pass_name,
                        "openingBounds": list(opening_bounds),
                        "openingHeightRangeMeters": list(opening_height),
                        "passMode": pass_mode,
                        "passEnvelope": pass_envelope,
                        "passEnvelopes": pass_envelopes,
                        "shortAxisContained": short_contained,
                        "longAxisContained": long_contained,
                        "longAxisRequirementSatisfied": long_requirement_satisfied,
                        "heightContained": height_contained,
                    }
                else:
                    success = True
                    resolution = "legacyPortalRatioRequiresCadReview"
                    portal_check = {
                        "portalComponentName": portal_name,
                        "passThroughComponentName": pass_name,
                        "openingBounds": None,
                        "openingHeightRangeMeters": None,
                        "shortAxisContained": None,
                        "heightContained": None,
                        "legacyRatioFallback": True,
                    }
            diagnostics.append(
                {
                    "id": f"interaction-{first.component_name}-{second.component_name}",
                    "type": "interactionEnvelopeClearance",
                    "firstComponent": first.component_name,
                    "secondComponent": second.component_name,
                    "success": success,
                    "resolution": resolution,
                    "minimumClearanceMeters": clearance,
                    "firstEnvelope": first_envelope,
                    "secondEnvelope": second_envelope,
                    "portalCheck": portal_check,
                    "requiresCadInterferenceValidation": bool(
                        first_envelope["source"] != "fullAabb"
                        or second_envelope["source"] != "fullAabb"
                        or portal_check
                    ),
                }
            )
            if fast_candidate_check and not success:
                return _interaction_validation_result(diagnostics)
    return _interaction_validation_result(diagnostics)


def _interaction_validation_result(diagnostics: list[dict[str, Any]]) -> dict[str, Any]:
    failures = [
        item
        for item in diagnostics
        if item.get("hard", True) and not item["success"]
    ]
    soft_violations = [
        item
        for item in diagnostics
        if not item.get("hard", True) and not item["success"]
    ]
    hard_diagnostics = [item for item in diagnostics if item.get("hard", True)]
    return {
        "success": not failures,
        "hardFeasible": not failures,
        "constraintCount": len(diagnostics),
        "passedCount": sum(1 for item in diagnostics if item["success"]),
        "hardConstraintCount": len(hard_diagnostics),
        "hardPassedCount": len(hard_diagnostics) - len(failures),
        "hardFailureCount": len(failures),
        "softViolationCount": len(soft_violations),
        "diagnostics": diagnostics,
        "message": (
            "2.5D interaction hard constraints failed: "
            + "; ".join(
                f"{item['firstComponent']} vs {item['secondComponent']}"
                for item in failures
            )
            if failures
            else (
                "All hard interaction constraints pass; advisory service-space warnings remain."
                if soft_violations
                else "All coarse AABB overlaps are resolved by interaction-envelope separation or a configured portal opening."
            )
        ),
    }


def _collision_responsibility_key(
    validation: dict[str, Any],
    parent: Placement,
    repaired: Placement,
    lane_resolution_meters: float = 0.01,
) -> tuple[Any, ...]:
    """Identify equivalent failed repair branches without weakening constraints.

    Two failed repairs are considered dominated only when the same module pair,
    rule and measured leaf-box pair block motion in the same direction along
    the same axis and coarse lane.  The first deterministic boundary event is
    retained; distinct obstacles, axes, directions and lanes remain searchable.
    """
    failed = next(
        (
            item
            for item in validation.get("diagnostics", [])
            if item.get("hard", True) and not item.get("success", False)
        ),
        {},
    )
    colliding_pairs = failed.get("collidingBoxPairs") or []
    first_collision = colliding_pairs[0] if colliding_pairs else {}
    delta_u = repaired.anchor_u - parent.anchor_u
    delta_v = repaired.anchor_v - parent.anchor_v
    movement_axis = "u" if abs(delta_u) >= abs(delta_v) else "v"
    movement_delta = delta_u if movement_axis == "u" else delta_v
    movement_direction = -1 if movement_delta < -1e-12 else 1
    lane_value = repaired.anchor_v if movement_axis == "u" else repaired.anchor_u
    resolution = max(float(lane_resolution_meters), 1e-6)
    return (
        str(failed.get("firstComponent") or "unknown"),
        str(failed.get("secondComponent") or "unknown"),
        str(failed.get("resolution") or failed.get("type") or "interaction"),
        str(first_collision.get("firstBox") or ""),
        str(first_collision.get("secondBox") or ""),
        repaired.rotation_quarters,
        movement_axis,
        movement_direction,
        round(lane_value / resolution),
    )


def _interaction_envelope(
    placement: Placement,
    footprint: Footprint,
    semantic: ModuleSemantic | None,
) -> dict[str, Any]:
    return _configured_local_envelope(
        placement,
        footprint,
        semantic,
        bounds_parameter="interactionBoundsLocal",
        height_parameter="interactionHeightRangeMeters",
        configured_source="semanticInteractionBounds",
        default_source="fullAabb",
    )


def _candidate_interaction_feasible(
    candidate: Placement,
    placements: list[Placement],
    footprints: dict[str, Footprint],
    semantics: dict[str, ModuleSemantic],
    portal_pass_through: dict[str, tuple[str, ...]],
    long_axis: str,
    clearance: float,
) -> bool:
    validation = _evaluate_interaction_hard_constraints(
        [*placements, candidate],
        footprints,
        semantics,
        portal_pass_through,
        long_axis,
        clearance,
        collision_pair_limit=1,
        focus_component_name=candidate.component_name,
    )
    return bool(validation["hardFeasible"])


def _candidate_collision_boundary_repairs(
    candidate: Placement,
    placements: list[Placement],
    footprints: dict[str, Footprint],
    semantics: dict[str, ModuleSemantic],
    portal_pass_through: dict[str, tuple[str, ...]],
    clearance: float,
    occupancy_envelope_cache: dict[
        tuple[str, int, int, int], list[dict[str, Any]]
    ] | None = None,
) -> tuple[Placement, ...]:
    """Return bounded one-axis moves that cross a current collision boundary.

    The returned locations are analytic configuration-space events rather than
    another dense grid.  Repeated calls can therefore walk around several fixed
    obstacles while retaining deterministic, source-position-independent output.
    """

    del portal_pass_through  # Portal-specific passage is handled by the normal validator.
    candidate_semantic = semantics.get(candidate.component_name)
    candidate_footprint = footprints[candidate.component_name]
    epsilon = max(1e-6, clearance * 1e-4)
    shifts: list[tuple[float, float]] = []

    def cached_occupancy(
        placement: Placement,
        footprint: Footprint,
        semantic: ModuleSemantic | None,
    ) -> list[dict[str, Any]]:
        if occupancy_envelope_cache is None:
            return _occupancy_envelopes(placement, footprint, semantic)
        key = (
            placement.component_name,
            placement.rotation_quarters,
            round(placement.anchor_u * 1_000_000),
            round(placement.anchor_v * 1_000_000),
        )
        cached = occupancy_envelope_cache.get(key)
        if cached is None:
            cached = _occupancy_envelopes(placement, footprint, semantic)
            occupancy_envelope_cache[key] = cached
        return cached

    def add_envelope_repairs(
        candidate_boxes: list[dict[str, Any]],
        other_boxes: list[dict[str, Any]],
        maximum_pairs: int = 8,
    ) -> None:
        # Evidence-derived boxes normally name the module codes they can collide
        # with.  Filter by that sparse relation before the Cartesian scan.  This
        # preserves the exact per-pair checks below, while avoiding hundreds of
        # irrelevant box comparisons for every repair candidate.
        candidate_codes = {
            str(item["componentCode"])
            for item in candidate_boxes
            if item.get("componentCode") is not None
        }
        other_codes = {
            str(item["componentCode"])
            for item in other_boxes
            if item.get("componentCode") is not None
        }

        def can_target(box: dict[str, Any], target_codes: set[str]) -> bool:
            partners = box.get("collisionPartnerCodes")
            if partners is None:
                return True
            return any(code in partners for code in target_codes)

        candidate_boxes = [
            item for item in candidate_boxes if can_target(item, other_codes)
        ]
        other_boxes = [
            item for item in other_boxes if can_target(item, candidate_codes)
        ]
        if not candidate_boxes or not other_boxes:
            return

        collision_count = 0
        for left in candidate_boxes:
            for right in other_boxes:
                left_partners = left.get("collisionPartnerCodes")
                right_partners = right.get("collisionPartnerCodes")
                if left_partners is not None and right.get("componentCode") not in left_partners:
                    continue
                if right_partners is not None and left.get("componentCode") not in right_partners:
                    continue
                box_clearances = [
                    float(item["minimumClearanceMeters"])
                    for item in (left, right)
                    if item.get("minimumClearanceMeters") is not None
                ]
                effective_clearance = max(box_clearances) if box_clearances else clearance
                if not _intervals_touch_or_overlap(
                    left["heightRangeMeters"], right["heightRangeMeters"], effective_clearance
                ) or not _rectangles_touch_or_overlap(
                    left["bounds"], right["bounds"], effective_clearance
                ):
                    continue
                left_bounds = left["bounds"]
                right_bounds = right["bounds"]
                shifts.extend(
                    (
                        (right_bounds[0] - effective_clearance - epsilon - left_bounds[2], 0.0),
                        (right_bounds[2] + effective_clearance + epsilon - left_bounds[0], 0.0),
                        (0.0, right_bounds[1] - effective_clearance - epsilon - left_bounds[3]),
                        (0.0, right_bounds[3] + effective_clearance + epsilon - left_bounds[1]),
                    )
                )
                collision_count += 1
                if collision_count >= maximum_pairs:
                    return

    for other in placements:
        if other.component_name == candidate.component_name:
            continue
        other_semantic = semantics.get(other.component_name)
        if _uses_multi_box_clearance(candidate, other, semantics):
            add_envelope_repairs(
                cached_occupancy(candidate, candidate_footprint, candidate_semantic),
                cached_occupancy(
                    other,
                    footprints[other.component_name],
                    other_semantic,
                ),
            )
            continue

        if other.role != "transport" or candidate_semantic is None:
            continue
        if not candidate_semantic.parameters.get("avoidTransportSweep", False):
            continue
        body = _hard_body_envelope(candidate, candidate_footprint, candidate_semantic)
        transport_boxes: list[dict[str, Any]] = []
        sweep = _transport_sweep_envelope(
            other,
            footprints[other.component_name],
            other_semantic,
        )
        if sweep is not None:
            transport_boxes.append(sweep)
        if candidate_semantic.parameters.get("avoidTransportStaticKeepout", False):
            static = _transport_static_keepout_envelope(
                other,
                footprints[other.component_name],
                other_semantic,
            )
            if static is not None:
                transport_boxes.append(static)
        add_envelope_repairs([body], transport_boxes, maximum_pairs=2)

    unique: dict[tuple[int, int], Placement] = {}
    for delta_u, delta_v in sorted(
        shifts,
        key=lambda value: (abs(value[0]) + abs(value[1]), abs(value[1]), abs(value[0]), value),
    ):
        if abs(delta_u) <= 1e-12 and abs(delta_v) <= 1e-12:
            continue
        repaired = _translate_placement(candidate, delta_u, delta_v)
        key = (
            round(repaired.anchor_u * 1_000_000),
            round(repaired.anchor_v * 1_000_000),
        )
        unique.setdefault(key, repaired)
        if len(unique) >= 32:
            break
    return tuple(unique.values())


def _hard_body_envelope(
    placement: Placement,
    footprint: Footprint,
    semantic: ModuleSemantic | None,
) -> dict[str, Any]:
    """Return the conservative fixed-body occupancy used by hard clearance checks."""
    return _configured_local_envelope(
        placement,
        footprint,
        semantic,
        bounds_parameter="hardBodyBoundsLocal",
        height_parameter="hardBodyHeightRangeMeters",
        configured_source="semanticHardBodyBounds",
        default_source="fullAabbBody",
    )


def _full_aabb_envelope(
    placement: Placement,
    footprint: Footprint,
) -> dict[str, Any]:
    return {
        "bounds": placement.bounds,
        "heightRangeMeters": (0.0, footprint.height_normal),
        "source": "fullTopLevelAabb",
    }


def _strict_aabb_pair_clearance(
    first_name: str,
    second_name: str,
    semantics: dict[str, ModuleSemantic],
    fallback_clearance: float,
) -> float | None:
    first = semantics.get(first_name)
    second = semantics.get(second_name)
    first_partners = first.parameters.get("strictAabbSeparationWith", []) if first else []
    second_partners = second.parameters.get("strictAabbSeparationWith", []) if second else []
    if isinstance(first_partners, str):
        first_partners = [first_partners]
    if isinstance(second_partners, str):
        second_partners = [second_partners]
    configured = (
        any(str(name).lower() == second_name.lower() for name in first_partners)
        or any(str(name).lower() == first_name.lower() for name in second_partners)
    )
    if not configured:
        return None
    inflation = max(
        float(first.parameters.get("strictAabbInflationPerSideMeters", 0.0)) if first else 0.0,
        float(second.parameters.get("strictAabbInflationPerSideMeters", 0.0)) if second else 0.0,
    )
    return max(float(fallback_clearance), inflation * 2.0)


def _is_conditional_brep_pair(
    first_name: str,
    second_name: str,
    semantics: dict[str, ModuleSemantic],
) -> bool:
    first = semantics.get(first_name)
    second = semantics.get(second_name)
    first_partners = first.parameters.get("brepOnAabbOverlapWith", []) if first else []
    second_partners = second.parameters.get("brepOnAabbOverlapWith", []) if second else []
    if isinstance(first_partners, str):
        first_partners = [first_partners]
    if isinstance(second_partners, str):
        second_partners = [second_partners]
    return (
        any(str(name).lower() == second_name.lower() for name in first_partners)
        or any(str(name).lower() == first_name.lower() for name in second_partners)
    )


def _is_forced_hard_occupancy_pair(
    first_name: str,
    second_name: str,
    semantics: dict[str, ModuleSemantic],
) -> bool:
    """Return whether measured leaf occupancy must block the solver for a pair.

    This is intentionally narrower than strict top-level AABB separation.  It
    is used for sparse frames/portals where AABBs may overlap legitimately,
    while measured leaf-body occupancy is reliable enough to reject a layout
    before an expensive CAD replay.
    """
    first = semantics.get(first_name)
    second = semantics.get(second_name)
    first_partners = first.parameters.get("hardOccupancyClearanceWith", []) if first else []
    second_partners = second.parameters.get("hardOccupancyClearanceWith", []) if second else []
    if isinstance(first_partners, str):
        first_partners = [first_partners]
    if isinstance(second_partners, str):
        second_partners = [second_partners]
    return (
        any(str(name).lower() == second_name.lower() for name in first_partners)
        or any(str(name).lower() == first_name.lower() for name in second_partners)
    )


def _occupancy_pair_clearance(
    first_name: str,
    second_name: str,
    semantics: dict[str, ModuleSemantic],
    fallback_clearance: float,
) -> float:
    """Resolve an optional pair-specific leaf-occupancy clearance."""

    def configured(owner_name: str, partner_name: str) -> float:
        semantic = semantics.get(owner_name)
        raw = semantic.parameters.get("occupancyClearanceMetersByComponent", {}) if semantic else {}
        if not isinstance(raw, dict):
            return 0.0
        for name, value in raw.items():
            if str(name).lower() == partner_name.lower():
                result = float(value)
                if not math.isfinite(result) or result < 0:
                    raise ConstraintLayoutError(
                        f"Component '{owner_name}' occupancy clearance for '{partner_name}' "
                        "must be a finite non-negative number."
                    )
                return result
        return 0.0

    return max(
        float(fallback_clearance),
        configured(first_name, second_name),
        configured(second_name, first_name),
    )


def _conditional_brep_overlap_count(
    candidate: Placement,
    placements: list[Placement],
    semantics: dict[str, ModuleSemantic],
) -> int:
    return sum(
        1
        for other in placements
        if _is_conditional_brep_pair(candidate.component_name, other.component_name, semantics)
        and _rectangles_touch_or_overlap(candidate.bounds, other.bounds, 0.0)
    )


def _conditional_brep_pair_count(
    placements: list[Placement],
    semantics: dict[str, ModuleSemantic],
) -> int:
    return sum(
        1
        for index, first in enumerate(placements)
        for second in placements[index + 1 :]
        if _is_conditional_brep_pair(first.component_name, second.component_name, semantics)
        and _rectangles_touch_or_overlap(first.bounds, second.bounds, 0.0)
    )


def _conditional_brep_leaf_hit_count(
    candidate: Placement,
    placements: list[Placement],
    footprints: dict[str, Footprint],
    semantics: dict[str, ModuleSemantic],
    clearance: float,
    occupancy_envelope_cache: dict[tuple[str, int, int, int], list[dict[str, Any]]] | None = None,
) -> int:
    """Count leaf-AABB broad-phase hits for conditional pairs touching a candidate."""

    def boxes(placement: Placement) -> list[dict[str, Any]]:
        if occupancy_envelope_cache is None:
            return _occupancy_envelopes(
                placement,
                footprints[placement.component_name],
                semantics.get(placement.component_name),
            )
        key = (
            placement.component_name,
            placement.rotation_quarters,
            round(placement.anchor_u * 1_000_000),
            round(placement.anchor_v * 1_000_000),
        )
        cached = occupancy_envelope_cache.get(key)
        if cached is None:
            cached = _occupancy_envelopes(
                placement,
                footprints[placement.component_name],
                semantics.get(placement.component_name),
            )
            occupancy_envelope_cache[key] = cached
        return cached

    total = 0
    candidate_boxes: list[dict[str, Any]] | None = None
    for other in placements:
        if not _is_conditional_brep_pair(
            candidate.component_name,
            other.component_name,
            semantics,
        ):
            continue
        if not _rectangles_touch_or_overlap(candidate.bounds, other.bounds, 0.0):
            continue
        if candidate_boxes is None:
            candidate_boxes = boxes(candidate)
        pair_clearance = _occupancy_pair_clearance(
            candidate.component_name,
            other.component_name,
            semantics,
            clearance,
        )
        total += len(
            _overlapping_envelope_pairs(
                candidate_boxes,
                boxes(other),
                pair_clearance,
                maximum_collisions=100,
            )
        )
    return total


def _conditional_brep_leaf_hit_count_for_layout(
    placements: list[Placement],
    footprints: dict[str, Footprint],
    semantics: dict[str, ModuleSemantic],
    clearance: float,
    occupancy_envelope_cache: dict[tuple[str, int, int, int], list[dict[str, Any]]] | None = None,
) -> int:
    total = 0
    prefix: list[Placement] = []
    for placement in placements:
        total += _conditional_brep_leaf_hit_count(
            placement,
            prefix,
            footprints,
            semantics,
            clearance,
            occupancy_envelope_cache,
        )
        prefix.append(placement)
    return total


def _occupancy_envelopes(
    placement: Placement,
    footprint: Footprint,
    semantic: ModuleSemantic | None,
) -> list[dict[str, Any]]:
    parameters = semantic.parameters if semantic else {}
    raw_boxes = parameters.get("occupancyBoxesLocal")
    if raw_boxes is None:
        return [_hard_body_envelope(placement, footprint, semantic)]
    if not isinstance(raw_boxes, list) or not raw_boxes:
        raise ConstraintLayoutError(
            f"Component '{placement.component_name}' occupancyBoxesLocal must be a non-empty list."
        )
    result: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_boxes):
        if not isinstance(raw, dict):
            raise ConstraintLayoutError(
                f"Component '{placement.component_name}' occupancy box {index} must be an object."
            )
        item = _named_local_envelope(
            placement,
            raw,
            "measuredLeafBodyOccupancy",
        )
        item["id"] = str(raw.get("id") or f"box-{index + 1}")
        item["evidence"] = raw.get("evidence")
        item["componentCode"] = raw.get("componentCode")
        if "minimumClearanceMeters" in raw:
            item["minimumClearanceMeters"] = float(raw["minimumClearanceMeters"])
        if "collisionPartnerCodes" in raw:
            item["collisionPartnerCodes"] = list(raw.get("collisionPartnerCodes") or [])
        result.append(item)
    return result


def _protected_space_envelopes_for_partner(
    placement: Placement,
    semantic: ModuleSemantic | None,
    partner_name: str,
) -> list[dict[str, Any]]:
    """Return non-solid service/maintenance spaces that a partner must not occupy."""
    raw_spaces = semantic.parameters.get("protectedSpaceBoxesLocal", []) if semantic else []
    if raw_spaces is None:
        return []
    if not isinstance(raw_spaces, list):
        raise ConstraintLayoutError(
            f"Component '{placement.component_name}' protectedSpaceBoxesLocal must be a list."
        )
    result: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_spaces):
        if not isinstance(raw, dict):
            raise ConstraintLayoutError(
                f"Component '{placement.component_name}' protected space {index} must be an object."
            )
        partners = raw.get("hardClearanceWith", [])
        if isinstance(partners, str):
            partners = [partners]
        if not any(str(name).lower() == partner_name.lower() for name in partners):
            continue
        item = _named_local_envelope(placement, raw, "semanticProtectedServiceSpace")
        item["id"] = str(raw.get("id") or f"protected-space-{index + 1}")
        item["purpose"] = raw.get("purpose")
        item["enforcement"] = str(raw.get("enforcement") or "hard")
        item["evidenceStatus"] = raw.get("evidenceStatus")
        item["confirmed"] = raw.get("confirmed")
        item["source"] = raw.get("source")
        if "conditionalBrepWith" in raw:
            item["conditionalBrepWith"] = list(raw.get("conditionalBrepWith") or [])
        if "minimumClearanceMeters" in raw:
            item["minimumClearanceMeters"] = float(raw["minimumClearanceMeters"])
        result.append(item)
    return result


def _channel_body_envelopes(
    placement: Placement,
    footprint: Footprint,
    semantic: ModuleSemantic | None,
) -> list[dict[str, Any]]:
    parameters = semantic.parameters if semantic else {}
    raw_boxes = parameters.get("channelBodyBoxesLocal")
    if not isinstance(raw_boxes, list) or not raw_boxes:
        raise ConstraintLayoutError(
            f"Component '{placement.component_name}' must define channelBodyBoxesLocal for namedChannel passage."
        )
    return [
        {
            **_named_local_envelope(placement, raw, "measuredChannelBody"),
            "id": str(raw.get("id") or f"channel-body-{index + 1}"),
        }
        for index, raw in enumerate(raw_boxes)
        if isinstance(raw, dict)
    ]


def _named_local_envelope(
    placement: Placement,
    raw: dict[str, Any],
    source: str,
) -> dict[str, Any]:
    bounds = raw.get("bounds")
    height = raw.get("heightRangeMeters")
    if not isinstance(bounds, (list, tuple)) or len(bounds) != 4:
        raise ConstraintLayoutError(
            f"Component '{placement.component_name}' local envelope bounds must contain four values."
        )
    if not isinstance(height, (list, tuple)) or len(height) != 2:
        raise ConstraintLayoutError(
            f"Component '{placement.component_name}' local envelope heightRangeMeters must contain two values."
        )
    local = tuple(float(value) for value in bounds)
    height_range = tuple(float(value) for value in height)
    if local[0] >= local[2] or local[1] >= local[3] or height_range[0] < 0 or height_range[0] >= height_range[1]:
        raise ConstraintLayoutError(
            f"Component '{placement.component_name}' local envelope is empty or inverted."
        )
    corners = [
        _rotate_local_point(u, v, placement.rotation_quarters)
        for u in (local[0], local[2])
        for v in (local[1], local[3])
    ]
    return {
        "bounds": (
            placement.anchor_u + min(point[0] for point in corners),
            placement.anchor_v + min(point[1] for point in corners),
            placement.anchor_u + max(point[0] for point in corners),
            placement.anchor_v + max(point[1] for point in corners),
        ),
        "heightRangeMeters": height_range,
        "source": source,
    }


def _uses_multi_box_clearance(
    first: Placement,
    second: Placement,
    semantics: dict[str, ModuleSemantic],
) -> bool:
    first_semantic = semantics.get(first.component_name)
    second_semantic = semantics.get(second.component_name)
    return bool(
        first_semantic
        and second_semantic
        and (
            first_semantic.parameters.get("useOccupancyBoxesForClearance", False)
            or second_semantic.parameters.get("useOccupancyBoxesForClearance", False)
        )
    )


def _overlapping_envelope_pairs(
    first: list[dict[str, Any]],
    second: list[dict[str, Any]],
    clearance: float,
    maximum_collisions: int | None = None,
) -> list[dict[str, Any]]:
    first, second = _prefilter_envelope_boxes(first, second)
    collisions: list[dict[str, Any]] = []
    for left in first:
        for right in second:
            if not _envelope_pair_is_eligible(left, right):
                continue
            box_clearances = [
                float(item["minimumClearanceMeters"])
                for item in (left, right)
                if item.get("minimumClearanceMeters") is not None
            ]
            effective_clearance = max(box_clearances) if box_clearances else clearance
            if _rectangles_touch_or_overlap(left["bounds"], right["bounds"], effective_clearance) and _intervals_touch_or_overlap(
                left["heightRangeMeters"], right["heightRangeMeters"], effective_clearance
            ):
                collisions.append(
                    {
                        "firstBox": left.get("id"),
                        "secondBox": right.get("id"),
                    }
                )
                if maximum_collisions is not None and len(collisions) >= maximum_collisions:
                    return collisions
    return collisions


def _envelope_pair_is_eligible(
    left: dict[str, Any],
    right: dict[str, Any],
) -> bool:
    left_partners = left.get("collisionPartnerCodes")
    right_partners = right.get("collisionPartnerCodes")
    if left_partners is not None and right.get("componentCode") not in left_partners:
        return False
    if right_partners is not None and left.get("componentCode") not in right_partners:
        return False
    return True


def _prefilter_envelope_boxes(
    first: list[dict[str, Any]],
    second: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Discard evidence boxes that explicitly target unrelated module codes."""
    first_codes = {
        str(item["componentCode"])
        for item in first
        if item.get("componentCode") is not None
    }
    second_codes = {
        str(item["componentCode"])
        for item in second
        if item.get("componentCode") is not None
    }

    def can_target(box: dict[str, Any], target_codes: set[str]) -> bool:
        partners = box.get("collisionPartnerCodes")
        if partners is None:
            return True
        return any(code in partners for code in target_codes)

    return (
        [item for item in first if can_target(item, second_codes)],
        [item for item in second if can_target(item, first_codes)],
    )


def _eligible_envelope_pair_count(
    first: list[dict[str, Any]],
    second: list[dict[str, Any]],
) -> int:
    """Count box pairs actually covered by partner-scoped occupancy evidence.

    Zero eligible pairs means that the sparse evidence says nothing about this
    module pair.  It must remain a CAD validation item and must never be
    reported as geometrically separated by the occupancy model.
    """
    first, second = _prefilter_envelope_boxes(first, second)
    return sum(
        1
        for left in first
        for right in second
        if _envelope_pair_is_eligible(left, right)
    )


def _has_eligible_envelope_pair(
    first: list[dict[str, Any]],
    second: list[dict[str, Any]],
) -> bool:
    first, second = _prefilter_envelope_boxes(first, second)
    return any(
        _envelope_pair_is_eligible(left, right)
        for left in first
        for right in second
    )


def _union_envelopes(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "bounds": (
            min(item["bounds"][0] for item in items),
            min(item["bounds"][1] for item in items),
            max(item["bounds"][2] for item in items),
            max(item["bounds"][3] for item in items),
        ),
        "heightRangeMeters": (
            min(item["heightRangeMeters"][0] for item in items),
            max(item["heightRangeMeters"][1] for item in items),
        ),
        "source": "unionMeasuredOccupancyBoxes",
    }


def _envelope_contained(
    outer: dict[str, Any],
    inner: dict[str, Any],
    clearance: float,
) -> bool:
    return bool(
        inner["bounds"][0] >= outer["bounds"][0] + clearance - 1e-9
        and inner["bounds"][1] >= outer["bounds"][1] + clearance - 1e-9
        and inner["bounds"][2] <= outer["bounds"][2] - clearance + 1e-9
        and inner["bounds"][3] <= outer["bounds"][3] - clearance + 1e-9
        and inner["heightRangeMeters"][0] >= outer["heightRangeMeters"][0] + clearance - 1e-9
        and inner["heightRangeMeters"][1] <= outer["heightRangeMeters"][1] - clearance + 1e-9
    )


def _transport_sweep_envelope(
    placement: Placement,
    footprint: Footprint,
    semantic: ModuleSemantic | None,
) -> dict[str, Any] | None:
    parameters = semantic.parameters if semantic else {}
    if parameters.get("transportSweepBoundsLocal") is None:
        return None
    return _configured_local_envelope(
        placement,
        footprint,
        semantic,
        bounds_parameter="transportSweepBoundsLocal",
        height_parameter="transportSweepHeightRangeMeters",
        configured_source="semanticTransportSweepBounds",
        default_source="fullTransportSweep",
    )


def _transport_static_keepout_envelope(
    placement: Placement,
    footprint: Footprint,
    semantic: ModuleSemantic | None,
) -> dict[str, Any] | None:
    parameters = semantic.parameters if semantic else {}
    if parameters.get("transportStaticKeepoutBoundsLocal") is None:
        return None
    return _configured_local_envelope(
        placement,
        footprint,
        semantic,
        bounds_parameter="transportStaticKeepoutBoundsLocal",
        height_parameter="transportStaticKeepoutHeightRangeMeters",
        configured_source="semanticTransportStaticKeepoutBounds",
        default_source="fullTransportStaticKeepout",
    )


def _configured_local_envelope(
    placement: Placement,
    footprint: Footprint,
    semantic: ModuleSemantic | None,
    *,
    bounds_parameter: str,
    height_parameter: str,
    configured_source: str,
    default_source: str,
) -> dict[str, Any]:
    parameters = semantic.parameters if semantic else {}
    raw_bounds = parameters.get(bounds_parameter)
    source = default_source
    if raw_bounds is not None:
        if isinstance(raw_bounds, dict):
            local = tuple(float(raw_bounds[name]) for name in ("minU", "minV", "maxU", "maxV"))
        elif isinstance(raw_bounds, (list, tuple)) and len(raw_bounds) == 4:
            local = tuple(float(value) for value in raw_bounds)
        else:
            raise ConstraintLayoutError(
                f"Component '{placement.component_name}' {bounds_parameter} must contain minU/minV/maxU/maxV."
            )
        if local[0] >= local[2] or local[1] >= local[3]:
            raise ConstraintLayoutError(
                f"Component '{placement.component_name}' {bounds_parameter} is empty or inverted."
            )
        corners = [
            _rotate_local_point(u, v, placement.rotation_quarters)
            for u in (local[0], local[2])
            for v in (local[1], local[3])
        ]
        bounds = (
            placement.anchor_u + min(point[0] for point in corners),
            placement.anchor_v + min(point[1] for point in corners),
            placement.anchor_u + max(point[0] for point in corners),
            placement.anchor_v + max(point[1] for point in corners),
        )
        source = configured_source
    else:
        bounds = placement.bounds
    raw_height = parameters.get(height_parameter)
    if raw_height is None:
        height_range = (0.0, footprint.height_normal)
    elif isinstance(raw_height, (list, tuple)) and len(raw_height) == 2:
        height_range = (float(raw_height[0]), float(raw_height[1]))
    else:
        raise ConstraintLayoutError(
            f"Component '{placement.component_name}' {height_parameter} must contain two values."
        )
    if height_range[0] < 0 or height_range[0] >= height_range[1]:
        raise ConstraintLayoutError(
            f"Component '{placement.component_name}' {height_parameter} is invalid."
        )
    return {
        "bounds": bounds,
        "heightRangeMeters": height_range,
        "source": source,
    }


def _portal_opening_height_range(
    semantic: ModuleSemantic | None,
    footprint: Footprint,
) -> tuple[float, float] | None:
    if not semantic or "portalOpening" not in semantic.regions:
        return None
    raw = semantic.parameters.get("portalOpeningHeightRangeMeters")
    if raw is None:
        return None
    if not isinstance(raw, (list, tuple)) or len(raw) != 2:
        raise ConstraintLayoutError(
            f"Portal '{semantic.component_name}' portalOpeningHeightRangeMeters must contain two values."
        )
    result = (float(raw[0]), float(raw[1]))
    if result[0] < 0 or result[0] >= result[1] or result[1] > footprint.height_normal + 1e-9:
        raise ConstraintLayoutError(
            f"Portal '{semantic.component_name}' portalOpeningHeightRangeMeters is outside its captured height."
        )
    return result


def _portal_pair(
    first_name: str,
    second_name: str,
    portal_pass_through: dict[str, tuple[str, ...]],
) -> tuple[str | None, str | None]:
    if second_name in portal_pass_through.get(first_name, ()):
        return first_name, second_name
    if first_name in portal_pass_through.get(second_name, ()):
        return second_name, first_name
    return None, None


def _intervals_touch_or_overlap(
    first: tuple[float, float],
    second: tuple[float, float],
    clearance: float,
) -> bool:
    return not (
        first[1] + clearance <= second[0]
        or second[1] + clearance <= first[0]
    )


def _is_allowed_portal_overlap(
    first_name: str,
    second_name: str,
    portal_pass_through: dict[str, tuple[str, ...]],
) -> bool:
    return (
        second_name in portal_pass_through.get(first_name, ())
        or first_name in portal_pass_through.get(second_name, ())
    )


def _is_service_cluster_projection_overlap_allowed(
    first_name: str,
    second_name: str,
    semantics: dict[str, ModuleSemantic],
) -> bool:
    first = semantics.get(first_name)
    second = semantics.get(second_name)
    if first is None or second is None:
        return False
    first_cluster = str(first.parameters.get("serviceClusterId") or "").strip()
    second_cluster = str(second.parameters.get("serviceClusterId") or "").strip()
    return bool(
        first_cluster
        and first_cluster == second_cluster
        and first.parameters.get("allowServiceClusterProjectionOverlap", False)
        and second.parameters.get("allowServiceClusterProjectionOverlap", False)
    )


def _is_configured_projection_overlap_allowed(
    first_name: str,
    second_name: str,
    semantics: dict[str, ModuleSemantic],
) -> bool:
    first = semantics.get(first_name)
    second = semantics.get(second_name)
    first_allowed = first.parameters.get("allowProjectedOverlapWith", []) if first else []
    second_allowed = second.parameters.get("allowProjectedOverlapWith", []) if second else []
    if isinstance(first_allowed, str):
        first_allowed = [first_allowed]
    if isinstance(second_allowed, str):
        second_allowed = [second_allowed]
    return (
        any(str(name).strip().lower() == second_name.lower() for name in first_allowed)
        or any(str(name).strip().lower() == first_name.lower() for name in second_allowed)
    )


def _is_post_solve_projection_overlap_allowed(
    first_name: str,
    second_name: str,
    semantics: dict[str, ModuleSemantic],
) -> bool:
    first = semantics.get(first_name)
    second = semantics.get(second_name)
    first_allowed = first.parameters.get("allowPostSolveProjectedOverlapWith", []) if first else []
    second_allowed = second.parameters.get("allowPostSolveProjectedOverlapWith", []) if second else []
    if isinstance(first_allowed, str):
        first_allowed = [first_allowed]
    if isinstance(second_allowed, str):
        second_allowed = [second_allowed]
    return (
        any(str(name).strip().lower() == second_name.lower() for name in first_allowed)
        or any(str(name).strip().lower() == first_name.lower() for name in second_allowed)
    )


def _contains_bounds(
    outer: tuple[float, float, float, float],
    inner: tuple[float, float, float, float],
) -> bool:
    return (
        inner[0] >= outer[0] - 1e-9
        and inner[1] >= outer[1] - 1e-9
        and inner[2] <= outer[2] + 1e-9
        and inner[3] <= outer[3] + 1e-9
    )


def _inset_bounds(
    bounds: tuple[float, float, float, float],
    margin_long: float,
    margin_short: float,
    long_axis: str,
) -> tuple[float, float, float, float]:
    if long_axis == "u":
        return (
            bounds[0] + margin_long,
            bounds[1] + margin_short,
            bounds[2] - margin_long,
            bounds[3] - margin_short,
        )
    return (
        bounds[0] + margin_short,
        bounds[1] + margin_long,
        bounds[2] - margin_short,
        bounds[3] - margin_long,
    )


def _ratio(value: float, label: str) -> float:
    if not 0.0 < value <= 1.0:
        raise ConstraintLayoutError(f"{label} ratio must be in (0, 1].")
    return value


def _rectangles_touch_or_overlap(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
    clearance: float,
) -> bool:
    return not (
        first[2] + clearance <= second[0]
        or second[2] + clearance <= first[0]
        or first[3] + clearance <= second[1]
        or second[3] + clearance <= first[1]
    )


def _rectangle_distance(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> float:
    """Euclidean edge-to-edge distance; zero means the projections touch or overlap."""
    delta_u = max(second[0] - first[2], first[0] - second[2], 0.0)
    delta_v = max(second[1] - first[3], first[1] - second[3], 0.0)
    return math.hypot(delta_u, delta_v)


def _intersection_area(first: tuple[float, float, float, float], second: tuple[float, float, float, float]) -> float:
    width = max(0.0, min(first[2], second[2]) - max(first[0], second[0]))
    height = max(0.0, min(first[3], second[3]) - max(first[1], second[1]))
    return width * height


def _overlap_ratio(
    inner: tuple[float, float, float, float],
    outer: tuple[float, float, float, float],
) -> float:
    return _intersection_area(inner, outer) / max(_area(inner), 1e-12)


def _bounds_overhang(
    bounds: tuple[float, float, float, float],
    container: tuple[float, float, float, float],
) -> dict[str, float]:
    return {
        "lowU": max(0.0, container[0] - bounds[0]),
        "lowV": max(0.0, container[1] - bounds[1]),
        "highU": max(0.0, bounds[2] - container[2]),
        "highV": max(0.0, bounds[3] - container[3]),
    }


def _maximum_bounds_overhang(
    bounds: tuple[float, float, float, float],
    container: tuple[float, float, float, float],
) -> float:
    return max(_bounds_overhang(bounds, container).values())


def _axis_overhang(bounds: tuple[float, float, float, float], container: tuple[float, float, float, float], axis: str) -> float:
    amount = max(0.0, _axis_min(container, axis) - _axis_min(bounds, axis)) + max(0.0, _axis_max(bounds, axis) - _axis_max(container, axis))
    return amount / max(_axis_size(container, axis), 1e-12)


def _axis_min(bounds: tuple[float, float, float, float], axis: str) -> float:
    return bounds[0] if axis == "u" else bounds[1]


def _axis_max(bounds: tuple[float, float, float, float], axis: str) -> float:
    return bounds[2] if axis == "u" else bounds[3]


def _axis_center(bounds: tuple[float, float, float, float], axis: str) -> float:
    return (_axis_min(bounds, axis) + _axis_max(bounds, axis)) / 2.0


def _axis_size(bounds: tuple[float, float, float, float], axis: str) -> float:
    return _axis_max(bounds, axis) - _axis_min(bounds, axis)


def _other_axis(axis: str) -> str:
    return "v" if axis == "u" else "u"


def _width(bounds: tuple[float, float, float, float]) -> float:
    return bounds[2] - bounds[0]


def _height(bounds: tuple[float, float, float, float]) -> float:
    return bounds[3] - bounds[1]


def _area(bounds: tuple[float, float, float, float]) -> float:
    return max(0.0, _width(bounds)) * max(0.0, _height(bounds))


def _center(bounds: tuple[float, float, float, float]) -> tuple[float, float]:
    return (bounds[0] + bounds[2]) / 2.0, (bounds[1] + bounds[3]) / 2.0


def _contains_point(bounds: tuple[float, float, float, float], point: tuple[float, float]) -> bool:
    return bounds[0] <= point[0] <= bounds[2] and bounds[1] <= point[1] <= bounds[3]


def _normalize_angle(value: float) -> float:
    normalized = (value + 180.0) % 360.0 - 180.0
    return 180.0 if math.isclose(normalized, -180.0) else normalized


def _target_orientation_frame(
    component: dict[str, Any],
    frame: dict[str, Any],
    rotation_quarters: int,
) -> dict[str, list[float]] | None:
    """Preserve the captured rigid frame, including roll, for deterministic Replay.

    Layout2D's thetaAxis only describes one projected direction and cannot distinguish
    a 180-degree roll around that axis.  The full target triad removes that ambiguity.
    """
    raw_axes = (
        component.get("componentXAxis"),
        component.get("componentYAxis"),
        component.get("componentZAxis"),
    )
    if any(not isinstance(axis, list) or len(axis) < 3 for axis in raw_axes):
        return None
    normal = _unit(_vector3(frame.get("normal"), "baseFrame.normal"))
    angle_radians = math.radians((rotation_quarters % 4) * 90.0)
    axes = [
        _rotate_vector_about_axis(_vector3(axis, "component axis"), normal, angle_radians)
        for axis in raw_axes
    ]
    return {
        "targetXAxisWorld": list(_unit(axes[0])),
        "targetYAxisWorld": list(_unit(axes[1])),
        "targetZAxisWorld": list(_unit(axes[2])),
    }


def _rotate_vector_about_axis(
    vector: tuple[float, float, float],
    axis: tuple[float, float, float],
    angle_radians: float,
) -> tuple[float, float, float]:
    cosine = math.cos(angle_radians)
    sine = math.sin(angle_radians)
    cross = (
        axis[1] * vector[2] - axis[2] * vector[1],
        axis[2] * vector[0] - axis[0] * vector[2],
        axis[0] * vector[1] - axis[1] * vector[0],
    )
    projection = _dot(axis, vector) * (1.0 - cosine)
    return (
        vector[0] * cosine + cross[0] * sine + axis[0] * projection,
        vector[1] * cosine + cross[1] * sine + axis[1] * projection,
        vector[2] * cosine + cross[2] * sine + axis[2] * projection,
    )


def _vector3(value: Any, label: str) -> tuple[float, float, float]:
    if not isinstance(value, list) or len(value) < 3:
        raise ConstraintLayoutError(f"Capture JSON does not contain {label}.")
    return float(value[0]), float(value[1]), float(value[2])


def _unit(value: tuple[float, float, float]) -> tuple[float, float, float]:
    length = math.sqrt(_dot(value, value))
    if length < 1e-12:
        raise ConstraintLayoutError("Base-frame axis has zero length.")
    return value[0] / length, value[1] / length, value[2] / length


def _subtract(first: tuple[float, float, float], second: tuple[float, float, float]) -> tuple[float, float, float]:
    return first[0] - second[0], first[1] - second[1], first[2] - second[2]


def _dot(first: tuple[float, float, float], second: tuple[float, float, float]) -> float:
    return first[0] * second[0] + first[1] * second[1] + first[2] * second[2]
