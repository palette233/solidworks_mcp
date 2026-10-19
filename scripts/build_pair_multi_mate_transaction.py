#!/usr/bin/env python3
"""Build a fail-closed direct-edit transaction for one real module pair."""

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


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_pair_transaction(
    source_graph: dict,
    *,
    target_module_token: str,
    context_module_token: str,
) -> tuple[dict, dict, dict, dict]:
    target = target_module_token.strip().upper()
    context = context_module_token.strip().upper()
    if not target or not context or target == context:
        raise ValueError("target and context must be two different module tokens.")
    pair = {target, context}
    mates = [
        row
        for row in source_graph.get("Mates") or []
        if not bool(row.get("IsSuppressed", False))
        and {str(value).upper() for value in row.get("ModuleTokens") or []} == pair
    ]
    if len(mates) < 2:
        raise ValueError(f"Expected at least two active relations for {target}/{context}.")
    if any(not row.get("Endpoints") for row in mates):
        raise ValueError("Every source relation must contain endpoint evidence.")
    if any(
        not endpoint.get("SourceAssemblyPersistentReferenceBase64")
        for row in mates
        for endpoint in row.get("Endpoints") or []
    ):
        raise ValueError("Every endpoint must carry a source-assembly persistent reference.")

    hierarchy_paths = {
        str(value)
        for row in mates
        for value in row.get("ModuleHierarchyPaths") or []
        if str(value)
    }
    modules = [
        row
        for row in source_graph.get("Modules") or []
        if str(row.get("HierarchyPath") or "") in hierarchy_paths
    ]
    if {str(row.get("ModuleToken") or "").upper() for row in modules} != pair:
        raise ValueError("The selected pair does not resolve to exactly the requested module tokens.")

    subset = dict(source_graph)
    subset["Modules"] = modules
    subset["Mates"] = mates
    subset["ModuleCount"] = len(modules)
    subset["InterModuleMateCount"] = len(mates)
    patch = {
        "schemaVersion": "mate-graph-patch/v1",
        "baseModuleToken": context,
        "initialPlacementMode": "source_pose",
        "fixedContextModuleTokens": [context],
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
        target,
        require_closed_dof=True,
        require_multiple_operations=True,
    )
    if not preflight["publishAllowed"]:
        raise ValueError(
            "Pair transaction is not publishable: "
            + json.dumps(preflight["blockers"], ensure_ascii=False)
        )
    return subset, patch, effective, preflight


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-graph", required=True, type=Path)
    parser.add_argument("--target", required=True)
    parser.add_argument("--context", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    source_path = args.source_graph.resolve()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    source = json.loads(source_path.read_text(encoding="utf-8-sig"))
    subset, patch, effective, preflight = build_pair_transaction(
        source,
        target_module_token=args.target,
        context_module_token=args.context,
    )
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
        "schemaVersion": "pair-multi-mate-transaction/v1",
        "status": "ready_for_explicit_cad_execution",
        "sourceGraphPath": str(source_path),
        "sourceGraphSha256": _sha(source_path),
        "sourceAssemblyPath": source.get("SourceAssemblyPath"),
        "targetModuleToken": args.target.strip().upper(),
        "contextModuleToken": args.context.strip().upper(),
        "mateCount": len(effective.get("Mates") or []),
        "artifacts": {
            key: {"path": str(path), "sha256": _sha(path)}
            for key, path in artifacts.items()
        },
        "claimBoundary": (
            "All relations and endpoint references come from the selected source graph. "
            "CAD save/reopen remains the authoritative acceptance boundary."
        ),
    }
    _write(output / "manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
