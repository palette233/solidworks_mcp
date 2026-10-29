import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from demo_backend.broad_combination_cad_validation_batch import (
    build_broad_combination_cad_validation_batch,
)
from demo_backend.broad_combination_cad_validation_execution import (
    build_broad_combination_cad_validation_state,
    mark_broad_combination_item_completed,
    mark_broad_combination_item_failed,
    plan_next_broad_combination_cad_validation,
    recover_failed_broad_combination_item_completed,
    validate_broad_combination_cad_validation_state,
)
from demo_backend.mechanical_interface_contracts import (
    MechanicalInterfaceContractError,
)


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import run_broad_combination_cad_validation_batch as batch_runner


def _batch() -> dict:
    return json.loads(
        (
            ROOT
            / "demo/cross_project_substitution/broad-combination-cad-validation-v1/"
            "batch-20261026-v3/batch-plan.json"
        ).read_text(encoding="utf-8-sig")
    )


def test_first_six_items_use_complete_parameterized_publication_adapter():
    batch = _batch()
    assert [row["adapter"] for row in batch["items"][:6]] == [
        "parameterized_datum_queue"
    ] * 6
    assert batch["items"][-1]["adapter"] == "direct_interface"
    first = batch["items"][0]
    assert first["moduleDefinitionId"] == "project01::GN00"
    assert first["baseDefinitionId"] == "project05::A000"
    assert batch["executionPolicy"]["solidWorksOpenDocumentCountMustEqual"] == 0


def test_completion_requires_release_and_advances_successor_queue():
    batch = _batch()
    state = build_broad_combination_cad_validation_state(ROOT, batch)
    first = batch["items"][0]
    with pytest.raises(MechanicalInterfaceContractError, match="exact-pair release"):
        mark_broad_combination_item_completed(
            batch,
            state,
            item_id=first["itemId"],
            completion_evidence={"exactPairReleased": False},
        )
    advanced = mark_broad_combination_item_completed(
        batch,
        state,
        item_id=first["itemId"],
        completion_evidence={
            "exactPairReleased": True,
            "releaseManifestPath": "demo/releases/one/release-manifest.json",
        },
        successor_queue_directory="demo/next-queue",
    )
    assert advanced["completedItemCount"] == 1
    assert advanced["items"][0]["status"] == "completed"
    assert advanced["currentParameterizedQueueDirectory"] == "demo/next-queue"
    validate_broad_combination_cad_validation_state(batch, advanced)


def test_resume_cannot_skip_pending_item_or_reorder_completions():
    batch = _batch()
    state = build_broad_combination_cad_validation_state(ROOT, batch)
    with pytest.raises(MechanicalInterfaceContractError, match="immutable batch order"):
        mark_broad_combination_item_completed(
            batch,
            state,
            item_id=batch["items"][1]["itemId"],
            completion_evidence={
                "exactPairReleased": True,
                "releaseManifestPath": "demo/releases/two/release-manifest.json",
            },
        )


def test_failure_stops_queue_and_preserves_checkpoint():
    batch = _batch()
    state = build_broad_combination_cad_validation_state(ROOT, batch)
    first = batch["items"][0]
    failed = mark_broad_combination_item_failed(
        batch,
        state,
        item_id=first["itemId"],
        failure_evidence={"returnCode": 1, "attemptPath": "attempt.json"},
    )
    assert failed["status"] == "failed_stop_queue"
    assert failed["failedItemId"] == first["itemId"]
    with pytest.raises(MechanicalInterfaceContractError, match="stop-on-failure"):
        plan_next_broad_combination_cad_validation(
            ROOT, batch, failed, batch_directory=ROOT / "demo/fake-batch"
        )


def test_failed_publication_can_recover_without_incrementing_cad_attempt():
    batch = _batch()
    state = build_broad_combination_cad_validation_state(ROOT, batch)
    first = batch["items"][0]
    failed = mark_broad_combination_item_failed(
        batch,
        state,
        item_id=first["itemId"],
        failure_evidence={"returnCode": 1, "phase": "publication"},
    )
    recovered = recover_failed_broad_combination_item_completed(
        batch,
        failed,
        item_id=first["itemId"],
        completion_evidence={
            "exactPairReleased": True,
            "naturalLanguageAuthorityReady": True,
            "releaseManifestPath": "demo/releases/recovered/release-manifest.json",
        },
        successor_queue_directory="demo/recovered-queue",
    )
    assert recovered["status"] == "pending"
    assert recovered["failedItemId"] is None
    assert recovered["completedItemCount"] == 1
    assert recovered["items"][0]["attemptCount"] == 1
    assert recovered["items"][0]["failureEvidence"]["phase"] == "publication"
    assert recovered["items"][0]["recoveryEvidence"][
        "publicationRecoveredWithoutCadRerun"
    ] is True
    assert recovered["currentParameterizedQueueDirectory"] == "demo/recovered-queue"
    validate_broad_combination_cad_validation_state(batch, recovered)


