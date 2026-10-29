"""Final evidence assembly is read-only and rechecks sources, not cached labels."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest


ROOT=Path(__file__).resolve().parents[3]


@pytest.fixture
def finalizer():
    spec=importlib.util.spec_from_file_location("gn00_finalizer_test",ROOT / "scripts/finalize_gn00_six_role_experiment.py")
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_real_initial_variant_reports_have_bound_distinct_inputs(finalizer):
    result=finalizer.compare_initial_variants()
    assert result["success"] is True
    assert result["inputEvidence"]["initialPlacementVariants"]==[1,2]


def test_initial_comparison_rejects_reused_variant_label(finalizer,monkeypatch):
    monkeypatch.setattr(finalizer,"verified_cad",lambda path: (
        {"outputAssemblyPath":str(path)+".SLDASM"},
        {"EditPolicy":{"initialPlacementMode":"deterministic","initialPlacementVariant":1},"Mates":[]},
    ))
    with pytest.raises(ValueError,match="不同初始化变体"):
        finalizer.compare_initial_variants()


def test_readonly_snapshot_must_match_current_output_hash(finalizer,tmp_path):
    output=tmp_path / "output.SLDASM"
    output.write_bytes(b"new output")
    path=tmp_path / "readonly.json"
    path.write_text(json.dumps({"success":True,"checks":{"read":True},"observed":{"readOnly":True},
        "assemblyPath":str(output),"assemblySha256":"old hash"}))
    with pytest.raises(ValueError,match="未绑定当前CAD实体"):
        finalizer.verified_state(path,{"outputAssemblyPath":str(output),"outputAssemblySha256":finalizer.sha(output)})


def test_changed_closure_is_not_accepted_from_its_passed_status(finalizer,tmp_path,monkeypatch):
    monkeypatch.setattr(finalizer,"read",lambda path:{"jobId":"job","status":"passed","closureDigest":"old"})
    monkeypatch.setattr(finalizer,"build_multi_release_stage_closure",lambda *a,**k:{"jobId":"job","status":"passed","closureDigest":"new"})
    with pytest.raises(ValueError,match="闭合证据"):
        finalizer.verified_closure(tmp_path,{}, {"stageId":"x"})


def test_write_reuses_equal_evidence_but_never_overwrites_different_result(finalizer,tmp_path):
    path=tmp_path / "result.json"
    finalizer.write(path,{"success":True})
    finalizer.write(path,{"success":True})
    with pytest.raises(ValueError,match="拒绝覆盖"):
        finalizer.write(path,{"success":False})


def test_reverification_retains_original_generation_time(finalizer,tmp_path):
    path=tmp_path / "summary.json"
    stamp=finalizer.report_generation_time(path)
    first={"schemaVersion":"gn00-six-role-datum-experiment/v1","generatedAtUtc":stamp,"success":True}
    finalizer.write(path,first)
    before=path.read_bytes()
    finalizer.write(path,{**first,"generatedAtUtc":finalizer.report_generation_time(path)})
    assert path.read_bytes()==before
    with pytest.raises(ValueError,match="拒绝覆盖"):
        finalizer.write(path,{**first,"success":False})


def test_reverification_rejects_invalid_report_time(finalizer,tmp_path):
    path=tmp_path / "summary.json"
    path.write_text(json.dumps({"schemaVersion":"gn00-six-role-datum-experiment/v1",
                               "generatedAtUtc":"2026-10-23T17:00:00"}))
    with pytest.raises(ValueError,match="时间戳无效"):
        finalizer.report_generation_time(path)


def test_failed_attempts_and_successful_packet_timing_are_separate(finalizer):
    job={"status":"succeeded","executionDurationSeconds":270.,"steps":[{
        "status":"succeeded","attemptCount":2,"attempts":[
            {"attempt":1,"durationSeconds":130.444205,"completedAt":"2026-10-23T16:41:56Z"},
            {"attempt":2,"durationSeconds":131.71447,"completedAt":"2026-10-23T16:48:56Z"},
        ]}]}
    result=finalizer.stage_attempt_timings(job)
    assert result["lastSuccessfulAttemptSeconds"]==131.71447
    assert result["failedAttemptSeconds"]==130.444205
    assert len(result["attempts"])==2
    calls=[
        {"startedAtUtc":"2026-10-23T16:00:00Z","finishedAtUtc":"2026-10-23T16:04:00Z","durationSeconds":240.},
        {"startedAtUtc":"2026-10-23T16:08:00Z","finishedAtUtc":"2026-10-23T16:11:00Z","durationSeconds":180.},
    ]
    summary=finalizer.chain_timing_summary([result],calls)
    assert summary["totalRunInvocationSeconds"]==420.
    assert summary["wallSpanSeconds"]==660.
    assert summary["successfulStepSeconds"]==131.71447
    assert summary["failedAttemptSeconds"]==130.444205


def test_incomplete_attempt_timing_is_not_reported_as_zero(finalizer):
    job={"status":"succeeded","steps":[{"status":"succeeded","attemptCount":1,
        "attempts":[{"durationSeconds":None,"completedAt":"2026-10-23T16:00:00Z"}]}]}
    with pytest.raises(ValueError,match="计时缺失"):
        finalizer.stage_attempt_timings(job)


def test_scanner_full_token_requires_matching_source_filename(finalizer):
    tool={"TargetModuleToken":"FL9A24D063AI00", "TargetModuleSourcePath":"D:/parts/FL9A24D063AI00.001.SLDASM"}
    assert finalizer.target_alias_matches("AI00",tool)
    assert not finalizer.target_alias_matches("SM00",tool)
    assert not finalizer.target_alias_matches("AI00",{**tool,"TargetModuleSourcePath":"D:/parts/other-AI00.001.SLDASM"})


def test_parameter_comparison_is_recomputed_and_stale_cached_pass_is_rejected(finalizer,monkeypatch,tmp_path):
    from demo_backend.datum_chain_verification import compare_cad_states
    identity=[1.,0.,0.,0.,1.,0.,0.,0.,1.,0.,0.,0.,1.,0.,0.,0.]
    roles=("LONGITUDINAL","LATERAL","SUPPORT")
    old_names={r:"MCP_GRAPH_OLD_"+r for r in roles}
    new_names={r:"MCP_GRAPH_NEW_"+r for r in roles}
    before={"success":True,"observed":{"readOnly":True,"components":[
        {"sourcePath":f"D:/cad/{token}.001.SLDASM","transform":identity[:],"configuration":"Default", "solvingState":0,
         "constrainedStatus":3,"isFixed":token=="AA00"} for token in ("AA00","GN00")],
        "allTopLevelMates":[{"name":old_names[r],"mateType":0 if r=="SUPPORT" else 5,"alignment":0,
                             "isSuppressed":False,"errorCode":0,"dimensionSystemValue":value}
                            for r,value in zip(roles,(.354,.2535,None))]}}
    after=copy.deepcopy(before)
    after["observed"]["components"][1]["transform"][9]=.01
    for mate,role in zip(after["observed"]["allTopLevelMates"],roles):
        mate["name"]=new_names[role]
    after["observed"]["allTopLevelMates"][0]["dimensionSystemValue"]=.364
    recorded=compare_cad_states(before,after,base_token="AA00",moved_token="GN00",
        expected_displacement_meters=[.01,0,0],mate_name_map={old_names[r]:new_names[r] for r in roles},
        expected_parameter_changes={old_names["LONGITUDINAL"]:[.354,.364]})
    def graph(prefix,distance):
        return {"Mates":[{"MateName":prefix+"_"+r,"ModuleTokens":["GN00","AA00"],"Distance":v,
                          "MateType":0 if r=="SUPPORT" else 5,"Alignment":0,"Endpoints":[]}
                         for r,v in zip(roles,(distance,.2535,None))]}
    source=tmp_path / "source.SLDASM"
    cad={"sourceAssemblyPath":str(source),"sourceAssemblySha256Before":"hash","sourceAssemblySha256After":"hash","sourceAssemblyUnchanged":True}
    def read(path):
        if Path(path).name=="chain.json": return {"stages":[{"stageId":"s03-bd00"},{"stageId":"s04-gn00"}]}
        if Path(path).name=="envelope.json": return {"cadResultPath":"default-cad.json"}
        if Path(path).name=="comparison.json": return recorded
        pytest.fail(f"unexpected read {path}")
    monkeypatch.setattr(finalizer,"read",read)
    monkeypatch.setattr(finalizer,"sha",lambda path:"hash")
    monkeypatch.setattr(finalizer,"verified_closure",lambda *args:{"finalAssemblyPath":str(source),"finalAssemblySha256":"hash",
        "executionEnvelopePath":"envelope.json","closureDigest":"closure"})
    monkeypatch.setattr(finalizer,"verified_cad",lambda path:(cad,graph("OLD",.354)) if str(path)=="default-cad.json" else (cad,graph("NEW",.364)))
    monkeypatch.setattr(finalizer,"verified_state",lambda path,cad: before if Path(path).name.startswith("default") else after)
    assert finalizer.compare_parameter_change()["success"] is True
    after["observed"]["components"][1]["transform"][9]=.02
    with pytest.raises(ValueError,match="重新计算结果不一致"):
        finalizer.compare_parameter_change()
