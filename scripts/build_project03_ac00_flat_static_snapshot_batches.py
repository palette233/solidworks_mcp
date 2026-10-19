#!/usr/bin/env python3
"""Split a large AC00 leaf snapshot graph into restartable CAD batches."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any


IDENTITY = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.resolve().read_text(encoding="utf-8-sig"))


def write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def split_graph(
    graph: dict[str, Any], output_dir: Path, chunk_size: int
) -> dict[str, Any]:
    if chunk_size < 1:
        raise ValueError("chunk_size must be positive")
    modules = graph.get("Modules") or []
    manifest = graph.get("StaticSnapshotAudit", {}).get("leafManifest") or []
    if len(modules) != len(manifest):
        raise ValueError("Module and leaf-manifest counts must match.")
    manifest_by_token = {item["moduleToken"]: item for item in manifest}
    batches: list[dict[str, Any]] = []
    for batch_index, start in enumerate(range(0, len(modules), chunk_size), start=1):
        selected = copy.deepcopy(modules[start : start + chunk_size])
        tokens = [item["ModuleToken"] for item in selected]
        batch_graph = copy.deepcopy(graph)
        batch_graph["Modules"] = selected
        batch_graph["ModuleCount"] = len(selected)
        batch_graph["EditPolicy"]["baseModuleToken"] = tokens[0]
        batch_graph["EditPolicy"]["fixedModuleTokens"] = tokens
        batch_graph["StaticSnapshotAudit"]["leafInstanceCount"] = len(selected)
        batch_graph["StaticSnapshotAudit"]["leafManifest"] = [
            copy.deepcopy(manifest_by_token[token]) for token in tokens
        ]
        batch_graph["StaticSnapshotAudit"]["batch"] = {
            "batchIndex": batch_index,
            "startLeafIndex": start + 1,
            "endLeafIndex": start + len(selected),
            "parentLeafInstanceCount": len(modules),
        }
        graph_path = output_dir / f"batch_{batch_index:02d}.graph.json"
        assembly_path = output_dir / f"AC00_flat_batch_{batch_index:02d}.SLDASM"
        result_path = output_dir / f"batch_{batch_index:02d}.result.json"
        closure_path = output_dir / f"batch_{batch_index:02d}.closure.json"
        write(graph_path, batch_graph)
        batches.append(
            {
                "batchIndex": batch_index,
                "leafCount": len(selected),
                "graphPath": str(graph_path.resolve()),
                "assemblyPath": str(assembly_path.resolve()),
                "resultPath": str(result_path.resolve()),
                "closurePath": str(closure_path.resolve()),
                "moduleTokens": tokens,
            }
        )
    return {
        "schemaVersion": "project03-ac00-flat-static-snapshot-batches/v1",
        "leafInstanceCount": len(modules),
        "chunkSize": chunk_size,
        "batchCount": len(batches),
        "batches": batches,
    }


def build_root_graph(batch_manifest: dict[str, Any]) -> dict[str, Any]:
    modules: list[dict[str, Any]] = []
    fixed: list[str] = []
    for batch in batch_manifest["batches"]:
        assembly = Path(batch["assemblyPath"])
        closure = Path(batch["closurePath"])
        if not assembly.is_file():
            raise FileNotFoundError(assembly)
        if not closure.is_file() or not load(closure).get("success"):
            raise ValueError(f"Batch closure has not passed: {closure}")
        token = f"AC00_STATIC_BATCH_{int(batch['batchIndex']):02d}"
        fixed.append(token)
        modules.append(
            {
                "ModuleToken": token,
                "Name": assembly.stem,
                "Path": str(assembly.resolve()),
                "HierarchyPath": f"{assembly.stem}-1",
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
    return {
        "SchemaVersion": "editable-module-mate-graph/v1",
        "SourceAssemblyPath": "project03-ac00-flat-static-snapshot-batches",
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
        "StaticSnapshotBatchRootAudit": {
            "batchCount": len(modules),
            "leafInstanceCount": batch_manifest["leafInstanceCount"],
            "allBatchClosuresPassed": True,
            "batchAssembliesInsertedAtIdentity": True,
            "hierarchyPreserved": False,
            "internalMatesPreserved": False,
            "motionSemanticsPreserved": False,
            "productionReady": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--chunk-size", type=int, default=20)
    parser.add_argument("--build-root", action="store_true")
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    manifest_path = output_dir / "batch_manifest.json"
    if args.build_root:
        manifest = load(manifest_path)
        root = build_root_graph(manifest)
        root_path = output_dir / "ac00_flat_static_root.graph.json"
        write(root_path, root)
        print(json.dumps({"rootGraph": str(root_path), "batchCount": root["ModuleCount"]}, ensure_ascii=False))
        return 0
    if args.graph is None:
        parser.error("--graph is required unless --build-root is used")
    manifest = split_graph(load(args.graph), output_dir, args.chunk_size)
    write(manifest_path, manifest)
    print(json.dumps({"manifest": str(manifest_path), "batchCount": manifest["batchCount"], "leafCount": manifest["leafInstanceCount"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
