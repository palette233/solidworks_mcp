from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

from build_ordered_project05_eleven_module_solution import (  # noqa: E402
    _audit_leaf_body_extents,
    _rows_with_runtime_component_names,
    build_plan,
)


def test_project05_ordered_direct_plan_covers_all_active_modules_once(tmp_path: Path) -> None:
    output_root = tmp_path / "project05_ordered_direct"
    plan = build_plan(
        ROOT / "demo/layout_previews/project05_selected_solution_replay.json",
        ROOT / "demo/layout_previews/project05_selected_solution_direct_poses.json",
        output_root,
    )

    assert plan["stageCount"] == 9
    assert plan["moduleCount"] == 11
    assert [stage["moduleToken"] for stage in plan["stages"]] == [
        "A000", "D000", "K000", "F000", "M000", "G000", "N000", "P000", "B000"
    ]
    added = [code for stage in plan["stages"] for code in stage["addedCodes"]]
    assert len(added) == 11
    assert len(set(added)) == 11
    assert plan["stages"][0]["addedCodes"] == ["A000", "E000"]
    assert plan["stages"][-1]["addedCodes"] == ["B000", "Z000"]
    assert plan["stages"][-1]["expectedTopLevelCountAfterStage"] == 11
    assert plan["prototypeAssemblyCopied"] is False


def test_leaf_extent_audit_compares_like_for_like_leaf_unions() -> None:
    expected = [{
        "componentName": "module-1",
        "boundingBoxWorld": [0.0, 0.0, 0.0, 1.0, 2.0, 3.0],
        "fixedEnvironment": False,
    }]
    captures = [{
        "componentName": "module-1",
        "boundingBoxWorld": [10.0, 20.0, 30.0, 11.0, 22.0, 33.0],
        "bodyCount": 7,
        "coverageComplete": True,
    }]

    audit = _audit_leaf_body_extents(captures, expected)

    assert audit["success"] is True
    assert audit["method"] == "complete-leaf-body-union-v1"
    assert audit["components"][0]["bodyCount"] == 7


def test_leaf_extent_audit_rejects_real_internal_shape_drift() -> None:
    expected = [{
        "componentName": "module-1",
        "boundingBoxWorld": [0.0, 0.0, 0.0, 1.0, 2.0, 3.0],
        "fixedEnvironment": False,
    }]
    captures = [{
        "componentName": "module-1",
        "boundingBoxWorld": [0.0, 0.0, 0.0, 1.0, 2.0, 3.02],
        "bodyCount": 7,
        "coverageComplete": True,
    }]

    audit = _audit_leaf_body_extents(captures, expected)

    assert audit["success"] is False
    assert audit["mismatchComponents"] == ["module-1"]


def test_runtime_instance_suffix_is_resolved_from_file_path() -> None:
    expected = [{
        "componentCode": "N000",
        "componentName": "N000-4",
        "filePath": r"D:\modules\N000.SLDASM",
    }]
    actual = [{
        "Name": "N000-1",
        "Path": r"D:\modules\N000.SLDASM",
    }]

    rows, aliases = _rows_with_runtime_component_names(actual, expected)

    assert rows[0]["componentName"] == "N000-1"
    assert aliases[0]["plannedComponentName"] == "N000-4"
    assert aliases[0]["runtimeComponentName"] == "N000-1"
