from pathlib import Path

from demo_backend.ordered_assembly_planner import preview_ordered_assembly
from demo_backend.project03_dynamic_release_gate import (
    evaluate_project03_ad20_process_request,
    load_project03_ad20_dynamic_closure,
    parse_project03_ad20_process_request,
)


ROOT = Path(__file__).resolve().parents[3]
CLOSURE = ROOT / "demo/semantic_ports/project03_ad20_context_rebased_dynamic_refinement_closure_v1.json"


def test_discrete_15_degree_state_is_evidence_backed() -> None:
    request = parse_project03_ad20_process_request("验证AD20在15度静态状态")
    result = evaluate_project03_ad20_process_request(
        request, load_project03_ad20_dynamic_closure(CLOSURE)
    )
    assert result["accepted"] is True
    assert result["status"] == "ACCEPTED_VERIFIED_DISCRETE_STATE"


def test_discrete_20_degree_state_is_rejected_with_collision_identity() -> None:
    request = parse_project03_ad20_process_request("检查AD20在20度静态姿态")
    result = evaluate_project03_ad20_process_request(
        request, load_project03_ad20_dynamic_closure(CLOSURE)
    )
    assert result["accepted"] is False
    assert result["status"] == "REJECTED_DISCRETE_STATE_INTERFERENCE"
    assert len(result["newLeafSourcePairs"]) == 1


def test_discrete_16_degree_state_tightens_first_collision_bracket() -> None:
    request = parse_project03_ad20_process_request("检查AD20在16度静态姿态")
    closure = load_project03_ad20_dynamic_closure(CLOSURE)
    result = evaluate_project03_ad20_process_request(request, closure)
    assert result["accepted"] is False
    assert len(result["newLeafSourcePairs"]) == 1
    assert closure["firstObservedCollisionBracketDegrees"] == [15, 16]


def test_continuous_motion_is_not_inferred_from_safe_samples() -> None:
    request = parse_project03_ad20_process_request("将AD20从0度翻转到15度")
    result = evaluate_project03_ad20_process_request(
        request, load_project03_ad20_dynamic_closure(CLOSURE)
    )
    assert result["accepted"] is False
    assert result["status"] == "REJECTED_CONTINUOUS_PATH_NOT_VERIFIED"
    assert result["firstObservedCollisionBracketDegrees"] == [15, 16]
    assert result["knownPairFirstObservedCollisionBracketDegrees"] == [15.5, 15.6]


def test_ordered_plan_exposes_dynamic_hard_gate_before_cad() -> None:
    preview = preview_ordered_assembly(
        "project03",
        "项目03先添加传输模组，然后添加翻转模组，并验证AD20在20度静态状态",
    )
    plan = preview["plan"]
    assert plan["summary"]["orderValid"] is True
    assert plan["summary"]["allStepsCadExecutableNow"] is False
    assert plan["executionBoundary"]["safeToStartCad"] is False
    assert plan["dynamicProcessGate"]["status"] == "REJECTED_DISCRETE_STATE_INTERFERENCE"


def test_static_ordered_plan_remains_allowed_without_dynamic_claim() -> None:
    preview = preview_ordered_assembly(
        "project03", "项目03先添加传输模组，然后添加翻转模组"
    )
    plan = preview["plan"]
    assert plan["summary"]["allStepsCadExecutableNow"] is True
    assert plan["dynamicProcessGate"]["status"] == "STATIC_ASSEMBLY_ONLY_DYNAMIC_GATE_NOT_REQUESTED"