def test_failed_final_direct_item_can_recover_without_successor_queue():
    batch = _batch()
    state = build_broad_combination_cad_validation_state(ROOT, batch)
    for index, item in enumerate(batch["items"][:6], start=1):
        state = mark_broad_combination_item_completed(
            batch,
            state,
            item_id=item["itemId"],
            completion_evidence={
                "exactPairReleased": True,
                "releaseManifestPath": f"demo/releases/{index}/release-manifest.json",
            },
            successor_queue_directory=f"demo/queue-{index}",
        )
    final = batch["items"][-1]
    failed = mark_broad_combination_item_failed(
        batch,
        state,
        item_id=final["itemId"],
        failure_evidence={"phase": "mate-solve"},
    )
    recovered = recover_failed_broad_combination_item_completed(
        batch,
        failed,
        item_id=final["itemId"],
        completion_evidence={
            "exactPairReleased": True,
            "naturalLanguageAuthorityReady": True,
            "releaseManifestPath": "demo/releases/final/release-manifest.json",
        },
    )
    assert recovered["status"] == "completed"
    assert recovered["completedItemCount"] == 7
    assert recovered["currentParameterizedQueueDirectory"] == "demo/queue-6"
    assert recovered["items"][-1]["failureEvidence"]["phase"] == "mate-solve"


def test_final_direct_item_uses_cad_and_publication_bridge():
    batch = _batch()
    state = build_broad_combination_cad_validation_state(ROOT, batch)
    for index, item in enumerate(batch["items"][:6], start=1):
        state = mark_broad_combination_item_completed(
            batch,
            state,
            item_id=item["itemId"],
            completion_evidence={
                "exactPairReleased": True,
                "releaseManifestPath": f"demo/releases/test-{index}/release-manifest.json",
            },
            successor_queue_directory=f"demo/test-queue-{index}",
        )
    plan = plan_next_broad_combination_cad_validation(
        ROOT, batch, state, batch_directory=ROOT / "demo/fake-batch"
    )
    assert plan["action"] in {
        "run_direct_item_and_publish",
        "finish_direct_publication_without_rerunning_cad",
        "direct_item_failed_evidence_requires_superseding_candidate",
    }
    assert plan["item"]["moduleDefinitionId"] == "project01::BD00"
    assert plan["item"]["baseDefinitionId"] == "project02::A600"
    if plan["action"] == "run_direct_item_and_publish":
        assert plan["adapterPlan"]["preconditions"][
            "nonPrototypeInitialPoseRequired"
        ] is True
        assert plan["command"][1].endswith("run_context_mate_graph_insert.py")
    else:
        assert plan["preconditions"]["cadSessionRequired"] is False


