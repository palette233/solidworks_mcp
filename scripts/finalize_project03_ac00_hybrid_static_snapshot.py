#!/usr/bin/env python3
"""Create the release evidence envelope for the batched AC00 hybrid snapshot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.resolve().read_text(encoding="utf-8-sig"))


def pick(value: dict[str, Any], name: str, default: Any = None) -> Any:
    return value.get(name, value.get(name[0].lower() + name[1:], default))


def build(
    hybrid_graph: dict[str, Any],
    batch_manifest: dict[str, Any],
    batch_closures: list[dict[str, Any]],
    root_run: dict[str, Any],
    branch_comparisons: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    audit = hybrid_graph["StaticSnapshotAudit"]
    tool = root_run.get("toolResult") or root_run.get("ToolResult") or {}
    all_batches_passed = (
        len(batch_closures) == batch_manifest["batchCount"]
        and all(item.get("success") for item in batch_closures)
    )
    root_statuses = pick(tool, "ComponentStatuses", []) or []
    root_passed = (
        bool(root_run.get("success"))
        and bool(pick(tool, "Success", False))
        and len(root_statuses) == batch_manifest["batchCount"]
        and all(pick(item, "SolvingStateMatches", False) for item in root_statuses)
    )
    branches_passed = bool(branch_comparisons) and all(
        item.get("stable") is True and item.get("unstableCount") == 0
        for item in branch_comparisons.values()
    )
    coverage_passed = (
        audit["coveredSourceLeafInstanceCount"]
        == audit["sourceLeafInstanceCount"]
        == 118
    )
    success = all([all_batches_passed, root_passed, branches_passed, coverage_passed])
    return {
        "schemaVersion": "project03-ac00-hybrid-static-snapshot-closure/v1",
        "success": success,
        "status": (
            "STATIC_FULL_GEOMETRY_HYBRID_RECONSTRUCTION_PASSED"
            if success
            else "STATIC_FULL_GEOMETRY_HYBRID_RECONSTRUCTION_FAILED"
        ),
        "outputAssemblyPath": root_run.get("outputAssemblyPath"),
        "claims": {
            "sourceLeafGeometryCoverageComplete": coverage_passed,
            "topLevelSnapshotPosesReconstructed": all_batches_passed and root_passed,
            "collapsedRigidBranchPosesReconstructed": branches_passed,
            "originalAC00HierarchyReconstructed": False,
            "originalAC00MateGraphReconstructed": False,
            "motionSemanticsReconstructed": False,
            "productionDynamicClosure": False,
        },
        "metrics": {
            "sourceLeafInstanceCount": audit["sourceLeafInstanceCount"],
            "coveredSourceLeafInstanceCount": audit["coveredSourceLeafInstanceCount"],
            "hybridTopLevelNodeCount": hybrid_graph["ModuleCount"],
            "batchCount": batch_manifest["batchCount"],
            "batchClosuresPassed": sum(bool(item.get("success")) for item in batch_closures),
            "rootReopenedModuleCount": len(root_statuses),
            "rootCadDurationSeconds": root_run.get("durationSeconds"),
            "branchComparisons": {
                name: {
                    "comparedCount": item.get("comparedCount"),
                    "unstableCount": item.get("unstableCount"),
                    "maximumTransformElementError": item.get("maximumTransformElementError"),
                    "maximumTranslationDistanceMeters": item.get("maximumTranslationDistanceMeters"),
                }
                for name, item in branch_comparisons.items()
            },
        },
        "blockers": [] if success else [
            label
            for label, passed in (
                ("one or more CAD batch closures failed", all_batches_passed),
                ("snapshot root save/reopen verification failed", root_passed),
                ("one or more collapsed rigid branch poses drifted", branches_passed),
                ("source leaf geometry coverage is incomplete", coverage_passed),
            )
            if not passed
        ],
        "limitations": [
            "AC00 was reconstructed as a static hybrid snapshot.",
            "AC20/AC30/AC40 preserve their native rigid subassembly hierarchy; other selected nodes are fixed snapshots.",
            "The result is suitable for static geometry/collision evidence, not kinematic or production motion validation.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hybrid-graph", required=True, type=Path)
    parser.add_argument("--batch-manifest", required=True, type=Path)
    parser.add_argument("--root-run", required=True, type=Path)
    parser.add_argument("--branch-comparison", action="append", default=[])
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    manifest = load(args.batch_manifest)
    batch_closures = [load(Path(item["closurePath"])) for item in manifest["batches"]]
    comparisons = {
        Path(path).name.split("_")[0].upper(): load(Path(path))
        for path in args.branch_comparison
    }
    closure = build(
        load(args.hybrid_graph), manifest, batch_closures, load(args.root_run), comparisons
    )
    args.output.resolve().write_text(
        json.dumps(closure, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"success": closure["success"], "status": closure["status"], **closure["metrics"]}, ensure_ascii=False))
    return 0 if closure["success"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
