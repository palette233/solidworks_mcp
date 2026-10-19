from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from demo_backend.global_cad_manifest_orchestrator import (
    GlobalCadManifestOrchestrationError,
    _packet_module_token,
    build_manifest_job_plan,
    manifest_cad_step_runner,
    manifest_job_status_view,
    run_manifest_job,
    validate_seed_evidence,
    write_manifest_job_artifacts,
)
from demo_backend.semantic_assembly_jobs import AssemblyJobExecutor, DurableAssemblyJobStore


WORKSPACE = Path(__file__).resolve().parents[3]
MANIFEST = (
    WORKSPACE
    / "demo/global_assembly_contexts/project05-full-static-graph-v1.cad-transaction-manifest.json"
)
PROJECT01_MANIFEST = (
    WORKSPACE
    / "demo/global_assembly_contexts/"
    "project01-cross-family-relation-v2-v1.cad-transaction-manifest.json"
)
PROJECT02_VERIFY_MANIFEST = (
    WORKSPACE
    / "demo/global_assembly_contexts/"
    "project02-full-static-graph-spacing-validation-v2.cad-transaction-manifest.json"
)
PROJECT05_V7_RELEASED_MANIFEST = (
    WORKSPACE
    / "demo/global_assembly_contexts/project05-a000-d000-v7-driving-v1/"
    "cad-transaction-manifest.json"
)
PROJECT03_V13_RELEASED_MANIFEST = (
    WORKSPACE
    / "demo/global_assembly_contexts/project03-aa00-ae00-ad00-ai00-v13-driving-v1/"
    "cad-transaction-manifest.json"
)
PROJECT02_A700_FALLBACK_MANIFEST = (
    WORKSPACE
    / "demo/global_assembly_contexts/"
    "project02-explicit-a700-fallback-v14.cad-transaction-manifest.json"
)


