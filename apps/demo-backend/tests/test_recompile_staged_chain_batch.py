import copy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

from recompile_staged_chain_batch import rebase_request


def example():
    return {
        "chainId": "scanner-chain-v1",
        "baseSelection": {
            "projectId": "project01",
            "moduleToken": "JJ00",
            "confirmed": True,
        },
        "stationRegistryPath": "old.json",
        "allowPrototypeEstimate": True,
        "steps": [
            {
                "stageId": "s01",
                "moduleRole": "Transport",
                "moduleSelection": {
                    "projectId": "project01",
                    "moduleToken": "SS00",
                    "confirmed": True,
                },
            },
            {
                "stageId": "s02",
                "moduleRole": "Scanner",
                "moduleSelection": {
                    "projectId": "project03",
                    "moduleToken": "AI00",
                    "confirmed": True,
                },
            },
        ],
    }


def test_rebase_changes_only_chain_identity_and_registry():
    source = example()
    original = copy.deepcopy(source)
    result = rebase_request(
        source,
        registry_path="data/assembly_stations/station-rules-v34.json",
        chain_suffix="station-v34",
    )
    assert source == original
    assert result["chainId"] == "scanner-chain-v1-station-v34"
    assert result["stationRegistryPath"].endswith("station-rules-v34.json")
    assert result["steps"] == source["steps"]


@pytest.mark.parametrize("suffix", ["", "V34", "bad_suffix", "../bad"])
def test_rebase_rejects_unsafe_suffix(suffix):
    with pytest.raises(ValueError, match="suffix"):
        rebase_request(example(), registry_path="rules.json", chain_suffix=suffix)


def test_rebase_can_narrow_prototype_measurement_authority_to_scanner_stage():
    source = example()
    result = rebase_request(
        source,
        registry_path="rules.json",
        chain_suffix="scanner-proxy-scope",
        prototype_estimate_roles={"Scanner"},
    )
    assert "allowPrototypeEstimate" not in result
    assert result["steps"][0].get("allowPrototypeEstimate") is None
    assert result["steps"][1]["allowPrototypeEstimate"] is True
    assert source["allowPrototypeEstimate"] is True


def test_rebase_rejects_scope_role_absent_from_request():
    with pytest.raises(ValueError, match="absent"):
        rebase_request(
            example(),
            registry_path="rules.json",
            chain_suffix="scanner-proxy-scope",
            prototype_estimate_roles={"Calibration"},
        )


def test_rebase_preserves_only_requested_pre_scoped_stage_authority():
    source = example()
    source.pop("allowPrototypeEstimate")
    source["steps"][1]["allowPrototypeEstimate"] = True
    result = rebase_request(
        source,
        registry_path="rules.json",
        chain_suffix="scanner-proxy-scope",
        prototype_estimate_roles={"Scanner"},
    )
    assert "allowPrototypeEstimate" not in result
    assert result["steps"][0].get("allowPrototypeEstimate") is None
    assert result["steps"][1]["allowPrototypeEstimate"] is True


def test_rebase_cannot_add_role_to_pre_scoped_stage_authority():
    source = example()
    source.pop("allowPrototypeEstimate")
    source["steps"][1]["allowPrototypeEstimate"] = True
    with pytest.raises(ValueError, match="explicitly authorized"):
        rebase_request(
            source,
            registry_path="rules.json",
            chain_suffix="broaden-scope",
            prototype_estimate_roles={"Scanner", "Transport"},
        )


def test_v34_scanner_chains_scope_prototype_measurement_to_scanner_only():
    batch_root = (
        ROOT
        / "demo/station_gap_batch_20261028/scanner-context-chain-recompile-v34-v3"
    )
    report = json.loads(
        (batch_root / "batch-report.json").read_text(encoding="utf-8-sig")
    )
    assert report["chainCount"] == 6
    assert report["readyCount"] == 6
    assert report["cadStarted"] is False
    assert report["prototypeEstimateScopeRoles"] == ["Scanner"]
    for row in report["chains"]:
        request = json.loads(
            (ROOT / row["generatedRequestPath"]).read_text(encoding="utf-8-sig")
        )
        assert "allowPrototypeEstimate" not in request
        assert [
            step.get("moduleRole")
            for step in request["steps"]
            if step.get("allowPrototypeEstimate") is True
        ] == ["Scanner"]
        planning = json.loads(
            (
                (ROOT / row["compilationPath"]).parent
                / "station-preparation/station-planning.json"
            ).read_text(encoding="utf-8-sig")
        )
        assert [
            stage["plan"]["ruleBinding"]["prototypeEstimateAuthorized"]
            for stage in planning["stages"]
        ] == [False, True]
        assert all(
            stage["plan"]["geometry"].get("sourceWorldPoseCopied") is False
            for stage in planning["stages"]
        )
