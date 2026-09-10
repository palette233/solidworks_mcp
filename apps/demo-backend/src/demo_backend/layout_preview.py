from __future__ import annotations

import copy
import itertools
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .assembly_sequence import (
    AssemblySequenceConfigurationError,
    build_assembly_sequence_plan,
)
from .constraint_layout import ConstraintLayoutOptions, generate_constraint_layout
from .pipeline_timing import PipelineTiming
from .project01_layout import solve_project01_top3
from .project02_fixed_environment import (
    Project02FixedEnvironmentError,
    attach_project02_fixed_environment,
    augment_project02_collision_policy,
)
from .project03_layout import solve_project03_top3


CASE_DEFINITIONS = {
    "project01": {
        "title": "项目01 · 通用顺序约束Top-3",
        "solutionPath": "demo/layout_previews/project01_solution.json",
        "previewPath": "demo/layout_previews/project01_preview.json",
        "selectedSolutionPath": "demo/layout_previews/project01_selected_solution.json",
        "verificationPlanPath": "demo/layout_previews/project01_verification_plan.json",
    },
    "project02": {
        "title": "项目02 · 通用约束去原型求解",
        "requestPath": "demo/FL9A24D062A000_real_process_request.json",
        "solutionPath": "demo/layout_previews/project02_solution.json",
        "previewPath": "demo/layout_previews/project02_preview.json",
        "selectedSolutionPath": "demo/layout_previews/project02_selected_solution.json",
        "verificationPlanPath": "demo/layout_previews/project02_verification_plan.json",
    },
    "project03": {
        "title": "项目03 · 通用顺序约束Top-3",
        "solutionPath": "demo/layout_previews/project03_solution.json",
        "previewPath": "demo/layout_previews/project03_preview.json",
        "selectedSolutionPath": "demo/layout_previews/project03_selected_solution.json",
        "verificationPlanPath": "demo/layout_previews/project03_verification_plan.json",
    }
}

MODULE_LABELS = {
    "frame": "箱体/回流固定环境",
    "positioning": "翻转定位模组",
    "service": "组合功能模组",
    "gantry": "龙门模组",
    "transport": "传输模组",
    "scanner": "扫描模组",
    "ccd": "CCD模组",
    "calibration": "校准模组",
    "cleaning": "清洁/称重模组",
    "weighing": "称重模组",
    "glue_supply": "供胶组件",
    "functional": "排胶/功能模组",
}

MODULE_COLORS = {
    "frame": "#475569",
    "positioning": "#9333ea",
    "service": "#16a34a",
    "gantry": "#2563eb",
    "transport": "#0f766e",
    "scanner": "#7c3aed",
    "ccd": "#0891b2",
    "calibration": "#d97706",
    "cleaning": "#16a34a",
    "weighing": "#4d7c0f",
    "glue_supply": "#be185d",
    "functional": "#dc2626",
}


class LayoutPreviewError(ValueError):
    pass


PROJECT02_SOLVE_PROFILES = ("calibrated", "reduced-prototype")


