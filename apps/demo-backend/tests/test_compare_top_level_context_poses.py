from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/compare_top_level_context_poses.py"
SPEC = importlib.util.spec_from_file_location("compare_top_level", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_added_target_does_not_invalidate_stable_context(tmp_path: Path) -> None:
    path_a = str(tmp_path / "A.SLDASM")
    path_b = str(tmp_path / "B.SLDASM")
    transform = [1, 0, 0, 0, 1, 0, 0, 0, 1, 1, 2, 3, 1, 0, 0, 0]
    before = {"components": [{"Path": path_a, "Transform": transform, "Name": "A-1"}]}
    after = {
        "components": [
            {"Path": path_a, "Transform": transform, "Name": "A-1"},
            {"Path": path_b, "Transform": transform, "Name": "B-1"},
        ]
    }
    result = MODULE.build(before, after, 1e-10)
    assert result["stable"] is True
    assert result["stableContextCount"] == 1
    assert result["observedTotalCount"] == 2
    assert result["addedTopLevelPaths"] == [path_b]
