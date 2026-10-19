#!/usr/bin/env python3
"""Validate A300/A700 escape poses against the fixed selected layout.

Unlike the combinatorial diagnostic, this script does not re-enumerate every
module.  It keeps the selected solver layout fixed, moves only A300 to each
candidate relation, and evaluates process, spatial, projected-overlap, and
interaction-envelope hard gates.  CAD is never opened or modified.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.constraint_layout import (  # noqa: E402
    _apply_semantic_footprint_override,
    _evaluate_interaction_hard_constraints,
    _evaluate_spatial_hard_constraints,
    _infer_roles,
    _inject_provisional_components,
    _normalize_allowed_projected_overlap_pairs,
    _normalize_portal_constraints,
    _placement_at_anchor,
    _post_solve_projected_overlap_pairs,
    _read_footprints,
    _semantic_projected_overlap_pairs,
    _validate_placements,
)
from demo_backend.layout_preview import (  # noqa: E402
    apply_project02_solve_profile,
    build_source_independent_options,
)
from demo_backend.process_constraints import (  # noqa: E402
    compile_process_constraints,
    evaluate_process_constraints,
    normalize_module_semantics,
    role_overrides_from_semantics,
)


A300 = "FL9A24D062A300.001-1"
A700 = "FL9A24D062A700.001-1"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def failures(validation: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for item in validation.get("diagnostics") or []
        if item.get("hard", True) and item.get("success") is False
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--solution", type=Path, required=True)
    parser.add_argument("--feedback", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    request, profile_metadata = apply_project02_solve_profile(
        load(args.request.resolve()), "reduced-prototype"
    )
    solution = load(args.solution.resolve())
    feedback = load(args.feedback.resolve())
    options = build_source_independent_options(request, ROOT)
    geometry_path = Path(str(request["geometryCapturePath"]))
    if not geometry_path.is_absolute():
        geometry_path = ROOT / geometry_path
    capture, _ = _inject_provisional_components(
        load(geometry_path.resolve()), options.provisional_components
    )
    footprints = _read_footprints(capture)
    semantics = normalize_module_semantics(
        [item.component_name for item in footprints], options.module_semantics
    )
    footprints = [
        _apply_semantic_footprint_override(item, semantics.get(item.component_name))
        for item in footprints
    ]
    footprint_by_name = {item.component_name: item for item in footprints}
    roles = _infer_roles(
        footprints,
        {**role_overrides_from_semantics(semantics), **options.role_overrides},
    )[0]
    portal = _normalize_portal_constraints(
        footprints, roles, options.portal_pass_through
    )
    explicit_overlaps = _normalize_allowed_projected_overlap_pairs(
        footprints, options.allowed_projected_overlap_pairs
    )
    semantic_overlaps = _semantic_projected_overlap_pairs(semantics, roles) | explicit_overlaps
    semantic_overlaps |= _post_solve_projected_overlap_pairs(semantics)
    gantry_name = next(name for name, role in roles.items() if role == "gantry")

    solution_by_name = {
        item["componentName"]: item for item in solution.get("components") or []
    }
    placements = []
    for footprint in footprints:
        component = solution_by_name[footprint.component_name]
        layout = component["layout2d"]
        constraint_placement = component.get("constraintPlacement") or {}
        placements.append(
            _placement_at_anchor(
                footprint,
                roles[footprint.component_name],
                int(constraint_placement.get("rotationQuarters") or 0),
                float(layout["x"]),
                float(layout["y"]),
                bool(constraint_placement.get("containmentRelaxed", False)),
            )
        )
    base_by_name = {item.component_name: item for item in placements}
    gantry = base_by_name[gantry_name]
    long_axis = "u" if (gantry.bounds[2] - gantry.bounds[0]) >= (gantry.bounds[3] - gantry.bounds[1]) else "v"
    process_constraints = compile_process_constraints(
        [item.component_name for item in footprints],
        semantics,
        roles,
        gantry_name,
        long_axis,
        options.process_constraints,
        options.auto_generate_process_constraints,
        options.minimum_clearance_meters,
    )

    current_u = base_by_name[A300].anchor_u - base_by_name[A700].anchor_u
    current_v = base_by_name[A300].anchor_v - base_by_name[A700].anchor_v
    exclusion = feedback["confirmedCollisionPairs"][0]["relativePoseExclusion"]
    offsets = exclusion.get("candidateEscapeOffsetsMeters") or []
    margin = 0.0001
    labels = ("negative-u", "positive-v", "negative-v", "positive-u")
    scenarios: list[dict[str, Any]] = []
    for label, offset in zip(labels, offsets):
        du, dv = float(offset[0]), float(offset[1])
        du += margin if du > 0 else -margin if du < 0 else 0.0
        dv += margin if dv > 0 else -margin if dv < 0 else 0.0
        scenarios.append(
            {
                "id": f"exact-escape-{label}",
                "deltaU": current_u + du,
                "deltaV": current_v + dv,
            }
        )
    scenarios.append(
        {"id": "prototype-service-relation", "deltaU": 0.0, "deltaV": 0.12075}
    )

    results = []
    for scenario in scenarios:
        started = time.perf_counter()
        changed = list(placements)
        a300_index = next(
            index for index, item in enumerate(changed) if item.component_name == A300
        )
        a700 = base_by_name[A700]
        a300 = base_by_name[A300]
        changed[a300_index] = _placement_at_anchor(
            footprint_by_name[A300],
            roles[A300],
            a300.rotation_quarters,
            a700.anchor_u + float(scenario["deltaU"]),
            a700.anchor_v + float(scenario["deltaV"]),
            a300.containment_relaxed,
        )
        geometric = _validate_placements(
            changed,
            gantry_name,
            portal,
            semantic_overlaps,
            explicit_overlaps,
        )
        process = evaluate_process_constraints(
            process_constraints,
            semantics,
            footprint_by_name,
            changed,
            roles,
            long_axis,
        )
        spatial = _evaluate_spatial_hard_constraints(
            changed,
            footprint_by_name,
            roles,
            semantics,
            gantry_name,
            portal,
            minimum_transport_gantry_overlap_ratio=options.minimum_transport_gantry_overlap_ratio,
            minimum_portal_gantry_overlap_ratio=options.minimum_portal_gantry_overlap_ratio,
            minimum_functional_gantry_overlap_ratio=options.minimum_functional_gantry_overlap_ratio,
            minimum_functional_gantry_boundary_clearance_meters=options.minimum_functional_gantry_boundary_clearance_meters,
            maximum_transport_gantry_center_offset_meters=options.maximum_transport_gantry_center_offset_meters,
            maximum_portal_gantry_center_offset_meters=options.maximum_portal_gantry_center_offset_meters,
            maximum_portal_gantry_overhang_meters=options.maximum_portal_gantry_overhang_meters,
        )
        interaction = _evaluate_interaction_hard_constraints(
            changed,
            footprint_by_name,
            semantics,
            portal,
            long_axis,
            options.minimum_clearance_meters,
            allow_post_solve_projection_overlaps=True,
            focus_component_name=A300,
        )
        hard_feasible = bool(
            geometric.get("success")
            and process.get("hardFeasible")
            and spatial.get("hardFeasible")
            and interaction.get("hardFeasible")
        )
        results.append(
            {
                **scenario,
                "hardFeasible": hard_feasible,
                "elapsedSeconds": time.perf_counter() - started,
                "geometricOverlapPairs": geometric.get("overlapPairs") or [],
                "processHardFailures": failures(process),
                "spatialHardFailures": failures(spatial),
                "interactionHardFailures": failures(interaction),
                "conditionalCadReviewDiagnostics": [
                    item
                    for item in interaction.get("diagnostics") or []
                    if item.get("requiresCadInterferenceValidation")
                    and item.get("collisionDetected")
                ],
            }
        )
        print(
            f"{scenario['id']}: feasible={hard_feasible} "
            f"elapsed={results[-1]['elapsedSeconds']:.3f}s",
            flush=True,
        )

    feasible = [item for item in results if item["hardFeasible"]]
    report = {
        "schemaVersion": "project02-a300-a700-direct-escape-validation/v1",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "success": True,
        "status": "DIRECT_ESCAPE_FOUND" if feasible else "DIRECT_ESCAPE_NOT_FOUND",
        "cadMutationPerformed": False,
        "profileMetadata": profile_metadata,
        "currentRejectedRelation": {"deltaU": current_u, "deltaV": current_v},
        "scenarios": results,
        "recommendedScenarioId": feasible[0]["id"] if feasible else None,
        "nextGate": (
            "Use the recommended relation as a deterministic repair seed, then run a full solve."
            if feasible
            else "Use the recorded hard failures to redesign the repair domain; do not weaken unrelated constraints."
        ),
    }
    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.output.resolve().write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "status": report["status"],
        "recommendedScenarioId": report["recommendedScenarioId"],
        "output": str(args.output.resolve()),
    }, ensure_ascii=False, indent=2))
    return 0 if feasible else 2


if __name__ == "__main__":
    raise SystemExit(main())
