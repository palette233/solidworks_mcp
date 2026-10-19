from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/build_project03_ac00_flat_static_snapshot_graph.py"
SPEC = importlib.util.spec_from_file_location("ac00_flat_snapshot", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_build_flattens_only_leaf_parts_and_marks_semantic_loss(tmp_path: Path) -> None:
    part_a = tmp_path / "A.SLDPRT"
    part_b = tmp_path / "B.SLDPRT"
    assembly = tmp_path / "Nested.SLDASM"
    for path in (part_a, part_b, assembly):
        path.write_bytes(b"fixture")
    identity = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]
    capture = {
        "components": [
            {
                "name": "Nested-1",
                "path": str(assembly),
                "relativeHierarchyPath": "Nested-1",
                "transform": identity,
            },
            {
                "name": "A-1",
                "path": str(part_a),
                "relativeHierarchyPath": "Nested-1/A-1",
                "transform": identity,
                "referencedConfiguration": "Default",
            },
            {
                "name": "B-1",
                "path": str(part_b),
                "relativeHierarchyPath": "Nested-1/B-1",
                "transform": identity,
            },
        ]
    }

    result = MODULE.build(capture)

    assert result["SchemaVersion"] == "editable-module-mate-graph/v1"
    assert result["ModuleCount"] == 2
    assert result["InterModuleMateCount"] == 0
    assert result["Mates"] == []
    assert len(result["EditPolicy"]["fixedModuleTokens"]) == 2
    assert result["Modules"][0]["SourceTransform"] == identity
    assert result["Modules"][0]["ReferencedConfiguration"] == "Default"
    audit = result["StaticSnapshotAudit"]
    assert audit["hierarchyPreserved"] is False
    assert audit["internalMatesPreserved"] is False
    assert audit["motionSemanticsPreserved"] is False
    assert audit["productionReady"] is False


def test_build_rejects_missing_leaf_file(tmp_path: Path) -> None:
    capture = {
        "components": [
            {
                "name": "missing-1",
                "path": str(tmp_path / "missing.SLDPRT"),
                "relativeHierarchyPath": "missing-1",
                "transform": [0] * 16,
            }
        ]
    }
    try:
        MODULE.build(capture)
    except FileNotFoundError:
        return
    raise AssertionError("expected a missing source part to be rejected")
