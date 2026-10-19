from __future__ import annotations

from pathlib import Path

import pytest

from demo_backend.semantic_assembly_sequence import (
    SemanticAssemblySequenceError,
    build_project02_validated_demo_run,
    build_project02_ordered_assembly_plan,
    load_project02_ordered_assembly_closure,
    parse_project02_ordered_assembly_command,
    preview_project02_ordered_assembly,
)


def test_loads_latest_true_increment_closure() -> None:
    workspace = Path(__file__).resolve().parents[3]
    closure = load_project02_ordered_assembly_closure(workspace)
    assert closure["available"] is True
    assert closure["allCadStepsPassed"] is True
    assert closure["sequence"] == [
        "A600", "A800", "A180", "A700", "A300", "A500", "A100", "A200", "T401"
    ]
    assert closure["interferenceGate"]["checkedPairCount"] == 45
    assert closure["interferenceGate"]["acceptedPairCount"] == 45
    assert closure["releaseDecision"]["staticTenObjectDemoReleaseAllowed"] is True
    assert closure["releaseDecision"]["productionReleaseAllowed"] is False


def test_parses_module_codes_and_chinese_aliases_in_source_order() -> None:
    intent = parse_project02_ordered_assembly_command(
        "项目02：以A600为基座，先添加传输模组，再加入扫描模组，然后添加A700，最后添加校准模组。"
    )
    assert [item["moduleToken"] for item in intent["steps"]] == [
        "A800",
        "A180",
        "A700",
        "A500",
    ]
    assert intent["initialContextModules"] == ["A600"]


def test_valid_order_builds_auditable_preview_but_not_false_cad_claim() -> None:
    result = preview_project02_ordered_assembly(
        "项目02：以A600为基座，先添加A800，再添加A180，然后添加A700，最后添加A500。"
    )
    plan = result["plan"]
    assert plan["summary"]["orderValid"] is True
    assert plan["summary"]["finalPlannedModuleTokens"] == [
        "A600",
        "A800",
        "A180",
        "A700",
        "A500",
    ]
    a500 = plan["steps"][-1]
    a800 = plan["steps"][0]
    a180 = plan["steps"][1]
    assert a800["cadExecutableNow"] is True
    assert a800["implementationStatus"] == "single_module_cad_validated"
    assert a180["cadExecutableNow"] is True
    assert a180["implementationStatus"] == "single_module_cad_validated"
    assert "槽口3尚未作为驱动配合重建。" in a180["engineeringLimitations"]
    assert a500["cadExecutableNow"] is True
    assert a500["implementationStatus"] == "single_module_cad_validated"
    assert plan["summary"]["cadExecutableStepCount"] == 4
    assert plan["summary"]["allStepsCadExecutableNow"] is True
    assert plan["executionBoundary"]["safeToStartCad"] is True
    assert result["audit"]["runId"].startswith("project02-ordered-")
    assert result["audit"]["timingSeconds"]["total"] >= 0


def test_invalid_order_is_reported_without_silently_reordering() -> None:
    intent = parse_project02_ordered_assembly_command(
        "项目02：先添加A180，再添加A800，然后添加A700。"
    )
    plan = build_project02_ordered_assembly_plan(intent)
    assert plan["summary"]["orderValid"] is False
    assert plan["steps"][0]["status"] == "blocked_by_order"
    assert plan["steps"][0]["missingRequiredModules"] == ["A800"]
    assert plan["steps"][1]["status"] == "cad_validated_single_step"
    assert plan["steps"][1]["implementationStatus"] == "single_module_cad_validated"


def test_a500_requires_a700_for_current_validated_demo() -> None:
    intent = parse_project02_ordered_assembly_command(
        "项目02：先添加A800，再添加A500。"
    )
    plan = build_project02_ordered_assembly_plan(intent)
    assert plan["steps"][1]["status"] == "blocked_by_order"
    assert plan["steps"][1]["missingRequiredModules"] == ["A700"]


def test_full_mechanical_order_is_ready_for_static_demo() -> None:
    result = preview_project02_ordered_assembly(
        "项目02：先添加A800，再添加A180，然后添加A700，接着添加A300，"
        "再添加A500，最后添加A100。"
    )
    plan = result["plan"]
    assert plan["summary"]["orderValid"] is True
    assert plan["steps"][-1]["moduleToken"] == "A100"
    assert plan["steps"][-1]["dependenciesSatisfied"] is True
    assert plan["steps"][-1]["cadExecutableNow"] is True
    assert plan["steps"][-1]["implementationStatus"] == "single_module_cad_validated"
    assert plan["steps"][-1]["missingImplementation"] is None
    assert any(
        "A100/A600新增干涉已消除" in item
        for item in plan["steps"][-1]["engineeringLimitations"]
    )
    assert plan["summary"]["allStepsCadExecutableNow"] is True
    assert plan["executionBoundary"]["safeToStartCad"] is True


def test_a100_requires_all_preceding_process_modules() -> None:
    intent = parse_project02_ordered_assembly_command(
        "项目02：先添加A800，再添加A180，最后添加A100。"
    )
    plan = build_project02_ordered_assembly_plan(intent)
    assert plan["steps"][-1]["status"] == "blocked_by_order"
    assert plan["steps"][-1]["missingRequiredModules"] == ["A700", "A300", "A500"]


def test_full_command_binds_to_validated_static_cad_chain() -> None:
    workspace = Path(__file__).resolve().parents[3]
    closure_path = workspace / (
        "demo/semantic_ports/project02_ordered_true_increment_v1/"
        "project02_ordered_true_increment_closure.json"
    )
    import json

    closure = json.loads(closure_path.read_text(encoding="utf-8"))
    result = build_project02_validated_demo_run(
        "项目02：先添加A800，再添加A180，然后添加A700，接着添加A300，"
        "再添加A500，最后添加A100。",
        closure,
    )

    assert result["success"] is True
    assert result["executionMode"] == "validated_artifact_replay"
    assert result["cadExecutedThisRequest"] is False
    assert result["validatedCadArtifactReused"] is True
    assert result["interferenceGate"]["acceptedPairCount"] == 21
    assert Path(result["finalAssemblyPath"]).is_file()


def test_validated_demo_rejects_a_different_sequence_even_if_preview_is_valid() -> None:
    closure = {
        "sequence": ["A600", "A800", "A180", "A700", "A300", "A500", "A100"],
        "releaseDecision": {"staticSevenModuleDemoReleaseAllowed": True},
        "interferenceGate": {"acceptedPairCount": 21},
        "finalAssemblyPath": __file__,
    }
    with pytest.raises(SemanticAssemblySequenceError, match="完整顺序"):
        build_project02_validated_demo_run(
            "项目02：先添加A800，再添加A180，然后添加A700，最后添加A500。",
            closure,
        )


@pytest.mark.parametrize(
    "requirement, message",
    [
        ("先添加A800，再添加A180", "只支持明确指定项目02"),
        ("项目02：先添加A800，再添加A800", "重复出现"),
        ("项目02：希望方案合理", "没有识别到添加步骤"),
    ],
)
def test_rejects_unsafe_or_ambiguous_commands(requirement: str, message: str) -> None:
    with pytest.raises(SemanticAssemblySequenceError, match=message):
        parse_project02_ordered_assembly_command(requirement)


def test_single_step_command_supports_arbitrary_subsequence_execution() -> None:
    intent = parse_project02_ordered_assembly_command("项目02：添加A800")
    assert [step["moduleToken"] for step in intent["steps"]] == ["A800"]
