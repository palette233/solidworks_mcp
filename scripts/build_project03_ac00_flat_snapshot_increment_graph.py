#!/usr/bin/env python3
"""Replace AC00 in a Project03 effective graph with a fixed flat snapshot."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any


TARGET_TOKEN = "FL9A24D063AC00_STATIC_SNAPSHOT"
IDENTITY = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.resolve().read_text(encoding="utf-8-sig"))


def build(
    source_effective: dict[str, Any], snapshot_path: Path, snapshot_closure: dict[str, Any]
) -> dict[str, Any]:
    snapshot_path = snapshot_path.resolve()
    if not snapshot_path.is_file():
        raise FileNotFoundError(snapshot_path)
    if not snapshot_closure.get("success"):
        raise ValueError("The AC00 flat snapshot closure must pass before final insertion.")
    graph = copy.deepcopy(source_effective)
    modules = [
        module
        for module in graph["Modules"]
        if str(module.get("ModuleToken", "")).casefold() != "fl9a24d063ac00".casefold()
    ]
    if len(modules) != len(graph["Modules"]) - 1:
        raise ValueError("Expected exactly one AC00 module in the source effective graph.")
    modules.append(
        {
            "ModuleToken": TARGET_TOKEN,
            "Name": snapshot_path.stem,
            "Path": str(snapshot_path),
            "HierarchyPath": f"{snapshot_path.stem}-1",
            "SourceTransform": IDENTITY,
            "IsSuppressed": False,
            "SuppressionState": 3,
            "SuppressionStateName": "swComponentFullyResolved",
            "VisibilityState": 1,
            "ReferencedConfiguration": None,
            "SolvingState": 0,
            "SolvingStateName": "swComponentRigidSolving",
        }
    )
    graph["Modules"] = modules
    graph["ModuleCount"] = len(modules)
    graph["Mates"] = []
    graph["InterModuleMateCount"] = 0
    graph["MateBundles"] = []
    graph["MateBundleCount"] = 0
    policy = graph.setdefault("EditPolicy", {})
    policy["caseAnchoredModuleTokens"] = [TARGET_TOKEN]
    policy["targetLeafPoseAnchors"] = []
    policy["fixCaseAnchorBeforeMates"] = True
    policy["sourceGraphImmutable"] = True
    audit = graph.setdefault("SemanticAssemblyPlanAudit", {})
    audit["executionMode"] = "incremental-insert-flat-static-snapshot"
    audit["flatStaticSnapshot"] = {
        "targetModuleToken": TARGET_TOKEN,
        "snapshotAssemblyPath": str(snapshot_path),
        "snapshotAssemblySha256": hashlib.sha256(snapshot_path.read_bytes()).hexdigest(),
        "snapshotClosureStatus": snapshot_closure.get("status"),
        "leafGeometryAndWorldPoseReconstructed": True,
        "internalMatesPreserved": False,
        "motionSemanticsPreserved": False,
        "productionReady": False,
    }
    return graph


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-effective", required=True, type=Path)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--snapshot-closure", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = build(load(args.source_effective), args.snapshot, load(args.snapshot_closure))
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"output": str(output), "moduleCount": result["ModuleCount"], "target": TARGET_TOKEN}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
