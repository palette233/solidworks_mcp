#!/usr/bin/env python3
"""Build a real three-relation A500/A600 direct-edit transaction from Project02."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.mate_graph_edit import compile_mate_graph_patch
from demo_backend.mate_transaction_preflight import preflight_direct_mate_transaction


DEFAULT_GRAPH = (
    ROOT
    / "demo/global_assembly_contexts/checkpoint-graphs/project02-full-static-graph-v1/"
    "project02-job-635438e6d96f-4e686e861b08.mate-graph.json"
)
DEFAULT_OUTPUT = (
    ROOT
    / "demo/global_assembly_contexts/checkpoint-graphs/project02-full-static-graph-v1/"
    "multi-mate-a500-a600-v1"
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build(source_graph: dict) -> tuple[dict, dict, dict, dict]:
    modules = [
        row
        for row in source_graph.get("Modules") or []
        if str(row.get("ModuleToken") or "").upper() in {"A500", "A600"}
    ]
    module_paths = {str(row.get("HierarchyPath") or "") for row in modules}
    mates = [
        row
        for row in source_graph.get("Mates") or []
        if {str(value).upper() for value in row.get("ModuleTokens") or []}
        == {"A500", "A600"}
        and set(str(value) for value in row.get("ModuleHierarchyPaths") or [])
        <= module_paths
    ]
    if len(modules) != 2:
        raise ValueError(f"Expected A500 and A600 modules, found {len(modules)} rows.")
    if len(mates) != 3 or {int(row.get("MateType", -1)) for row in mates} != {0, 5, 11}:
        raise ValueError("Expected real Project02 coincident, width, and distance relations.")

    subset = dict(source_graph)
    subset["Modules"] = modules
    subset["Mates"] = mates
    subset["ModuleCount"] = len(modules)
    subset["InterModuleMateCount"] = len(mates)
    patch = {
        "schemaVersion": "mate-graph-patch/v1",
        "baseModuleToken": "A600",
        "initialPlacementMode": "source_pose",
        "fixedContextModuleTokens": ["A600"],
        "caseAnchoredModuleTokens": [],
        "sourceMateNamesToSuppress": [str(row["MateName"]) for row in mates],
        "targetLeafPoseAnchors": [],
        "operations": [
            {
                "operation": "updateMate",
                "mateName": str(row["MateName"]),
                "changes": {"IsSuppressed": False},
            }
            for row in mates
        ],
    }
    effective = compile_mate_graph_patch(subset, patch)
    preflight = preflight_direct_mate_transaction(
        effective,
        "A500",
        require_closed_dof=True,
        require_multiple_operations=True,
    )
    if not preflight["publishAllowed"]:
        raise ValueError("Generated transaction did not pass fail-closed preflight.")
    return subset, patch, effective, preflight


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    source_path = args.source_graph.resolve()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    source = json.loads(source_path.read_text(encoding="utf-8"))
    subset, patch, effective, preflight = build(source)
    artifacts = {
        "sourceSubset": output / "source-subset.json",
        "patch": output / "patch.json",
        "effectiveGraph": output / "effective-graph.json",
        "preflight": output / "preflight.json",
    }
    for key, payload in (
        ("sourceSubset", subset),
        ("patch", patch),
        ("effectiveGraph", effective),
        ("preflight", preflight),
    ):
        _write(artifacts[key], payload)
    manifest = {
        "schemaVersion": "project02-a500-a600-multi-mate-transaction/v1",
        "status": "ready_for_explicit_cad_execution",
        "sourceGraphPath": str(source_path),
        "sourceGraphSha256": _sha(source_path),
        "targetModuleToken": "A500",
        "relationTypes": ["coincident", "width-centered", "distance"],
        "artifacts": {
            key: {"path": str(path), "sha256": _sha(path)}
            for key, path in artifacts.items()
        },
        "claimBoundary": (
            "The three relations are extracted Project02 A500/A600 relations, not invented "
            "faces. CAD save/reopen remains the authoritative acceptance boundary."
        ),
    }
    _write(output / "manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