def test_state_digest_and_batch_binding_are_fail_closed():
    batch = _batch()
    state = build_broad_combination_cad_validation_state(ROOT, batch)
    tampered = copy.deepcopy(state)
    tampered["completedItemCount"] = 1
    with pytest.raises(MechanicalInterfaceContractError, match="state digest"):
        validate_broad_combination_cad_validation_state(batch, tampered)
    other = copy.deepcopy(state)
    other["batchDigest"] = "0" * 64
    core = {key: value for key, value in other.items() if key != "stateDigest"}
    import hashlib

    other["stateDigest"] = hashlib.sha256(
        json.dumps(
            core, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    with pytest.raises(MechanicalInterfaceContractError, match="another batch"):
        validate_broad_combination_cad_validation_state(batch, other)


def test_materialized_batch_cli_status_and_plan_are_read_only():
    batch_dir = ROOT / (
        "demo/cross_project_substitution/broad-combination-cad-validation-v1/"
        "batch-20261026-v3"
    )
    state_before = (batch_dir / "execution-state.json").read_bytes()
    expected_state = json.loads(state_before)
    for action in ("status", "plan-next"):
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/run_broad_combination_cad_validation_batch.py"),
                action,
                "--batch-dir",
                str(batch_dir),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if action == "status":
            assert completed.returncode == 0, completed.stderr
            payload = json.loads(completed.stdout)
            assert payload == expected_state
        elif expected_state.get("failedItemId"):
            assert completed.returncode != 0
            assert "stop-on-failure" in completed.stderr
        elif completed.returncode != 0:
            # A CAD/publication step may have advanced the canonical catalog
            # before the batch checkpoint is recovered.  Planning must fail
            # closed and remain read-only in that transitional state.
            assert "stale datum catalog" in completed.stderr
        else:
            payload = json.loads(completed.stdout)
            assert payload["action"] in {
                "run_parameterized_item_and_publish",
                "run_direct_item_and_publish",
                "finish_direct_publication_without_rerunning_cad",
                "batch_complete",
            }
            if payload["action"] != "batch_complete":
                expected_next = next(
                    row for row in expected_state["items"] if row["status"] == "pending"
                )
                assert payload["item"]["itemId"] == expected_next["itemId"]
    assert (batch_dir / "execution-state.json").read_bytes() == state_before


def test_direct_publication_binding_is_recoverable_and_exact_pair_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    candidate = tmp_path / "direct"
    candidate.mkdir()
    package_path = candidate / "validation-package.json"
    package_path.write_text("{}\n", encoding="utf-8")
    pair = {
        "moduleDefinitionId": "project01::BD00",
        "slotDefinitionId": "project02::A600",
        "releaseDigest": "1" * 64,
    }
    relation = {
        "releaseId": "relation-direct-test",
        "releaseDigest": "2" * 64,
        "releaseManifestPath": "demo/releases/relation-direct-test/release-manifest.json",
        "globalTemplateId": "template/project-global/direct-test",
        "moduleDefinitionId": "project01::BD00",
        "slotDefinitionId": "project02::A600",
        "relationExecutionMode": "direct_installation",
        "physicalFasteningVerified": False,
        "collisionOrBrep": "not_evaluated",
        "cadStarted": False,
    }
    authority = {
        "ready": True,
        "selectedMode": "mechanical_interface",
        "relationExecutionMode": "direct_installation",
        "releaseManifestPath": relation["releaseManifestPath"],
    }
    monkeypatch.setattr(
        batch_runner,
        "ensure_direct_interface_relation_release",
        lambda *args, **kwargs: {
            "pairRelease": pair,
            "relationRelease": relation,
            "cadRerun": False,
        },
    )
    monkeypatch.setattr(
        batch_runner,
        "_refresh_calibration_contract_catalog",
        lambda: {"catalogDigest": "3" * 64},
    )
    monkeypatch.setattr(
        batch_runner,
        "resolve_preferred_released_interface_authority",
        lambda *args, **kwargs: authority,
    )
    item = {"validationPackagePath": str(package_path)}
    first = batch_runner._finish_direct_publication(item)
    second = batch_runner._finish_direct_publication(item)
    assert first["binding"] == second["binding"]
    assert first["binding"]["pairReleaseDigest"] == "1" * 64
    assert first["binding"]["naturalLanguageAuthority"]["ready"] is True
    assert Path(first["bindingPath"]).is_file()


def test_batch_cleanup_independently_restores_and_verifies_zero_documents(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        batch_runner,
        "restore_packet_document_baseline",
        lambda baseline, timeout: {
            "baselineOpenDocumentCount": 0,
            "closedDocumentPaths": ["batch-owned.SLDPRT"],
            "errors": [],
            "sessionRestoredToBaseline": True,
        },
    )
    monkeypatch.setattr(
        batch_runner,
        "capture_open_document_baseline",
        lambda timeout: {"paths": [], "openDocumentCount": 0},
    )
    result = batch_runner._restore_and_verify_zero_document_baseline(
        {"paths": [], "openDocumentCount": 0}, timeout=10
    )
    assert result["verified"] is True
    assert result["cleanup"]["closedDocumentPaths"] == ["batch-owned.SLDPRT"]


def test_batch_cleanup_fails_closed_when_a_document_remains(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        batch_runner,
        "restore_packet_document_baseline",
        lambda baseline, timeout: {
            "baselineOpenDocumentCount": 0,
            "closedDocumentPaths": [],
            "errors": [],
            "sessionRestoredToBaseline": True,
        },
    )
    monkeypatch.setattr(
        batch_runner,
        "capture_open_document_baseline",
        lambda timeout: {
            "paths": ["left-open.SLDPRT"],
            "openDocumentCount": 1,
        },
    )
    with pytest.raises(RuntimeError, match="zero-document baseline"):
        batch_runner._restore_and_verify_zero_document_baseline(
            {"paths": [], "openDocumentCount": 0}, timeout=10
        )
