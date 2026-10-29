"""CLI control-flow tests; CAD is deliberately simulated, never launched."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[3]


@pytest.fixture
def cli(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "staged_chain_cli_under_test", REPO / "scripts/run_natural_language_staged_chain.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    return module


def _request():
    return {
        "chainId": "six-role-test", "baseRequirement": "建立设备基座",
        "baseSelection": {"projectId": "project03", "moduleToken": "AA00", "confirmed": True},
        "steps": [{
            "stageId": "cleaning", "requirement": "增加清洁称重模组，允许按基准定位",
            "releaseManifestPath": "release.json", "relationExecutionMode": "datum_placement_demo",
            "moduleSelection": {"projectId": "project01", "moduleToken": "GN00", "confirmed": True},
        }],
    }


def test_station_checkpoint_retries_inspection_and_revalidates_saved_result(cli, tmp_path, monkeypatch):
    from types import SimpleNamespace
    out = tmp_path / "chain"
    _write(out / "station-preparation/s1/station-plan.json", {"targetBaseDefinitionId": "p::BASE"})
    cad = _write(tmp_path / "cad.json", {})
    envelope = _write(tmp_path / "envelope.json", {"cadResultPath": str(cad),
                                                  "executionSourceAssemblyPath": "source.SLDASM"})
    closure = {"executionEnvelopePath": str(envelope), "executionEnvelopeSha256": cli.sha(envelope)}
    calls = []
    def inspect(command, **kwargs):
        calls.append(command)
        if len(calls) == 1:
            return SimpleNamespace(returncode=2, stdout=b"", stderr=b"inspection failed")
        _write(Path(command[command.index("--report")+1]), {"success": True})
        return SimpleNamespace(returncode=0, stdout=b"ok", stderr=b"")
    monkeypatch.setattr(cli.subprocess, "run", inspect)
    checks = []
    def check(*args, **kwargs):
        checks.append(kwargs)
        return {"cadPassed": True, "targetStationValidated": True}
    monkeypatch.setattr(cli, "verify_station_stage", check)
    with pytest.raises(ValueError, match="独立重开检查失败"):
        cli.verify_stage_checkpoint(out, "s1", closure, expected_count=2)
    assert not (out / "s1/station-postcheck.json").exists()
    result = cli.verify_stage_checkpoint(out, "s1", closure, expected_count=2)
    assert result["targetStationValidated"]
    assert cli.verify_stage_checkpoint(out, "s1", closure, expected_count=2) == result
    assert len(calls) == 2 and len(checks) == 2
    _write(Path(result["savedStatePath"]), {"changed": True})
    with pytest.raises(ValueError, match="证据已变化"):
        cli.verify_stage_checkpoint(out, "s1", closure, expected_count=2)


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


def _catalog():
    return {"moduleDefinitions": [
        {"moduleDefinitionId": "actual-base-cad-id", "projectAliases": [{"projectId": "project03", "moduleToken": "AA00"}]},
        {"moduleDefinitionId": "actual-cleaning-cad-id", "projectAliases": [{"projectId": "project01", "moduleToken": "GN00"}]},
    ]}


def test_station_authority_does_not_reuse_release_for_changed_parameters(cli):
    with pytest.raises(ValueError, match="NEW_CAD_RELEASE"):
        cli.station_authority({}, {}, {"requiresFreshCadValidation": True})
    plan = {"requiresFreshCadValidation": False, "reusableExecutionAuthority": {
        "releaseManifestPath": "new.json", "relationExecutionMode": "datum_placement_demo"}}
    with pytest.raises(ValueError, match="AUTHORIZATION_REQUIRED"):
        cli.station_authority({}, {}, plan)
    with pytest.raises(ValueError, match="RELEASE_DIFFERS"):
        cli.station_authority({}, {"allowDatumFallback": True, "releaseManifestPath": "old.json"}, plan)
    authority = cli.station_authority({}, {"allowDatumFallback": True}, plan)
    assert authority["releaseManifestPath"] == "new.json"
    assert authority["source"] == "registered_station_rule"


def test_compile_preserves_engineering_prompt_and_explicit_selection_without_starting_cad(cli, tmp_path, monkeypatch):
    requests = []
    monkeypatch.setattr(cli, "load_relation_catalog_release", lambda *_args, **_kwargs: (_catalog(), {}))

    def compile_request(workspace, payload):
        requests.append(copy.deepcopy(payload))
        manifest = _write(workspace / "compiled/source-manifest.json", {"packetCount": 1})
        return {"success": True, "manifestPath": str(manifest), "status": "job_created_not_started"}

    monkeypatch.setattr(cli, "compile_natural_language_manifest_job", compile_request)
    monkeypatch.setattr(cli, "build_multi_release_cad_chain", lambda workspace, **kwargs: kwargs)
    monkeypatch.setattr(cli, "manifest_cad_step_runner", lambda *args, **kwargs: pytest.fail("compile不得启动CAD"))
    request_path = _write(tmp_path / "request.json", _request())
    output = tmp_path / "compiled-chain"
    report = cli.compile_chain(request_path, output)
    assert report["status"] == "ready_not_started"
    assert report["cadStarted"] is False
    assert report["collisionOrBrep"] == "not_evaluated"
    assert report["actualFasteningMethod"] == "not_verified"
    assert report["durationSeconds"] >= 0
    assert report["placementValidationMode"] == "cad_only_legacy"
    assert report["targetStationValidated"] is False
    assert requests[0]["requirements"] == ["建立设备基座", "增加清洁称重模组，允许按基准定位"]
    assert requests[0]["confirmedModuleSelections"] == [
        {"moduleDefinitionId": "actual-base-cad-id", "confirmed": True},
        {"moduleDefinitionId": "actual-cleaning-cad-id", "confirmed": True},
    ]
    assert requests[0]["relationExecutionMode"] == "datum_placement_demo"
    assert requests[0]["enforceMechanicalInterfaceContracts"] is True
    assert requests[0]["autoOrderByReleasedDependencies"] is False
    assert cli.read(output / "cleaning/natural-language-request.json") == requests[0]
    assert cli.read(output / "chain.json")["stages"][0]["stageId"] == "cleaning"


def test_requested_registry_never_silently_falls_back_to_legacy_positions(cli, tmp_path, monkeypatch):
    request = _request(); request["stationRegistryPath"] = "rules.json"
    monkeypatch.setattr(cli, "plan_station_chain", lambda *_a, **_k: {
        "planningComplete": True, "stages": [], "cadLaunchAllowed": False})
    monkeypatch.setattr(cli, "compile_natural_language_manifest_job", lambda *_a, **_k: pytest.fail("Do not compile historical positions"))
    path = _write(tmp_path / "request.json", request)
    result = cli.compile_chain(path, tmp_path / "with-stations")
    assert result["status"] == "blocked_before_chain_compile"
    assert not result["cadStarted"]
    assert result["blockingReasonCodes"] == ["TARGET_STATION_PLAN_INCOMPLETE"]


def test_station_preparation_saves_candidates_without_starting_cad(cli, tmp_path, monkeypatch):
    package = {"effectiveGraph": {"Mates": []}, "selectedEndpointCatalog": {"Endpoints": []}, "validationRequiredBeforeRelease": True}
    plan = {"validationPackage": package, "targetStationValidated": False}
    monkeypatch.setattr(cli, "plan_station_chain", lambda *_a, **_k: {
        "planningComplete": True, "stages": [{"stageId": "cleaning", "planned": True, "plan": plan}], "cadLaunchAllowed": False})
    monkeypatch.setattr(cli, "manifest_cad_step_runner", lambda *_a, **_k: pytest.fail("No CAD in planning"))
    path = _write(tmp_path / "request.json", _request())
    result = cli.plan_stations(path, tmp_path / "prepared", prepare_candidates=True)
    saved = cli.read(result["stages"][0]["candidatePackagePath"])
    assert saved["validationRequiredBeforeRelease"]
    graph = saved["artifacts"]["effectiveGraph"]
    assert cli.sha(graph["path"]) == graph["sha256"]
    assert cli.read(graph["path"]) == package["effectiveGraph"]
    assert not result["cadLaunchAllowed"]
    with pytest.raises(FileExistsError):
        cli.plan_stations(path, tmp_path / "prepared")


def test_compile_auto_selects_released_authority_from_confirmed_pair(cli, tmp_path, monkeypatch):
    request = _request()
    request["steps"][0].pop("releaseManifestPath")
    request["steps"][0].pop("relationExecutionMode")
    request["steps"][0]["allowDatumFallback"] = True
    _write(
        tmp_path / "demo/global_assembly_catalog/v1/global_module_catalog.json",
        _catalog(),
    )
    authority_calls = []

    def resolve_authority(workspace, module_definition_id, **kwargs):
        authority_calls.append((module_definition_id, kwargs))
        return {
            "ready": True,
            "status": "released_interface_authority_ready",
            "releaseManifestPath": "auto-release.json",
            "relationExecutionMode": "datum_placement_demo",
            "selectedMode": "parameterized_datum_placement",
        }

    monkeypatch.setattr(cli, "resolve_preferred_released_interface_authority", resolve_authority)
    monkeypatch.setattr(cli, "load_relation_catalog_release", lambda *_args, **_kwargs: (_catalog(), {}))
    requests = []

    def compile_request(workspace, payload):
        requests.append(copy.deepcopy(payload))
        manifest = _write(workspace / "compiled/auto-manifest.json", {"packetCount": 1})
        return {"success": True, "manifestPath": str(manifest), "status": "job_created_not_started"}

    monkeypatch.setattr(cli, "compile_natural_language_manifest_job", compile_request)
    monkeypatch.setattr(cli, "build_multi_release_cad_chain", lambda workspace, **kwargs: kwargs)
    path = _write(tmp_path / "request.json", request)
    output = tmp_path / "auto-output"
    cli.compile_chain(path, output)
    assert authority_calls == [(
        "actual-cleaning-cad-id",
        {
            "selected_slot_definition_id": "actual-base-cad-id",
            "allow_datum_fallback": True,
        },
    )]
    assert requests[0]["releaseManifestPath"] == "auto-release.json"
    assert requests[0]["relationExecutionMode"] == "datum_placement_demo"
    decision = cli.read(output / "cleaning/interface-authority-decision.json")
    assert decision["source"] == "confirmed_module_and_slot_planner"
    assert decision["confirmedModuleDefinitionId"] == "actual-cleaning-cad-id"
    assert cli.read(output / "chain.json")["stages"][0]["authoritySource"] == "confirmed_module_and_slot_planner"


def test_auto_selection_fails_closed_when_datum_was_not_explicitly_allowed(cli, tmp_path, monkeypatch):
    request = _request()
    request["steps"][0].pop("releaseManifestPath")
    request["steps"][0].pop("relationExecutionMode")
    _write(
        tmp_path / "demo/global_assembly_catalog/v1/global_module_catalog.json",
        _catalog(),
    )

    def resolve_authority(workspace, module_definition_id, **kwargs):
        assert kwargs["allow_datum_fallback"] is False
        return {
            "ready": False,
            "status": "native_interface_unavailable_datum_fallback_disabled",
        }

    monkeypatch.setattr(cli, "resolve_preferred_released_interface_authority", resolve_authority)
    path = _write(tmp_path / "request.json", request)
    with pytest.raises(ValueError, match="datum_fallback_disabled"):
        cli.compile_chain(path, tmp_path / "blocked-output")
    assert not (tmp_path / "blocked-output").exists()


@pytest.mark.parametrize("mutation, message", [
    (lambda request: request.update(chainId="../escape"), "chainId"),
    (lambda request: request["steps"][0].update(stageId="../escape"), "stageId"),
    (lambda request: request["steps"].append(copy.deepcopy(request["steps"][0])), "唯一"),
    (lambda request: request.update(steps=[]), "1至19"),
    (lambda request: request["steps"][0].update(relationExecutionMode="prototype_fallback"), "不支持"),
])
def test_compile_rejects_unsafe_or_invalid_request_before_nl_side_effects(cli, tmp_path, monkeypatch, mutation, message):
    request = _request()
    mutation(request)
    path = _write(tmp_path / "request.json", request)
    monkeypatch.setattr(cli, "compile_natural_language_manifest_job", lambda *_args: pytest.fail("输入无效不应编译"))
    with pytest.raises(ValueError, match=message):
        cli.compile_chain(path, tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_compile_rejects_output_outside_workspace_before_writes(cli, tmp_path, monkeypatch):
    path = _write(tmp_path / "request.json", _request())
    monkeypatch.setattr(cli, "compile_natural_language_manifest_job", lambda *_args: pytest.fail("工作区外不应编译"))
    with pytest.raises(ValueError):
        cli.compile_chain(path, tmp_path.parent / "outside-this-workspace")


@pytest.mark.parametrize("selection", [None, {}, {"projectId": "project01", "moduleToken": "GN00", "confirmed": False}])
def test_selection_must_be_confirmed(cli, selection):
    with pytest.raises(ValueError, match="显式确认"):
        cli.resolve_confirmed_selection(selection, _catalog())


def test_selection_must_identify_exactly_one_cad_definition(cli):
    selection = {"projectId": "project01", "moduleToken": "GN00", "confirmed": True}
    catalog = _catalog()
    catalog["moduleDefinitions"].append(copy.deepcopy(catalog["moduleDefinitions"][1]))
    with pytest.raises(ValueError, match="唯一"):
        cli.resolve_confirmed_selection(selection, catalog)
    with pytest.raises(ValueError, match="唯一"):
        cli.resolve_confirmed_selection({**selection, "moduleToken": "unknown"}, _catalog())


def test_compile_failure_records_reason_without_building_ready_chain(cli, tmp_path, monkeypatch):
    request = _request()
    request.pop("baseSelection")
    request["steps"][0].pop("moduleSelection")
    path = _write(tmp_path / "request.json", request)
    monkeypatch.setattr(cli, "compile_natural_language_manifest_job", lambda *_args: {
        "success": False, "status": "needs_interface_confirmation",
    })
    monkeypatch.setattr(cli, "build_multi_release_cad_chain", lambda *_args, **_kwargs: pytest.fail("失败不能生成ready链"))
    with pytest.raises(ValueError, match="needs_interface_confirmation"):
        cli.compile_chain(path, tmp_path / "output")
    assert cli.read(tmp_path / "output/cleaning/natural-language-compilation.json")["success"] is False
    assert not (tmp_path / "output/chain.json").exists()


@pytest.fixture
def simulated_execution(cli, tmp_path, monkeypatch):
    output = tmp_path / "run"
    _write(output / "chain.json", {
        "chainId": "test", "stages": [{"stageId": "direct"}, {"stageId": "datum"}],
    })
    request = {"chainId": "test", "steps": [{"stageId": "direct"}, {"stageId": "datum"}]}
    request_path = _write(tmp_path / "execution-request.json", request)
    preflight = cli.build_target_station_chain_preflight(tmp_path, request, stage_bindings=[])
    preflight_path = _write(output / "target-station-preflight.json", preflight)
    _write(output / "compilation.json", {
        "requestPath": str(request_path), "requestSha256": cli.sha(request_path), "request": request,
        "targetStationPreflightSha256": cli.sha(preflight_path), "chainSha256": cli.sha(output / "chain.json"),
    })

    class Store:
        def __init__(self):
            self.jobs = {}
            self.resume_calls = []

        def load(self, job_id):
            return copy.deepcopy(self.jobs[job_id])

        def prepare_resume(self, job_id):
            self.resume_calls.append(job_id)
            self.jobs[job_id]["status"] = "queued"
            return self.load(job_id)

    store = Store()
    monkeypatch.setattr(cli, "DurableAssemblyJobStore", lambda _: store)
    source_inputs, run_calls = [], []

    def prepare(workspace, chain, *, stage_id, store, artifacts_root, previous_closure_path):
        source_inputs.append((stage_id, previous_closure_path))
        if stage_id == "datum":
            assert previous_closure_path == output / "direct/stage-closure.json"
            assert previous_closure_path.is_file()
        store.jobs.setdefault(stage_id, {"jobId": stage_id, "status": "queued", "attempts": 0})
        return store.load(stage_id)

    def run(store, job_id, runner):
        run_calls.append(job_id)
        job = store.jobs[job_id]
        job["attempts"] += 1
        job["status"] = "failed" if runner.get("fail_before_packet") else "succeeded"
        return store.load(job_id)

    def closure(workspace, chain, *, stage_id, store, job_id):
        assert store.jobs[job_id]["status"] == "succeeded"
        return {"status": "passed", "jobId": job_id, "stageId": stage_id,
                "finalAssemblyPath": str(output / f"{stage_id}.SLDASM"),
                "finalAssemblySha256": f"hash-{stage_id}", "checks": {"saveReopenPassed": True}}

    monkeypatch.setattr(cli, "prepare_multi_release_stage_job", prepare)
    monkeypatch.setattr(cli, "manifest_cad_step_runner", lambda *args, **kwargs: kwargs)
    monkeypatch.setattr(cli, "guard_multi_release_stage_runner", lambda *args, **kwargs: kwargs["runner"])
    monkeypatch.setattr(cli, "run_manifest_job", run)
    monkeypatch.setattr(cli, "build_multi_release_stage_closure", closure)
    return output, store, run_calls, source_inputs


def test_run_success_reuses_committed_stages_without_reexecuting_cad(cli, simulated_execution, capsys):
    output, store, calls, source_inputs = simulated_execution
    first = cli.execute_chain(output)
    assert first["success"] is True
    assert first["targetStationValidated"] is False
    assert calls == ["direct", "datum"]
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [row["event"] for row in events] == [
        "cad_job_finished", "stage_checkpoint_committed",
        "cad_job_finished", "stage_checkpoint_committed",
    ]
    assert [row["checkpointCommitted"] for row in events] == [False, True, False, True]
    assert all(row["totalStageDurationSeconds"] >= row["durationSeconds"]
               for row in events if row["checkpointCommitted"])
    second = cli.execute_chain(output)
    assert second["success"] is True
    assert calls == ["direct", "datum"]
    assert all(row["status"] == "reused_committed_checkpoint" for row in second["stages"])
    assert len(list((output / "run-attempts").glob("*.json"))) == 2


def test_failure_keeps_previous_stage_and_explicit_resume_retries_only_failed_stage(cli, simulated_execution):
    output, store, calls, source_inputs = simulated_execution
    failed = cli.execute_chain(output, fail_before_stage="datum")
    assert failed["success"] is False
    assert failed["lastCommittedClosurePath"] == str(output / "direct/stage-closure.json")
    assert not (output / "datum/stage-closure.json").exists()
    with pytest.raises(ValueError, match="resume"):
        cli.execute_chain(output)
    resumed = cli.execute_chain(output, resume=True)
    assert resumed["success"] is True
    assert resumed["stages"][0]["status"] == "reused_committed_checkpoint"
    assert calls == ["direct", "datum", "datum"]
    assert store.jobs["direct"]["attempts"] == 1
    assert store.jobs["datum"]["attempts"] == 2
    assert store.resume_calls == ["datum"]


def test_pause_between_packets_then_resume_preserves_completed_packet(cli, simulated_execution):
    output, store, calls, _ = simulated_execution
    paused = cli.execute_chain(output, pause_after_stage="direct")
    assert not paused["success"] and paused["pausedAfterStage"] == "direct"
    assert calls == ["direct"]
    assert (output / "direct/stage-closure.json").is_file()
    assert "datum" not in store.jobs
    resumed = cli.execute_chain(output, resume=True)
    assert resumed["success"] and calls == ["direct", "datum"]
    assert store.jobs["direct"]["attempts"] == 1


def test_final_closure_tampering_is_not_hidden_by_unchanged_output_identity(cli, simulated_execution):
    output, store, calls, source_inputs = simulated_execution
    cli.execute_chain(output)
    path = output / "datum/stage-closure.json"
    value = cli.read(path)
    value["checks"]["saveReopenPassed"] = False
    _write(path, value)
    with pytest.raises(ValueError, match="已提交阶段证据发生变化"):
        cli.execute_chain(output)
    assert calls == ["direct", "datum"]


@pytest.mark.parametrize("preflight,expected", [
    ({"ruleDriven": True, "readyForCadCompilation": True, "targetStationValidated": False,
      "blockingReasonCodes": []}, True),
    ({"ruleDriven": True, "readyForCadCompilation": False, "targetStationValidated": True}, False),
    ({"ruleDriven": True, "readyForCadCompilation": True, "blockingReasonCodes": ["missing"]}, False),
    ({"readyForCadCompilation": True, "targetStationValidated": False}, False),
    ({"targetStationValidated": True}, True),
])
def test_preflight_reporting_does_not_confuse_ready_plan_with_cad_validation(cli, preflight, expected):
    original = copy.deepcopy(preflight)
    assert cli.station_preflight_passed(preflight) is expected
    assert preflight == original


def test_postcheck_failure_has_run_report_and_resume_does_not_repeat_cad(cli, simulated_execution, monkeypatch):
    output, store, calls, _ = simulated_execution
    _write(output / "station-preparation/direct/station-plan.json", {})
    def fail(*_a, **_k):
        raise ValueError("synthetic target underconstrained")
    monkeypatch.setattr(cli, "verify_stage_checkpoint", fail)
    result = cli.execute_chain(output)
    assert result["success"] is False
    assert result["targetStationPostcheckStatus"] == "failed_current_state"
    assert result["lastCommittedClosurePath"] is None
    assert result["stages"][0]["cadJobStatus"] == "succeeded"
    assert result["stages"][0]["checkpointCommitted"] is False
    assert not (output / "direct/stage-closure.json").exists()
    assert (output / "run-attempts/attempt-001.json").is_file()
    assert calls == ["direct"] and "datum" not in store.jobs
    monkeypatch.setattr(cli, "verify_stage_checkpoint", lambda *_a, **_k: {})
    recovered = cli.execute_chain(output, resume=True)
    assert recovered["success"] is True
    assert calls == ["direct", "datum"]
    assert store.jobs["direct"]["attempts"] == 1


def test_pause_at_reused_checkpoint_preserves_pause_status(cli, simulated_execution):
    output, _, calls, _ = simulated_execution
    assert cli.execute_chain(output)["success"]
    paused = cli.execute_chain(output, pause_after_stage="direct")
    assert paused["pausedAfterStage"] == "direct"
    assert not paused["success"]
    assert calls == ["direct", "datum"]


@pytest.mark.parametrize("failure", [None, "changed_assembly", "measurement_only"])
def test_saved_state_comparison_binds_assembly_before_delegating(cli, tmp_path, monkeypatch, failure):
    import demo_backend.datum_chain_verification as verifier
    assembly = tmp_path / "fixture.SLDASM"
    assembly.write_bytes(b"synthetic test data, not CAD")
    state = {"assemblyPath": str(assembly), "assemblySha256": cli.sha(assembly)}
    if failure == "changed_assembly": assembly.write_bytes(b"changed")
    if failure == "measurement_only": state["cadAcceptanceEvaluated"] = False
    state_path = _write(tmp_path / "state.json", state)
    request = _write(tmp_path / "comparison.json", {"beforeStatePath": str(state_path),
        "afterStatePath": str(state_path), "baseToken": "BASE"})
    calls = []
    def compare(*args, **kwargs):
        calls.append(kwargs)
        return {"success": True, "checks": {"mockOnly": True}}
    monkeypatch.setattr(verifier, "compare_cad_states", compare)
    if failure:
        with pytest.raises(ValueError):
            cli.compare_saved_states(request, tmp_path / "report.json")
        assert not calls
    else:
        report = cli.compare_saved_states(request, tmp_path / "report.json")
        assert report["newCadExecuted"] is False and report["functionalPassed"] is None
        assert len(report["evidence"]) == 4 and calls[0]["base_token"] == "BASE"
