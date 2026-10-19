#!/usr/bin/env python3
"""Build a hybrid AC00 snapshot, collapsing CAD-fragile branches as subassemblies."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.resolve().read_text(encoding="utf-8-sig"))


def _components(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("components") or payload.get("Components")
    if rows is None:
        tool = payload.get("toolResult") or payload.get("ToolResult") or {}
        rows = tool.get("components") or tool.get("Components")
    if not isinstance(rows, list):
        raise ValueError("Subtree capture has no components list.")
    return rows


def build(
    capture: dict[str, Any], collapsed_assemblies: list[str], capture_path: Path | None = None
) -> dict[str, Any]:
    rows = _components(capture)
    by_relative = {str(row["relativeHierarchyPath"]): row for row in rows}
    for relative in collapsed_assemblies:
        row = by_relative.get(relative)
        if row is None:
            raise ValueError(f"Collapsed branch was not captured: {relative}")
        if not str(row.get("path") or "").lower().endswith(".sldasm"):
            raise ValueError(f"Collapsed branch is not an assembly: {relative}")

    selected: list[tuple[dict[str, Any], str]] = []
    for row in rows:
        relative = str(row["relativeHierarchyPath"])
        if relative == "@root":
            continue
        collapsed_owner = next(
            (
                branch
                for branch in collapsed_assemblies
                if relative == branch or relative.startswith(branch + "/")
            ),
            None,
        )
        if collapsed_owner is not None:
            if relative == collapsed_owner:
                selected.append((row, "collapsed-subassembly"))
            continue
        if str(row.get("path") or "").lower().endswith(".sldprt"):
            selected.append((row, "leaf-part"))

    modules: list[dict[str, Any]] = []
    manifest: list[dict[str, Any]] = []
    fixed: list[str] = []
    covered_leaf_count = 0
    for index, (row, kind) in enumerate(selected, start=1):
        source = Path(str(row["path"]))
        if not source.is_file():
            raise FileNotFoundError(source)
        transform = [float(value) for value in row["transform"]]
        if len(transform) != 16:
            raise ValueError(f"Invalid Transform2 for {row['relativeHierarchyPath']}")
        token = f"AC00_HYBRID_NODE_{index:03d}"
        fixed.append(token)
        relative = str(row["relativeHierarchyPath"])
        modules.append(
            {
                "ModuleToken": token,
                "Name": str(row.get("name") or source.stem),
                "Path": str(source.resolve()),
                "HierarchyPath": f"{token}::{relative}",
                "SourceTransform": transform,
                "IsSuppressed": False,
                "SuppressionState": 3,
                "SuppressionStateName": "swComponentFullyResolved",
                "VisibilityState": 1,
                "ReferencedConfiguration": row.get("referencedConfiguration"),
                "SolvingState": 0,
                "SolvingStateName": "swComponentRigidSolving",
            }
        )
        covered = [
            child
            for child in rows
            if str(child.get("path") or "").lower().endswith(".sldprt")
            and (
                str(child["relativeHierarchyPath"]) == relative
                or str(child["relativeHierarchyPath"]).startswith(relative + "/")
            )
        ]
        covered_leaf_count += len(covered)
        manifest.append(
            {
                "moduleToken": token,
                "sourceRelativeHierarchyPath": relative,
                "sourceNodePath": str(source.resolve()),
                "nodeKind": kind,
                "coveredLeafInstanceCount": len(covered),
                "expectedWorldTransform": transform,
            }
        )
    total_leaves = sum(
        str(row.get("path") or "").lower().endswith(".sldprt") for row in rows
    )
    if covered_leaf_count != total_leaves:
        raise ValueError(
            f"Hybrid coverage mismatch: covered={covered_leaf_count}, expected={total_leaves}"
        )
    capture_sha = (
        hashlib.sha256(capture_path.resolve().read_bytes()).hexdigest()
        if capture_path
        else None
    )
    return {
        "SchemaVersion": "editable-module-mate-graph/v1",
        "SourceAssemblyPath": capture.get("sourceAssemblyPath", ""),
        "ModuleCount": len(modules),
        "InterModuleMateCount": 0,
        "Modules": modules,
        "Mates": [],
        "MateBundleCount": 0,
        "MateBundles": [],
        "SavedJsonPath": None,
        "EditPolicy": {
            "baseModuleToken": fixed[0],
            "initialPlacementMode": "source_pose",
            "sourceGraphImmutable": True,
            "fixedModuleTokens": fixed,
            "caseAnchoredModuleTokens": [],
            "targetLeafPoseAnchors": [],
        },
        "StaticSnapshotAudit": {
            "schemaVersion": "project03-ac00-hybrid-static-snapshot/v1",
            "sourceCapturePath": str(capture_path.resolve()) if capture_path else None,
            "sourceCaptureSha256": capture_sha,
            "leafInstanceCount": len(modules),
            "sourceLeafInstanceCount": total_leaves,
            "coveredSourceLeafInstanceCount": covered_leaf_count,
            "collapsedAssemblyBranches": collapsed_assemblies,
            "leafManifest": manifest,
            "hierarchyPreserved": False,
            "internalMatesPreservedOnlyInsideCollapsedBranches": True,
            "motionSemanticsPreserved": False,
            "productionReady": False,
            "allowedClaim": "static full-geometry hybrid reconstruction only",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", required=True, type=Path)
    parser.add_argument("--collapse-assembly", action="append", default=[])
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if not args.collapse_assembly:
        parser.error("at least one --collapse-assembly is required")
    capture_path = args.capture.resolve()
    graph = build(load(capture_path), args.collapse_assembly, capture_path)
    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.output.resolve().write_text(
        json.dumps(graph, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"output": str(args.output.resolve()), "nodeCount": graph["ModuleCount"], "coveredSourceLeafCount": graph["StaticSnapshotAudit"]["coveredSourceLeafInstanceCount"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
