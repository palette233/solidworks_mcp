from pathlib import Path

from demo_backend.assembly_release_contract import build_assembly_release_contract


WORKSPACE = Path(__file__).resolve().parents[3]


def test_project03_contract_exposes_real_dynamic_failure_separately_from_static() -> None:
    result = build_assembly_release_contract(WORKSPACE, "project03")
    assert result["static"]["allowed"] is True
    assert result["liveCad"]["allowed"] is True
    assert result["dynamic"]["configured"] is True
    assert result["dynamic"]["evidenceExists"] is True
    assert result["dynamic"]["commandGateEnabled"] is True
    assert result["dynamic"]["productionReady"] is False
    assert result["dynamic"]["firstObservedCollisionBracketDegrees"] == [15, 16]
    assert result["dynamic"]["knownPairFirstContactRefinement"][
        "firstObservedCollisionBracketDegrees"
    ] == [15.5, 15.6]
    assert result["release"]["productionAllowed"] is False


def test_project01_contract_does_not_invent_missing_dynamic_evidence() -> None:
    result = build_assembly_release_contract(WORKSPACE, "project01")
    assert result["static"]["allowed"] is True
    assert result["dynamic"]["configured"] is False
    assert result["dynamic"]["status"] == "DYNAMIC_EVIDENCE_NOT_REGISTERED"
    assert result["release"]["productionAllowed"] is False
    assert any("动态证据闭包" in row for row in result["release"]["productionBlockers"])
