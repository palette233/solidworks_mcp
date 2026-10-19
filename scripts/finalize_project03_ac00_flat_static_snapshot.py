#!/usr/bin/env python3
"""Certify one AC00 flattened static snapshot rebuild against its leaf manifest."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.resolve().read_text(encoding="utf-8-sig"))


def _pick(value: dict[str, Any], name: str, default: Any = None) -> Any:
    return value.get(name, value.get(name[0].lower() + name[1:], default))


def build_closure(
    graph: dict[str, Any], run: dict[str, Any], graph_path: Path, run_path: Path
) -> dict[str, Any]:
    tool = run.get("toolResult") or run.get("ToolResult") or {}
    statuses = _pick(tool, "ComponentStatuses", []) or []
    status_by_token = {
        str(_pick(item, "ModuleToken")): item for item in statuses
    }
    manifest = graph["StaticSnapshotAudit"]["leafManifest"]
    comparisons: list[dict[str, Any]] = []
    max_error = 0.0
    for expected in manifest:
        token = expected["moduleToken"]
        status = status_by_token.get(token)
        observed = _pick(status or {}, "WorldTransform")
        expected_transform = expected["expectedWorldTransform"]
        error = math.inf
        if isinstance(observed, list) and len(observed) == 16:
            error = max(abs(float(a) - float(b)) for a, b in zip(expected_transform, observed))
            max_error = max(max_error, error)
        comparisons.append(
            {
                "moduleToken": token,
                "sourceRelativeHierarchyPath": expected["sourceRelativeHierarchyPath"],
                "found": status is not None,
                "maxTransformElementError": None if math.isinf(error) else error,
                "poseMatches": error <= 1e-10,
                "solvingStateMatches": bool(
                    _pick(status or {}, "SolvingStateMatches", False)
                ),
                "notOverConstrained": _pick(status or {}, "ConstrainedStatus") != 2,
            }
        )
    all_found = len(statuses) == len(manifest) and all(item["found"] for item in comparisons)
    all_pose_match = all(item["poseMatches"] for item in comparisons)
    semantics_match = all(item["solvingStateMatches"] for item in comparisons)
    not_overconstrained = all(item["notOverConstrained"] for item in comparisons)
    run_success = bool(run.get("success", False)) and bool(_pick(tool, "Success", False))
    success = all(
        [run_success, all_found, all_pose_match, semantics_match, not_overconstrained]
    )
    return {
        "schemaVersion": "project03-ac00-flat-static-snapshot-closure/v1",
        "success": success,
        "status": (
            "STATIC_FULL_GEOMETRY_RECONSTRUCTION_PASSED"
            if success
            else "STATIC_FULL_GEOMETRY_RECONSTRUCTION_FAILED"
        ),
        "graphPath": str(graph_path.resolve()),
        "runPath": str(run_path.resolve()),
        "outputAssemblyPath": run.get("outputAssemblyPath"),
        "claims": {
            "leafGeometryAndWorldPoseReconstructed": success,
            "originalHierarchyReconstructed": False,
            "internalMatesReconstructed": False,
            "motionSemanticsReconstructed": False,
            "productionDynamicClosure": False,
        },
        "metrics": {
            "expectedLeafCount": len(manifest),
            "observedLeafCount": len(statuses),
            "allLeavesFound": all_found,
            "allLeafPosesMatch": all_pose_match,
            "maxTransformElementError": max_error if all_found else None,
            "allSolvingStatesMatch": semantics_match,
            "noLeafOverConstrained": not_overconstrained,
            "cadRunDurationSeconds": run.get("durationSeconds"),
        },
        "comparisons": comparisons,
        "blockers": [] if success else [
            name
            for name, passed in (
                ("cad rebuild/reopen failed", run_success),
                ("leaf component count or identity mismatch", all_found),
                ("one or more leaf poses drifted", all_pose_match),
                ("one or more solving states changed", semantics_match),
                ("one or more leaves are over-constrained", not_overconstrained),
            )
            if not passed
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", required=True, type=Path)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    closure = build_closure(load(args.graph), load(args.run), args.graph, args.run)
    args.output.resolve().write_text(
        json.dumps(closure, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"success": closure["success"], **closure["metrics"]}, ensure_ascii=False))
    return 0 if closure["success"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
