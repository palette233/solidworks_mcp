#!/usr/bin/env python3
"""Initialize, inspect or plan the broad-combination CAD validation batch."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.broad_combination_cad_validation_batch import (  # noqa: E402
    validate_broad_combination_cad_validation_batch,
)
from demo_backend.broad_combination_cad_validation_execution import (  # noqa: E402
    build_broad_combination_cad_validation_state,
    mark_broad_combination_item_completed,
    mark_broad_combination_item_failed,
    plan_next_broad_combination_cad_validation,
    recover_failed_broad_combination_item_completed,
    validate_broad_combination_cad_validation_state,
)
from demo_backend.direct_interface_relation_release import (  # noqa: E402
    ensure_direct_interface_relation_release,
)
from demo_backend.global_interface_contract_planner import (  # noqa: E402
    resolve_preferred_released_interface_authority,
)
from demo_backend.parameterized_datum_validation_execution import (  # noqa: E402
    load_materialized_validation_queue,
)
from run_global_cad_transaction_packet import (  # noqa: E402
    capture_open_document_baseline,
    restore_packet_document_baseline,
)


DEFAULT_BATCH = ROOT / (
    "demo/cross_project_substitution/broad-combination-cad-validation-v1/"
    "batch-20261026-v3"
)
BASE_GLOBAL_CATALOG = ROOT / "demo/global_assembly_catalog/v1/global_module_catalog.json"
CALIBRATION_CONTRACT_CATALOG = ROOT / (
    "demo/cross_project_substitution/calibration-interface-contract-v1/"
    "interface-contract-catalog.json"
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_new(path: Path, payload: dict) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite batch state: {path}")
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _replace(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def _workspace_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _refresh_calibration_contract_catalog() -> dict:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts/build_calibration_interface_contracts.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "Direct relation was published but calibration contract refresh failed: "
            + completed.stderr.strip()
        )
    return _read(CALIBRATION_CONTRACT_CATALOG)


def _normalize_direct_relation(relation: dict) -> dict:
    keys = (
        "releaseId",
        "releaseDigest",
        "releaseManifestPath",
        "globalTemplateId",
        "moduleDefinitionId",
        "slotDefinitionId",
        "relationExecutionMode",
        "physicalFasteningVerified",
        "collisionOrBrep",
    )
    return {key: relation.get(key) for key in keys}


def _restore_and_verify_zero_document_baseline(
    baseline: dict, *, timeout: float
) -> dict:
    """Independently close batch-owned documents and prove the session is empty."""

    cleanup = restore_packet_document_baseline(baseline, timeout=timeout)
    after = capture_open_document_baseline(timeout=timeout)
    result = {
        "cleanup": cleanup,
        "postCleanupBaseline": after,
        "verified": (
            cleanup.get("sessionRestoredToBaseline") is True
            and not (cleanup.get("errors") or [])
            and int(after.get("openDocumentCount") or 0) == 0
            and not (after.get("paths") or [])
        ),
    }
    if result["verified"] is not True:
        raise RuntimeError(
            "Broad CAD validation did not restore the zero-document baseline: "
            + json.dumps(result, ensure_ascii=False)
        )
    return result


def _finish_direct_publication(item: dict) -> dict:
    package_path = _workspace_path(str(item["validationPackagePath"]))
    candidate = package_path.parent
    recovery = ensure_direct_interface_relation_release(
        ROOT,
        candidate,
        BASE_GLOBAL_CATALOG,
    )
    catalog = _refresh_calibration_contract_catalog()
    pair = recovery["pairRelease"]
    relation = _normalize_direct_relation(recovery["relationRelease"])
    authority = resolve_preferred_released_interface_authority(
        ROOT,
        str(pair["moduleDefinitionId"]),
        selected_slot_definition_id=str(pair["slotDefinitionId"]),
        allow_datum_fallback=False,
    )
    if (
        authority.get("ready") is not True
        or authority.get("selectedMode") != "mechanical_interface"
        or authority.get("relationExecutionMode") != "direct_installation"
        or authority.get("releaseManifestPath") != relation["releaseManifestPath"]
    ):
        raise RuntimeError(
            "Direct release was written but natural-language authority did not "
            "resolve to the exact release: "
            + str(authority.get("status"))
        )
    binding = {
        "schemaVersion": "direct-interface-relation-release-binding/v1",
        "pairReleaseDigest": pair["releaseDigest"],
        "relationRelease": relation,
        "calibrationContractCatalogDigest": catalog["catalogDigest"],
        "naturalLanguageAuthority": authority,
        "claimBoundary": (
            "This exact pair is authorized for direct mechanical CAD installation. "
            "Physical fastening, collision and production approval remain separate."
        ),
    }
    binding_path = candidate / "relation-release-binding.json"
    if binding_path.is_file():
        if _read(binding_path) != binding:
            raise RuntimeError(
                "Existing direct relation binding differs from authenticated evidence"
            )
    else:
        _write_new(binding_path, binding)
    return {
        "recovery": recovery,
        "binding": binding,
        "bindingPath": str(binding_path.resolve()),
    }


def _recover_parameterized_publication(
    batch_dir: Path, batch: dict, state: dict
) -> dict:
    """Authenticate and record publication already completed outside batch state."""

    failed_id = str(state.get("failedItemId") or "")
    if failed_id:
        item_id = failed_id
    else:
        pending = next(
            (row for row in state["items"] if row.get("status") == "pending"), None
        )
        if pending is None:
            raise RuntimeError("Broad CAD batch has no incomplete item to recover")
        item_id = str(pending["itemId"])
    item = next(row for row in batch["items"] if row["itemId"] == item_id)
    if item.get("adapter") != "parameterized_datum_queue":
        raise RuntimeError("Only parameterized publication failures are recoverable")
    bindings = []
    for path in batch_dir.glob("queue-*/validation-*/relation-release-binding.json"):
        payload = _read(path)
        relation = payload.get("relationRelease") or {}
        if (
            relation.get("moduleDefinitionId") == item["moduleDefinitionId"]
            and relation.get("slotDefinitionId") == item["baseDefinitionId"]
        ):
            bindings.append((path, payload))
    if len(bindings) != 1:
        raise RuntimeError(
            "Expected exactly one recovered relation binding for failed item; "
            f"found {len(bindings)}"
        )
    binding_path, binding = bindings[0]
    authority = binding.get("naturalLanguageAuthority") or {}
    relation = binding.get("relationRelease") or {}
    if authority.get("ready") is not True:
        raise RuntimeError("Recovered relation has no ready natural-language authority")
    manifest_path = _workspace_path(str(relation.get("releaseManifestPath") or ""))
    if not manifest_path.is_file():
        raise RuntimeError(f"Recovered relation manifest is missing: {manifest_path}")
    successor = batch_dir / f"queue-successor-{int(item['sequence']):02d}"
    successor_queue = load_materialized_validation_queue(successor)
    successor_relative = successor.resolve().relative_to(ROOT.resolve()).as_posix()
    completion_evidence = {
        "exactPairReleased": True,
        "relationReleaseId": relation.get("releaseId"),
        "releaseManifestPath": str(manifest_path.resolve()),
        "relationReleaseBindingPath": str(binding_path.resolve()),
        "naturalLanguageAuthorityReady": True,
        "successorQueueDigest": successor_queue["queueDigest"],
        "cadRerunDuringPublicationRecovery": False,
    }
    if failed_id:
        advanced = recover_failed_broad_combination_item_completed(
            batch,
            state,
            item_id=item["itemId"],
            completion_evidence=completion_evidence,
            successor_queue_directory=successor_relative,
        )
    else:
        advanced = mark_broad_combination_item_completed(
            batch,
            state,
            item_id=item["itemId"],
            completion_evidence=completion_evidence,
            successor_queue_directory=successor_relative,
        )
    return {
        "state": advanced,
        "item": item,
        "binding": binding,
        "successorQueueDirectory": successor_relative,
    }


def _recover_direct_superseding_publication(
    batch: dict, state: dict, candidate: Path
) -> dict:
    """Bind a corrected immutable direct candidate to the failed exact pair."""

    failed_id = str(state.get("failedItemId") or "")
    if not failed_id:
        raise RuntimeError("Broad CAD batch has no failed direct item to recover")
    item = next(row for row in batch["items"] if row["itemId"] == failed_id)
    if item.get("adapter") != "direct_interface":
        raise RuntimeError("Recorded failed item is not a direct-interface item")
    candidate = candidate.resolve()
    binding_path = candidate / "relation-release-binding.json"
    pair_path = candidate / "pair-release.json"
    result_path = candidate / "cad-result.json"
    for path in (binding_path, pair_path, result_path):
        if not path.is_file():
            raise RuntimeError(f"Direct recovery evidence is missing: {path}")
    binding = _read(binding_path)
    pair = _read(pair_path)
    result = _read(result_path)
    relation = binding.get("relationRelease") or {}
    authority = binding.get("naturalLanguageAuthority") or {}
    expected = (item["moduleDefinitionId"], item["baseDefinitionId"])
    actual = (relation.get("moduleDefinitionId"), relation.get("slotDefinitionId"))
    if actual != expected or (
        pair.get("moduleDefinitionId"), pair.get("slotDefinitionId")
    ) != expected:
        raise RuntimeError("Direct recovery evidence belongs to another exact pair")
    if (
        result.get("success") is not True
        or pair.get("nonPrototypeCadValidated") is not True
        or authority.get("ready") is not True
        or authority.get("selectedMode") != "mechanical_interface"
        or authority.get("relationExecutionMode") != "direct_installation"
    ):
        raise RuntimeError("Direct recovery evidence does not pass all hard gates")
    manifest_path = _workspace_path(str(relation.get("releaseManifestPath") or ""))
    if not manifest_path.is_file():
        raise RuntimeError(f"Direct recovery release is missing: {manifest_path}")
    advanced = recover_failed_broad_combination_item_completed(
        batch,
        state,
        item_id=item["itemId"],
        completion_evidence={
            "exactPairReleased": True,
            "relationReleaseId": relation.get("releaseId"),
            "releaseManifestPath": str(manifest_path.resolve()),
            "relationReleaseBindingPath": str(binding_path.resolve()),
            "naturalLanguageAuthorityReady": True,
            "cadRerunDuringPublicationRecovery": False,
            "supersedingValidationPackagePath": str(
                (candidate / "validation-package.json").resolve()
            ),
            "supersedingReason": (
                "The original candidate used incorrect hard-coded concentric "
                "alignment; the corrected immutable candidate passed real CAD."
            ),
        },
    )
    return {"state": advanced, "item": item, "binding": binding}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=[
            "init",
            "status",
            "plan-next",
            "run-next",
            "recover-failed",
            "recover-publication",
            "recover-direct",
        ],
    )
    parser.add_argument("--batch-dir", type=Path, default=DEFAULT_BATCH)
    parser.add_argument("--recovery-candidate-dir", type=Path)
    parser.add_argument("--session-check-timeout", type=float, default=120.0)
    args = parser.parse_args()
    batch_dir = args.batch_dir.resolve()
    batch = _read(batch_dir / "batch-plan.json")
    validate_broad_combination_cad_validation_batch(ROOT, batch)
    state_path = batch_dir / "execution-state.json"
    if args.action == "init":
        state = build_broad_combination_cad_validation_state(ROOT, batch)
        _write_new(state_path, state)
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return 0
    if not state_path.is_file():
        raise FileNotFoundError(
            f"batch state is missing; run init first: {state_path}"
        )
    state = _read(state_path)
    validate_broad_combination_cad_validation_state(batch, state)
    if args.action == "status":
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return 0
    if args.action in {"recover-failed", "recover-publication"}:
        recovered = _recover_parameterized_publication(batch_dir, batch, state)
        advanced = recovered["state"]
        _replace(state_path, advanced)
        relation = recovered["binding"]["relationRelease"]
        print(
            json.dumps(
                {
                    "success": True,
                    "recoveredItemId": recovered["item"]["itemId"],
                    "completedItemCount": advanced["completedItemCount"],
                    "batchStatus": advanced["status"],
                    "nextQueueDirectory": recovered["successorQueueDirectory"],
                    "relationReleaseId": relation.get("releaseId"),
                    "cadRerun": False,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.action == "recover-direct":
        if args.recovery_candidate_dir is None:
            raise RuntimeError("recover-direct requires --recovery-candidate-dir")
        recovered = _recover_direct_superseding_publication(
            batch, state, args.recovery_candidate_dir
        )
        advanced = recovered["state"]
        _replace(state_path, advanced)
        relation = recovered["binding"]["relationRelease"]
        print(
            json.dumps(
                {
                    "success": True,
                    "recoveredItemId": recovered["item"]["itemId"],
                    "completedItemCount": advanced["completedItemCount"],
                    "batchStatus": advanced["status"],
                    "relationReleaseId": relation.get("releaseId"),
                    "cadRerunDuringRecovery": False,
                    "supersedingCandidate": str(
                        args.recovery_candidate_dir.resolve()
                    ),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    plan = plan_next_broad_combination_cad_validation(
        ROOT, batch, state, batch_directory=batch_dir
    )
    if args.action == "plan-next":
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0
    if plan["action"] == "batch_complete":
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0
    supported = {
        "run_parameterized_item_and_publish",
        "run_direct_item_and_publish",
        "finish_direct_publication_without_rerunning_cad",
    }
    if plan["action"] not in supported:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 3

    item = plan["item"]
    baseline = None
    cleanup = None
    if plan["action"] in {
        "run_parameterized_item_and_publish",
        "run_direct_item_and_publish",
    }:
        baseline = capture_open_document_baseline(timeout=args.session_check_timeout)
        if int(baseline.get("openDocumentCount") or 0) != 0:
            raise RuntimeError(
                "Broad CAD validation requires an empty SolidWorks document session; "
                f"observed {baseline.get('openDocumentCount')} open documents."
            )
        completed = subprocess.run(plan["command"], cwd=ROOT, check=False)
        cleanup = _restore_and_verify_zero_document_baseline(
            baseline, timeout=args.session_check_timeout
        )
        if completed.returncode != 0:
            candidate_value = item.get("candidateDirectory")
            if not candidate_value:
                candidate_value = str(
                    _workspace_path(str(item["validationPackagePath"])).parent
                )
            failed = mark_broad_combination_item_failed(
                batch,
                state,
                item_id=item["itemId"],
                failure_evidence={
                    "returnCode": completed.returncode,
                    "candidateDirectory": candidate_value,
                    "solidWorksBaseline": baseline,
                    "solidWorksCleanup": cleanup,
                },
            )
            _replace(state_path, failed)
            return completed.returncode

    if plan["action"] in {
        "run_direct_item_and_publish",
        "finish_direct_publication_without_rerunning_cad",
    }:
        direct = _finish_direct_publication(item)
        binding = direct["binding"]
        relation = binding["relationRelease"]
        manifest_path = _workspace_path(str(relation["releaseManifestPath"]))
        advanced = mark_broad_combination_item_completed(
            batch,
            state,
            item_id=item["itemId"],
            completion_evidence={
                "exactPairReleased": True,
                "relationReleaseId": relation["releaseId"],
                "releaseManifestPath": str(manifest_path.resolve()),
                "relationReleaseBindingPath": direct["bindingPath"],
                "naturalLanguageAuthorityReady": True,
                "solidWorksBaseline": baseline,
                "solidWorksCleanup": cleanup,
                "cadRerunDuringPublicationRecovery": direct["recovery"]["cadRerun"],
            },
        )
        _replace(state_path, advanced)
        print(
            json.dumps(
                {
                    "success": True,
                    "completedItemId": item["itemId"],
                    "completedItemCount": advanced["completedItemCount"],
                    "batchStatus": advanced["status"],
                    "relationReleaseId": relation["releaseId"],
                    "cadRerun": direct["recovery"]["cadRerun"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    candidate = Path(plan["adapterPlan"]["candidateDirectory"]).resolve()
    binding_path = candidate / "relation-release-binding.json"
    if not binding_path.is_file():
        raise RuntimeError(
            "Parameterized runner returned success without relation release binding: "
            f"{binding_path}"
        )
    binding = _read(binding_path)
    authority = binding.get("naturalLanguageAuthority") or {}
    relation = binding.get("relationRelease") or {}
    if (
        authority.get("ready") is not True
        or relation.get("moduleDefinitionId") != item["moduleDefinitionId"]
        or relation.get("slotDefinitionId") != item["baseDefinitionId"]
    ):
        raise RuntimeError("Published relation binding does not match the batch item")
    manifest_path = _workspace_path(str(relation.get("releaseManifestPath") or ""))
    if not manifest_path.is_file():
        raise RuntimeError(f"Published relation manifest is missing: {manifest_path}")
    successor = _workspace_path(plan["successorQueueDirectory"])
    successor_queue = load_materialized_validation_queue(successor)
    advanced = mark_broad_combination_item_completed(
        batch,
        state,
        item_id=item["itemId"],
        completion_evidence={
            "exactPairReleased": True,
            "relationReleaseId": relation.get("releaseId"),
            "releaseManifestPath": str(manifest_path.resolve()),
            "relationReleaseBindingPath": str(binding_path.resolve()),
            "naturalLanguageAuthorityReady": True,
            "successorQueueDigest": successor_queue["queueDigest"],
            "solidWorksBaseline": baseline,
            "solidWorksCleanup": cleanup,
        },
        successor_queue_directory=plan["successorQueueDirectory"],
    )
    _replace(state_path, advanced)
    print(
        json.dumps(
            {
                "success": True,
                "completedItemId": item["itemId"],
                "completedItemCount": advanced["completedItemCount"],
                "nextQueueDirectory": advanced["currentParameterizedQueueDirectory"],
                "relationReleaseId": relation.get("releaseId"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
