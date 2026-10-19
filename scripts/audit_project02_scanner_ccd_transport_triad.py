"""Enumerate a small A180/A200/A800 relative-process grid without using source poses.

The prototype is used only to calibrate broad relative windows in the request JSON.
This audit consumes those windows, the currently selected solution, and the normal
process/spatial/interaction validators.  It does not write a solver result or move CAD.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "demo-backend" / "src"))

from demo_backend.constraint_layout import (  # noqa: E402
    _apply_semantic_footprint_override,
    _conditional_brep_leaf_hit_count,
    _evaluate_interaction_hard_constraints,
    _evaluate_spatial_hard_constraints,
    _height,
    _infer_roles,
    _placement_at_anchor,
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
SELECTED = ROOT / "demo" / "layout_previews" / "project02_selected_solution.json"
OUTPUT = ROOT / "demo" / "layout_previews" / "project02_v45_triad_offline_audit.json"

A180 = "FL9A24D062A180.001-1"
A200 = "FL9A24D062A200.001-1"
A800 = "FL9A24D062A800.001-1"


def _resolve(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _window_values(constraint: dict[str, object]) -> tuple[tuple[float, ...], tuple[float, ...]]:
    min_u = float(constraint["minDeltaU"])
    max_u = float(constraint["maxDeltaU"])
    min_v = float(constraint["minDeltaV"])
    max_v = float(constraint["maxDeltaV"])
    return (
        (min_u, (min_u + max_u) / 2.0, max_u),
        (min_v, (min_v + max_v) / 2.0, max_v),
    )


def main() -> None:
    request = json.loads(REQUEST.read_text(encoding="utf-8"))
    selected = json.loads(SELECTED.read_text(encoding="utf-8"))
    capture = json.loads(_resolve(request["geometryCapturePath"]).read_text(encoding="utf-8"))
    options = build_source_independent_options(request, ROOT)
    footprints = _read_footprints(capture)
    semantics = normalize_module_semantics(
        [item.component_name for item in footprints], options.module_semantics
    )
    footprints = [
        _apply_semantic_footprint_override(item, semantics.get(item.component_name))
        for item in footprints
    ]
    by_name = {item.component_name: item for item in footprints}
    roles, _ = _infer_roles(
        footprints,
        {**role_overrides_from_semantics(semantics), **options.role_overrides},
    )
    source_by_name = {
        item.component_name: _placement_at_source(item, roles[item.component_name])
        for item in footprints
    }
    source_gantry = next(value for value in source_by_name.values() if value.role == "gantry")
    selected_by_name = {item["componentName"]: item for item in selected["components"]}

    def placement_from_selected(component_name: str):
        item = by_name[component_name]
        raw = selected_by_name[component_name]["layout2d"]
        quarters = int(round((float(raw["thetaDegrees"]) - item.source_theta) / 90.0)) % 4
        return _placement_at_anchor(
            item,
            roles[component_name],
            quarters,
            source_gantry.anchor_u + float(raw["x"]),
            source_gantry.anchor_v + float(raw["y"]),
        )

    base_placements = [placement_from_selected(item.component_name) for item in footprints]
    base_by_name = {item.component_name: item for item in base_placements}
    gantry = next(item for item in base_placements if item.role == "gantry")
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
    configured = {str(item.get("id")): item for item in options.process_constraints}
    ccd_transport_u, ccd_transport_v = _window_values(
        configured["a200-a800-ccd-transport-process-window"]
    )
    scanner_transport_u, scanner_transport_v = _window_values(
        configured["a180-a800-v44-brep-clearance-window"]
    )
    current_transport = base_by_name[A800]
    transport_offsets = (-0.05, 0.0, 0.05)
    short_offsets = (-0.02, 0.0, 0.02)
    failures: Counter[str] = Counter()
    feasible: list[dict[str, object]] = []
    checked = 0

    for transport_u_offset in transport_offsets:
        for transport_v_offset in short_offsets:
            transport = _placement_at_anchor(
                by_name[A800],
                roles[A800],
                current_transport.rotation_quarters,
                current_transport.anchor_u + transport_u_offset,
                current_transport.anchor_v + transport_v_offset,
            )
            for ccd_du in ccd_transport_u:
                for ccd_dv in ccd_transport_v:
                    ccd = _placement_at_anchor(
                        by_name[A200],
                        roles[A200],
                        base_by_name[A200].rotation_quarters,
                        transport.anchor_u + ccd_du,
                        transport.anchor_v + ccd_dv,
                    )
                    # Enumerate the new direct scanner/transport clearance window.
                    # The independent scanner/CCD window is still evaluated below;
                    # treating all three windows independently as Cartesian min/mid/max
                    # grids misses their shared feasible event points.
                    for scanner_transport_du in scanner_transport_u:
                        for scanner_transport_dv in scanner_transport_v:
                            scanner = _placement_at_anchor(
                                by_name[A180],
                                roles[A180],
                                base_by_name[A180].rotation_quarters,
                                transport.anchor_u + scanner_transport_du,
                                transport.anchor_v + scanner_transport_dv,
                            )
                            replacements = {A180: scanner, A200: ccd, A800: transport}
                            placements = [replacements.get(item.component_name, item) for item in base_placements]
                            checked += 1
                            process = evaluate_process_constraints(
                                constraints, semantics, by_name, placements, roles, long_axis
                            )
                            if not process["hardFeasible"]:
                                failures["process"] += 1
                                for diagnostic in process.get("diagnostics") or []:
                                    if diagnostic.get("hard") and not diagnostic.get("success"):
                                        failures[f"process:{diagnostic.get('id', 'unknown')}"] += 1
                                continue
                            interaction = _evaluate_interaction_hard_constraints(
                                placements,
                                by_name,
                                semantics,
                                options.portal_pass_through,
                                long_axis,
                                options.minimum_clearance_meters,
                            )
                            if not interaction["hardFeasible"]:
                                failures["interaction"] += 1
                                continue
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
                            if not spatial["hardFeasible"]:
                                failures["spatial"] += 1
                                continue
                            reach = _validate_gantry_reach_regions(
                                gantry,
                                semantics.get(gantry.component_name),
                                require_contained=options.require_reach_inside_gantry,
                            )
                            if not reach["hardFeasible"]:
                                failures["reach"] += 1
                                continue
                            scanner_ccd_hits = _conditional_brep_leaf_hit_count(
                                scanner,
                                [ccd],
                                by_name,
                                semantics,
                                options.minimum_clearance_meters,
                            )
                            scanner_transport_hits = _conditional_brep_leaf_hit_count(
                                scanner,
                                [transport],
                                by_name,
                                semantics,
                                options.minimum_clearance_meters,
                            )
                            movement = sum(
                                math.dist(
                                    (replacements[name].anchor_u, replacements[name].anchor_v),
                                    (base_by_name[name].anchor_u, base_by_name[name].anchor_v),
                                )
                                for name in (A180, A200, A800)
                            )
                            feasible.append(
                                {
                                    "a800": [transport.anchor_u - gantry.anchor_u, transport.anchor_v - gantry.anchor_v],
                                    "a200": [ccd.anchor_u - gantry.anchor_u, ccd.anchor_v - gantry.anchor_v],
                                    "a180": [scanner.anchor_u - gantry.anchor_u, scanner.anchor_v - gantry.anchor_v],
                                    "a200RelativeToA800": [ccd_du, ccd_dv],
                                    "a180RelativeToA200": [scanner.anchor_u - ccd.anchor_u, scanner.anchor_v - ccd.anchor_v],
                                    "a180RelativeToA800": [scanner_transport_du, scanner_transport_dv],
                                    "a180A200LeafAabbHits": scanner_ccd_hits,
                                    "a180A800LeafAabbHits": scanner_transport_hits,
                                    "movementFromSelectedMeters": movement,
                                }
                            )

    feasible.sort(
        key=lambda item: (
            int(item["a180A200LeafAabbHits"]),
            int(item["a180A800LeafAabbHits"]),
            float(item["movementFromSelectedMeters"]),
        )
    )
    result = {
        "success": bool(feasible),
        "sourceIndependent": True,
        "prototypePoseUsedAsCandidate": False,
        "checkedCandidateCount": checked,
        "feasibleCandidateCount": len(feasible),
        "failureCounts": dict(failures),
        "topCandidates": feasible[:20],
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
