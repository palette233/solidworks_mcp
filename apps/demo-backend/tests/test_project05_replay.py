from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

import pytest

from demo_backend.project05_replay import build_project05_replay_layout


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

from build_direct_project02_nine_module_solution import load_direct_manifest  # noqa: E402


def _load(name: str) -> dict:
    return json.loads((ROOT / "demo/layout_previews" / name).read_text(encoding="utf-8-sig"))


def test_project05_approved_rank_one_expands_nine_objects_to_eleven_active_modules() -> None:
    result = build_project05_replay_layout(
        _load("project05_selected_solution.json"),
        _load("project05_module_occupancy.json"),
        _load("project05_top_level_poses.json"),
    )

    assert len(result["components"]) == 11
    assert len({item["componentName"] for item in result["components"]}) == 11
    assert {item["memberCode"] for item in result["components"]} == {
        "A000", "E000", "D000", "K000", "F000", "M000",
        "G000", "N000", "P000", "B000", "Z000",
    }
    assert "FL9C251093N000.001-4" in {
        item["componentName"] for item in result["components"]
    }
    assert "FL9C254098P000.001-2" in {
        item["componentName"] for item in result["components"]
    }
    assert result["constraintPlan"]["solveObjectCount"] == 9
    assert result["constraintPlan"]["replayComponentCount"] == 11
    assert result["constraintPlan"]["prototypeEquivalent"] is True
    scanner = next(item for item in result["components"] if item["memberCode"] == "F000")
    scanner_box = scanner["boundingBoxWorld"]
    assert scanner["boundingBoxEvidence"]["source"] == "complete-leaf-body-aabb-union"
    assert abs((scanner_box[5] - scanner_box[2]) - 0.5301471402047597) < 1e-9


def test_project05_replay_rejects_unapproved_selection() -> None:
    selected = copy.deepcopy(_load("project05_selected_solution.json"))
    selected["visualApproval"]["approved"] = False
    with pytest.raises(ValueError, match="visually approved"):
        build_project05_replay_layout(
            selected,
            _load("project05_module_occupancy.json"),
            _load("project05_top_level_poses.json"),
        )


def test_project05_direct_manifest_accepts_exactly_one_fixed_a000() -> None:
    rows = load_direct_manifest(
        ROOT / "demo/layout_previews/project05_selected_solution_replay.json",
        ROOT / "demo/layout_previews/project05_selected_solution_direct_poses.json",
        expected_module_count=11,
        fixed_environment_code="A000",
    )

    assert len(rows) == 11
    assert rows[0]["componentCode"] == "A000"
    assert rows[0]["fixedEnvironment"] is True
    assert sum(bool(row["fixedEnvironment"]) for row in rows) == 1
