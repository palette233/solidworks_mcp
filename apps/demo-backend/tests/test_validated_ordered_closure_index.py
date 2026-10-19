from __future__ import annotations

import importlib.util
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[3]
SCRIPT = WORKSPACE / "scripts" / "build_validated_ordered_closure_index.py"
SPEC = importlib.util.spec_from_file_location("build_validated_ordered_closure_index", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_project01_ordered_index_has_all_real_cumulative_artifacts() -> None:
    payload = MODULE.build_index("project01")
    assert payload["success"] is True
    assert payload["sequence"] == ["JJ00", "SS00", "FF00", "SM00", "GN00", "BD00", "GJ00", "LM00"]
    assert len(payload["steps"]) == 7
    assert all(Path(row["assemblyPath"]).is_file() for row in payload["steps"])
    assert all(Path(row["evidencePath"]).is_file() for row in payload["steps"])
    assert all(len(row["assemblySha256"]) == 64 for row in payload["steps"])


def test_project03_ordered_index_has_all_real_cumulative_artifacts() -> None:
    payload = MODULE.build_index("project03")
    assert payload["success"] is True
    assert payload["sequence"] == ["AA00", "AE00", "AD00", "AI00", "AG00", "AH00", "AJ00", "AB00"]
    assert len(payload["steps"]) == 7
    assert all(Path(row["assemblyPath"]).is_file() for row in payload["steps"])
    assert all(Path(row["evidencePath"]).is_file() for row in payload["steps"])
