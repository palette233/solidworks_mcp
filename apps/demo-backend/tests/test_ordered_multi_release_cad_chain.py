from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from demo_backend import global_cad_manifest_orchestrator as orchestrator
from demo_backend import multi_release_cad_chain as chain_module
from demo_backend.semantic_assembly_jobs import DurableAssemblyJobStore


def _write(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _authority(_workspace, manifest, **_kwargs):
    return {
        "status": "verified", "binding": manifest["relationReleaseBinding"],
        "authorizedDrivingTemplateIds": ["three-plane"],
        "usedDrivingTemplateIds": ["three-plane"],
    }


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(chain_module, "validate_cad_manifest_release_authority", _authority)
    monkeypatch.setattr(orchestrator, "validate_cad_manifest_release_authority", _authority)
    stages = []
    for index, (token, mode) in enumerate([
        ("SS00", "direct_installation"), ("GN00", "datum_placement_demo"),
        ("AI00", "direct_installation"), ("BD00", "direct_installation"),
        ("P000", "datum_placement_demo"),
    ]):
        packet = {
            "packetId": "packet-001", "order": 1,
            "status": "ready_for_executor_implementation",
            "targetProjectAliases": [{"projectId": "project01", "moduleToken": token}],
            "cumulativeInput": {"kind": "base_module_source", "instanceId": "aa00"},
            "operation": "INSERT_AND_CONNECT", "connections": [],
        }
        packet["packetDigest"] = chain_module._digest(packet)
        manifest = {
            "schemaVersion": "global-cad-transaction-manifest/v1",
            "status": "ready_for_generic_executor_implementation",
            "contextId": f"ordered-{token}", "packetCount": 1, "packets": [packet],
            "relationReleaseBinding": {
                "releaseId": f"release-{token}", "releaseDigest": token,
                "releaseMetadata": {"relationExecutionMode": mode},
            },
        }
        manifest["manifestDigest"] = chain_module._digest(manifest)
        path = _write(tmp_path / "input" / f"{token}.json", manifest)
        stages.append({"stageId": f"stage-{index + 1}-{token}", "manifestPath": str(path)})
    chain = chain_module.build_multi_release_cad_chain(
        tmp_path, chain_id="ordered-six-module-chain", stages=stages,
    )
    return tmp_path, chain, DurableAssemblyJobStore(tmp_path / "jobs")


def _fake_command(command, **kwargs):
    output = Path(command[command.index("--output") + 1])
    run_dir = Path(command[command.index("--run-dir") + 1])
    manifest = json.loads(Path(command[2]).read_text(encoding="utf-8"))
    packet = manifest["packets"][0]
    prior = None
    if "--input-checkpoint" in command:
        prior = Path(command[command.index("--input-checkpoint") + 1]).read_bytes()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes((prior or b"AA00") + b"|" + manifest["contextId"].encode())
    _write(run_dir / "execution-envelope.json", {
        "schemaVersion": "global-cad-packet-execution/v1", "success": True,
        "packetId": packet["packetId"], "packetDigest": packet["packetDigest"],
        "sourceAssemblyUnchanged": True, "executionSourceUnchanged": True,
        "outputAssemblyPath": str(output),
        "outputAssemblySha256": hashlib.sha256(output.read_bytes()).hexdigest(),
    })
    return subprocess.CompletedProcess(command, 0, stdout="simulated-cad", stderr="")


def _prepare(root, chain, store, index, previous=None):
    return chain_module.prepare_multi_release_stage_job(
        root, chain, chain["stages"][index]["stageId"], store, root / "prepared",
        previous_closure_path=previous,
    )


def _run(root, chain, store, index, job, **kwargs):
    runner = orchestrator.manifest_cad_step_runner(root, store, command_runner=_fake_command, **kwargs)
    return orchestrator.run_manifest_job(
        store, job["jobId"], chain_module.guard_multi_release_stage_runner(
            root, chain, chain["stages"][index]["stageId"], store, runner,
        ),
    )


def _closure(root, chain, store, index, job):
    stage_id = chain["stages"][index]["stageId"]
    return _write(root / "closures" / f"{stage_id}.json", chain_module.build_multi_release_stage_closure(
        root, chain, stage_id, store, job["jobId"],
    ))


def test_ordered_mixed_stages_reuse_durable_runner_and_allow_datum_in_middle(setup):
    root, chain, store = setup
    assert chain["stageCount"] == 5
    assert chain["packetCount"] == 5
    assert chain["stages"][1]["relationExecutionMode"] == "datum_placement_demo"
    previous = None
    for index in range(5):
        job = _prepare(root, chain, store, index, previous)
        same = _prepare(root, chain, store, index, previous)
        assert job["jobId"] == same["jobId"]
        job = _run(root, chain, store, index, job)
        assert job["status"] == "succeeded"
        previous = _closure(root, chain, store, index, job)
        assert job["steps"][0]["attemptCount"] == 1
    contents = Path(job["lastCommittedCheckpoint"]["assemblyPath"]).read_text()
    assert contents == "AA00|ordered-SS00|ordered-GN00|ordered-AI00|ordered-BD00|ordered-P000"


def test_failed_stage_does_not_advance_checkpoint_resume_retries_only_failed_packet(setup):
    root, chain, store = setup
    first = _run(root, chain, store, 0, _prepare(root, chain, store, 0))
    prior = _closure(root, chain, store, 0, first)
    second = _prepare(root, chain, store, 1, prior)
    seed = copy.deepcopy(second["lastCommittedCheckpoint"])
    failed = _run(root, chain, store, 1, second, fail_before_packet="packet-001")
    assert failed["status"] == "failed"
    assert failed["lastCommittedCheckpoint"] == seed
    assert failed["rollback"]["checkpoint"] == seed
    with pytest.raises(chain_module.MultiReleaseCadChainError, match="未成功"):
        _closure(root, chain, store, 1, failed)
    store.prepare_resume(second["jobId"])
    resumed = _run(root, chain, store, 1, second)
    assert resumed["status"] == "succeeded"
    assert resumed["steps"][0]["attemptCount"] == 2
    assert store.load(first["jobId"])["steps"][0]["attemptCount"] == 1
    assert "attempt-02" in resumed["lastCommittedCheckpoint"]["assemblyPath"]


def test_source_hash_is_checked_before_prepare_and_again_before_execution(setup):
    root, chain, store = setup
    first = _run(root, chain, store, 0, _prepare(root, chain, store, 0))
    prior = _closure(root, chain, store, 0, first)
    second = _prepare(root, chain, store, 1, prior)
    source = Path(first["lastCommittedCheckpoint"]["assemblyPath"])
    source.write_bytes(b"modified-after-prepare")
    with pytest.raises(chain_module.MultiReleaseCadChainError, match="摘要发生变化"):
        _prepare(root, chain, store, 1, prior)
    failed = _run(root, chain, store, 1, second)
    assert failed["status"] == "failed"
    assert "摘要发生变化" in failed["error"]
    assert not (store._dir(second["jobId"]) / "packet-runs").exists()


def test_existing_attempt_output_is_never_overwritten(setup):
    root, chain, store = setup
    job = _prepare(root, chain, store, 0)
    old = store._dir(job["jobId"]) / "packet-runs/packet-001-attempt-01/old.SLDASM"
    old.parent.mkdir(parents=True)
    old.write_bytes(b"preserve")
    failed = _run(root, chain, store, 0, job)
    assert failed["status"] == "failed"
    assert "拒绝覆盖" in failed["error"]
    assert old.read_bytes() == b"preserve"


def test_changed_parameters_invalidate_ordered_chain_plan(setup):
    root, chain, store = setup
    path = root / chain["stages"][1]["manifestPath"]
    changed = json.loads(path.read_text())
    changed["parameterOverride"] = {"offsetMm": 60}
    changed["manifestDigest"] = chain_module._digest({
        key: value for key, value in changed.items() if key != "manifestDigest"
    })
    _write(path, changed)
    with pytest.raises(chain_module.MultiReleaseCadChainError, match="已变化"):
        chain_module.validate_multi_release_cad_chain(root, chain)


def test_stage_id_duplicate_and_unclosed_predecessor_are_rejected(setup):
    root, chain, store = setup
    with pytest.raises(chain_module.MultiReleaseCadChainError, match="前置闭合"):
        _prepare(root, chain, store, 1)
    specs = [{"stageId": "same", "manifestPath": row["manifestPath"]} for row in chain["stages"]]
    with pytest.raises(chain_module.MultiReleaseCadChainError, match="唯一"):
        chain_module.build_multi_release_cad_chain(root, chain_id="bad", stages=specs)


def test_reordered_chain_is_data_not_a_fixed_direct_then_demo_sequence(setup):
    root, chain, store = setup
    specs = [{"stageId": row["stageId"], "manifestPath": row["manifestPath"]}
             for row in [chain["stages"][1], chain["stages"][4], chain["stages"][3],
                         chain["stages"][0], chain["stages"][2]]]
    reordered = chain_module.build_multi_release_cad_chain(root, chain_id="reordered", stages=specs)
    prior = None
    for index in range(5):
        job = _run(root, reordered, store, index, _prepare(root, reordered, store, index, prior))
        assert job["status"] == "succeeded"
        prior = _closure(root, reordered, store, index, job)
    assert Path(job["lastCommittedCheckpoint"]["assemblyPath"]).read_text() == (
        "AA00|ordered-GN00|ordered-P000|ordered-BD00|ordered-SS00|ordered-AI00"
    )


def test_modified_output_cannot_be_published_as_stage_closure(setup):
    root, chain, store = setup
    job = _run(root, chain, store, 0, _prepare(root, chain, store, 0))
    Path(job["lastCommittedCheckpoint"]["assemblyPath"]).write_bytes(b"not-cad-output")
    with pytest.raises(chain_module.MultiReleaseCadChainError, match="真实执行证据不一致"):
        _closure(root, chain, store, 0, job)


def test_source_mutation_during_runner_is_rejected_without_committing(setup):
    root, chain, store = setup
    first = _run(root, chain, store, 0, _prepare(root, chain, store, 0))
    previous = _closure(root, chain, store, 0, first)
    job = _prepare(root, chain, store, 1, previous)

    def bad_runner(_job, _step, source):
        source.write_bytes(b"unexpected-edit")
        return {"accepted": True, "assemblyPath": str(source)}

    failed = orchestrator.run_manifest_job(
        store, job["jobId"], chain_module.guard_multi_release_stage_runner(
            root, chain, chain["stages"][1]["stageId"], store, bad_runner,
        ),
    )
    assert failed["status"] == "failed"
    assert "修改了前置检查点" in failed["error"]
    assert failed["lastCommittedCheckpoint"] == job["lastCommittedCheckpoint"]


def _add_real_audit_sources(root, chain):
    """Small valid JSON documents, read by the real command-audit builder."""
    path = root / chain["stages"][0]["manifestPath"]
    manifest = json.loads(path.read_text())
    context_id = manifest["contextId"]
    catalog = {
        "schemaVersion": "global-module-catalog/v1",
        "moduleDefinitions": [
            {"moduleDefinitionId": "base", "category": "frame"},
            {"moduleDefinitionId": "transport", "category": "transport"},
        ], "semanticPorts": [],
    }
    catalog["catalogDigest"] = chain_module._digest(catalog)
    _write(root / "source-catalog.json", catalog)
    context = {
        "schemaVersion": "global-assembly-context/v1", "contextId": context_id,
        "catalogDigest": catalog["catalogDigest"], "revision": 2,
        "instances": [
            {"instanceId": "base", "moduleDefinitionId": "base", "placementStatus": "base_context_unlocated"},
            {"instanceId": "transport", "moduleDefinitionId": "transport"},
        ],
        "connections": [{"connectionId": "transport-on-base", "instanceAId": "base", "instanceBId": "transport"}],
        "history": [
            {"operation": "add_base_instance", "requirement": "建立设备基座"},
            {"operation": "add_module", "requirement": "在基座上安装产品传输", "connectionId": "transport-on-base"},
        ],
    }
    context["contextDigest"] = chain_module._digest(context)
    context_path = _write(path.with_name(f"{context_id}.json"), context)
    _write(path.with_name("transaction-dag.json"), {
        "contextId": context_id, "contextDigest": context["contextDigest"],
        "catalogDigest": catalog["catalogDigest"],
        "steps": [{"stepId": "step-1", "connections": [{"connectionId": "transport-on-base"}]}],
    })
    manifest["relationReleaseBinding"]["releasedCatalogRelativePath"] = "source-catalog.json"
    manifest["contextDigest"] = context["contextDigest"]
    manifest["catalogDigest"] = catalog["catalogDigest"]
    packet = manifest["packets"][0]
    packet["connections"] = [{"connectionId": "transport-on-base"}]
    packet["packetDigest"] = chain_module._digest({key: value for key, value in packet.items() if key != "packetDigest"})
    manifest["manifestDigest"] = chain_module._digest({key: value for key, value in manifest.items() if key != "manifestDigest"})
    _write(path, manifest)
    report_path = _write(path.with_name(f"{context_id}.natural-language-compilation.json"), {
        "success": True, "contextId": context_id, "manifestPath": str(path.resolve()),
        "requirements": ["建立设备基座", "在基座上安装产品传输"],
        "originalRequirements": ["建立设备基座", "在基座上安装产品传输"],
        "timingSeconds": {"totalSeconds": 0.4},
    })
    chain = chain_module.build_multi_release_cad_chain(root, chain_id=chain["chainId"], stages=[{
        "stageId": chain["stages"][0]["stageId"], "manifestPath": str(path),
    }])
    return chain, context_path, report_path


def test_source_nl_audit_is_rebuilt_from_real_context_dag_and_kept_in_job(setup):
    root, chain, store = setup
    chain, context_path, report_path = _add_real_audit_sources(root, chain)
    job = _prepare(root, chain, store, 0)
    audit = job["plan"]["sourceCommandAudit"]
    assert audit["status"] == "complete"
    assert audit["payload"]["mappedCommandCount"] == 2
    assert audit["payload"]["commands"][1]["requirement"] == "在基座上安装产品传输"
    assert audit["payload"]["commands"][1]["cadPacketIds"] == ["packet-001"]
    assert audit["sources"]["contextPath"] == str(context_path.resolve())
    assert audit["naturalLanguageCompilation"]["path"] == str(report_path.resolve())
    assert audit["naturalLanguageCompilation"]["timingSeconds"]["totalSeconds"] == 0.4
    assert json.loads((store._dir(job["jobId"]) / "source-command-audit.json").read_text(encoding="utf-8")) == audit
    assert job["plan"]["sourceCommandAuditProvenance"]["change"] == "unchanged_manifest_copy"


@pytest.mark.parametrize("source_kind", ["context", "compilation"])
def test_source_nl_audit_inputs_changed_after_prepare_block_before_cad(setup, source_kind):
    root, chain, store = setup
    chain, context_path, report_path = _add_real_audit_sources(root, chain)
    job = _prepare(root, chain, store, 0)
    path = context_path if source_kind == "context" else report_path
    path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    failed = _run(root, chain, store, 0, job)
    assert failed["status"] == "failed"
    assert "原始自然语言" in failed["error"]
    assert not (store._dir(job["jobId"]) / "packet-runs").exists()


def test_absent_source_nl_documents_stay_explicitly_unavailable(setup):
    root, chain, store = setup
    job = _prepare(root, chain, store, 0)
    audit = job["plan"]["sourceCommandAudit"]
    assert audit["status"] == "unavailable"
    assert "payload" not in audit
    assert "naturalLanguageCompilation" not in audit


@pytest.mark.parametrize("authority", [
    {"status": "legacy_unbound", "binding": {}},
    {"status": "legacy_unbound", "binding": {"releaseId": "misleading", "releaseDigest": "hash"}},
    {"status": "verified", "binding": {"releaseId": "missing-digest"}},
    {"status": "verified", "binding": {"releaseDigest": "missing-id"}},
])
def test_ordered_chain_requires_verified_immutable_release_not_legacy_authority(setup, monkeypatch, authority):
    root, chain, _ = setup
    monkeypatch.setattr(chain_module, "validate_cad_manifest_release_authority", lambda *_args, **_kwargs: authority)
    specs = [{"stageId": row["stageId"], "manifestPath": row["manifestPath"]} for row in chain["stages"]]
    with pytest.raises(chain_module.MultiReleaseCadChainError, match="已验证的不可变发布"):
        chain_module.build_multi_release_cad_chain(root, chain_id="unpublished", stages=specs)
