import json
from pathlib import Path

import pytest

from demo_backend.assembly_conversation import conversation_snapshot, reset_conversation
from demo_backend.historical_checkpoint_import import (
    HistoricalCheckpointImportError,
    build_historical_checkpoint_import_assessment,
    commit_historical_checkpoint_import,
    infer_component_inventory_path,
)


def _context() -> dict:
    return {
        "contextId": "legacy-import-unit",
        "revision": 2,
        "contextDigest": "c" * 64,
        "updatedAt": "2026-10-09T00:00:00Z",
        "instances": [
            {"instanceId": "case-001", "moduleDefinitionId": "global/case"},
            {"instanceId": "supply-001", "moduleDefinitionId": "global/supply"},
            {"instanceId": "supply-002", "moduleDefinitionId": "global/supply"},
        ],
        "history": [
            {
                "revision": 1,
                "requirement": "添加箱体",
                "previewDigest": "p1",
                "timestamp": "2026-10-09T00:00:00Z",
            },
            {
                "revision": 2,
                "requirement": "添加两套供胶",
                "previewDigest": "p2",
                "timestamp": "2026-10-09T00:01:00Z",
            },
        ],
    }


def _catalog() -> dict:
    return {
        "moduleDefinitions": [
            {
                "moduleDefinitionId": "global/case",
                "componentNames": ["FRAME.SLDASM"],
                "projectAliases": [{"projectId": "project02", "moduleToken": "A600"}],
            },
            {
                "moduleDefinitionId": "global/supply",
                "componentNames": ["T401AA-07388-0.SLDPRT"],
                "projectAliases": [{"projectId": "project02", "moduleToken": "T401"}],
            },
        ]
    }


def _files(tmp_path: Path):
    assembly = tmp_path / "legacy.SLDASM"
    assembly.write_bytes(b"legacy-assembly")
    inventory = tmp_path / "attempt1-poses.json"
    inventory.write_text(
        json.dumps(
            {
                "schemaVersion": "assembly-top-level-component-poses/v1",
                "assemblyPath": str(assembly),
                "componentCount": 3,
                "components": [
                    {"Name": "FRAME-1", "Path": "D:/FRAME.SLDASM"},
                    {"Name": "T401AA-07388-0-1", "Path": "D:/T401AA-07388-0.SLDPRT"},
                    {"Name": "T401AA-07388-0-2", "Path": "D:/T401AA-07388-0.SLDPRT"},
                ],
            }
        ),
        encoding="utf-8",
    )
    return assembly, inventory


def _job(assembly: Path, inventory: Path) -> dict:
    import hashlib

    sha = hashlib.sha256(assembly.read_bytes()).hexdigest()
    gate = inventory.with_name("attempt1-gate.json")
    gate.write_text("{}", encoding="utf-8")
    return {
        "jobId": "project02-job-legacy",
        "projectId": "project02",
        "status": "succeeded",
        "validationProfile": "demo",
        "assemblyStatus": "assembled",
        "collisionStatus": "passed",
        "createdAt": "2026-10-09T00:02:00Z",
        "updatedAt": "2026-10-09T00:03:00Z",
        "demoCheckpoint": {
            "assemblyPath": str(assembly),
            "committedAt": "2026-10-09T00:03:00Z",
        },
        "engineeringCheckpoint": {
            "evidencePath": str(gate),
            "sourceAssemblyIdentity": {
                "path": str(assembly),
                "sizeBytes": assembly.stat().st_size,
                "sha256": sha,
            },
        },
        "plan": {"schemaVersion": "pre-ledger-plan/v1"},
    }


def test_duplicate_module_instances_are_attested_and_bound_idempotently(tmp_path: Path):
    context_path = tmp_path / "context.json"
    context = _context()
    reset_conversation(context_path, context)
    assembly, inventory = _files(tmp_path)
    job = _job(assembly, inventory)

    assessment = build_historical_checkpoint_import_assessment(
        context, _catalog(), job, inventory
    )
    assert assessment["status"] == "ready_for_import"
    assert assessment["expectedModuleTokenCounts"] == {"A600": 1, "T401": 2}
    assert assessment["observedModuleTokenCounts"] == {"A600": 1, "T401": 2}
    assert infer_component_inventory_path(job) == inventory

    first = commit_historical_checkpoint_import(
        context_path,
        context,
        job,
        assessment,
        expected_assessment_digest=assessment["assessmentDigest"],
        confirmed=True,
    )
    repeated = commit_historical_checkpoint_import(
        context_path,
        context,
        job,
        assessment,
        expected_assessment_digest=assessment["assessmentDigest"],
        confirmed=True,
    )
    assert first["status"] == repeated["status"] == "imported"
    snapshot = conversation_snapshot(context_path, context, lambda _: job)
    assert snapshot["latestSuccessfulDemo"]["jobId"] == job["jobId"]
    assert snapshot["latestSuccessfulDemo"]["projectId"] == "project02"
    binding = snapshot["turns"][-1]["jobs"][0]
    assert binding["bindingKind"] == "historical_attested_import"
    assert Path(binding["attestationPath"]).is_file()


def test_inventory_mismatch_blocks_import(tmp_path: Path):
    assembly, inventory = _files(tmp_path)
    payload = json.loads(inventory.read_text(encoding="utf-8"))
    payload["components"].pop()
    payload["componentCount"] = 2
    inventory.write_text(json.dumps(payload), encoding="utf-8")
    assessment = build_historical_checkpoint_import_assessment(
        _context(), _catalog(), _job(assembly, inventory), inventory
    )

    assert assessment["status"] == "blocked"
    assert "MODULE_MULTISET_MISMATCH" in {
        row["code"] for row in assessment["blockers"]
    }
    with pytest.raises(HistoricalCheckpointImportError, match="存在阻塞项"):
        commit_historical_checkpoint_import(
            tmp_path / "context.json",
            _context(),
            _job(assembly, inventory),
            assessment,
            expected_assessment_digest=assessment["assessmentDigest"],
            confirmed=True,
        )


def test_file_change_after_preview_fails_closed(tmp_path: Path):
    context_path = tmp_path / "context.json"
    context = _context()
    reset_conversation(context_path, context)
    assembly, inventory = _files(tmp_path)
    job = _job(assembly, inventory)
    assessment = build_historical_checkpoint_import_assessment(
        context, _catalog(), job, inventory
    )
    assembly.write_bytes(b"changed-after-preview")

    with pytest.raises(HistoricalCheckpointImportError, match="确认前发生变化"):
        commit_historical_checkpoint_import(
            context_path,
            context,
            job,
            assessment,
            expected_assessment_digest=assessment["assessmentDigest"],
            confirmed=True,
        )
