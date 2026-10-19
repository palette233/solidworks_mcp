from pathlib import Path
import hashlib
import json

import pytest

from demo_backend.assembly_conversation import (
    AssemblyConversationError,
    bind_direct_mate_execution,
    bind_job,
    conversation_path,
    conversation_snapshot,
    record_graph_turn,
    reset_conversation,
)


def _context(revision: int = 1) -> dict:
    return {
        "contextId": "conversation-unit",
        "revision": revision,
        "contextDigest": f"digest-{revision}",
        "updatedAt": "2026-10-09T00:00:00Z",
    }


def _preview() -> dict:
    return {
        "requirement": "然后添加扫描模组",
        "previewDigest": "preview-1",
        "proposedPatch": {
            "operation": "add_module",
            "instance": {
                "instanceId": "scanner-001",
                "moduleDefinitionId": "global/scanner/a180",
            },
            "connection": {"connectionId": "connection-001"},
        },
    }


def _job(status: str = "queued") -> dict:
    checkpoint = None
    if status == "succeeded":
        checkpoint = {
            "assemblyPath": "D:/demo/turn-1.SLDASM",
            "committedAt": "2026-10-09T00:02:00Z",
        }
    return {
        "jobId": "project02-job-unit",
        "projectId": "project02",
        "validationProfile": "demo",
        "status": status,
        "assemblyStatus": "assembled" if status == "succeeded" else "seeded",
        "collisionStatus": "not_evaluated",
        "createdAt": "2026-10-09T00:01:00Z",
        "updatedAt": "2026-10-09T00:02:00Z",
        "demoCheckpoint": checkpoint,
        "plan": {
            "contextRevision": 1,
            "executionScope": {
                "kind": "validated_continuation",
                "seedJobId": "project02-job-prior",
            },
        },
    }


def test_turn_job_and_checkpoint_are_durably_recoverable(tmp_path: Path):
    context_file = tmp_path / "context.json"
    context = _context()
    reset_conversation(context_file, context)

    first = record_graph_turn(context_file, context, _preview())
    repeated = record_graph_turn(context_file, context, _preview())
    assert len(first["turns"]) == 1
    assert len(repeated["turns"]) == 1
    assert conversation_path(context_file).is_file()

    bind_job(context_file, context, _job())
    bind_job(context_file, context, _job())
    current = _job("succeeded")
    snapshot = conversation_snapshot(
        context_file,
        context,
        lambda job_id: current,
    )

    assert snapshot["turnCount"] == 1
    assert len(snapshot["turns"][0]["jobs"]) == 1
    assert snapshot["turns"][0]["jobs"][0]["sourceJobId"] == (
        "project02-job-prior"
    )
    assert snapshot["latestSuccessfulDemo"]["jobId"] == "project02-job-unit"
    assert snapshot["latestSuccessfulDemo"]["projectId"] == "project02"
    assert snapshot["latestSuccessfulDemo"]["contextRevision"] == 1
    assert snapshot["continuationReady"] is True


def test_generic_manifest_checkpoint_is_continuable_without_collision_gate(
    tmp_path: Path,
):
    context_file = tmp_path / "context.json"
    context = _context()
    reset_conversation(context_file, context)
    record_graph_turn(context_file, context, _preview())
    job = _job("succeeded")
    job["validationProfile"] = "generic-cad-transaction-manifest-v1"
    bind_job(context_file, context, job)

    snapshot = conversation_snapshot(context_file, context, lambda _job_id: job)

    assert snapshot["continuationReady"] is True
    assert snapshot["latestSuccessfulDemo"]["jobId"] == "project02-job-unit"
    assert snapshot["latestSuccessfulDemo"]["validationProfile"] == (
        "generic-cad-transaction-manifest-v1"
    )
    assert snapshot["latestSuccessfulDemo"]["collisionStatus"] == "not_evaluated"


def test_rejected_generic_manifest_checkpoint_is_not_continuable(tmp_path: Path):
    context_file = tmp_path / "context.json"
    context = _context()
    reset_conversation(context_file, context)
    record_graph_turn(context_file, context, _preview())
    job = _job("succeeded")
    job["validationProfile"] = "generic-cad-transaction-manifest-v1"
    job["collisionStatus"] = "rejected"
    bind_job(context_file, context, job)

    snapshot = conversation_snapshot(context_file, context, lambda _job_id: job)

    assert snapshot["continuationReady"] is False
    assert snapshot["latestSuccessfulDemo"] is None


