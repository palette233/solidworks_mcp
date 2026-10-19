from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/extract_project03_ac00_branch_snapshot.py"
SPEC = importlib.util.spec_from_file_location("extract_branch", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_normalizes_repeated_parent_context_markers() -> None:
    branch = "AC20-1"
    snapshot = {
        "components": [
            {"relativeHierarchyPath": branch, "depthFromModuleRoot": 1},
            {
                "relativeHierarchyPath": (
                    "AC20-1/@module/AC20-1/AC21-1/"
                    "@module/AC20-1/AC21-1/P-1"
                ),
                "depthFromModuleRoot": 8,
            },
        ]
    }
    result = MODULE.extract(snapshot, branch)
    assert result["componentCount"] == 2
    assert result["components"][0]["relativeHierarchyPath"] == "@root"
    assert result["components"][1]["relativeHierarchyPath"] == (
        "AC21-1/@module/AC21-1/P-1"
    )
