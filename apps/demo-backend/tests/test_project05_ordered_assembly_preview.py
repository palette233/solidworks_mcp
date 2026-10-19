from __future__ import annotations

from demo_backend.ordered_assembly_planner import preview_ordered_assembly


def test_project05_natural_language_sequence_is_explainable_and_cad_validated() -> None:
    result = preview_ordered_assembly(
        "project05",
        (
            "项目05：先添加输送模组，再添加顶升定位模组，然后添加扫描模组，"
            "接着添加CCD模组，再添加校准称重模组，随后添加清洁模组，"
            "再添加排胶杯，最后添加龙门模组。"
        ),
    )

    plan = result["plan"]
    assert [row["moduleToken"] for row in plan["steps"]] == [
        "D000", "K000", "F000", "M000", "G000", "N000", "P000", "B000"
    ]
    assert plan["summary"]["orderValid"] is True
    assert plan["summary"]["previewReady"] is True
    assert plan["summary"]["cadExecutableStepCount"] == 8
    assert plan["summary"]["missingImplementationCount"] == 0
    assert plan["summary"]["allStepsCadExecutableNow"] is True
    assert plan["executionBoundary"]["safeToStartCad"] is True
    assert plan["steps"][-1]["requiredModules"] == [
        "D000", "K000", "F000", "M000", "G000", "N000", "P000"
    ]


def test_project05_rejects_gantry_before_required_process_modules() -> None:
    result = preview_ordered_assembly(
        "project05",
        "项目05：先添加输送模组，再添加龙门模组，最后添加顶升定位模组。",
    )

    plan = result["plan"]
    assert plan["summary"]["orderValid"] is False
    gantry = plan["steps"][1]
    assert gantry["moduleToken"] == "B000"
    assert gantry["status"] == "blocked_by_order"
    assert gantry["missingRequiredModules"] == [
        "K000", "F000", "M000", "G000", "N000", "P000"
    ]
    assert plan["executionBoundary"]["safeToStartCad"] is False