def _fake_command(command, **kwargs):
    output = Path(command[command.index("--output") + 1])
    run_dir = Path(command[command.index("--run-dir") + 1])
    packet_id = command[3]
    manifest = json.loads(Path(command[2]).read_text(encoding="utf-8-sig"))
    packet = next(row for row in manifest["packets"] if row["packetId"] == packet_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    output.write_bytes(packet_id.encode())
    envelope = {
        "schemaVersion": "global-cad-packet-execution/v1",
        "success": True,
        "packetId": packet_id,
        "packetDigest": packet["packetDigest"],
        "sourceAssemblyUnchanged": True,
        "executionSourceUnchanged": True,
        "outputAssemblyPath": str(output),
        "collisionStatus": "not_evaluated",
    }
    (run_dir / "execution-envelope.json").write_text(
        json.dumps(envelope), encoding="utf-8"
    )
    if packet.get("executionStrategy") == "calibrated_static_snapshot_insert":
        (run_dir / "cad-result.json").write_text(
            json.dumps(
                {
                    "success": True,
                    "durationSeconds": 1.0,
                    "toolResult": {
                        "TargetCaseAnchored": True,
                        "CaseAnchorPoseMatch": True,
                        "RequestedTargetLeafPoseAnchorCount": 2,
                        "AppliedTargetLeafPoseAnchorCount": 2,
                        "TargetLeafPoseAnchorComparison": {"Stable": True},
                        "TargetConstraintStateAccepted": True,
                        "ReopenedMateParametersMatch": True,
                    },
                }
            ),
            encoding="utf-8",
        )
    return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")


def test_cross_project_slot_provenance_does_not_erase_unique_target_alias():
    packet = {
        "packetId": "packet-cross-project",
        "operation": "INSERT_AND_CONNECT",
        "targetProjectAliases": [
            {"projectId": "project03", "moduleToken": "AH00"}
        ],
        "connections": [
            {"templateEvidenceSource": {"projectId": "project02"}}
        ],
    }

    assert _packet_module_token(packet) == "AH00"


def test_calibrated_fallback_step_keeps_nonportable_boundary_and_hard_evidence(
    tmp_path: Path,
):
    plan = build_manifest_job_plan(
        WORKSPACE,
        PROJECT02_A700_FALLBACK_MANIFEST,
        start_order=4,
        packet_limit=1,
    )
    step = plan["steps"][0]
    assert step["executionStrategy"] == "calibrated_static_snapshot_insert"
    assert step["requestedDrivingMateCount"] == 0
    assert step["sourceMateProvenanceCount"] == 6
    assert step["drivingExecutionOverride"]["portable"] is False

    seed = tmp_path / "packet-003.SLDASM"
    seed.write_bytes(b"verified-upstream-checkpoint")
    seed_evidence = tmp_path / "seed-evidence.json"
    seed_evidence.write_text(
        json.dumps(
            {
                "schemaVersion": "global-cad-packet-execution/v1",
                "success": True,
                "packetId": plan["expectedSeed"]["packetId"],
                "packetDigest": plan["expectedSeed"]["packetDigest"],
                "outputAssemblyPath": str(seed.resolve()),
                "outputAssemblySha256": hashlib.sha256(seed.read_bytes()).hexdigest(),
            }
        ),
        encoding="utf-8",
    )
    binding = validate_seed_evidence(plan, seed, seed_evidence)
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    job = store.create(plan, execution_mode="generic_cad_manifest")
    store.seed_verified_checkpoint(
        job["jobId"],
        step_id=binding["packetId"],
        module_token=binding["moduleToken"],
        assembly_path=seed,
        evidence_path=seed_evidence,
    )
    result = AssemblyJobExecutor(
        store,
        manifest_cad_step_runner(WORKSPACE, store, command_runner=_fake_command),
    ).run(job["jobId"])

    assert result["status"] == "succeeded"
    evidence = json.loads(
        (
            store._dir(job["jobId"])
            / "packet-runs/packet-004-attempt-01/orchestration-step-evidence.json"
        ).read_text(encoding="utf-8")
    )
    assert evidence["calibratedFallbackVerification"]["portable"] is False
    assert evidence["calibratedFallbackVerification"][
        "internalLeafPoseAnchorsStable"
    ] is True


def test_plan_binds_contiguous_manifest_slice():
    plan = build_manifest_job_plan(WORKSPACE, MANIFEST, start_order=3, packet_limit=3)
    assert plan["projectId"] == "project05"
    assert [step["packetId"] for step in plan["steps"]] == [
        "packet-003",
        "packet-004",
        "packet-005",
    ]
    assert plan["requiresSeedCheckpoint"] is True
    assert plan["expectedSeed"]["packetId"] == "packet-002"
    assert plan["collisionStatus"] == "not_evaluated"


def test_released_manifest_plan_and_step_evidence_keep_release_binding(tmp_path: Path):
    plan = build_manifest_job_plan(WORKSPACE, PROJECT05_V7_RELEASED_MANIFEST)
    assert plan["releaseAuthority"]["status"] == "verified"
    assert plan["relationReleaseBinding"]["releaseId"] == (
        "relation-v7-project05-driving-independent-20261011"
    )

    store = DurableAssemblyJobStore(tmp_path / "jobs")
    job = store.create(plan, execution_mode="generic_cad_manifest")
    result = AssemblyJobExecutor(
        store,
        manifest_cad_step_runner(WORKSPACE, store, command_runner=_fake_command),
    ).run(job["jobId"])
    assert result["status"] == "succeeded"
    evidence_path = (
        store._dir(job["jobId"])
        / "packet-runs/packet-001-attempt-01/orchestration-step-evidence.json"
    )
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["releaseAuthority"]["status"] == "verified"
    assert evidence["relationReleaseBinding"] == plan["relationReleaseBinding"]


def test_manifest_job_automatically_materializes_command_audit_and_timing(
    tmp_path: Path,
):
    plan = build_manifest_job_plan(WORKSPACE, PROJECT05_V7_RELEASED_MANIFEST)
    assert plan["commandAudit"]["status"] == "complete"
    assert plan["commandAudit"]["payload"]["jobSelection"][
        "selectedPacketIds"
    ] == ["packet-001"]

    store = DurableAssemblyJobStore(tmp_path / "jobs")
    job = store.create(plan, execution_mode="generic_cad_manifest")
    created = write_manifest_job_artifacts(store, job["jobId"])
    assert Path(str(created["commandAuditPath"])).is_file()
    assert Path(str(created["timingReportPath"])).is_file()
    assert Path(str(created["userSummaryPath"])).is_file()
    assert Path(str(created["userSummaryMarkdownPath"])).is_file()

    result = run_manifest_job(
        store,
        job["jobId"],
        manifest_cad_step_runner(WORKSPACE, store, command_runner=_fake_command),
    )
    assert result["status"] == "succeeded"
    timing = json.loads(
        (store._dir(job["jobId"]) / "timing-report.json").read_text(
            encoding="utf-8"
        )
    )
    audit = json.loads(
        (store._dir(job["jobId"]) / "command-audit.json").read_text(
            encoding="utf-8"
        )
    )
    assert timing["status"] == "succeeded"
    assert timing["steps"][0]["status"] == "succeeded"
    assert audit["schemaVersion"] == "global-command-audit/v1"
    view = manifest_job_status_view(store, job["jobId"])
    assert view["commandAudit"]["status"] == "complete"
    assert view["timingReport"]["status"] == "available"
    assert view["userSummary"]["path"].endswith("user-summary.json")
    assert view["userSummary"]["markdownPath"].endswith("user-summary.md")


def test_blocked_manifest_is_rejected():
    blocked = (
        WORKSPACE
        / "demo/global_assembly_contexts/project02-full-static-graph-v1.cad-transaction-manifest.json"
    )
    with pytest.raises(GlobalCadManifestOrchestrationError, match="尚未满足"):
        build_manifest_job_plan(WORKSPACE, blocked)


def test_pause_resume_and_automatic_checkpoint_chaining(tmp_path: Path):
    plan = build_manifest_job_plan(WORKSPACE, MANIFEST, packet_limit=4)
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    job = store.create(plan, execution_mode="generic_cad_manifest")
    pausing = manifest_cad_step_runner(
        WORKSPACE,
        store,
        pause_after_packet="packet-002",
        command_runner=_fake_command,
    )
    paused = AssemblyJobExecutor(store, pausing).run(job["jobId"])
    assert paused["status"] == "paused"
    assert [step["status"] for step in paused["steps"]] == [
        "succeeded",
        "succeeded",
        "pending",
        "pending",
    ]
    assert paused["lastCommittedCheckpoint"]["packetId"] == "packet-002"

    store.prepare_resume(job["jobId"])
    resumed = AssemblyJobExecutor(
        store,
        manifest_cad_step_runner(WORKSPACE, store, command_runner=_fake_command),
    ).run(job["jobId"])
    assert resumed["status"] == "succeeded"
    assert all(step["status"] == "succeeded" for step in resumed["steps"])
    assert resumed["lastCommittedCheckpoint"]["packetId"] == "packet-004"
    third_plan = json.loads(
        (
            store._dir(job["jobId"])
            / "packet-runs/packet-003-attempt-01/orchestration-step-evidence.json"
        ).read_text(encoding="utf-8")
    )
    assert third_plan["inputCheckpointPath"].endswith("packet-002.SLDASM")


def test_failure_rolls_back_and_resume_retries_only_failed_tail(tmp_path: Path):
    plan = build_manifest_job_plan(WORKSPACE, MANIFEST, packet_limit=4)
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    job = store.create(plan, execution_mode="generic_cad_manifest", idempotency_key="failure")
    failed = AssemblyJobExecutor(
        store,
        manifest_cad_step_runner(
            WORKSPACE,
            store,
            fail_before_packet="packet-003",
            command_runner=_fake_command,
        ),
    ).run(job["jobId"])
    assert failed["status"] == "failed"
    assert failed["rollback"]["checkpoint"]["packetId"] == "packet-002"
    assert failed["steps"][0]["attemptCount"] == 1
    assert failed["steps"][1]["attemptCount"] == 1
    assert failed["steps"][2]["attemptCount"] == 1

    store.prepare_resume(job["jobId"])
    recovered = AssemblyJobExecutor(
        store,
        manifest_cad_step_runner(WORKSPACE, store, command_runner=_fake_command),
    ).run(job["jobId"])
    assert recovered["status"] == "succeeded"
    assert recovered["steps"][0]["attemptCount"] == 1
    assert recovered["steps"][1]["attemptCount"] == 1
    assert recovered["steps"][2]["attemptCount"] == 2
    assert recovered["steps"][3]["attemptCount"] == 1


def test_status_view_exposes_progress_failure_and_last_checkpoint(tmp_path: Path):
    plan = build_manifest_job_plan(WORKSPACE, MANIFEST, packet_limit=3)
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    job = store.create(plan, execution_mode="generic_cad_manifest")
    failed = AssemblyJobExecutor(
        store,
        manifest_cad_step_runner(
            WORKSPACE,
            store,
            fail_before_packet="packet-003",
            command_runner=_fake_command,
        ),
    ).run(job["jobId"])
    view = manifest_job_status_view(store, failed["jobId"])
    assert view["status"] == "failed"
    assert view["progress"] == {
        "completedSteps": 2,
        "totalSteps": 3,
        "currentStepId": None,
        "nextStepId": None,
    }
    assert view["failure"]["stepId"] == "packet-003"
    assert "诊断故障注入" in view["failure"]["reason"]
    assert view["failure"]["userExplanation"]["reasonCode"] == (
        "CAD_EXECUTION_FAILED"
    )
    assert view["failure"]["userExplanation"]["cadLaunchDecision"] == (
        "stopped_after_failure"
    )
    assert view["lastCheckpoint"]["packetId"] == "packet-002"
    assert view["collisionStatus"] == "not_evaluated"
    assert any(event["eventType"] == "step-failed" for event in view["events"])


def test_manifest_change_is_detected_before_packet_execution(tmp_path: Path):
    manifest_copy = tmp_path / "manifest.json"
    manifest_copy.write_bytes(MANIFEST.read_bytes())
    # Plan construction requires a workspace-contained path, so use the temp
    # directory itself as the workspace for this isolated mutation test.
    plan = build_manifest_job_plan(tmp_path, manifest_copy, packet_limit=1)
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    job = store.create(plan, execution_mode="generic_cad_manifest", idempotency_key="mutated")
    manifest_copy.write_text(manifest_copy.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    result = AssemblyJobExecutor(
        store,
        manifest_cad_step_runner(tmp_path, store, command_runner=_fake_command),
    ).run(job["jobId"])
    assert result["status"] == "failed"
    assert "发生变化" in result["error"]


def test_project01_combined_connection_packet_pause_resume_and_rollback(tmp_path: Path):
    plan = build_manifest_job_plan(WORKSPACE, PROJECT01_MANIFEST)
    assert plan["stepCount"] == 2
    assert plan["steps"][1]["operation"] == "INSERT_AND_CONNECT"
    assert plan["steps"][1]["connectionCount"] == 2
    assert plan["steps"][1]["requestedMateCount"] == 3
    assert plan["steps"][1]["requestedDrivingMateCount"] == 3
    assert plan["steps"][1]["requestedValidationRelationCount"] == 0
    assert plan["steps"][1]["requestedRelationCount"] == 3

    store = DurableAssemblyJobStore(tmp_path / "jobs")
    job = store.create(
        plan,
        execution_mode="generic_cad_manifest",
        idempotency_key="project01-combined-packet",
    )
    failed = AssemblyJobExecutor(
        store,
        manifest_cad_step_runner(
            WORKSPACE,
            store,
            fail_before_packet="packet-002",
            command_runner=_fake_command,
        ),
    ).run(job["jobId"])
    assert failed["status"] == "failed"
    assert failed["rollback"]["checkpoint"]["packetId"] == "packet-001"

    store.prepare_resume(job["jobId"])
    recovered = AssemblyJobExecutor(
        store,
        manifest_cad_step_runner(WORKSPACE, store, command_runner=_fake_command),
    ).run(job["jobId"])
    assert recovered["status"] == "succeeded"
    assert recovered["steps"][0]["attemptCount"] == 1
    assert recovered["steps"][1]["attemptCount"] == 2
    assert recovered["lastCommittedCheckpoint"]["packetId"] == "packet-002"


def test_project03_ai00_plan_separates_driving_and_validation_relations():
    plan = build_manifest_job_plan(WORKSPACE, PROJECT03_V13_RELEASED_MANIFEST)
    ai00 = plan["steps"][2]

    assert ai00["moduleToken"] == "AI00"
    assert ai00["requestedMateCount"] == 3
    assert ai00["requestedDrivingMateCount"] == 3
    assert ai00["requestedValidationRelationCount"] == 2
    assert ai00["requestedRelationCount"] == 5


def test_verify_relation_packet_can_be_bound_as_a_durable_resume_slice(tmp_path: Path):
    plan = build_manifest_job_plan(
        WORKSPACE,
        PROJECT02_VERIFY_MANIFEST,
        start_order=10,
        packet_limit=1,
    )

    assert plan["stepCount"] == 1
    assert plan["projectId"] == "project02"
    assert plan["steps"][0]["operation"] == "VERIFY_RELATION"
    assert plan["steps"][0]["moduleToken"] == "A500"
    assert plan["steps"][0]["relationModuleTokens"] == ["A500", "A700"]
    assert plan["expectedSeed"]["packetId"] == "packet-009"

    seed = tmp_path / "ten-modules.SLDASM"
    seed.write_bytes(b"verified-ten-module-checkpoint")
    seed_evidence = tmp_path / "seed-evidence.json"
    seed_evidence.write_text(
        json.dumps(
            {
                "schemaVersion": "global-cad-packet-execution/v1",
                "success": True,
                "packetId": plan["expectedSeed"]["packetId"],
                "packetDigest": plan["expectedSeed"]["packetDigest"],
                "outputAssemblyPath": str(seed.resolve()),
                "outputAssemblySha256": hashlib.sha256(seed.read_bytes()).hexdigest(),
            }
        ),
        encoding="utf-8",
    )
    seed_binding = validate_seed_evidence(plan, seed, seed_evidence)
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    job = store.create(plan, execution_mode="generic_cad_manifest")
    store.seed_verified_checkpoint(
        job["jobId"],
        step_id=seed_binding["packetId"],
        module_token=seed_binding["moduleToken"],
        assembly_path=seed,
        evidence_path=seed_evidence,
    )

    failed = AssemblyJobExecutor(
        store,
        manifest_cad_step_runner(
            WORKSPACE,
            store,
            fail_before_packet="packet-010",
            command_runner=_fake_command,
        ),
    ).run(job["jobId"])
    assert failed["status"] == "failed"
    assert failed["rollback"]["checkpoint"]["stepId"] == "packet-009"

    store.prepare_resume(job["jobId"])
    recovered = AssemblyJobExecutor(
        store,
        manifest_cad_step_runner(WORKSPACE, store, command_runner=_fake_command),
    ).run(job["jobId"])
    assert recovered["status"] == "succeeded"
    assert recovered["steps"][0]["attemptCount"] == 2
    assert recovered["lastCommittedCheckpoint"]["packetId"] == "packet-010"
