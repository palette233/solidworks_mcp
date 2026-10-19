"""Audit captured source poses against the current semantic hard constraints.

This is a calibration diagnostic only.  It never contributes source coordinates
to source-independent candidate generation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "demo-backend" / "src"))

from demo_backend.constraint_layout import (  # noqa: E402
    _apply_semantic_footprint_override,
    _evaluate_interaction_hard_constraints,
    _evaluate_spatial_hard_constraints,
    _height,
    _infer_roles,
    _placement_at_source,
    _read_footprints,
    _validate_gantry_reach_regions,
    _width,
)
from demo_backend.layout_preview import build_source_independent_options  # noqa: E402
from demo_backend.process_constraints import (  # noqa: E402
    compile_process_constraints,
    evaluate_process_constraints,
    normalize_module_semantics,
    role_overrides_from_semantics,
)


REQUEST = ROOT / "demo" / "FL9A24D062A000_real_process_request.json"
OUTPUT = ROOT / "demo" / "FL9A24D062A000_prototype_constraint_audit.json"


def resolve(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def main() -> None:
    request = json.loads(REQUEST.read_text(encoding="utf-8"))
    capture = json.loads(resolve(request["geometryCapturePath"]).read_text(encoding="utf-8"))
    options = build_source_independent_options(request, ROOT)
    footprints = _read_footprints(capture)
    semantics = normalize_module_semantics(
        [item.component_name for item in footprints], options.module_semantics
    )
    footprints = [
        _apply_semantic_footprint_override(item, semantics.get(item.component_name))
        for item in footprints
    ]
    roles, _ = _infer_roles(
        footprints,
        {**role_overrides_from_semantics(semantics), **options.role_overrides},
    )
    by_name = {item.component_name: item for item in footprints}
    placements = [
        _placement_at_source(item, roles[item.component_name]) for item in footprints
    ]
    gantry = next(item for item in placements if item.role == "gantry")
    long_axis = "u" if _width(gantry.bounds) >= _height(gantry.bounds) else "v"
    constraints = compile_process_constraints(
        list(by_name),
        semantics,
        roles,
        gantry.component_name,
        long_axis,
        options.process_constraints,
        options.auto_generate_process_constraints,
        options.minimum_clearance_meters,
    )
    process = evaluate_process_constraints(
        constraints, semantics, by_name, placements, roles, long_axis
    )
    interaction = _evaluate_interaction_hard_constraints(
        placements,
        by_name,
        semantics,
        options.portal_pass_through,
        long_axis,
        options.minimum_clearance_meters,
    )
    policy = request.get("sourceIndependentPolicy", {})
    spatial = _evaluate_spatial_hard_constraints(
        placements,
        by_name,
        roles,
        semantics,
        gantry.component_name,
        options.portal_pass_through,
        minimum_transport_gantry_overlap_ratio=options.minimum_transport_gantry_overlap_ratio,
        minimum_portal_gantry_overlap_ratio=options.minimum_portal_gantry_overlap_ratio,
        minimum_functional_gantry_overlap_ratio=options.minimum_functional_gantry_overlap_ratio,
        minimum_functional_gantry_boundary_clearance_meters=options.minimum_functional_gantry_boundary_clearance_meters,
        maximum_transport_gantry_center_offset_meters=options.maximum_transport_gantry_center_offset_meters,
        maximum_portal_gantry_center_offset_meters=options.maximum_portal_gantry_center_offset_meters,
        maximum_portal_gantry_overhang_meters=options.maximum_portal_gantry_overhang_meters,
    )
    reach = _validate_gantry_reach_regions(
        gantry, semantics.get(gantry.component_name), require_contained=options.require_reach_inside_gantry
    )
    result = {
        "success": bool(
            process["hardFeasible"]
            and interaction["hardFeasible"]
            and spatial["hardFeasible"]
            and reach["hardFeasible"]
        ),
        "auditOnly": True,
        "sourceCoordinatesUsedForSolving": False,
        "request": str(REQUEST),
        "processValidation": process,
        "interactionValidation": interaction,
        "spatialValidation": spatial,
        "reachValidation": reach,
        "note": (
            "Captured prototype poses are evaluated only to detect over-conservative or "
            "miscalibrated constraints; they are not source-independent solver candidates."
        ),
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": result["success"],
        "processHardFeasible": process["hardFeasible"],
        "interactionHardFeasible": interaction["hardFeasible"],
        "spatialHardFeasible": spatial["hardFeasible"],
        "reachHardFeasible": reach["hardFeasible"],
        "failedInteractionDiagnostics": [
            item for item in interaction["diagnostics"]
            if item.get("hard", True) and not item.get("success", False)
        ][:20],
        "failedSpatialDiagnostics": [
            item for item in spatial["diagnostics"]
            if item.get("hard", True) and not item.get("success", False)
        ][:20],
        "output": str(OUTPUT),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