def apply_project02_solve_profile(
    request: dict[str, Any],
    profile: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply an auditable Project 02 dependency profile without editing its source JSON.

    ``reduced-prototype`` is intentionally not described as fully prototype-free:
    it removes prototype layout-copy mechanisms and prototype-calibrated relative
    pose windows while retaining the explicitly packaged Project 02 engineering
    baselines needed for a useful coarse layout. A preceding source-independent
    solver result may still be used as an unlocked deterministic candidate seed.
    """
    if profile not in PROJECT02_SOLVE_PROFILES:
        raise LayoutPreviewError(
            f"Unknown Project 02 solve profile '{profile}'. Expected one of "
            f"{', '.join(PROJECT02_SOLVE_PROFILES)}."
        )
    profiled = copy.deepcopy(request)
    metadata: dict[str, Any] = {
        "name": profile,
        "sourceTopLevelPoseUsed": False,
        "removedWarmStart": False,
        "removedConstraintIds": [],
        "retainedPrototypeBaselineCategories": [],
    }
    if profile == "calibrated":
        metadata["description"] = (
            "Current Project 02 calibrated solve. Source top-level poses are not read, "
            "but the previous solver Replay and prototype-calibrated relative windows remain."
        )
        return profiled, metadata

    policy = profiled.setdefault("sourceIndependentPolicy", {})
    solver_generated_warm_start = policy.pop(
        "solverGeneratedWarmStartReplayResultPath", None
    )
    metadata["removedWarmStart"] = bool(
        policy.get("warmStartReplayResultPath") or policy.get("warmStartKind")
    )
    policy.pop("warmStartReplayResultPath", None)
    policy["warmStartKind"] = "none"
    policy["warmStartLockedComponents"] = []
    if solver_generated_warm_start:
        # A previous source-independent solution may seed candidate ordering,
        # but it never locks a component and does not restore removed
        # prototype-relative constraints.
        policy["warmStartReplayResultPath"] = solver_generated_warm_start
        policy["warmStartKind"] = "previousSolverReplayResult"
    # This exact A700 offset was introduced to preserve a prior accepted pose.
    # The generic service-side, reach, access and collision rules remain active.
    policy.pop("functionalAnchorBiasV", None)

    removed_types = {"relativeAnchorWindow", "relativeAnchorExclusionWindow"}
    kept_constraints: list[dict[str, Any]] = []
    removed_ids: list[str] = []
    for constraint in profiled.get("processConstraints") or []:
        if (
            constraint.get("type") in removed_types
            and not constraint.get("retainInReducedPrototype", False)
        ):
            removed_ids.append(str(constraint.get("id") or "unnamed"))
        else:
            kept_constraints.append(constraint)
    profiled["processConstraints"] = kept_constraints
    metadata.update(
        {
            "description": (
                "No source-pose copy and no prototype Replay warm start. A previous "
                "source-independent solver result may seed candidate ordering without locking "
                "any pose. Prototype-calibrated top-level pose windows are removed, while "
                "explicitly opted-in module-local "
                "interface baselines may remain when backed by geometry and B-Rep evidence. "
                "Project-specific engineering baselines remain provisional inputs for coarse layout."
            ),
            "solverGeneratedWarmStartUsed": bool(solver_generated_warm_start),
            "solverGeneratedWarmStartReplayResultPath": solver_generated_warm_start,
            "removedConstraintIds": removed_ids,
            "retainedPrototypeBaselineCategories": [
                "A600 installation frame and A800 installation anchor",
                "scanner/barcode point geometry and coarse working-distance band",
                "dual-valve reach estimate",
                "service points and protected maintenance spaces",
                "module-local candidate refinement and placement heuristics",
                "explicitly retained module-local interface windows backed by geometry/B-Rep evidence",
            ],
        }
    )
    return profiled, metadata


def _load_solver_warm_start(
    request: dict[str, Any],
    workspace: Path | None,
) -> tuple[dict[str, Any], ...]:
    policy = request.get("sourceIndependentPolicy", {})
    value = policy.get("warmStartReplayResultPath")
    if not value:
        return ()
    if policy.get("warmStartKind") != "previousSolverReplayResult":
        raise LayoutPreviewError(
            "warmStartReplayResultPath requires warmStartKind='previousSolverReplayResult'."
        )
    path = Path(str(value))
    if not path.is_absolute():
        path = (workspace or Path.cwd()) / path
    path = path.resolve()
    if not path.is_file():
        raise LayoutPreviewError(f"Solver warm-start result does not exist: {path}")
    document = json.loads(path.read_text(encoding="utf-8"))
    components = document.get("components")
    if not isinstance(components, list):
        components = next(
            (
                step.get("payload", {}).get("components")
                for step in document.get("steps", [])
                if step.get("tool") == "apply_captured_common_base_layout"
                and isinstance(step.get("payload", {}).get("components"), list)
            ),
            None,
        )
    if not isinstance(components, list) or not components:
        raise LayoutPreviewError(
            f"Solver warm-start result has no durable Replay layout: {path}"
        )
    gantry_name = next(
        (
            name
            for name, role in request.get("roleOverrides", {}).items()
            if role == "gantry"
        ),
        None,
    )
    if gantry_name is None:
        gantry_name = next(
            (
                name
                for name, semantic in request.get("moduleSemantics", {}).items()
                if semantic.get("moduleType") == "gantry"
            ),
            None,
        )
    gantry_item = next(
        (item for item in components if item.get("componentName") == gantry_name),
        None,
    )
    gantry_layout = gantry_item.get("layout2d") if isinstance(gantry_item, dict) else None
    if not isinstance(gantry_layout, dict):
        raise LayoutPreviewError(
            f"Solver warm-start result has no gantry layout for '{gantry_name}': {path}"
        )
    gantry_x = float(gantry_layout["x"])
    gantry_y = float(gantry_layout["y"])
    normalized: list[dict[str, Any]] = []
    for item in components:
        layout = item.get("layout2d") if isinstance(item, dict) else None
        name = item.get("componentName") if isinstance(item, dict) else None
        if not name or not isinstance(layout, dict):
            continue
        normalized.append(
            {
                "componentName": str(name),
                "x": float(layout["x"]) - gantry_x,
                "y": float(layout["y"]) - gantry_y,
                "thetaDegrees": float(layout.get("thetaDegrees", 0.0)),
                "sourcePath": str(path),
            }
        )
    return tuple(normalized)


def build_source_independent_options(
    request: dict[str, Any],
    workspace: Path | None = None,
) -> ConstraintLayoutOptions:
    """Translate a case request into the shared source-position-independent solver options."""
    semantics = copy.deepcopy(request.get("moduleSemantics", {}))
    policy = request.get("sourceIndependentPolicy", {})
    sequence_policy = request.get("assemblySequencePolicy", {})
    case_anchor_world, case_anchor_metadata = _resolve_case_anchor_target_world(
        policy,
        sequence_policy,
        workspace,
    )

    static_collision_policy = _compile_static_collision_policy(
        request,
        list(semantics),
    )
    _apply_static_collision_policy_to_semantics(
        semantics,
        static_collision_policy,
    )

    occupancy_value = request.get("structuralOccupancyPath")
    if occupancy_value:
        occupancy_path = Path(str(occupancy_value))
        if not occupancy_path.is_absolute():
            occupancy_path = (workspace or Path.cwd()) / occupancy_path
        occupancy_path = occupancy_path.resolve()
        if not occupancy_path.is_file():
            raise LayoutPreviewError(
                f"Structural occupancy capture does not exist: {occupancy_path}"
            )
        occupancy = json.loads(occupancy_path.read_text(encoding="utf-8"))
        for component_name, item in (occupancy.get("components") or {}).items():
            boxes = item.get("boxes") if isinstance(item, dict) else None
            if not isinstance(boxes, list) or not boxes:
                raise LayoutPreviewError(
                    f"Structural occupancy for '{component_name}' has no boxes."
                )
            parameters = semantics.setdefault(component_name, {}).setdefault(
                "parameters", {}
            )
            parameters["occupancyBoxesLocal"] = boxes
            parameters["useOccupancyBoxesForClearance"] = True
            parameters["structuralOccupancySource"] = str(occupancy_path)
            parameters["structuralOccupancyBoxCount"] = len(boxes)
            parameters["occupancyBoxesHardClearance"] = bool(
                item.get("hardClearance", True)
            )

    glue_supplies = [
        item for item in semantics.values() if item.get("moduleType") == "glue_supply"
    ]
    for item in glue_supplies:
        item.setdefault("preferredSide", "low")

    # The engineer's service-placement rule is intentionally inactive until
    # both the operation face is mapped into the legacy solver's low/high axis
    # and the available/required widths are confirmed.  Once those measurements
    # exist, the same generic branch chooses the operation side or its opposite.
    operation_face = sequence_policy.get("operationFace") or {}
    service_rule = sequence_policy.get("servicePlacementRule") or {}
    side_capacity = sequence_policy.get("operationSideCapacity") or {}
    operation_solver_side = str(
        operation_face.get("legacySolverSide") or "unknown"
    ).lower()
    confirmed_side_branch = bool(
        operation_face.get("confirmed")
        and service_rule.get("confirmed")
        and side_capacity.get("confirmed")
        and operation_solver_side in {"low", "high"}
        and isinstance(side_capacity.get("availableWidthMeters"), (int, float))
        and isinstance(side_capacity.get("requiredWidthMeters"), (int, float))
    )
    estimated_side_branch = bool(
        operation_face.get("confirmed")
        and service_rule.get("confirmed")
        and side_capacity.get("estimateAcceptedForCoarseLayout")
        and str(side_capacity.get("estimatedSelectedSide") or "").lower()
        in {"front", "back"}
        and str(side_capacity.get("legacySolverSide") or operation_solver_side).lower()
        in {"low", "high"}
    )
    side_branch_ready = confirmed_side_branch or estimated_side_branch
    if side_branch_ready:
        if confirmed_side_branch:
            selected_side = operation_solver_side
            if float(side_capacity["availableWidthMeters"]) < float(
                side_capacity["requiredWidthMeters"]
            ):
                selected_side = "high" if operation_solver_side == "low" else "low"
            selection_source = "operationFaceCapacityBranch"
        else:
            selected_side = str(
                side_capacity.get("legacySolverSide") or operation_solver_side
            ).lower()
            if (
                str(side_capacity.get("estimatedSelectedSide")).lower()
                != str(operation_face.get("side") or "").lower()
            ):
                selected_side = "high" if selected_side == "low" else "low"
            selection_source = "operationFaceNonConvexCapacityEstimate"
        service_codes = {
            str(code).upper()
            for code in service_rule.get("moduleCodes", [])
            if str(code).strip()
        }
        for component_name, semantic in semantics.items():
            if _component_code(component_name) not in service_codes:
                continue
            semantic["preferredSide"] = selected_side
            parameters = semantic.setdefault("parameters", {})
            parameters["serviceSideSelectionResult"] = selected_side
            parameters["serviceSideSelectionSource"] = selection_source
            parameters["serviceSideSelectionProvisional"] = not confirmed_side_branch

    transport_bias_v = policy.get("transportWorkEnvelopeBiasV")
    if transport_bias_v is not None:
        for item in semantics.values():
            if item.get("moduleType") == "transport":
                item.setdefault("parameters", {})["workEnvelopeBiasV"] = float(
                    transport_bias_v
                )

    for name in policy.get("forbidTransportProjectionOverlapComponents", []):
        parameters = semantics.setdefault(name, {}).setdefault("parameters", {})
        parameters["allowTransportProjectionOverlap"] = False
        parameters["sourceIndependentTransportOverlapPolicy"] = "forbidden"

    for name, bias_v in policy.get("functionalAnchorBiasV", {}).items():
        semantics.setdefault(name, {}).setdefault("parameters", {})[
            "sourceIndependentAnchorBiasV"
        ] = float(bias_v)

    return ConstraintLayoutOptions(
        role_overrides=request.get("roleOverrides", {}),
        margin_ratios=tuple(request.get("marginRatios", [0.05, 0.03, 0.01, 0.0])),
        minimum_clearance_meters=float(request.get("minimumClearanceMeters", 0.01)),
        glue_distance_meters=float(request.get("glueDistanceMeters", 0.05)),
        allow_rotation=bool(request.get("allowRotation", False)),
        portal_pass_through={
            name: tuple(values)
            for name, values in request.get("portalPassThrough", {}).items()
        },
        portal_opening_width_ratio=float(request.get("portalOpeningWidthRatio", 0.8)),
        portal_opening_height_ratio=float(request.get("portalOpeningHeightRatio", 0.75)),
        module_semantics=semantics,
        process_constraints=tuple(request.get("processConstraints", [])),
        auto_generate_process_constraints=bool(
            request.get("autoGenerateProcessConstraints", True)
        ),
        provisional_components=tuple(request.get("provisionalComponents", [])),
        prefer_source_layout=False,
        source_position_independent=True,
        allowed_projected_overlap_pairs=tuple(
            tuple(pair) for pair in request.get("allowedProjectedOverlapPairs", [])
        ),
        minimum_transport_gantry_overlap_ratio=float(
            request.get("minimumTransportGantryOverlapRatio", 0.5)
        ),
        minimum_portal_gantry_overlap_ratio=float(
            request.get("minimumPortalGantryOverlapRatio", 0.5)
        ),
        minimum_functional_gantry_overlap_ratio=float(
            policy.get(
                "minimumFunctionalGantryOverlapRatio",
                request.get("minimumFunctionalGantryOverlapRatio", 0.0),
            )
        ),
        minimum_functional_gantry_boundary_clearance_meters=float(
            policy.get("minimumFunctionalGantryBoundaryClearanceMeters", 0.0)
        ),
        maximum_transport_gantry_center_offset_meters=(
            float(policy["maximumTransportGantryCenterOffsetMeters"])
            if policy.get("maximumTransportGantryCenterOffsetMeters") is not None
            else None
        ),
        maximum_portal_gantry_center_offset_meters=(
            float(policy["maximumPortalGantryCenterOffsetMeters"])
            if policy.get("maximumPortalGantryCenterOffsetMeters") is not None
            else None
        ),
        maximum_portal_gantry_overhang_meters=(
            float(policy["maximumPortalGantryOverhangMeters"])
            if policy.get("maximumPortalGantryOverhangMeters") is not None
            else None
        ),
        require_reach_inside_gantry=bool(
            request.get("requireReachInsideGantry", True)
        ),
        joint_candidate_search=bool(policy.get("jointCandidateSearch", False)),
        joint_candidate_limit=int(policy.get("jointCandidateLimit", 18)),
        maximum_layout_solutions=int(policy.get("maximumLayoutSolutions", 3)),
        warm_start_placements=_load_solver_warm_start(request, workspace),
        warm_start_locked_components=tuple(
            str(name) for name in policy.get("warmStartLockedComponents", [])
        ),
        joint_search_time_limit_seconds=(
            float(policy["jointSearchTimeLimitSeconds"])
            if policy.get("jointSearchTimeLimitSeconds") is not None
            else None
        ),
        case_anchor_component_name=(
            str(policy["caseAnchorComponentName"])
            if (
                policy.get("caseAnchorEnabled")
                or policy.get("caseSpecificPrototypeAnchor")
            )
            and policy.get("caseAnchorComponentName")
            else None
        ),
        case_anchor_target_world=case_anchor_world,
        case_anchor_target_kind=str(
            case_anchor_metadata.get("targetKind") or "sourceCapture"
        ),
        case_anchor_target_source=case_anchor_metadata.get("targetSource"),
        case_anchor_target_prototype_derived=bool(
            case_anchor_metadata.get("prototypeDerivedParameter")
        ),
        case_anchor_scope=str(
            case_anchor_metadata.get("scope") or "caseSpecific"
        ),
    )


def _resolve_case_anchor_target_world(
    policy: dict[str, Any],
    sequence_policy: dict[str, Any],
    workspace: Path | None,
) -> tuple[tuple[float, float, float] | None, dict[str, Any]]:
    """Resolve an explicit installation-frame anchor without reading its source pose."""
    target_kind = str(policy.get("caseAnchorTargetKind") or "sourceCapture")
    metadata = {
        "targetKind": target_kind,
        "targetSource": policy.get("caseAnchorTargetSource"),
        "prototypeDerivedParameter": bool(
            policy.get("caseAnchorTargetPrototypeDerived", False)
        ),
        "scope": str(policy.get("caseAnchorScope") or "caseSpecific"),
    }
    if target_kind == "sourceCapture":
        return None, metadata
    if target_kind != "installationFramePoint":
        raise LayoutPreviewError(
            f"Unsupported caseAnchorTargetKind '{target_kind}'."
        )

    raw_point = policy.get("caseAnchorTargetFrameMeters")
    if not isinstance(raw_point, list) or len(raw_point) != 3:
        raise LayoutPreviewError(
            "caseAnchorTargetFrameMeters must contain three numbers for installationFramePoint."
        )
    try:
        point = tuple(float(value) for value in raw_point)
    except (TypeError, ValueError) as exc:
        raise LayoutPreviewError(
            "caseAnchorTargetFrameMeters must contain three finite numbers."
        ) from exc
    if not all(math.isfinite(value) for value in point):
        raise LayoutPreviewError(
            "caseAnchorTargetFrameMeters must contain three finite numbers."
        )

    frame_policy = sequence_policy.get("installationFrame") or {}
    evidence_value = frame_policy.get("evidencePath")
    if not evidence_value:
        raise LayoutPreviewError(
            "assemblySequencePolicy.installationFrame.evidencePath is required for installationFramePoint."
        )
    evidence_path = Path(str(evidence_value))
    if not evidence_path.is_absolute():
        evidence_path = (workspace or Path.cwd()) / evidence_path
    evidence_path = evidence_path.resolve()
    if not evidence_path.is_file():
        raise LayoutPreviewError(
            f"Installation-frame evidence does not exist: {evidence_path}"
        )
    frame = json.loads(evidence_path.read_text(encoding="utf-8"))
    if frame.get("success") is not True:
        raise LayoutPreviewError("Installation-frame evidence is not successful.")
    expected_name = str(policy.get("caseAnchorTargetFrameName") or "").strip()
    actual_name = str(frame.get("frameName") or "").strip()
    if expected_name and expected_name != actual_name:
        raise LayoutPreviewError(
            f"Case anchor frame mismatch: expected '{expected_name}', got '{actual_name}'."
        )

    origin = frame.get("originWorldMeters")
    axes = frame.get("axesWorld") or {}
    x_axis = axes.get("xIntoMachine")
    y_axis = axes.get("yTransportLateral")
    z_axis = axes.get("zUp")
    vectors = (origin, x_axis, y_axis, z_axis)
    if any(not isinstance(value, list) or len(value) != 3 for value in vectors):
        raise LayoutPreviewError("Installation-frame evidence has incomplete origin or axes.")
    try:
        world = tuple(
            float(origin[index])
            + point[0] * float(x_axis[index])
            + point[1] * float(y_axis[index])
            + point[2] * float(z_axis[index])
            for index in range(3)
        )
    except (TypeError, ValueError) as exc:
        raise LayoutPreviewError("Installation-frame evidence contains non-numeric values.") from exc
    if not all(math.isfinite(value) for value in world):
        raise LayoutPreviewError("Resolved case anchor world point is not finite.")
    metadata["targetSource"] = metadata["targetSource"] or str(evidence_path)
    return world, metadata


def solve_case_preview(
    workspace: Path,
    case_id: str,
    *,
    persist: bool = True,
    profile: str = "calibrated",
    request_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    definition = CASE_DEFINITIONS.get(case_id)
    if definition is None:
        raise LayoutPreviewError(f"Unknown layout case '{case_id}'.")

    if case_id in {"project01", "project03"}:
        readiness_path = workspace / f"demo/layout_previews/{case_id}_migration_readiness.json"
        if not readiness_path.is_file():
            raise LayoutPreviewError(f"{case_id} migration readiness has not been generated.")
        readiness = json.loads(readiness_path.read_text(encoding="utf-8-sig"))
        if readiness.get("top3SolveReady") is not True:
            raise LayoutPreviewError(
                f"{case_id} Top-3 gate is blocked by: "
                + ", ".join(
                    list(readiness.get("missingRequiredEvidence") or [])
                    + list(readiness.get("partialEvidence") or [])
                )
            )

        def load(relative: str) -> dict[str, Any]:
            return json.loads((workspace / relative).read_text(encoding="utf-8-sig"))

        solver = solve_project01_top3 if case_id == "project01" else solve_project03_top3
        generated = solver(
            load(f"demo/layout_previews/{case_id}_module_occupancy.json"),
            load(f"demo/layout_previews/{case_id}_work_positions.json"),
            load(f"demo/layout_previews/{case_id}_service_points.json"),
            load(f"demo/layout_previews/{case_id}_dual_valve_reach.json"),
            load(f"demo/layout_previews/{case_id}_scanner_geometry.json"),
        )
        solution_path = (workspace / definition["solutionPath"]).resolve()
        preview_path = (workspace / definition["previewPath"]).resolve()
        preview = build_preview_payload(
            generated,
            case_id=case_id,
            title=definition["title"],
            solution_path=solution_path,
            preview_path=preview_path,
        )
        if case_id == "project01":
            review_items = [
                {"severity": "pass", "title": "项目01顺序求解", "message": "SS00/FF00安装基准固定，SM00保持扫码几何，GN00/BD00/GJ00先排布，再由8个目标反求LM00+ZZ00公共覆盖。"},
                {"severity": "info", "title": "Top-3候选差异", "message": "候选1为项目01原型参数下的最小位移基线；候选2/3分别对综合功能模组或标定模组作30 mm离散调整，均重新通过同一套硬约束筛选。"},
                {"severity": "warning", "title": "当前只到粗布局", "message": "操作面、扫描光束和双阀刻度行程采用项目01原型基线；选中候选后才允许Replay和9组条件B-rep。"},
            ]
        else:
            review_items = [
                {"severity": "pass", "title": "项目03顺序求解", "message": "AE00安装基准固定，AD00/AI00保持工作与扫描关系，AG00/AH00/AJ00先排布，再反求AB00+AC00公共覆盖。"},
                {"severity": "info", "title": "项目03自主选案原则", "message": "优先选择满足全部硬约束、严格AABB为零命中且总位移最小的候选；分数相同时再比较条件宽相数量与服务区分散度。"},
                {"severity": "warning", "title": "粗布局证据边界", "message": "20 mm安装边缘容差、100 mm扫描光束与双阀尺度来自项目03原型；精确操作面、维护空间及身份头角色仍待工程确认。"},
            ]
        preview["reviewItems"] = [*review_items, *preview.get("reviewItems", [])]
        if persist:
            solution_path.parent.mkdir(parents=True, exist_ok=True)
            solution_path.write_text(
                json.dumps(generated, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            preview_path.write_text(
                json.dumps(preview, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            selected_solution_path = (workspace / definition["selectedSolutionPath"]).resolve()
            selected_solution_path.write_text(
                json.dumps(
                    {
                        "caseId": case_id,
                        "status": "awaiting_visual_selection",
                        "sourcePreviewGeneratedAt": preview["generatedAt"],
                        "message": f"No {case_id} candidate is selected; Replay remains blocked.",
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            verification_plan_path = (workspace / definition["verificationPlanPath"]).resolve()
            verification_plan_path.write_text(
                json.dumps(
                    _verification_plan(
                        case_id=case_id,
                        generated_at=preview["generatedAt"],
                        status="awaiting_visual_review",
                        static_collision_policy=generated["constraintPlan"]["staticCollisionPolicy"],
                    ),
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        return preview

    timing = PipelineTiming(f"{case_id}.solve-preview")
    with timing.stage("load-and-profile-request", profile=profile):
        request_path = (workspace / definition["requestPath"]).resolve()
        if request_override is None:
            if not request_path.is_file():
                raise LayoutPreviewError(f"Case request does not exist: {request_path}")
            request = json.loads(request_path.read_text(encoding="utf-8"))
        else:
            request = copy.deepcopy(request_override)
        request, solve_profile = apply_project02_solve_profile(request, profile)

    with timing.stage("load-captured-geometry"):
        geometry_value = request.get("geometryCapturePath")
        if not geometry_value:
            raise LayoutPreviewError(f"Case '{case_id}' has no geometryCapturePath.")
        geometry_path = Path(str(geometry_value))
        if not geometry_path.is_absolute():
            geometry_path = workspace / geometry_path
        geometry_path = geometry_path.resolve()
        if not geometry_path.is_file():
            raise LayoutPreviewError(f"Captured geometry does not exist: {geometry_path}")
        capture = json.loads(geometry_path.read_text(encoding="utf-8"))

    with timing.stage("build-source-independent-options"):
        options = build_source_independent_options(request, workspace)
    with timing.stage("constraint-layout-solve"):
        generated = generate_constraint_layout(capture, options)
    with timing.stage("attach-a600-fixed-environment"):
        try:
            generated = attach_project02_fixed_environment(
                workspace,
                request,
                generated,
            )
        except (Project02FixedEnvironmentError, OSError, ValueError, json.JSONDecodeError) as exc:
            raise LayoutPreviewError(f"A600 fixed environment is invalid: {exc}") from exc
    with timing.stage("compile-static-collision-policy"):
        generated["constraintPlan"]["sourceIndependentPolicy"] = request.get(
            "sourceIndependentPolicy", {}
        )
        movable_names = [
            item["componentName"]
            for item in generated.get("components") or []
            if not bool(
                (item.get("constraintPlacement") or {}).get("fixedEnvironment")
            )
        ]
        static_collision_policy = _compile_static_collision_policy(
            request,
            movable_names,
        )
        static_collision_policy = augment_project02_collision_policy(
            static_collision_policy,
            generated,
        )
        generated["constraintPlan"]["staticCollisionPolicy"] = static_collision_policy
    with timing.stage("build-assembly-sequence-plan"):
        try:
            assembly_sequence_plan = build_assembly_sequence_plan(
                workspace,
                request,
                generated,
            )
        except (AssemblySequenceConfigurationError, OSError, ValueError, json.JSONDecodeError) as exc:
            raise LayoutPreviewError(f"Assembly sequence policy is invalid: {exc}") from exc
        if assembly_sequence_plan is not None:
            generated["constraintPlan"]["assemblySequencePlan"] = assembly_sequence_plan
    with timing.stage("annotate-solver-result"):
        generated["caseId"] = case_id
        generated["solveProfile"] = solve_profile
        anchor_policy = request.get("sourceIndependentPolicy", {})
        generated["prototypePoseUsedForSolving"] = bool(
            anchor_policy.get("caseSpecificPrototypeAnchor", False)
            or anchor_policy.get("caseAnchorTargetPrototypeDerived", False)
        )
        generated["sourceCapturePoseUsedForAnchoring"] = bool(
            anchor_policy.get("caseSpecificPrototypeAnchor", False)
            and str(anchor_policy.get("caseAnchorTargetKind") or "sourceCapture")
            == "sourceCapture"
        )

    solution_path = (workspace / definition["solutionPath"]).resolve()
    preview_path = (workspace / definition["previewPath"]).resolve()
    timing_path = preview_path.with_name(f"{case_id}_pipeline_timing.json")
    with timing.stage("build-preview-payload"):
        preview = build_preview_payload(
            generated,
            case_id=case_id,
            title=definition["title"],
            solution_path=solution_path,
            preview_path=preview_path,
        )
        preview["solveProfile"] = solve_profile
        preview["timingArtifactPath"] = str(timing_path)
    if persist:
        with timing.stage("persist-solution-preview-and-plan"):
            solution_path.parent.mkdir(parents=True, exist_ok=True)
            solution_path.write_text(
                json.dumps(generated, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            preview_path.write_text(
                json.dumps(preview, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            selected_solution_path = (
                workspace / definition["selectedSolutionPath"]
            ).resolve()
            selected_solution_path.write_text(
                json.dumps(
                    {
                        "caseId": case_id,
                        "status": "awaiting_visual_selection",
                        "sourcePreviewGeneratedAt": preview["generatedAt"],
                        "solveProfile": solve_profile,
                        "message": (
                            "The previous selection was invalidated by a new solve; "
                            "Replay remains blocked until one current candidate is approved."
                        ),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            verification_plan_path = (
                workspace / definition["verificationPlanPath"]
            ).resolve()
            verification_plan_path.write_text(
                json.dumps(
                    _verification_plan(
                        case_id=case_id,
                        generated_at=preview["generatedAt"],
                        status="awaiting_visual_review",
                        static_collision_policy=static_collision_policy,
                    ),
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
    timing_payload = timing.finish()
    timing_payload["profile"] = profile
    timing_payload["artifactPaths"] = {
        "solution": str(solution_path),
        "preview": str(preview_path),
        "selectedSolution": str(
            (workspace / definition["selectedSolutionPath"]).resolve()
        ),
        "verificationPlan": str(
            (workspace / definition["verificationPlanPath"]).resolve()
        ),
    }
    timing_payload["note"] = (
        "The final metadata rewrite is intentionally excluded from the persist-stage "
        "duration; the authoritative timing sidecar is written last."
    )
    generated["timing"] = timing_payload
    preview["timing"] = timing_payload
    if persist:
        solution_path.write_text(
            json.dumps(generated, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        preview_path.write_text(
            json.dumps(preview, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        timing_path.write_text(
            json.dumps(timing_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return preview


def approve_case_preview(
    workspace: Path,
    case_id: str,
    solution_rank: int,
    *,
    reviewer_note: str | None = None,
) -> dict[str, Any]:
    """Materialize a visually approved Top-K candidate and open the staged CAD gate."""
    timing = PipelineTiming(f"{case_id}.approve-preview")
    definition = CASE_DEFINITIONS.get(case_id)
    if definition is None:
        raise LayoutPreviewError(f"Unknown layout case '{case_id}'.")
    if solution_rank < 1:
        raise LayoutPreviewError("solutionRank must be a positive integer.")

    solution_path = (workspace / definition["solutionPath"]).resolve()
    preview_path = (workspace / definition["previewPath"]).resolve()
    if not solution_path.is_file() or not preview_path.is_file():
        raise LayoutPreviewError(
            "No persisted preview solve exists. Run solve-preview before approval."
        )

    with timing.stage("load-persisted-top-k"):
        generated = json.loads(solution_path.read_text(encoding="utf-8"))
        preview = json.loads(preview_path.read_text(encoding="utf-8"))
        joint_search = (generated.get("constraintPlan") or {}).get("jointSearch") or {}
        selected = next(
            (
                item
                for item in joint_search.get("solutions") or []
                if int(item.get("rank", 0)) == solution_rank
            ),
            None,
        )
        if selected is None:
            raise LayoutPreviewError(
                f"Solution rank {solution_rank} is not present in the persisted Top-K solve."
            )

    with timing.stage("materialize-selected-solution", solutionRank=solution_rank):
        materialized = _materialize_solution(generated, selected)
        approved_at = datetime.now(timezone.utc).isoformat()
    selected_solution_path = (
        workspace / definition["selectedSolutionPath"]
    ).resolve()
    verification_plan_path = (
        workspace / definition["verificationPlanPath"]
    ).resolve()
    with timing.stage("persist-selected-solution"):
        materialized["visualApproval"] = {
            "approved": True,
            "approvedAt": approved_at,
            "selectedSolutionRank": solution_rank,
            "reviewerNote": reviewer_note or "",
            "sourcePreviewGeneratedAt": preview.get("generatedAt"),
            "requiresReplayBeforeBroadPhase": True,
            "allowsBrepNow": False,
        }
        materialized["message"] = (
            f"Top-K solution {solution_rank} was visually approved and materialized for Replay."
        )
        selected_solution_path.parent.mkdir(parents=True, exist_ok=True)
        selected_solution_path.write_text(
            json.dumps(materialized, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    plan = _verification_plan(
        case_id=case_id,
        generated_at=str(preview.get("generatedAt") or ""),
        status="visual_review_approved",
        selected_solution_rank=solution_rank,
        selected_solution_path=str(selected_solution_path),
        approved_at=approved_at,
        reviewer_note=reviewer_note,
        static_collision_policy=(generated.get("constraintPlan") or {}).get(
            "staticCollisionPolicy"
        ),
    )
    with timing.stage("persist-verification-plan"):
        verification_plan_path.write_text(
            json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    timing_payload = timing.finish()
    timing_payload["solutionRank"] = solution_rank
    plan["timing"] = timing_payload
    materialized["visualApproval"]["timing"] = timing_payload
    selected_solution_path.write_text(
        json.dumps(materialized, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    verification_plan_path.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return plan


def load_case_verification_plan(workspace: Path, case_id: str) -> dict[str, Any]:
    """Load the durable staged-verification state for a layout case."""
    definition = CASE_DEFINITIONS.get(case_id)
    if definition is None:
        raise LayoutPreviewError(f"Unknown layout case '{case_id}'.")
    path = (workspace / definition["verificationPlanPath"]).resolve()
    if not path.is_file():
        raise LayoutPreviewError(
            "No persisted verification plan exists. Run solve-preview first."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def load_case_preview(workspace: Path, case_id: str) -> dict[str, Any]:
    """Load the last persisted preview without starting another solve."""
    definition = CASE_DEFINITIONS.get(case_id)
    if definition is None:
        raise LayoutPreviewError(f"Unknown layout case '{case_id}'.")
    path = (workspace / definition["previewPath"]).resolve()
    if not path.is_file():
        raise LayoutPreviewError("No persisted preview exists. Run solve-preview first.")
    return json.loads(path.read_text(encoding="utf-8"))


def _materialize_solution(
    generated: dict[str, Any],
    selected: dict[str, Any],
    *,
    allow_orientation_change: bool = False,
) -> dict[str, Any]:
    result = copy.deepcopy(generated)
    placements = {
        item.get("componentName"): item
        for item in selected.get("placements") or []
        if item.get("componentName")
    }
    components = result.get("components") or []
    missing = [
        item.get("componentName")
        for item in components
        if item.get("componentName") not in placements
    ]
    if missing:
        raise LayoutPreviewError(
            "Selected solution is incomplete; missing placements for: "
            + ", ".join(str(item) for item in missing)
        )

    orientation_changed_components: list[dict[str, Any]] = []

    def rotate_about_axis(
        vector: list[float], axis: list[float], angle_degrees: float
    ) -> list[float]:
        axis_length = math.sqrt(sum(float(value) ** 2 for value in axis))
        if axis_length <= 1e-12:
            raise LayoutPreviewError("Base-frame normal is degenerate.")
        unit_axis = [float(value) / axis_length for value in axis]
        radians = math.radians(angle_degrees)
        cosine = math.cos(radians)
        sine = math.sin(radians)
        dot = sum(float(vector[index]) * unit_axis[index] for index in range(3))
        cross = [
            unit_axis[1] * float(vector[2]) - unit_axis[2] * float(vector[1]),
            unit_axis[2] * float(vector[0]) - unit_axis[0] * float(vector[2]),
            unit_axis[0] * float(vector[1]) - unit_axis[1] * float(vector[0]),
        ]
        return [
            float(vector[index]) * cosine
            + cross[index] * sine
            + unit_axis[index] * dot * (1.0 - cosine)
            for index in range(3)
        ]

    for component in components:
        name = component["componentName"]
        candidate = placements[name]
        layout = component.get("layout2d") or {}
        current_theta = float(layout.get("thetaDegrees") or 0.0)
        candidate_theta = float(candidate.get("thetaDegrees") or 0.0)
        current_quarters = int(
            (component.get("constraintPlacement") or {}).get("rotationQuarters", 0)
        )
        candidate_quarters = int(candidate.get("rotationQuarters", 0))
        orientation_changed = (
            abs(_angle_delta_degrees(candidate_theta, current_theta)) > 1e-7
            or candidate_quarters != current_quarters
        )
        if orientation_changed and not allow_orientation_change:
            raise LayoutPreviewError(
                f"Solution {selected.get('rank')} changes the orientation of '{name}'. "
                "Orientation-changing candidate materialization is not enabled yet."
            )
        if orientation_changed:
            base_frame = result.get("baseFrame") or {}
            normal = base_frame.get("normal")
            if not isinstance(normal, list) or len(normal) != 3:
                raise LayoutPreviewError(
                    f"Cannot materialize the orientation of '{name}' without a base-frame normal."
                )
            angle_delta = _angle_delta_degrees(candidate_theta, current_theta)
            for axis_key in (
                "targetXAxisWorld",
                "targetYAxisWorld",
                "targetZAxisWorld",
            ):
                axis_value = component.get(axis_key)
                if not isinstance(axis_value, list) or len(axis_value) != 3:
                    raise LayoutPreviewError(
                        f"Cannot materialize the orientation of '{name}'; {axis_key} is missing."
                    )
                component[axis_key] = rotate_about_axis(
                    [float(value) for value in axis_value],
                    [float(value) for value in normal],
                    angle_delta,
                )
            orientation_changed_components.append(
                {
                    "componentName": name,
                    "fromThetaDegrees": current_theta,
                    "toThetaDegrees": candidate_theta,
                    "deltaThetaDegrees": angle_delta,
                    "fromRotationQuarters": current_quarters,
                    "toRotationQuarters": candidate_quarters,
                }
            )

        delta_u = float(candidate["x"]) - float(layout.get("x", 0.0))
        delta_v = float(candidate["y"]) - float(layout.get("y", 0.0))
        layout["x"] = float(candidate["x"])
        layout["y"] = float(candidate["y"])
        layout["thetaDegrees"] = candidate_theta

        candidate_bounds = [float(value) for value in candidate.get("bounds") or []]
        if len(candidate_bounds) != 4:
            raise LayoutPreviewError(
                f"Solution {selected.get('rank')} has invalid bounds for '{name}'."
            )
        footprint = component.setdefault("projectedFootprint", {})
        for key, value in zip(("minU", "minV", "maxU", "maxV"), candidate_bounds):
            footprint[key] = value
        placement = component.setdefault("constraintPlacement", {})
        placement["rotationQuarters"] = candidate_quarters
        placement["selectedTopKSolutionRank"] = int(selected.get("rank", 0))

        for envelope_name in (
            "interactionEnvelope",
            "hardBodyEnvelope",
            "transportSweepEnvelope",
            "transportStaticKeepoutEnvelope",
        ):
            envelope = component.get(envelope_name)
            bounds = envelope.get("bounds") if isinstance(envelope, dict) else None
            if not isinstance(bounds, list) or len(bounds) < 4:
                continue
            bounds[0] = float(bounds[0]) + delta_u
            bounds[1] = float(bounds[1]) + delta_v
            bounds[2] = float(bounds[2]) + delta_u
            bounds[3] = float(bounds[3]) + delta_v

    plan = result.setdefault("constraintPlan", {})
    plan["selectedTopKSolution"] = {
        "rank": int(selected.get("rank", 0)),
        "score": float(selected.get("score", 0.0)),
        "candidateRanks": selected.get("candidateRanks") or [],
        "materialized": True,
        "orientationChanged": bool(orientation_changed_components),
        "orientationChangedComponents": orientation_changed_components,
    }
    plan["validationDiagnosticsCoordinateFrame"] = (
        f"rank-{int(selected.get('rank', 0))} diagnostics; selected candidate is solver-feasible and must be validated "
        "by Replay, world-AABB broad phase, and candidate-only B-rep checks"
    )
    return result


def _verification_plan(
    *,
    case_id: str,
    generated_at: str,
    status: str,
    selected_solution_rank: int | None = None,
    selected_solution_path: str | None = None,
    approved_at: str | None = None,
    reviewer_note: str | None = None,
    static_collision_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    visual_complete = status == "visual_review_approved"
    collision_policy = static_collision_policy or {}
    strict_pairs = collision_policy.get("strictAabbPairs") or []
    conditional_pairs = collision_policy.get("brepOnAabbOverlapPairs") or []
    installation_pairs = collision_policy.get("installationContactPairs") or []
    pair_count = int(
        collision_policy.get(
            "pairCount",
            len(strict_pairs) + len(conditional_pairs) + len(installation_pairs),
        )
    )
    return {
        "caseId": case_id,
        "status": status,
        "sourcePreviewGeneratedAt": generated_at,
        "selectedSolutionRank": selected_solution_rank,
        "selectedSolutionPath": selected_solution_path,
        "approvedAt": approved_at,
        "reviewerNote": reviewer_note or "",
        "stages": [
            {
                "id": "visual_review",
                "status": "completed" if visual_complete else "pending",
                "checks": [
                    "module orientation",
                    "gantry boundary escape",
                    "obvious solid penetration",
                    "process and maintenance plausibility",
                ],
            },
            {
                "id": "solidworks_replay",
                "status": "pending" if visual_complete else "blocked",
                "blockedBy": [] if visual_complete else ["visual_review"],
            },
            {
                "id": "world_aabb_broad_phase",
                "status": "blocked",
                "blockedBy": ["solidworks_replay"],
                "strictAabbPairs": strict_pairs,
                "brepOnAabbOverlapPairs": conditional_pairs,
                "installationContactPairs": installation_pairs,
                "rule": (
                    "strict pairs fail immediately on inflated-AABB contact; structural pairs "
                    "pass immediately when AABBs are separated; A600 installation-contact "
                    "pairs are checked for illegal penetration rather than zero nominal contact"
                ),
            },
            {
                "id": "candidate_brep",
                "status": "blocked",
                "blockedBy": ["world_aabb_broad_phase"],
                "scope": "AABB overlap/near-touch pairs and explicit high-risk pairs only",
                "maximumPairCount": len(conditional_pairs),
                "allPairBaselineCount": pair_count,
                "minimumAvoidedPairCount": max(
                    0, pair_count - len(conditional_pairs) - len(installation_pairs)
                ),
            },
            {
                "id": "installation_contact_review",
                "status": "blocked",
                "blockedBy": ["solidworks_replay"],
                "scope": "A600 mounting contact and structural nesting pairs",
                "pairCount": len(installation_pairs),
                "pairs": installation_pairs,
                "acceptanceRule": (
                    "preserve intended mounting contact while rejecting material penetration "
                    "outside the recorded A600 interface/keepout semantics"
                ),
            },
            {
                "id": "full_brep",
                "status": "deferred",
                "requiredWhen": "final acceptance or after all candidate checks pass",
            },
        ],
        "policy": {
            "manualModuleMoveAfterFailure": False,
            "failureAction": "calibrate constraints or solver scoring, then re-solve",
            "stopOnFirstHardInterference": True,
            "reusePassingPairResultsWhenPosesUnchanged": True,
            "solverInvokesBrep": False,
            "staticCollisionPolicy": collision_policy,
        },
    }


def _compile_static_collision_policy(
    request: dict[str, Any],
    component_names: list[str],
) -> dict[str, Any]:
    """Resolve code-level pair policy to exact component names and require full coverage."""
    raw = request.get("staticCollisionPolicy")
    if not isinstance(raw, dict):
        return {
            "enabled": False,
            "solverInvokesBrep": False,
            "pairCount": 0,
            "strictAabbPairs": [],
            "brepOnAabbOverlapPairs": [],
        }

    names = [str(name) for name in component_names]
    names_by_code: dict[str, list[str]] = {}
    for name in names:
        names_by_code.setdefault(_component_code(name).upper(), []).append(name)

    def resolve(value: Any) -> str:
        text = str(value).strip()
        exact = next((name for name in names if name.lower() == text.lower()), None)
        if exact is not None:
            return exact
        matches = names_by_code.get(text.upper(), [])
        if len(matches) != 1:
            raise LayoutPreviewError(
                f"Static collision policy component '{text}' resolves to {len(matches)} components."
            )
        return matches[0]

    def resolve_pairs(key: str) -> list[list[str]]:
        result: list[list[str]] = []
        for index, pair in enumerate(raw.get(key) or []):
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                raise LayoutPreviewError(
                    f"staticCollisionPolicy.{key}[{index}] must contain two components."
                )
            first, second = resolve(pair[0]), resolve(pair[1])
            if first == second:
                raise LayoutPreviewError(
                    f"staticCollisionPolicy.{key}[{index}] cannot pair a component with itself."
                )
            result.append(sorted((first, second)))
        return sorted(result)

    strict_pairs = resolve_pairs("strictAabbPairs")
    conditional_pairs = resolve_pairs("brepOnAabbOverlapPairs")
    strict_keys = {frozenset(pair) for pair in strict_pairs}
    conditional_keys = {frozenset(pair) for pair in conditional_pairs}
    if len(strict_keys) != len(strict_pairs) or len(conditional_keys) != len(conditional_pairs):
        raise LayoutPreviewError("Static collision policy contains duplicate component pairs.")
    duplicated = strict_keys & conditional_keys
    if duplicated:
        raise LayoutPreviewError(
            "Static collision policy assigns a pair to both strict AABB and conditional B-Rep."
        )

    all_pairs = {
        frozenset(pair)
        for pair in itertools.combinations(sorted(names), 2)
    }
    covered = strict_keys | conditional_keys
    require_complete = bool(raw.get("requireCompletePairCoverage", True))
    if require_complete and covered != all_pairs:
        missing = [sorted(pair) for pair in sorted(all_pairs - covered, key=lambda item: sorted(item))]
        extra = [sorted(pair) for pair in sorted(covered - all_pairs, key=lambda item: sorted(item))]
        raise LayoutPreviewError(
            f"Static collision policy must cover every pair; missing={missing}, extra={extra}."
        )

    inflation = float(raw.get("aabbInflationPerSideMeters", 0.0))
    if not math.isfinite(inflation) or inflation < 0:
        raise LayoutPreviewError(
            "staticCollisionPolicy.aabbInflationPerSideMeters must be a finite non-negative number."
        )
    return {
        "enabled": True,
        "schemaVersion": int(raw.get("schemaVersion", 1)),
        "requireCompletePairCoverage": require_complete,
        "solverInvokesBrep": False,
        "aabbInflationPerSideMeters": inflation,
        "strictMinimumSeparationMeters": inflation * 2.0,
        "pairCount": len(all_pairs),
        "coveredPairCount": len(covered),
        "strictAabbPairCount": len(strict_pairs),
        "brepOnAabbOverlapPairCount": len(conditional_pairs),
        "maximumBrepReductionPairCount": len(strict_pairs),
        "maximumBrepReductionRatio": len(strict_pairs) / max(1, len(all_pairs)),
        "strictAabbPairs": strict_pairs,
        "brepOnAabbOverlapPairs": conditional_pairs,
    }


def _apply_static_collision_policy_to_semantics(
    semantics: dict[str, dict[str, Any]],
    policy: dict[str, Any],
) -> None:
    if not policy.get("enabled"):
        return
    inflation = float(policy.get("aabbInflationPerSideMeters", 0.0))
    for first, second in policy.get("strictAabbPairs") or []:
        for name, other in ((first, second), (second, first)):
            parameters = semantics.setdefault(name, {}).setdefault("parameters", {})
            partners = parameters.setdefault("strictAabbSeparationWith", [])
            if other not in partners:
                partners.append(other)
            parameters["strictAabbInflationPerSideMeters"] = inflation
    for first, second in policy.get("brepOnAabbOverlapPairs") or []:
        for name, other in ((first, second), (second, first)):
            parameters = semantics.setdefault(name, {}).setdefault("parameters", {})
            partners = parameters.setdefault("brepOnAabbOverlapWith", [])
            if other not in partners:
                partners.append(other)


def _angle_delta_degrees(target: float, current: float) -> float:
    return (target - current + 180.0) % 360.0 - 180.0


def build_preview_payload(
    generated: dict[str, Any],
    *,
    case_id: str,
    title: str,
    solution_path: Path,
    preview_path: Path,
) -> dict[str, Any]:
    plan = generated.get("constraintPlan") or {}
    semantics = plan.get("moduleSemantics") or {}
    roles = plan.get("roles") or {}
    modules: list[dict[str, Any]] = []
    all_bounds: list[list[float]] = []

    for component in generated.get("components", []):
        name = component["componentName"]
        semantic = semantics.get(name) or {}
        module_type = semantic.get("moduleType", roles.get(name, "functional"))
        layout = component.get("layout2d") or {}
        footprint = component.get("projectedFootprint") or {}
        bounds = [
            float(footprint.get("minU", layout.get("x", 0.0))),
            float(footprint.get("minV", layout.get("y", 0.0))),
            float(footprint.get("maxU", layout.get("x", 0.0))),
            float(footprint.get("maxV", layout.get("y", 0.0))),
        ]
        all_bounds.append(bounds)
        quarters = int(
            (component.get("constraintPlacement") or {}).get("rotationQuarters", 0)
        )
        center = [float(layout.get("x", 0.0)), float(layout.get("y", 0.0))]
        points = [
            {
                "name": point_name,
                "position": list(_world_point(center, point, quarters)),
            }
            for point_name, point in (semantic.get("points") or {}).items()
        ]
        regions = [
            {
                "name": region_name,
                "bounds": list(_world_region(center, region, quarters)),
            }
            for region_name, region in (semantic.get("regions") or {}).items()
        ]
        protected_spaces = _preview_protected_spaces(center, semantic, quarters)
        all_bounds.extend(item["bounds"] for item in regions)
        all_bounds.extend(item["bounds"] for item in protected_spaces)
        interaction_envelope = _preview_envelope(
            component.get("interactionEnvelope"), "fullAabb"
        )
        hard_body_envelope = _preview_envelope(
            component.get("hardBodyEnvelope"), "fullAabbBody"
        )
        transport_sweep_envelope = _preview_envelope(
            component.get("transportSweepEnvelope"), "transportSweep"
        )
        transport_static_keepout_envelope = _preview_envelope(
            component.get("transportStaticKeepoutEnvelope"), "transportStaticKeepout"
        )
        for envelope in (
            interaction_envelope,
            hard_body_envelope,
            transport_sweep_envelope,
            transport_static_keepout_envelope,
        ):
            if envelope is not None:
                all_bounds.append(envelope["bounds"])
        modules.append(
            {
                "componentName": name,
                "code": _component_code(name),
                "label": MODULE_LABELS.get(module_type, "功能模组"),
                "moduleType": module_type,
                "role": roles.get(name, "functional"),
                "color": MODULE_COLORS.get(module_type, "#64748b"),
                "center": center,
                "bounds": bounds,
                "thetaDegrees": float(layout.get("thetaDegrees") or 0.0),
                "rotationQuarters": quarters,
                "points": points,
                "regions": regions,
                "protectedSpaces": protected_spaces,
                "interactionEnvelope": interaction_envelope,
                "hardBodyEnvelope": hard_body_envelope,
                "transportSweepEnvelope": transport_sweep_envelope,
                "transportStaticKeepoutEnvelope": transport_static_keepout_envelope,
                "provisional": bool(
                    (semantic.get("parameters") or {}).get("provisional", False)
                ),
            }
        )

    view_bounds = _view_bounds(all_bounds)
    process = plan.get("processValidation") or {}
    spatial = plan.get("spatialValidation") or {}
    interaction = plan.get("interactionValidation") or {}
    reach = plan.get("reachValidation") or {}
    fixed_environment_validation = plan.get("fixedEnvironmentValidation") or {}
    validation = plan.get("validation") or {}
    gantry_name = plan.get("gantryComponentName")
    gantry = next((item for item in modules if item["componentName"] == gantry_name), None)
    transport = next((item for item in modules if item["moduleType"] == "transport"), None)
    long_axis = plan.get("longAxis", "u")
    short_indices = (1, 3) if long_axis == "u" else (0, 2)
    transport_center_offset = None
    if gantry and transport:
        gantry_short_center = (
            gantry["bounds"][short_indices[0]] + gantry["bounds"][short_indices[1]]
        ) / 2.0
        transport_short_center = (
            transport["bounds"][short_indices[0]]
            + transport["bounds"][short_indices[1]]
        ) / 2.0
        transport_center_offset = abs(transport_short_center - gantry_short_center)

    portal_overlap_diagnostic = next(
        (
            item
            for item in spatial.get("diagnostics", [])
            if item.get("type") == "portalGantryOverlap"
        ),
        None,
    )
    portal_center_diagnostic = next(
        (
            item
            for item in spatial.get("diagnostics", [])
            if item.get("type") == "portalGantryCenterOffset"
        ),
        None,
    )
    portal_overhang_diagnostic = next(
        (
            item
            for item in spatial.get("diagnostics", [])
            if item.get("type") == "portalGantryOverhang"
        ),
        None,
    )
    relative_anchor_diagnostic = next(
        (
            item
            for item in process.get("diagnostics", [])
            if item.get("id") == "a300-a700-service-cluster-relative-window"
        ),
        None,
    )

    allowed_pairs = (
        validation.get("conditionalInteractionReviewPairs")
        or validation.get("allowedAabbOverlapPairs")
        or []
    )
    post_solve_overlap_pairs = plan.get("postSolveAllowedProjectedOverlapPairs") or []
    review_items = _review_items(
        process=process,
        spatial=spatial,
        interaction=interaction,
        reach=reach,
        validation=validation,
        transport_center_offset=transport_center_offset,
        portal_overlap_diagnostic=portal_overlap_diagnostic,
        portal_center_diagnostic=portal_center_diagnostic,
        portal_overhang_diagnostic=portal_overhang_diagnostic,
        relative_anchor_diagnostic=relative_anchor_diagnostic,
        allowed_pairs=allowed_pairs,
        assumption_warnings=plan.get("assumptionWarnings") or [],
    )
    diagnostics = [
        {**item, "group": "工艺约束"}
        for item in process.get("diagnostics", [])
    ] + [
        {**item, "group": "空间约束"}
        for item in spatial.get("diagnostics", [])
    ] + [
        {**item, "group": "2.5D交互约束"}
        for item in interaction.get("diagnostics", [])
    ] + [
        {
            "id": f"reach-{item.get('region', 'region')}",
            "type": "reachContained",
            "success": bool(item.get("success")),
            "hard": True,
            "message": "胶阀行程区域位于龙门范围内",
            "measured": item,
            "group": "行程约束",
        }
        for item in reach.get("diagnostics", [])
    ] + [
        {**item, "group": "A600固定环境约束"}
        for item in fixed_environment_validation.get("diagnostics", [])
    ]
    joint_search = plan.get("jointSearch") or {}
    static_collision_policy = plan.get("staticCollisionPolicy") or {}
    solution_variants: list[dict[str, Any]] = []
    for solution in joint_search.get("solutions") or []:
        placements = {
            item.get("componentName"): item
            for item in solution.get("placements") or []
        }
        variant_modules: list[dict[str, Any]] = []
        for module in modules:
            candidate = placements.get(module["componentName"])
            if not candidate:
                variant_modules.append(copy.deepcopy(module))
                continue
            variant = copy.deepcopy(module)
            delta_u = float(candidate["x"]) - float(module["center"][0])
            delta_v = float(candidate["y"]) - float(module["center"][1])
            variant["center"] = [float(candidate["x"]), float(candidate["y"])]
            variant["bounds"] = [float(value) for value in candidate["bounds"]]
            variant["thetaDegrees"] = float(candidate["thetaDegrees"])
            variant["rotationQuarters"] = int(candidate.get("rotationQuarters", 0))
            variant["points"] = [
                {
                    **point,
                    "position": [
                        float(point["position"][0]) + delta_u,
                        float(point["position"][1]) + delta_v,
                    ],
                }
                for point in variant.get("points") or []
            ]
            variant["regions"] = [
                {
                    **region,
                    "bounds": [
                        float(region["bounds"][0]) + delta_u,
                        float(region["bounds"][1]) + delta_v,
                        float(region["bounds"][2]) + delta_u,
                        float(region["bounds"][3]) + delta_v,
                    ],
                }
                for region in variant.get("regions") or []
            ]
            variant["protectedSpaces"] = _preview_protected_spaces(
                variant["center"],
                semantics.get(module["componentName"]) or {},
                variant["rotationQuarters"],
            )
            for envelope_name in (
                "interactionEnvelope",
                "hardBodyEnvelope",
                "transportSweepEnvelope",
                "transportStaticKeepoutEnvelope",
            ):
                envelope = variant.get(envelope_name)
                if not envelope:
                    continue
                envelope["bounds"] = [
                    float(envelope["bounds"][0]) + delta_u,
                    float(envelope["bounds"][1]) + delta_v,
                    float(envelope["bounds"][2]) + delta_u,
                    float(envelope["bounds"][3]) + delta_v,
                ]
            variant_modules.append(variant)
        conditional_leaf_risks = _conditional_leaf_aabb_risks(
            variant_modules,
            static_collision_policy.get("brepOnAabbOverlapPairs") or [],
            semantics,
            float(plan.get("minimumClearanceMeters", 0.0)),
        )
        solution_variants.append(
            {
                "rank": int(solution.get("rank", len(solution_variants) + 1)),
                "score": float(solution.get("score", 0.0)),
                "candidateRanks": solution.get("candidateRanks") or [],
                # Recompute from the exact materialized variant shown to the
                # reviewer.  The search-time estimate can differ after final
                # placement normalization/calibration, and displaying the
                # stale count would under-route the CAD broad phase.
                "predictedConditionalBrepPairCount": _conditional_overlap_count(
                    variant_modules,
                    static_collision_policy.get("brepOnAabbOverlapPairs") or [],
                ),
                "predictedConditionalLeafAabbHitCount": sum(
                    int(item["hitCount"]) for item in conditional_leaf_risks
                ),
                "conditionalLeafAabbRisks": conditional_leaf_risks,
                "modules": variant_modules,
            }
        )

    primary_leaf_risks = (
        solution_variants[0].get("conditionalLeafAabbRisks", [])
        if solution_variants
        else []
    )
    primary_leaf_hit_count = sum(
        int(item["hitCount"]) for item in primary_leaf_risks
    )
    if primary_leaf_hit_count:
        review_items.append(
            {
                "severity": "warning",
                "title": "叶盒宽相风险",
                "message": (
                    f"当前方案有 {primary_leaf_hit_count} 个叶级包围盒预命中，"
                    f"集中在 {len(primary_leaf_risks)} 组条件 B-rep 组合；"
                    "它们不是实体干涉结论，Replay 后应按命中数从高到低精检。"
                ),
            }
        )

    assembly_sequence_plan = plan.get("assemblySequencePlan")
    fixed_environment = plan.get("fixedEnvironment")
    if isinstance(fixed_environment, dict):
        fixed_ready = bool(fixed_environment_validation.get("hardFeasible"))
        review_items.insert(
            0,
            {
                "severity": "pass" if fixed_ready else "fail",
                "title": "A600固定环境根模组",
                "message": (
                    f"A600以0自由度固定基准加入九对象方案；当前候选通过"
                    f"{int(fixed_environment_validation.get('passedCount', 0))}/"
                    f"{int(fixed_environment_validation.get('constraintCount', 0))}条"
                    "安装锚点硬约束。Replay时保持A600世界位姿不变。"
                ),
            },
        )
    if isinstance(assembly_sequence_plan, dict):
        summary = assembly_sequence_plan.get("summary") or {}
        sequence_ready = bool(assembly_sequence_plan.get("sequentialSolverReady"))
        review_items.insert(
            0,
            {
                "severity": "pass" if sequence_ready else "warning",
                "title": "A600锚定顺序求解门禁",
                "message": (
                    "五阶段装配证据与实测参数齐备，可进入顺序求解。"
                    if sequence_ready
                    else (
                        f"当前 {int(summary.get('readyCount', 0))}/{int(summary.get('stageCount', 0))} "
                        "阶段达到正式就绪；现有结果仅是A600固定环境＋八个可动模组的粗排与碰撞筛选结果。"
                    )
                ),
            },
        )

    inverse_coverage = plan.get("inverseGantryCoverage")
    if isinstance(inverse_coverage, dict):
        selected_inside = bool(inverse_coverage.get("selectedInside"))
        target_count = int(inverse_coverage.get("targetPointCount", 0))
        feasible_region = inverse_coverage.get("feasibleAnchorRegion")
        review_items.insert(
            1 if isinstance(assembly_sequence_plan, dict) else 0,
            {
                "severity": "pass" if selected_inside else "warning",
                "title": "A100逆向覆盖门禁",
                "message": (
                    f"已由 {target_count} 个传输工作点/功能服务点反求A100锚点可行域；"
                    f"当前A100锚点{'位于' if selected_inside else '不在'}交集内"
                    + (f"，可行域={feasible_region}。" if feasible_region else "。")
                ),
            },
        )

    prototype_pose_used = bool(generated.get("prototypePoseUsedForSolving"))
    source_capture_anchor_used = bool(
        generated.get("sourceCapturePoseUsedForAnchoring")
    )
    case_anchor = plan.get("caseAnchor")

    return {
        "caseId": case_id,
        "title": title,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sourceIndependent": bool(plan.get("sourcePositionIndependent"))
        and not prototype_pose_used,
        "relativeConstraintsSourceIndependent": bool(
            plan.get("sourcePositionIndependent")
        ),
        "prototypePoseUsedForSolving": prototype_pose_used,
        "sourceCapturePoseUsedForAnchoring": source_capture_anchor_used,
        "caseAnchor": case_anchor,
        "inverseGantryCoverage": inverse_coverage,
        "fixedEnvironment": fixed_environment,
        "fixedEnvironmentValidation": fixed_environment_validation,
        "solverMode": str(plan.get("solverMode") or "deterministic-first-feasible"),
        "solutionPath": str(solution_path),
        "previewPath": str(preview_path),
        "viewBounds": view_bounds,
        "longAxis": long_axis,
        "modules": modules,
        "solutions": solution_variants,
        "jointSearchSummary": {
            "success": bool(joint_search.get("success")),
            "solutionCount": int(joint_search.get("solutionCount", 0)),
            "exploredNodeCount": int(joint_search.get("exploredNodeCount", 0)),
            "maximumSearchNodes": int(joint_search.get("maximumSearchNodes", 0)),
            "candidateCounts": joint_search.get("candidateCounts") or {},
            "acceptedCandidateCounts": joint_search.get("acceptedCandidateCounts") or {},
            "rejectionCounts": joint_search.get("rejectionCounts") or {},
            "processConstraintFailureCounts": joint_search.get(
                "processConstraintFailureCounts"
            )
            or {},
            "collisionMatrix": joint_search.get("collisionMatrix") or {},
            "moduleStageDiagnostics": joint_search.get("moduleStageDiagnostics") or {},
            "elapsedSeconds": joint_search.get("elapsedSeconds"),
            "timeLimitSeconds": joint_search.get("timeLimitSeconds"),
        },
        "assemblySequencePlan": assembly_sequence_plan,
        "staticCollisionPolicy": static_collision_policy,
        "diagnostics": diagnostics,
        "metrics": {
            "componentCount": len(modules),
            "processPassed": int(process.get("passedCount", 0)),
            "processTotal": int(process.get("constraintCount", 0)),
            "spatialPassed": int(spatial.get("passedCount", 0)),
            "spatialTotal": int(spatial.get("constraintCount", 0)),
            "interactionPassed": int(interaction.get("passedCount", 0)),
            "interactionTotal": int(interaction.get("constraintCount", 0)),
            "interactionHardPassed": int(interaction.get("hardPassedCount", 0)),
            "interactionHardTotal": int(interaction.get("hardConstraintCount", 0)),
            "interactionAdvisoryWarningCount": int(
                interaction.get("softViolationCount", 0)
            ),
            "fixedEnvironmentPassed": int(
                fixed_environment_validation.get("passedCount", 0)
            ),
            "fixedEnvironmentTotal": int(
                fixed_environment_validation.get("constraintCount", 0)
            ),
            "reachContained": bool(reach.get("hardFeasible")),
            "hardFeasible": bool(
                process.get("hardFeasible")
                and spatial.get("hardFeasible")
                and interaction.get("hardFeasible")
                and reach.get("hardFeasible")
                and (
                    not fixed_environment_validation
                    or fixed_environment_validation.get("hardFeasible")
                )
            ),
            "transportCenterOffsetMeters": transport_center_offset,
            "portalGantryOverlapRatio": (
                float(portal_overlap_diagnostic["overlapRatio"])
                if portal_overlap_diagnostic
                else None
            ),
            "portalCenterOffsetMeters": (
                float(portal_center_diagnostic["centerOffsetMeters"])
                if portal_center_diagnostic
                else None
            ),
            "portalMaximumCenterOffsetMeters": (
                float(portal_center_diagnostic["maximumCenterOffsetMeters"])
                if portal_center_diagnostic
                else None
            ),
            "portalMaximumOverhangMeters": (
                float(portal_overhang_diagnostic["maximumObservedOverhangMeters"])
                if portal_overhang_diagnostic
                else None
            ),
            "portalAllowedOverhangMeters": (
                float(portal_overhang_diagnostic["maximumAllowedOverhangMeters"])
                if portal_overhang_diagnostic
                else None
            ),
            "serviceClusterDeltaUMeters": (
                float(relative_anchor_diagnostic["measured"]["deltaU"])
                if relative_anchor_diagnostic
                else None
            ),
            "serviceClusterDeltaVMeters": (
                float(relative_anchor_diagnostic["measured"]["deltaV"])
                if relative_anchor_diagnostic
                else None
            ),
            "unallowedOverlapCount": len(validation.get("overlapPairs") or []),
            "allowedOverlapReviewCount": len(allowed_pairs),
            "strictAabbPairCount": int(
                static_collision_policy.get("strictAabbPairCount", 0)
            ),
            "conditionalBrepPairCount": int(
                static_collision_policy.get("brepOnAabbOverlapPairCount", 0)
            ),
            "installationContactPairCount": int(
                static_collision_policy.get("installationContactPairCount", 0)
            ),
            "predictedConditionalLeafAabbHitCount": primary_leaf_hit_count,
            "solverBrepCallCount": 0,
            "productionReady": bool(validation.get("productionReady")),
        },
        "allowedOverlapPairs": allowed_pairs,
        "postSolveAllowedProjectedOverlapPairs": post_solve_overlap_pairs,
        "conditionalLeafAabbRisks": primary_leaf_risks,
        "reviewItems": review_items,
        "assumptionWarnings": plan.get("assumptionWarnings") or [],
    }


def _conditional_overlap_count(
    modules: list[dict[str, Any]],
    pairs: list[list[str]],
) -> int:
    by_name = {item.get("componentName"): item for item in modules}
    count = 0
    for pair in pairs:
        if not isinstance(pair, list) or len(pair) != 2:
            continue
        first = by_name.get(pair[0])
        second = by_name.get(pair[1])
        if not first or not second:
            continue
        first_bounds = first.get("bounds") or []
        second_bounds = second.get("bounds") or []
        if len(first_bounds) != 4 or len(second_bounds) != 4:
            continue
        if not (
            first_bounds[2] < second_bounds[0]
            or second_bounds[2] < first_bounds[0]
            or first_bounds[3] < second_bounds[1]
            or second_bounds[3] < first_bounds[1]
        ):
            count += 1
    return count


def _preview_protected_spaces(
    center: list[float],
    semantic: dict[str, Any],
    quarters: int,
) -> list[dict[str, Any]]:
    raw_spaces = (semantic.get("parameters") or {}).get(
        "protectedSpaceBoxesLocal", []
    )
    if not isinstance(raw_spaces, list):
        return []
    result: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_spaces):
        if not isinstance(raw, dict):
            continue
        bounds = raw.get("bounds")
        height = raw.get("heightRangeMeters")
        if not isinstance(bounds, list) or len(bounds) != 4:
            continue
        result.append(
            {
                "id": str(raw.get("id") or f"protected-space-{index + 1}"),
                "bounds": list(_world_box(center, bounds, quarters)),
                "heightRangeMeters": (
                    [float(value) for value in height]
                    if isinstance(height, list) and len(height) == 2
                    else [0.0, 0.0]
                ),
                "purpose": str(raw.get("purpose") or "专用工艺保护空间"),
                "enforcement": str(raw.get("enforcement") or "hard"),
                "confirmed": raw.get("confirmed"),
                "evidenceStatus": raw.get("evidenceStatus"),
                "minimumClearanceMeters": float(
                    raw.get("minimumClearanceMeters", 0.0)
                ),
                "hardClearanceWith": [str(value) for value in (
                    [raw.get("hardClearanceWith")]
                    if isinstance(raw.get("hardClearanceWith"), str)
                    else raw.get("hardClearanceWith", [])
                )],
            }
        )
    return result


def _conditional_leaf_aabb_risks(
    modules: list[dict[str, Any]],
    pairs: list[list[str]],
    semantics: dict[str, Any],
    default_clearance: float,
) -> list[dict[str, Any]]:
    """Summarize conservative leaf-box hits for CAD review routing.

    These are broad-phase hits only.  They deliberately remain separate from
    hard feasibility because sparse frames and nested service structures may
    have overlapping leaf AABBs without touching B-rep bodies.
    """

    by_name = {str(item.get("componentName")): item for item in modules}

    def occupancy(module: dict[str, Any]) -> list[dict[str, Any]]:
        name = str(module.get("componentName"))
        semantic = semantics.get(name) or {}
        raw_boxes = (semantic.get("parameters") or {}).get("occupancyBoxesLocal")
        if not isinstance(raw_boxes, list) or not raw_boxes:
            envelope = module.get("hardBodyEnvelope") or {}
            bounds = envelope.get("bounds") or module.get("bounds") or []
            height = envelope.get("heightRangeMeters") or [0.0, 0.0]
            return [{"id": "full-body", "bounds": bounds, "heightRangeMeters": height}]
        result: list[dict[str, Any]] = []
        for index, raw in enumerate(raw_boxes):
            if not isinstance(raw, dict):
                continue
            bounds = raw.get("bounds")
            height = raw.get("heightRangeMeters")
            if not isinstance(bounds, list) or len(bounds) != 4:
                continue
            if not isinstance(height, list) or len(height) != 2:
                continue
            result.append(
                {
                    "id": str(raw.get("id") or f"box-{index + 1}"),
                    "bounds": list(
                        _world_box(
                            module["center"],
                            bounds,
                            int(module.get("rotationQuarters", 0)),
                        )
                    ),
                    "heightRangeMeters": [float(value) for value in height],
                    "minimumClearanceMeters": raw.get("minimumClearanceMeters"),
                    "componentCode": raw.get("componentCode"),
                    "collisionPartnerCodes": raw.get("collisionPartnerCodes"),
                }
            )
        return result

    occupancy_cache = {name: occupancy(module) for name, module in by_name.items()}
    risks: list[dict[str, Any]] = []
    for pair in pairs:
        if not isinstance(pair, list) or len(pair) != 2:
            continue
        first = by_name.get(str(pair[0]))
        second = by_name.get(str(pair[1]))
        if not first or not second:
            continue
        if not _bounds_touch(first.get("bounds") or [], second.get("bounds") or [], 0.0):
            continue
        clearance = _preview_pair_clearance(
            str(pair[0]), str(pair[1]), semantics, default_clearance
        )
        first_boxes = occupancy_cache[str(pair[0])]
        second_boxes = occupancy_cache[str(pair[1])]
        first_codes = {
            str(item["componentCode"])
            for item in first_boxes
            if item.get("componentCode") is not None
        }
        second_codes = {
            str(item["componentCode"])
            for item in second_boxes
            if item.get("componentCode") is not None
        }
        first_boxes = [
            item for item in first_boxes
            if item.get("collisionPartnerCodes") is None
            or any(code in item.get("collisionPartnerCodes", []) for code in second_codes)
        ]
        second_boxes = [
            item for item in second_boxes
            if item.get("collisionPartnerCodes") is None
            or any(code in item.get("collisionPartnerCodes", []) for code in first_codes)
        ]
        hit_count = 0
        for left in first_boxes:
            for right in second_boxes:
                if left.get("collisionPartnerCodes") is not None and right.get("componentCode") not in left.get("collisionPartnerCodes", []):
                    continue
                if right.get("collisionPartnerCodes") is not None and left.get("componentCode") not in right.get("collisionPartnerCodes", []):
                    continue
                local_clearances = [
                    float(item["minimumClearanceMeters"])
                    for item in (left, right)
                    if item.get("minimumClearanceMeters") is not None
                ]
                effective_clearance = max(local_clearances) if local_clearances else clearance
                if _bounds_touch(left["bounds"], right["bounds"], effective_clearance) and _intervals_touch(
                    left["heightRangeMeters"], right["heightRangeMeters"], effective_clearance
                ):
                    hit_count += 1
                    if hit_count >= 100:
                        break
            if hit_count >= 100:
                break
        if hit_count:
            risks.append(
                {
                    "firstComponentName": str(pair[0]),
                    "secondComponentName": str(pair[1]),
                    "firstCode": str(first.get("code")),
                    "secondCode": str(second.get("code")),
                    "firstCenter": list(first.get("center") or [0.0, 0.0]),
                    "secondCenter": list(second.get("center") or [0.0, 0.0]),
                    "hitCount": hit_count,
                    "broadPhaseOnly": True,
                }
            )
    return sorted(risks, key=lambda item: (-int(item["hitCount"]), item["firstCode"], item["secondCode"]))


def _preview_pair_clearance(
    first_name: str,
    second_name: str,
    semantics: dict[str, Any],
    default_clearance: float,
) -> float:
    values: list[float] = []
    for owner_name, partner_name in ((first_name, second_name), (second_name, first_name)):
        mapping = ((semantics.get(owner_name) or {}).get("parameters") or {}).get(
            "occupancyClearanceMetersByComponent", {}
        )
        if isinstance(mapping, dict):
            for key, value in mapping.items():
                if str(key).lower() == partner_name.lower():
                    values.append(float(value))
    return max(values) if values else default_clearance


def _world_box(
    center: list[float], bounds: list[float], quarters: int
) -> tuple[float, float, float, float]:
    corners = [
        _rotate(float(u), float(v), quarters)
        for u in (bounds[0], bounds[2])
        for v in (bounds[1], bounds[3])
    ]
    return (
        float(center[0]) + min(item[0] for item in corners),
        float(center[1]) + min(item[1] for item in corners),
        float(center[0]) + max(item[0] for item in corners),
        float(center[1]) + max(item[1] for item in corners),
    )


def _bounds_touch(first: list[float], second: list[float], clearance: float) -> bool:
    if len(first) != 4 or len(second) != 4:
        return False
    return not (
        first[2] + clearance < second[0]
        or second[2] + clearance < first[0]
        or first[3] + clearance < second[1]
        or second[3] + clearance < first[1]
    )


def _intervals_touch(first: list[float], second: list[float], clearance: float) -> bool:
    if len(first) != 2 or len(second) != 2:
        return False
    return not (
        first[1] + clearance < second[0]
        or second[1] + clearance < first[0]
    )


def _preview_envelope(raw: Any, default_source: str) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    bounds = raw.get("bounds")
    if not isinstance(bounds, list) or len(bounds) != 4:
        return None
    height = raw.get("heightRangeMeters", [0.0, 0.0])
    if not isinstance(height, list) or len(height) != 2:
        height = [0.0, 0.0]
    return {
        "bounds": [float(value) for value in bounds],
        "heightRangeMeters": [float(value) for value in height],
        "source": str(raw.get("source") or default_source),
    }


def _review_items(
    *,
    process: dict[str, Any],
    spatial: dict[str, Any],
    interaction: dict[str, Any],
    reach: dict[str, Any],
    validation: dict[str, Any],
    transport_center_offset: float | None,
    portal_overlap_diagnostic: dict[str, Any] | None,
    portal_center_diagnostic: dict[str, Any] | None,
    portal_overhang_diagnostic: dict[str, Any] | None,
    relative_anchor_diagnostic: dict[str, Any] | None,
    allowed_pairs: list[list[str]],
    assumption_warnings: list[str],
) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    hard_feasible = bool(
        process.get("hardFeasible")
        and spatial.get("hardFeasible")
        and interaction.get("hardFeasible")
        and reach.get("hardFeasible")
    )
    items.append(
        {
            "severity": "pass" if hard_feasible else "fail",
            "title": "通用硬约束",
            "message": "工艺、空间和行程硬约束均通过。"
            if hard_feasible
            else "存在未通过的通用硬约束，不能进入Replay。",
        }
    )
    if transport_center_offset is not None:
        severity = "pass" if transport_center_offset <= 0.05 else "warning"
        items.append(
            {
                "severity": severity,
                "title": "传输模组中心性",
                "message": (
                    f"传输与龙门短轴中心偏差为 {transport_center_offset * 1000:.1f} mm。"
                    + (
                        "低于展示层50 mm观察阈值。"
                        if severity == "pass"
                        else "超过展示层50 mm观察阈值，建议评估中心约束。"
                    )
                ),
            }
        )
    if portal_overlap_diagnostic and portal_center_diagnostic and portal_overhang_diagnostic:
        portal_passed = bool(
            portal_overlap_diagnostic.get("success")
            and portal_center_diagnostic.get("success")
            and portal_overhang_diagnostic.get("success")
        )
    if relative_anchor_diagnostic:
        measured = relative_anchor_diagnostic.get("measured") or {}
        items.append(
            {
                "severity": "pass"
                if relative_anchor_diagnostic.get("success")
                else "fail",
                "title": "A300/A700相对工艺窗口",
                "message": (
                    f"A300相对A700锚点差为 "
                    f"U={float(measured.get('deltaU', 0.0)) * 1000:.1f} mm、"
                    f"V={float(measured.get('deltaV', 0.0)) * 1000:.1f} mm；"
                    "该窗口来自原型工艺关系标定，实体结论仍以Replay后专项B-rep为准。"
                ),
            }
        )
        items.append(
            {
                "severity": "pass" if portal_passed else "fail",
                "title": "CCD工艺轴线与有限越界",
                "message": (
                    f"CCD与龙门投影重合率 {float(portal_overlap_diagnostic.get('overlapRatio', 0.0)) * 100:.1f}%，"
                    f"结构外框短轴中心偏置 {float(portal_center_diagnostic.get('centerOffsetMeters', 0.0)) * 1000:.1f} mm，"
                    f"最大单侧越界 {float(portal_overhang_diagnostic.get('maximumObservedOverhangMeters', 0.0)) * 1000:.1f} mm。"
                    "相机工艺轴由CCD视场覆盖两个传输工作位的硬约束单独保证。"
                ),
            }
        )
    if allowed_pairs:
        items.append(
            {
                "severity": "warning",
                "title": "粗AABB重叠复核",
                "message": f"存在 {len(allowed_pairs)} 对完整AABB投影重叠；必须由2.5D硬约束解析并继续进行CAD实体检查。",
            }
        )
    if interaction.get("constraintCount"):
        items.append(
            {
                "severity": "pass" if interaction.get("hardFeasible") else "fail",
                "title": "2.5D交互复核",
                "message": (
                    f"简化主体包络/高度层与A200开口约束 "
                    f"{interaction.get('passedCount', 0)}/{interaction.get('constraintCount', 0)} 通过；"
                    "临时包络仍须CAD实体复核。"
                ),
            }
        )
    if interaction.get("softViolationCount"):
        items.append(
            {
                "severity": "warning",
                "title": "待确认维护空间",
                "message": (
                    f"有 {int(interaction.get('softViolationCount', 0))} 条原型粗估的操作/维护空间告警；"
                    "它们不阻断粗布局，但须由机械工程师或厂商尺寸确认后再决定是否升级为硬约束。"
                ),
            }
        )
    if assumption_warnings:
        items.append(
            {
                "severity": "warning",
                "title": "临时估算参数",
                "message": f"当前有 {len(assumption_warnings)} 项几何或工艺参数仍为临时估算。",
            }
        )
    if not validation.get("productionReady"):
        items.append(
            {
                "severity": "info",
                "title": "验证阶段",
                "message": "当前结果仅用于快速布局观察，不代表已完成SolidWorks实体闭环。",
            }
        )
    return items


def _world_point(
    center: list[float],
    point: dict[str, Any],
    quarters: int,
) -> tuple[float, float]:
    u, v = _rotate(float(point.get("u", 0.0)), float(point.get("v", 0.0)), quarters)
    return center[0] + u, center[1] + v


def _world_region(
    center: list[float],
    region: dict[str, Any],
    quarters: int,
) -> tuple[float, float, float, float]:
    corners = [
        _rotate(float(u), float(v), quarters)
        for u in (region.get("minU", 0.0), region.get("maxU", 0.0))
        for v in (region.get("minV", 0.0), region.get("maxV", 0.0))
    ]
    return (
        center[0] + min(item[0] for item in corners),
        center[1] + min(item[1] for item in corners),
        center[0] + max(item[0] for item in corners),
        center[1] + max(item[1] for item in corners),
    )


def _rotate(u: float, v: float, quarters: int) -> tuple[float, float]:
    radians = math.radians((quarters % 4) * 90.0)
    cosine, sine = math.cos(radians), math.sin(radians)
    return cosine * u - sine * v, sine * u + cosine * v


def _view_bounds(bounds: list[list[float]]) -> dict[str, float]:
    if not bounds:
        return {"minU": -1.0, "minV": -1.0, "maxU": 1.0, "maxV": 1.0}
    min_u = min(item[0] for item in bounds)
    min_v = min(item[1] for item in bounds)
    max_u = max(item[2] for item in bounds)
    max_v = max(item[3] for item in bounds)
    padding = max(max_u - min_u, max_v - min_v, 0.5) * 0.08
    return {
        "minU": min_u - padding,
        "minV": min_v - padding,
        "maxU": max_u + padding,
        "maxV": max_v + padding,
    }


def _component_code(name: str) -> str:
    upper = name.upper()
    for code in ("A100", "A180", "A200", "A300", "A500", "A600", "A700", "A800", "T401"):
        if code in upper:
            return code
    return name.split("-")[0]
