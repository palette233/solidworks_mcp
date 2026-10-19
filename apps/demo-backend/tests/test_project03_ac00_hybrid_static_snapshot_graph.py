from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/build_project03_ac00_hybrid_static_snapshot_graph.py"
SPEC = importlib.util.spec_from_file_location("hybrid_snapshot", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_collapsed_assembly_replaces_all_descendant_leaves(tmp_path: Path) -> None:
    branch = tmp_path / "Branch.SLDASM"
    inside = tmp_path / "Inside.SLDPRT"
    outside = tmp_path / "Outside.SLDPRT"
    for path in (branch, inside, outside):
        path.write_bytes(b"cad")
    identity = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]
    capture = {
        "components": [
            {"relativeHierarchyPath": "Branch-1", "path": str(branch), "transform": identity},
            {"relativeHierarchyPath": "Branch-1/Inside-1", "path": str(inside), "transform": identity},
            {"relativeHierarchyPath": "Outside-1", "path": str(outside), "transform": identity},
        ]
    }
    result = MODULE.build(capture, ["Branch-1"])
    assert result["ModuleCount"] == 2
    assert [item["nodeKind"] for item in result["StaticSnapshotAudit"]["leafManifest"]] == [
        "collapsed-subassembly",
        "leaf-part",
    ]
    assert result["StaticSnapshotAudit"]["coveredSourceLeafInstanceCount"] == 2
    assert result["StaticSnapshotAudit"]["sourceLeafInstanceCount"] == 2