def test_legacy_job_revision_can_only_be_backfilled_by_exact_context_digest(
    tmp_path: Path,
):
    context_file = tmp_path / "context.json"
    context = _context()
    reset_conversation(context_file, context)
    record_graph_turn(context_file, context, _preview())
    job = _job("succeeded")
    job["plan"].pop("contextRevision")
    job["plan"]["contextId"] = context["contextId"]
    job["plan"]["contextDigest"] = context["contextDigest"]

    ledger = bind_job(context_file, context, job)

    assert ledger["turns"][0]["jobs"][0]["bindingRevisionSource"] == (
        "exact_context_digest_backfill"
    )

    reset_conversation(context_file, context)
    record_graph_turn(context_file, context, _preview())
    job["plan"]["contextDigest"] = "different"
    with pytest.raises(AssemblyConversationError, match="不能唯一回填"):
        bind_job(context_file, context, job)


def test_reset_removes_old_turns_without_touching_context_file(tmp_path: Path):
    context_file = tmp_path / "context.json"
    context_file.write_text("context-source", encoding="utf-8")
    context = _context()
    reset_conversation(context_file, context)
    record_graph_turn(context_file, context, _preview())

    reset = reset_conversation(context_file, {**context, "revision": 0})

    assert reset["turns"] == []
    assert context_file.read_text(encoding="utf-8") == "context-source"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_successful_direct_edit_advances_physical_continuation_checkpoint(tmp_path: Path):
    context_file = tmp_path / "context.json"
    context = _context()
    reset_conversation(context_file, context)
    record_graph_turn(context_file, context, _preview())
    source = tmp_path / "source.SLDASM"
    output = tmp_path / "output.SLDASM"
    source.write_bytes(b"source")
    output.write_bytes(b"output")
    job = _job("succeeded")
    job["demoCheckpoint"]["assemblyPath"] = str(source)
    bind_job(context_file, context, job)
    execution = {
        "schemaVersion": "context-direct-mate-edit-run/v1",
        "success": True,
        "published": True,
        "finishedAtUtc": "2026-10-09T00:03:00Z",
        "sourceAssemblyPath": str(source),
        "sourceAssemblySha256After": _digest(source),
        "outputAssemblyPath": str(output),
        "outputAssemblySha256": _digest(output),
        "effectiveGraphPath": str(tmp_path / "graph.json"),
        "effectiveGraphSha256": "graph-digest",
        "targetModuleToken": "A500",
        "preflight": {"rigidBodyDofAnalysis": {"constraintRank": 6, "residualDof": 0}},
        "toolResult": {
            "ExecutionMode": "direct_existing_component_mate_edit",
            "Reopened": True,
            "ReopenedMateParametersMatch": True,
            "ComponentSemanticsMatch": True,
            "TargetComponentReinserted": False,
            "TargetComponentExplicitlyDisplaced": False,
            "CreatedOrReplacedMateNames": ["mate-a", "mate-b", "mate-c"],
            "RemovedOrReplacedSourceMateNames": ["old-a", "old-b", "old-c"],
        },
    }
    evidence = tmp_path / "execution.json"
    evidence.write_text(json.dumps(execution), encoding="utf-8")

    ledger = bind_direct_mate_execution(
        context_file, context, execution, execution_path=evidence
    )
    snapshot = conversation_snapshot(context_file, context)

    assert len(ledger["turns"][0]["cadEdits"]) == 1
    assert snapshot["latestSuccessfulDemo"]["bindingKind"] == (
        "direct_existing_component_mate_edit"
    )
    assert snapshot["latestSuccessfulDemo"]["assemblyPath"] == str(output.resolve())
    assert snapshot["latestSuccessfulDemo"]["assemblySha256"] == _digest(output)
    assert snapshot["latestSuccessfulDemo"]["jobId"] == "project02-job-unit"
    assert snapshot["latestSuccessfulDemo"]["projectId"] == "project02"


def test_failed_direct_edit_cannot_advance_conversation(tmp_path: Path):
    context_file = tmp_path / "context.json"
    context = _context()
    reset_conversation(context_file, context)
    record_graph_turn(context_file, context, _preview())
    execution = {
        "schemaVersion": "context-direct-mate-edit-run/v1",
        "success": False,
        "published": False,
    }
    evidence = tmp_path / "execution.json"
    evidence.write_text(json.dumps(execution), encoding="utf-8")

    with pytest.raises(AssemblyConversationError, match="失败或未发布"):
        bind_direct_mate_execution(
            context_file, context, execution, execution_path=evidence
        )
