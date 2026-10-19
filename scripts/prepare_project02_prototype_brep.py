"""Extract the eight Replay targets and prepare staged B-Rep validation.

The full prototype contains unrelated top-level components and, in particular,
more than one T401 instance.  This script therefore matches the exact component
instances named by the solved layout before applying the exhaustive 28-pair
static-collision policy.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from screen_source_independent_layout_3d import classify_world_aabb_pairs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay-result", type=Path, required=True)
    parser.add_argument("--layout", type=Path, required=True)
    parser.add_argument("--assembly", type=Path, required=True)
    parser.add_argument("--poses-output", type=Path, required=True)
    parser.add_argument("--screening-output", type=Path, required=True)
    parser.add_argument("--manifest-output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    replay = json.loads(args.replay_result.read_text(encoding="utf-8"))
    layout = json.loads(args.layout.read_text(encoding="utf-8"))
    pose_step = next(
        step for step in replay["steps"] if step["tool"] == "list_component_poses"
    )
    all_poses = pose_step["payload"]
    expected = [item["componentName"] for item in layout["components"]]
    by_name: dict[str, list[dict]] = {}
    for pose in all_poses:
        by_name.setdefault(pose["Name"], []).append(pose)

    missing = [name for name in expected if len(by_name.get(name, [])) == 0]
    ambiguous = [name for name in expected if len(by_name.get(name, [])) > 1]
    if missing or ambiguous:
        raise RuntimeError(
            f"Replay targets are not uniquely resolved: missing={missing}, "
            f"ambiguous={ambiguous}"
        )
    selected = [by_name[name][0] for name in expected]
    boxes = {item["Name"]: item["BoundingBoxWorld"] for item in selected}
    policy = layout["constraintPlan"]["staticCollisionPolicy"]
    diagnostics = classify_world_aabb_pairs(boxes, policy)

    strict_failures = [
        item for item in diagnostics if item["status"] == "failed_strict_inflated_aabb"
    ]
    exact_candidates = [item for item in diagnostics if item["requiresExactBrep"]]
    broad_phase_passes = [
        item
        for item in diagnostics
        if item["status"] in {"passed_by_world_aabb", "passed_by_strict_inflated_aabb"}
    ]
    unclassified = [
        item for item in diagnostics if item["status"] == "failed_unclassified_pair"
    ]
    screening = {
        "success": not strict_failures and not unclassified,
        "status": (
            "BROAD_PHASE_READY_FOR_EXACT_BREP"
            if not strict_failures and not unclassified
            else "BROAD_PHASE_HARD_FAILURE"
        ),
        "assemblyPath": str(args.assembly.resolve()),
        "replayResultPath": str(args.replay_result.resolve()),
        "layoutPath": str(args.layout.resolve()),
        "selectedComponentCount": len(selected),
        "pairCount": len(diagnostics),
        "strictFailureCount": len(strict_failures),
        "unclassifiedPairCount": len(unclassified),
        "broadPhasePassCount": len(broad_phase_passes),
        "exactBrepCandidateCount": len(exact_candidates),
        "strictFailures": strict_failures,
        "exactBrepCandidates": exact_candidates,
        "broadPhasePasses": broad_phase_passes,
        "pairDiagnostics": diagnostics,
    }
    manifest = {
        "assemblyPath": str(args.assembly.resolve()),
        "pairs": [item["components"] for item in exact_candidates],
        "selectionReason": (
            "Only pairs classified as brep_on_aabb_overlap whose actual Replay "
            "world AABBs are not separated are submitted to leaf-level B-Rep."
        ),
    }

    for path, payload in (
        (args.poses_output, selected),
        (args.screening_output, screening),
        (args.manifest_output, manifest),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    print(json.dumps(screening, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
