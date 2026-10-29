"""Synthetic unit fixtures only: no SolidWorks and no real station PASS claim."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

from demo_backend import target_station_chain_preflight as gate


ROOT = Path(__file__).resolve().parents[3]
IDENTITY = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]
IDS = {token: "cad/" + token + "/synthetic-001" for token in ("base", "transport", "clean")}


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture
def synthetic(tmp_path):
    # These JSON bytes stand in for CAD files solely to exercise byte bindings.
    before = _write(tmp_path / "before.SLDASM", {"syntheticFixture": True, "moduleIds": [IDS["base"], IDS["transport"]]})
    output = _write(tmp_path / "output.SLDASM", {"syntheticFixture": True})
    graph = _write(tmp_path / "graph.json", {"syntheticFixture": True})
    cad = _write(tmp_path / "cad.json", {"syntheticFixture": True, "actualCadExecuted": False,
        "executionEffectiveGraphPath": str(graph), "executionEffectiveGraphSha256": gate.file_sha256(graph),
        "outputAssemblyPath": str(output), "outputAssemblySha256": gate.file_sha256(output),
        "sourceAssemblyPath": str(before), "sourceAssemblySha256Before": gate.file_sha256(before),
        "sourceAssemblySha256After": gate.file_sha256(before)})
    instances = [{"name": token, "sourcePath": str(tmp_path / (token + "-source.SLDASM"))} for token in ("base", "transport")]
    state = _write(tmp_path / "source-state.json", {"syntheticFixture": True, "success": True, "checks": {"outputFileUnchanged": True},
        "assemblyPath": str(before), "assemblySha256": gate.file_sha256(before),
        "observed": {"readOnly": True, "components": [{**item, "transform": IDENTITY.copy()} for item in instances]}})
    measured = _write(tmp_path / "synthetic-measurement.json", {"syntheticFixture": True})
    witness = _write(tmp_path / "witness.json", {"schemaVersion": "role-station-witness/v1", "syntheticFixture": True,
        "caseId": "synthetic-cleaning", "source": "p::clean", "target": "p::base",
        "cadResultSha256": gate.file_sha256(cad), "effectiveGraphSha256": gate.file_sha256(graph),
        "contextModuleDefinitionIds": [IDS["base"], IDS["transport"], IDS["clean"]], "contextStateSha256": gate.file_sha256(state),
        "sourceContextInstances": instances,
        "checks": {name: {"passed": True, "status": "passed", "method": "synthetic_unit_fixture_not_CAD",
            "evidence": [{"path": str(measured), "sha256": gate.file_sha256(measured)}]}
            for name in ("slotMembership", "supportAndDirectionBound", "installationSideBound", "transportContext")}})
    categories = {"base": "frame", "transport": "transport", "clean": "cleaning_weighing"}
    catalog = _write(tmp_path / "catalog.json", {"syntheticFixture": True,
        "moduleDefinitions": [{"moduleDefinitionId": IDS[token], "category": categories[token],
                               "cadSources": [{"path": str(tmp_path / (token + "-source.SLDASM"))}]}
                              for token in ("base", "transport", "clean")]})
    release = _write(tmp_path / "release.json", {"syntheticFixture": True, "status": "released_for_demo_relation_execution",
        "releasedCatalogPath": str(catalog), "releasedCatalogFileSha256": gate.file_sha256(catalog),
        "validationEvidence": [{"passed": True, "fileSha256": gate.file_sha256(cad)}]})
    request = {"chainId": "strict-synthetic", "placementValidationMode": "target_role_station",
        "baseRequirement": "base", "baseSelection": {"projectId": "p", "moduleToken": "base", "confirmed": True},
        "steps": [
            {"stageId": "transport", "moduleRole": "Transport", "requirement": "transport", "releaseManifestPath": str(release),
             "moduleSelection": {"projectId": "p", "moduleToken": "transport", "confirmed": True}},
            {"stageId": "clean", "moduleRole": "CleaningWeighing", "requirement": "clean", "releaseManifestPath": str(release),
             "moduleSelection": {"projectId": "p", "moduleToken": "clean", "confirmed": True},
             "stationEvidence": {"caseId": "synthetic-cleaning", "cadResultPath": str(cad), "effectiveGraphPath": str(graph),
                                 "witnessPath": str(witness), "contextStatePath": str(state)}}]}
    bindings = [{"stageId": token, "source": "p::" + token, "target": "p::base", "moduleDefinitionId": IDS[token],
                 "baseModuleDefinitionId": IDS["base"], "releaseManifestPath": str(release)} for token in ("transport", "clean")]
    return {"request": request, "bindings": bindings, "before": before, "state": state, "witness": witness,
            "release": release, "measurement": measured, "cad": cad, "graph": graph}


def _build(tmp_path, synthetic):
    return gate.build_target_station_chain_preflight(tmp_path, synthetic["request"], stage_bindings=synthetic["bindings"])


def test_synthetic_positive_only_allows_offline_compile_and_exact_runtime_source(tmp_path, synthetic):
    report = _build(tmp_path, synthetic)
    assert report["readyForCadCompilation"] is True
    assert report["targetStationValidated"] is True
    assert report["liveChainStationValidationPassed"] is False
    assert report["cadStarted"] is False
    assert gate.revalidate_target_station_preflight(tmp_path, synthetic["request"], report) == report
    gate.validate_stage_source_checkpoint(report, "clean", {
        "assemblyPath": str(synthetic["before"]), "assemblySha256": gate.file_sha256(synthetic["before"])})


@pytest.mark.parametrize("mutation,reason", [
    (lambda s: s["request"]["steps"][1].pop("stationEvidence"), "STATION_EVIDENCE_REQUIRED"),
    (lambda s: s["request"]["steps"][1]["stationEvidence"].pop("contextStatePath"), "STATION_EVIDENCE_UNREADABLE_OR_INCOMPLETE"),
    (lambda s: s["request"]["steps"][1].update(moduleRole="unregistered-role"), "MODULE_ROLE_MISSING_OR_UNKNOWN"),
    (lambda s: s["request"]["steps"].reverse(), "STATION_WITNESS_CONTEXT_MEMBERSHIP_MISMATCH"),
])
def test_strict_missing_or_reordered_inputs_block_without_cad(tmp_path, synthetic, mutation, reason):
    mutation(synthetic)
    report = _build(tmp_path, synthetic)
    assert report["readyForCadCompilation"] is False
    assert any(reason in error for error in report["blockingReasonCodes"])
    assert report["cadStarted"] is False


@pytest.mark.parametrize("field,value,reason", [
    ("contextModuleDefinitionIds", [IDS["base"], IDS["clean"]], "CONTEXT_MEMBERSHIP_MISMATCH"),
    ("contextStateSha256", "0" * 64, "CONTEXT_STATE_DIGEST_MISMATCH"),
])
def test_pair_only_or_unbound_pose_witness_is_not_a_chain_witness(tmp_path, synthetic, field, value, reason):
    witness = json.loads(synthetic["witness"].read_text())
    witness[field] = value
    _write(synthetic["witness"], witness)
    report = _build(tmp_path, synthetic)
    assert report["readyForCadCompilation"] is False
    assert any(reason in error for error in report["blockingReasonCodes"])


def test_release_must_bind_exact_station_cad_bytes(tmp_path, synthetic):
    _write(synthetic["release"], {"status": "released_for_demo_relation_execution", "validationEvidence": [{"passed": True, "fileSha256": "old"}]})
    assert any("RELEASE_DOES_NOT_BIND_STATION_CAD_RESULT" in error for error in _build(tmp_path, synthetic)["blockingReasonCodes"])


def test_user_cannot_relabel_cleaning_as_transport_to_skip_station_evidence(tmp_path, synthetic):
    synthetic["request"]["steps"][1]["moduleRole"] = "Transport"
    synthetic["request"]["steps"][1].pop("stationEvidence")
    report = _build(tmp_path, synthetic)
    assert report["readyForCadCompilation"] is False
    assert report["stages"][1]["stationEvidenceRequired"] is True
    assert any("STATION_EVIDENCE_REQUIRED" in error for error in report["blockingReasonCodes"])


def test_valid_state_cannot_be_spliced_onto_cad_from_different_source(tmp_path, synthetic):
    other = _write(tmp_path / "different-source.SLDASM", {"syntheticFixture": True, "differentPose": True})
    state = json.loads(synthetic["state"].read_text())
    state.update(assemblyPath=str(other), assemblySha256=gate.file_sha256(other))
    _write(synthetic["state"], state)
    witness = json.loads(synthetic["witness"].read_text())
    witness["contextStateSha256"] = gate.file_sha256(synthetic["state"])
    _write(synthetic["witness"], witness)
    report = _build(tmp_path, synthetic)
    assert report["readyForCadCompilation"] is False
    assert any("STATION_CAD_SOURCE_CONTEXT_BINDING_MISMATCH" in error for error in report["blockingReasonCodes"])


def test_two_self_reported_instance_lists_do_not_override_catalog_identity(tmp_path, synthetic):
    state = json.loads(synthetic["state"].read_text())
    state["observed"]["components"][1]["sourcePath"] = "invented-other-module.SLDASM"
    _write(synthetic["state"], state)
    witness = json.loads(synthetic["witness"].read_text())
    witness["sourceContextInstances"][1]["sourcePath"] = "invented-other-module.SLDASM"
    witness["contextStateSha256"] = gate.file_sha256(synthetic["state"])
    _write(synthetic["witness"], witness)
    report = _build(tmp_path, synthetic)
    assert report["readyForCadCompilation"] is False
    assert any("SOURCE_CONTEXT_COMPONENT_NOT_IN_RELEASED_DEFINITIONS" in error for error in report["blockingReasonCodes"])


@pytest.mark.parametrize("change,reason", [
    ("not_readonly", "SOURCE_CONTEXT_READONLY_STATE_INVALID"),
    ("empty_checks", "SOURCE_CONTEXT_READONLY_STATE_INVALID"),
    ("same_count_different_component", "SOURCE_CONTEXT_INSTANCE_IDENTITY_MISMATCH"),
    ("missing_mapping", "SOURCE_CONTEXT_INSTANCE_IDENTITY_MISMATCH"),
])
def test_readonly_snapshot_requires_successful_checks_and_exact_instance_identities(tmp_path, synthetic, change, reason):
    state = json.loads(synthetic["state"].read_text())
    witness = json.loads(synthetic["witness"].read_text())
    if change == "not_readonly":
        state["observed"]["readOnly"] = False
    elif change == "empty_checks":
        state["checks"] = {}
    elif change == "same_count_different_component":
        state["observed"]["components"][1]["sourcePath"] = "different-module.SLDASM"
    else:
        witness.pop("sourceContextInstances")
    _write(synthetic["state"], state)
    witness["contextStateSha256"] = gate.file_sha256(synthetic["state"])
    _write(synthetic["witness"], witness)
    report = _build(tmp_path, synthetic)
    assert report["readyForCadCompilation"] is False
    assert any(reason in error for error in report["blockingReasonCodes"])


@pytest.mark.parametrize("change", ["parameter", "evidence", "preflight"])
def test_run_resume_revalidation_rejects_mutated_parameters_or_evidence(tmp_path, synthetic, change):
    report = _build(tmp_path, synthetic)
    if change == "parameter":
        synthetic["request"]["steps"][1]["longitudinalMeters"] = 0.1
    elif change == "evidence":
        _write(synthetic["measurement"], {"changed": True})
    else:
        report["readyForCadCompilation"] = False
    with pytest.raises(ValueError):
        gate.revalidate_target_station_preflight(tmp_path, synthetic["request"], report)


def test_same_module_ids_but_different_actual_predecessor_is_rejected(tmp_path, synthetic):
    report = _build(tmp_path, synthetic)
    other = _write(tmp_path / "other.SLDASM", {"syntheticFixture": True, "moduleIds": [IDS["base"], IDS["transport"]], "poseChanged": True})
    with pytest.raises(ValueError, match="predecessor differs"):
        gate.validate_stage_source_checkpoint(report, "clean", {"assemblyPath": str(other), "assemblySha256": gate.file_sha256(other)})
    with pytest.raises(ValueError, match="unavailable"):
        gate.validate_stage_source_checkpoint(report, "clean", None)


def test_scanner_additionally_calls_process_association_gate(tmp_path, synthetic, monkeypatch):
    step = synthetic["request"]["steps"][1]
    step["moduleRole"] = "Scanner"
    association = _write(tmp_path / "association.json", {"syntheticFixture": True})
    evaluation = _write(tmp_path / "evaluation.json", {"syntheticFixture": True})
    step["scannerTargetEvidence"] = {"associationPath": str(association), "evaluationPath": str(evaluation),
        "plannedComponents": [{"moduleDefinitionId": item} for item in ("p::base", "p::transport", "p::clean")],
        "worldFrameId": "synthetic-world", "allowPrototypeProxy": True}
    calls = []

    def process(**kwargs):
        calls.append(kwargs)
        return {"processCandidateCompileAllowed": False, "blockingReasonCodes": ["synthetic_target_failure"]}

    monkeypatch.setattr(gate, "preflight_scanner_target_for_cumulative_chain", process)
    report = _build(tmp_path, synthetic)
    assert calls[0]["allow_prototype_proxy"] is True
    assert not any("SCANNER_PLANNED_CONTEXT_MEMBERSHIP_MISMATCH" in error for error in report["blockingReasonCodes"])
    assert any("SCANNER_TARGET_PREFLIGHT_NOT_PASSED" in error for error in report["blockingReasonCodes"])
    step.pop("scannerTargetEvidence")
    assert any("SCANNER_TARGET_EVIDENCE_REQUIRED" in error for error in _build(tmp_path, synthetic)["blockingReasonCodes"])


def _cli(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("strict_chain_cli", ROOT / "scripts/run_natural_language_staged_chain.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    return module


def test_blocked_compile_persists_preflight_without_nl_job_or_cad(tmp_path, synthetic, monkeypatch):
    cli = _cli(tmp_path, monkeypatch)
    catalog = {"moduleDefinitions": [{"moduleDefinitionId": IDS[token], "projectAliases": [{"projectId": "p", "moduleToken": token}]}
                                      for token in ("base", "transport", "clean")]}
    monkeypatch.setattr(cli, "load_relation_catalog_release", lambda *a, **k: (catalog, {}))
    monkeypatch.setattr(cli, "compile_natural_language_manifest_job", lambda *a, **k: pytest.fail("blocked preflight cannot create NL/CAD jobs"))
    synthetic["request"]["steps"][1].pop("stationEvidence")
    path = _write(tmp_path / "request.json", synthetic["request"])
    output = tmp_path / "blocked-chain"
    report = cli.compile_chain(path, output)
    assert report["status"] == "blocked_before_chain_compile"
    assert (output / "target-station-preflight.json").is_file()
    assert not (output / "chain.json").exists()
    assert not (output / "jobs").exists()


@pytest.mark.parametrize("mutation", ["delete_preflight", "request_changed", "predecessor_changed"])
def test_execution_stops_before_job_preparation_when_binding_is_invalid(tmp_path, synthetic, monkeypatch, mutation):
    cli = _cli(tmp_path, monkeypatch)
    # Simulated compiled chain; no real CAD release or execution is claimed.
    output = tmp_path / "compiled"
    preflight = _build(tmp_path, synthetic)
    request_path = _write(tmp_path / "request.json", synthetic["request"])
    preflight_path = _write(output / "target-station-preflight.json", preflight)
    chain_path = _write(output / "chain.json", {"chainId": "fixture", "stages": [{"stageId": "clean"}]})
    _write(output / "compilation.json", {"requestPath": str(request_path), "requestSha256": cli.sha(request_path),
        "request": synthetic["request"], "targetStationPreflightSha256": cli.sha(preflight_path), "chainSha256": cli.sha(chain_path)})
    if mutation == "delete_preflight":
        preflight_path.unlink()
    elif mutation == "request_changed":
        changed = copy.deepcopy(synthetic["request"])
        changed["steps"].reverse()
        _write(request_path, changed)
    # predecessor_changed uses a first station stage with no live predecessor;
    # the same module IDs in historical evidence cannot fill that missing state.
    monkeypatch.setattr(cli, "prepare_multi_release_stage_job", lambda *a, **k: pytest.fail("invalid bindings must not create a CAD job"))
    monkeypatch.setattr(cli, "manifest_cad_step_runner", lambda *a, **k: pytest.fail("must not start CAD"))
    with pytest.raises((ValueError, FileNotFoundError)):
        cli.execute_chain(output, resume=True)
