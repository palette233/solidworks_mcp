from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "demo-backend" / "src"))

from demo_backend.constraint_layout import (  # noqa: E402
    _apply_semantic_footprint_override,
    _candidate_has_disallowed_overlap,
    _candidate_interaction_feasible,
    _candidate_process_validation,
    _evaluate_interaction_hard_constraints,
    _infer_roles,
    _normalize_allowed_projected_overlap_pairs,
    _placement_at_source,
    _read_footprints,
    _semantic_projected_overlap_pairs,
)
from demo_backend.process_constraints import (  # noqa: E402
    compile_process_constraints,
    normalize_module_semantics,
    role_overrides_from_semantics,
)


REQUEST = ROOT / "demo" / "FL9A24D062A000_real_process_request.json"
OUTPUT = ROOT / "demo" / "layout_previews" / "project02_scanner_candidate_audit.json"


def main() -> None:
    request = json.loads(REQUEST.read_text(encoding="utf-8"))
    geometry_path = Path(request["geometryCapturePath"])
    if not geometry_path.is_absolute():
        geometry_path = ROOT / geometry_path
    capture = json.loads(geometry_path.read_text(encoding="utf-8"))
    footprints = _read_footprints(capture)
    semantics = normalize_module_semantics(
        [item.component_name for item in footprints], request["moduleSemantics"]
    )
    footprints = [
        _apply_semantic_footprint_override(item, semantics.get(item.component_name))
        for item in footprints
    ]
    by_name = {item.component_name: item for item in footprints}
    roles, _ = _infer_roles(
        footprints,
        {**role_overrides_from_semantics(semantics), **request.get("roleOverrides", {})},
    )
    gantry_name = next(name for name, role in roles.items() if role == "gantry")
    gantry = _placement_at_source(by_name[gantry_name], "gantry")
    long_axis = "u" if gantry.bounds[2] - gantry.bounds[0] >= gantry.bounds[3] - gantry.bounds[1] else "v"
    constraints = compile_process_constraints(
        list(by_name), semantics, roles, gantry_name, long_axis,
        tuple(request.get("processConstraints", [])),
        bool(request.get("autoGenerateProcessConstraints", True)),
        float(request.get("minimumClearanceMeters", 0.01)),
    )
    transport_name = next(name for name, role in roles.items() if role == "transport")
    scanner_name = next(
        name for name, semantic in semantics.items() if semantic.module_type == "scanner"
    )
    transport = _placement_at_source(by_name[transport_name], "transport")
    scanner = _placement_at_source(by_name[scanner_name], "functional")
    placements = [gantry, transport]
    overlap_pairs = _semantic_projected_overlap_pairs(semantics, roles) | _normalize_allowed_projected_overlap_pairs(
        footprints, tuple(tuple(pair) for pair in request.get("allowedProjectedOverlapPairs", []))
    )
    portal = {
        name: tuple(values) for name, values in request.get("portalPassThrough", {}).items()
    }
    process = _candidate_process_validation(
        scanner, placements, constraints, semantics, by_name, roles, long_axis
    )
    interaction_ok = _candidate_interaction_feasible(
        scanner, placements, by_name, semantics, portal, long_axis,
        float(request.get("minimumClearanceMeters", 0.01)),
    )
    interaction = _evaluate_interaction_hard_constraints(
        [*placements, scanner],
        by_name,
        semantics,
        portal,
        long_axis,
        float(request.get("minimumClearanceMeters", 0.01)),
        collision_pair_limit=1,
        focus_component_name=scanner.component_name,
    )
    report = {
        "scanner": scanner_name,
        "transport": transport_name,
        "scannerSourcePlacement": {
            "anchor": [scanner.anchor_u, scanner.anchor_v],
            "bounds": list(scanner.bounds),
        },
        "gantryBounds": list(gantry.bounds),
        "gantryOverlapRatio": (
            max(0.0, min(scanner.bounds[2], gantry.bounds[2]) - max(scanner.bounds[0], gantry.bounds[0]))
            * max(0.0, min(scanner.bounds[3], gantry.bounds[3]) - max(scanner.bounds[1], gantry.bounds[1]))
            / ((scanner.bounds[2] - scanner.bounds[0]) * (scanner.bounds[3] - scanner.bounds[1]))
        ),
        "disallowedProjectedOverlap": _candidate_has_disallowed_overlap(
            scanner,
            placements[1:],
            float(request.get("minimumClearanceMeters", 0.01)),
            portal,
            overlap_pairs,
        ),
        "processValidation": process,
        "interactionHardFeasible": interaction_ok,
        "interactionValidation": interaction,
    }
    report["sourceCandidateFeasible"] = bool(
        report["gantryOverlapRatio"]
        >= float(request.get("minimumFunctionalGantryOverlapRatio", 0.0)) - 1e-9
        and not report["disallowedProjectedOverlap"]
        and process["hardFeasible"]
        and interaction_ok
    )
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
