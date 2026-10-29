"""Prepare an explicit support-position Demo without authorizing hole compatibility."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

from build_cross_project_wastecup_datum_candidate import (
    ROOT, P02, P05, _read, build_project05_p000_to_project02_a600_datum_candidate,
)
from demo_backend.cross_project_wastecup_datum_candidate import _digest

OUTPUT = ROOT / "demo/cross_project_substitution/wastecup-project05-to-project02-v1/support-position-demo-v2"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--longitudinal-mm", type=float, default=80)
    parser.add_argument("--lateral-mm", type=float, default=390)
    parser.add_argument("--initial-placement-variant", type=int, default=1)
    args = parser.parse_args()
    started, clock = datetime.now(timezone.utc).isoformat(), time.perf_counter()
    if args.output.exists():
        raise FileExistsError("New demo must not overwrite an existing run directory")
    if args.initial_placement_variant < 0:
        raise ValueError("initial placement variant must be non-negative")
    result = build_project05_p000_to_project02_a600_datum_candidate(
        a300_graph=_read(P02 / "assembly_plan_effective.json"),
        a300_semantic_catalog=_read(P02 / "semantic_port_catalog.json"),
        a300_endpoint_catalog=_read(P02 / "face_endpoint_catalog.json"),
        p000_graph=_read(P05 / "assembly_plan_effective.json"),
        p000_semantic_catalog=_read(P05 / "semantic_port_catalog.json"),
        p000_endpoint_catalog=_read(P05 / "face_endpoint_catalog.json"),
        longitudinal_distance_meters=args.longitudinal_mm/1000,
        lateral_distance_meters=args.lateral_mm/1000,
    )
    graph, audit = result["effectiveGraph"], result["audit"]
    # The bridge uses target SourceTransform only for a legacy read-only witness
    # when case anchors are disabled. Remove the historical prototype pose even
    # from that field; this identity placeholder is NOT an expected final pose.
    identity = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]
    next(m for m in graph["Modules"] if m["ModuleToken"] == "P000")["SourceTransform"] = identity
    graph["EditPolicy"] = {
        "baseModuleToken": "A600", "initialPlacementMode": "deterministic",
        "initialPlacementVariant": args.initial_placement_variant,
        "sourceGraphImmutable": True, "fixedModuleTokens": ["A600"],
        "caseAnchoredModuleTokens": [], "targetLeafPoseAnchors": [],
        "fixCaseAnchorBeforeMates": False,
    }
    policy = {
        "mode": "support_position_demo", "holePatternMatchRequired": False,
        "actualFixationMethod": "not_verified", "actualFixationNotice": "实际固定方式暂未验证",
        "directMechanicalCompatibilityClaim": False,
        "positionParametersMeters": {"longitudinal": args.longitudinal_mm/1000,
                                     "lateral": args.lateral_mm/1000, "supportGap": 0},
        "parameterAuthority": "explicit_demo_design_parameters_not_vendor_mounting_dimensions",
        "targetSourceTransformMeaning": "identity_placeholder_not_final_pose_witness",
        "acceptance": "active_real_mates_support_and_distance_parameters_save_close_reopen",
    }
    graph["SupportPositionDemoPolicy"] = policy
    audit.update(policy)
    audit["effectiveGraphDigest"] = _digest(graph)
    old_run = _read(OUTPUT.parent / "project02-A600-project05-P000-datum-v1.context-insert.result.json")
    source = Path(old_run["sourceAssemblyPath"])
    args.output.mkdir(parents=True)
    def write(name, data):
        path = args.output/name
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        return path
    graph_path = write("candidate_effective_mate_graph.json", graph)
    write("candidate_audit.json", audit)
    summary = {
        "sourceAssemblyPath": str(source),
        "sourceAssemblySha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "effectiveGraphPath": str(graph_path.resolve()),
        "effectiveGraphSha256": hashlib.sha256(graph_path.read_bytes()).hexdigest(),
        "outputAssemblyPath": str((args.output/"project02-A600-project05-P000-support-demo-v2.SLDASM").resolve()),
        "initialPlacementVariant": args.initial_placement_variant,
        "startedAtUtc": started, "finishedAtUtc": datetime.now(timezone.utc).isoformat(),
        "durationSeconds": time.perf_counter()-clock, **policy,
    }
    write("build-summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
