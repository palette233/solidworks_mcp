from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("six_role_append_test_target", ROOT / "scripts/build_six_role_support_append.py")
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _manifest():
    return {"packetCount": 1, "packets": [{
        "targetProjectAliases": [{"projectId": "project05", "moduleToken": "P000"}],
        "cumulativeInput": {"kind": "base_module_source", "instanceId": "fl9a24d063aa00-001-001"},
    }]}


def _chain_and_plan():
    chain = {"packetCount": 5, "stages": [
        {"packetCount": 4, "relationExecutionMode": "direct_installation"},
        {"packetCount": 1, "relationExecutionMode": "datum_placement_demo"},
    ]}
    plan = {
        "targetModuleToken": "P000", "requestedMateCount": 3,
        "requestedDrivingMateCount": 3, "effectiveGraphMateCoverage": {"status": "exact"},
        "releaseAuthority": {"status": "verified", "binding": {"releaseMetadata": {
            "supportPositionDemoPolicy": {"mode": "support_position_demo", "holePatternMatchRequired": False,
                                          "actualFixationMethod": "not_verified", "directMechanicalCompatibilityClaim": False},
        }}},
    }
    return chain, plan


def test_new_p000_aa00_identity_is_accepted():
    MODULE.validate_demo_identity(_manifest())


@pytest.mark.parametrize("base", ["fl9a24d062a600-001-001", "fl9c24n074jj00-001-001", ""])
def test_previous_a600_or_other_base_cannot_be_relabelled(base):
    manifest = _manifest()
    manifest["packets"][0]["cumulativeInput"]["instanceId"] = base
    with pytest.raises(ValueError, match="AA00"):
        MODULE.validate_demo_identity(manifest)


def test_already_rebased_demo_must_not_be_silently_reused():
    manifest = _manifest()
    manifest["packets"][0]["cumulativeInput"]["kind"] = "previous_transaction_checkpoint"
    with pytest.raises(ValueError, match="AA00"):
        MODULE.validate_demo_identity(manifest)


def test_wrong_target_is_rejected():
    manifest = _manifest()
    manifest["packets"][0]["targetProjectAliases"][0]["moduleToken"] = "N000"
    with pytest.raises(ValueError, match="P000"):
        MODULE.validate_demo_identity(manifest)


def test_multiple_packets_are_rejected():
    manifest = _manifest()
    manifest["packetCount"] = 2
    with pytest.raises(ValueError, match="一个包"):
        MODULE.validate_demo_identity(manifest)


def test_two_release_modes_are_preserved():
    assert all(MODULE.validate_stage_modes(*_chain_and_plan()).values())


@pytest.mark.parametrize("stage,mode,expected", [
    (0, "datum_placement_demo", "directStageStillDirect"),
    (1, "direct_installation", "appendStageExplicitDemo"),
])
def test_modes_cannot_be_weakened_or_promoted(stage, mode, expected):
    chain, plan = _chain_and_plan()
    chain["stages"][stage]["relationExecutionMode"] = mode
    with pytest.raises(ValueError, match=expected):
        MODULE.validate_stage_modes(chain, plan)


@pytest.mark.parametrize("field,value,expected", [
    ("mode", "hole_mount", "supportPositionPolicyRetained"),
    ("holePatternMatchRequired", True, "holeMatchNotRequired"),
    ("actualFixationMethod", "verified", "actualFixationUnverified"),
    ("directMechanicalCompatibilityClaim", True, "noMechanicalCompatibilityClaim"),
])
def test_demo_boundary_must_be_explicit(field, value, expected):
    chain, plan = _chain_and_plan()
    plan["releaseAuthority"]["binding"]["releaseMetadata"]["supportPositionDemoPolicy"][field] = value
    with pytest.raises(ValueError, match=expected):
        MODULE.validate_stage_modes(chain, plan)


def test_unverified_release_and_incomplete_mates_are_rejected():
    chain, plan = _chain_and_plan()
    plan["releaseAuthority"]["status"] = "missing"
    plan["requestedDrivingMateCount"] = 2
    with pytest.raises(ValueError, match="authorityVerified.*threeDrivingMates"):
        MODULE.validate_stage_modes(chain, plan)


def test_existing_different_file_is_preserved(tmp_path):
    path = tmp_path / "plan.json"
    MODULE._write_new_or_equal(path, {"version": 1})
    MODULE._write_new_or_equal(path, {"version": 1})
    with pytest.raises(ValueError, match="拒绝覆盖"):
        MODULE._write_new_or_equal(path, {"version": 2})
    assert json.loads(path.read_text(encoding="utf-8")) == {"version": 1}


def test_build_uses_selected_case_checkpoint_and_never_runs_cad(tmp_path, monkeypatch):
    monkeypatch.setattr(MODULE, "ROOT", tmp_path)
    root = tmp_path / "output"
    root.mkdir()
    direct = root / "direct.json"
    prepared = {"cases": [{"orderName": "reordered", "moduleSequence": MODULE.ORDERS["reordered"], "manifestPath": str(direct)}]}
    (root / "direct-stage-preparation.json").write_text(json.dumps(prepared), encoding="utf-8")
    demo = root / "demo.json"
    demo.write_text(json.dumps(_manifest()), encoding="utf-8")
    chain, plan = _chain_and_plan()
    checkpoint = root / "five.SLDASM"
    chain["checkpointBinding"] = {"assemblyPath": str(checkpoint)}
    called = {}
    monkeypatch.setattr(MODULE, "rebase_single_packet_manifest_for_external_checkpoint", lambda manifest, **kw: {**manifest, "rebased": kw["source_stage_id"]})
    def chain_builder(workspace, **kwargs):
        called["chain"] = kwargs
        return chain
    monkeypatch.setattr(MODULE, "build_multi_release_cad_chain", chain_builder)
    monkeypatch.setattr(MODULE, "validate_multi_release_cad_chain", lambda *args: None)
    def plan_builder(workspace, manifest, packet_id, **kwargs):
        called["plan"] = kwargs
        return plan
    monkeypatch.setattr(MODULE, "build_global_cad_packet_execution_plan", plan_builder)
    report = MODULE.build("reordered", demo, root)
    assert called["chain"]["direct_manifest_path"] == direct
    assert called["chain"]["direct_closure_path"] == root / "reordered/direct-stage-closure.json"
    assert called["plan"]["input_checkpoint"] == checkpoint
    assert called["plan"]["output_path"] == root / "reordered/six-role-reordered.SLDASM"
    assert report["moduleSequence"] == ["AA00", "AG00", "BD00", "SS00", "AI00", "P000"]
    assert report["cadStarted"] is False
    assert report["completedSixRoleChain"] is False
    assert f'--run-dir "{root / "reordered/live-run"}"' in report["runCommand"]
    assert MODULE.build("reordered", demo, root) == report
