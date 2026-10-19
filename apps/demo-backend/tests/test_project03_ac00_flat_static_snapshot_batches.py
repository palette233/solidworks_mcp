from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/build_project03_ac00_flat_static_snapshot_batches.py"
SPEC = importlib.util.spec_from_file_location("flat_snapshot_batches", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_split_graph_is_complete_and_non_overlapping(tmp_path: Path) -> None:
    modules = [
        {"ModuleToken": f"L{i}", "SourceTransform": [i] * 16} for i in range(5)
    ]
    graph = {
        "Modules": modules,
        "ModuleCount": 5,
        "Mates": [],
        "InterModuleMateCount": 0,
        "EditPolicy": {"baseModuleToken": "L0", "fixedModuleTokens": []},
        "StaticSnapshotAudit": {
            "leafInstanceCount": 5,
            "leafManifest": [
                {"moduleToken": f"L{i}", "expectedWorldTransform": [i] * 16}
                for i in range(5)
            ],
        },
    }
    result = MODULE.split_graph(graph, tmp_path, 2)
    assert result["batchCount"] == 3
    assert [item["leafCount"] for item in result["batches"]] == [2, 2, 1]
    tokens = [token for batch in result["batches"] for token in batch["moduleTokens"]]
    assert tokens == ["L0", "L1", "L2", "L3", "L4"]


def test_root_requires_all_batch_closures(tmp_path: Path) -> None:
    assembly = tmp_path / "batch.SLDASM"
    closure = tmp_path / "batch.closure.json"
    assembly.write_bytes(b"cad")
    closure.write_text('{"success": true}', encoding="utf-8")
    manifest = {
        "leafInstanceCount": 2,
        "batches": [
            {"batchIndex": 1, "assemblyPath": str(assembly), "closurePath": str(closure)}
        ],
    }
    result = MODULE.build_root_graph(manifest)
    assert result["ModuleCount"] == 1
    assert result["Modules"][0]["SourceTransform"] == MODULE.IDENTITY
    assert result["StaticSnapshotBatchRootAudit"]["allBatchClosuresPassed"] is True
