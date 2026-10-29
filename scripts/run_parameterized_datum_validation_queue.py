#!/usr/bin/env python3
"""Inspect or execute one item from a parameterized-datum CAD queue."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))
sys.path.insert(0, str(ROOT / "scripts"))

from demo_backend.parameterized_datum_placement import (  # noqa: E402
    build_parameterized_datum_placement_catalog,
    publish_parameterized_datum_pair_release,
)
from demo_backend.parameterized_datum_relation_release import (  # noqa: E402
    publish_parameterized_datum_relation_release,
)
from demo_backend.direct_interface_relation_release import (  # noqa: E402
    ensure_direct_interface_relation_release,
)
from demo_backend.parameterized_datum_validation_execution import (  # noqa: E402
    derive_parameterized_datum_relation_release_id,
    inspect_materialized_validation_queue,
    plan_next_parameterized_datum_validation,
    materialize_station_candidate_validation_queue,
)
from demo_backend.parameterized_datum_validation_queue import (  # noqa: E402
    build_successor_parameterized_datum_validation_queue,
)
from demo_backend.global_interface_contract_planner import (  # noqa: E402
    resolve_preferred_released_interface_authority,
)
from demo_backend.global_relation_catalog_release import (  # noqa: E402
    load_relation_catalog_release,
)
from demo_backend.candidate_reuse_safety_supersession import (  # noqa: E402
    publish_candidate_reuse_safety_supersession,
)
from demo_backend.station_rule_planner import verify_station_stage  # noqa: E402
from run_global_cad_transaction_packet import capture_open_document_baseline  # noqa: E402
from build_parameterized_datum_validation_queue import (  # noqa: E402
    write_parameterized_datum_validation_queue,
)


BASE_CATALOG = ROOT / (
    "demo/cross_project_substitution/expanded-project03-v1/"
    "relation-v62-project03-expanded-cross-project-chain-driving-20261014."
    "catalog-preview.json"
)
BASE_GLOBAL_CATALOG = ROOT / "demo/global_assembly_catalog/v1/global_module_catalog.json"
DIRECT_PACKAGE_SCHEMA = "direct-interface-cad-validation-package/v1"
CANONICAL_DATUM_CATALOG = ROOT / (
    "demo/cross_project_substitution/parameterized-datum-placement-v1/"
    "interface-contract-catalog.json"
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_once(path: Path, payload: dict) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite evidence: {path}")
    _write(path, payload)


def _run_required_target_station_postcheck(candidate: Path, binding: dict) -> dict:
    """Verify the planned target station before publishing mechanical authority."""

    if binding.get("requiresTargetStationPostcheckBeforePublication") is not True:
        return {"required": False, "targetStationValidated": None}
    station_plan_path = Path(str(binding.get("stationPlanPath") or ""))
    if (
        not station_plan_path.is_file()
        or station_plan_path.parent.resolve() != candidate.resolve()
        or _sha256(station_plan_path) != binding.get("stationPlanSha256")
    ):
        raise RuntimeError("Target-station plan changed before postcheck")
    package_path = candidate / "validation-package.json"
    cad_result_path = candidate / "cad-result.json"
    if not package_path.is_file() or not cad_result_path.is_file():
        raise RuntimeError("Target-station postcheck requires package and CAD result")
    package = _read(package_path)
    cad_result = _read(cad_result_path)
    if cad_result.get("success") is not True:
        raise RuntimeError("Failed CAD result cannot enter target-station postcheck")
    committed_path = candidate / "station-postcheck.json"
    detail_path = candidate / "station-postcheck-detail.json"
    state_path = candidate / "reopened-state.json"
    if committed_path.is_file():
        committed = _read(committed_path)
        if (
            committed.get("targetStationValidated") is not True
            or committed.get("stationPlanSha256") != _sha256(station_plan_path)
            or committed.get("cadResultSha256") != _sha256(cad_result_path)
            or not state_path.is_file()
            or committed.get("savedStateSha256") != _sha256(state_path)
            or not detail_path.is_file()
            or committed.get("postcheckDetailSha256") != _sha256(detail_path)
        ):
            raise RuntimeError("Committed target-station postcheck evidence changed")
        current = verify_station_stage(
            ROOT,
            _read(station_plan_path),
            cad_result_path=cad_result_path,
            saved_state_path=state_path,
        )
        if (
            current.get("cadPassed") is not True
            or current.get("targetStationValidated") is not True
        ):
            raise RuntimeError("Committed target-station postcheck no longer passes")
        return committed
    error_path = candidate / "station-postcheck-error.json"
    if error_path.exists():
        raise RuntimeError("Target-station postcheck previously failed; queue is stopped")
    graph_path = Path(str((package.get("artifacts") or {}).get("effectiveGraph", {}).get("path") or ""))
    if not graph_path.is_file() or _sha256(graph_path) != (package.get("artifacts") or {}).get("effectiveGraph", {}).get("sha256"):
        raise RuntimeError("Target-station postcheck graph changed")
    graph = _read(graph_path)
    module_count = len(graph.get("Modules") or [])
    if module_count < 2:
        raise RuntimeError("Target-station postcheck has an invalid expected component count")
    inspection_path = candidate / "station-postcheck-inspection-process.json"
    if not state_path.exists():
        command = [
            sys.executable,
            str(ROOT / "scripts/verify_datum_chain_live_state.py"),
            "--cad-result",
            str(cad_result_path),
            "--report",
            str(state_path),
            "--count",
            str(module_count),
            "--base",
            str(package["baseModuleToken"]),
            "--source",
            str(package["sourceAssemblyPath"]),
        ]
        started = datetime.now(timezone.utc).isoformat()
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, check=False)
        inspection = {
            "startedAtUtc": started,
            "finishedAtUtc": datetime.now(timezone.utc).isoformat(),
            "command": command,
            "returnCode": completed.returncode,
            "stdout": completed.stdout.decode("utf-8", errors="replace"),
            "stderr": completed.stderr.decode("utf-8", errors="replace"),
        }
        _write_once(inspection_path, inspection)
        if completed.returncode != 0:
            _write_once(
                error_path,
                {
                    "stage": "independent_saved_output_inspection",
                    "returnCode": completed.returncode,
                    "inspectionProcessPath": str(inspection_path),
                    "pairReleaseWritten": False,
                },
            )
            raise RuntimeError("Independent target-station saved-output inspection failed")
    try:
        checked = verify_station_stage(
            ROOT,
            _read(station_plan_path),
            cad_result_path=cad_result_path,
            saved_state_path=state_path,
        )
    except Exception as exc:
        _write_once(
            error_path,
            {
                "stage": "target_station_postcheck",
                "errorType": type(exc).__name__,
                "message": str(exc),
                "pairReleaseWritten": False,
            },
        )
        raise
    _write_once(detail_path, checked)
    if (
        checked.get("cadPassed") is not True
        or checked.get("targetStationValidated") is not True
    ):
        _write_once(
            error_path,
            {
                "stage": "target_station_postcheck",
                "cadPassed": checked.get("cadPassed"),
                "targetStationValidated": checked.get("targetStationValidated"),
                "postcheckDetailPath": str(detail_path),
                "pairReleaseWritten": False,
            },
        )
        raise RuntimeError("Target-station postcheck failed; pair will not be published")
    committed = {
        "schemaVersion": "target-station-publication-gate/v1",
        "stationPlanPath": str(station_plan_path),
        "stationPlanSha256": _sha256(station_plan_path),
        "cadResultPath": str(cad_result_path),
        "cadResultSha256": _sha256(cad_result_path),
        "savedStatePath": str(state_path),
        "savedStateSha256": _sha256(state_path),
        "postcheckDetailPath": str(detail_path),
        "postcheckDetailSha256": _sha256(detail_path),
        "targetStationValidated": True,
        "pairReleaseWritten": False,
    }
    _write_once(committed_path, committed)
    return committed


def _compare_external_transforms(first: list, second: list) -> tuple[float, float]:
    if len(first) < 12 or len(second) < 12:
        raise RuntimeError("Flexible placement witness has an incomplete transform")
    rotation_error = max(abs(float(first[i]) - float(second[i])) for i in range(9))
    translation_error = math.sqrt(
        sum((float(first[i]) - float(second[i])) ** 2 for i in range(9, 12))
    )
    return translation_error, rotation_error


def _refresh_canonical_datum_catalog() -> dict:
    catalog = build_parameterized_datum_placement_catalog(ROOT)
    temporary = CANONICAL_DATUM_CATALOG.with_suffix(".json.tmp")
    if temporary.exists():
        temporary.unlink()
    _write(temporary, catalog)
    os.replace(temporary, CANONICAL_DATUM_CATALOG)
    return catalog


def _global_definition_id(catalog: dict, identity: str) -> str:
    project_id, module_token = identity.split("::", 1)
    matches = [
        row
        for row in catalog.get("moduleDefinitions") or []
        if any(
            alias.get("projectId") == project_id
            and alias.get("moduleToken") == module_token
            for alias in row.get("projectAliases") or []
        )
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"Existing relation release cannot resolve exact identity: {identity}"
        )
    return str(matches[0]["moduleDefinitionId"])


def _load_existing_relation_release(
    release_root: Path, pair_release: dict, release_id: str
) -> dict:
    """Authenticate an immutable release written before a later-stage failure."""

    manifest_path = release_root / "release-manifest.json"
    catalog, manifest = load_relation_catalog_release(
        manifest_path, workspace_root=ROOT
    )
    if manifest.get("releaseId") != release_id:
        raise RuntimeError("Existing relation release identity differs from the pair")
    metadata = manifest.get("releaseMetadata") or {}
    if metadata.get("parameterizedDatumPairBinding") != pair_release:
        raise RuntimeError("Existing relation release is bound to different pair evidence")
    template_ids = [str(value) for value in manifest.get("derivedTemplateIds") or []]
    if len(template_ids) != 1:
        raise RuntimeError("Existing datum relation release must contain one template")
    relative_manifest = manifest_path.resolve().relative_to(ROOT.resolve()).as_posix()
    return {
        "releaseId": release_id,
        "releaseDigest": manifest["releaseDigest"],
        "releaseManifestPath": relative_manifest,
        "globalTemplateId": template_ids[0],
        "moduleDefinitionId": pair_release["moduleDefinitionId"],
        "slotDefinitionId": pair_release["slotDefinitionId"],
        "globalModuleDefinitionId": _global_definition_id(
            catalog, str(pair_release["moduleDefinitionId"])
        ),
        "globalSlotDefinitionId": _global_definition_id(
            catalog, str(pair_release["slotDefinitionId"])
        ),
        "relationExecutionMode": "datum_placement_demo",
        "physicalFasteningVerified": False,
        "collisionOrBrep": "not_evaluated",
        "cadStarted": False,
    }


def _require_exact_parameterized_authority(
    authority: dict, relation: dict, pair_release: dict
) -> None:
    """Require the executable authority to select this validated release.

    A native/direct release may legitimately have higher global preference than
    a newly validated datum candidate.  That does not make the new candidate
    the authority used by a cumulative chain, so fail closed instead of writing
    a binding that claims the two are the same execution decision.
    """

    expected_manifest = str(relation.get("releaseManifestPath") or "")
    if (
        authority.get("ready") is not True
        or authority.get("moduleDefinitionId")
        != pair_release.get("moduleDefinitionId")
        or authority.get("slotDefinitionId") != pair_release.get("slotDefinitionId")
        or authority.get("selectedMode") != "parameterized_datum_placement"
        or authority.get("relationExecutionMode") != "datum_placement_demo"
        or authority.get("releaseManifestPath") != expected_manifest
    ):
        raise RuntimeError(
            "Validated datum release is not the authority selected for cumulative "
            "execution; selected="
            + str(authority.get("releaseManifestPath"))
            + ", validated="
            + expected_manifest
        )


def _publish_relation_authority(candidate: Path) -> dict:
    pair_release = _read(candidate / "pair-release.json")
    release_id = derive_parameterized_datum_relation_release_id(pair_release)
    release_root = ROOT / "demo/global_assembly_catalog/releases" / release_id
    binding_path = candidate / "relation-release-binding.json"
    if binding_path.exists():
        binding = _read(binding_path)
        if binding.get("pairReleaseDigest") != pair_release.get("releaseDigest"):
            raise RuntimeError("Existing relation binding differs from pair evidence")
        relation = binding.get("relationRelease") or {}
        current_authority = resolve_preferred_released_interface_authority(
            ROOT,
            str(pair_release["moduleDefinitionId"]),
            selected_slot_definition_id=str(pair_release["slotDefinitionId"]),
            allow_datum_fallback=True,
        )
        _require_exact_parameterized_authority(
            current_authority, relation, pair_release
        )
        stored_authority = binding.get("naturalLanguageAuthority") or {}
        _require_exact_parameterized_authority(
            stored_authority, relation, pair_release
        )
        return binding
    relation = (
        _load_existing_relation_release(release_root, pair_release, release_id)
        if release_root.exists()
        else publish_parameterized_datum_relation_release(
            ROOT,
            candidate,
            release_id,
            BASE_CATALOG,
        )
    )
    safety_supersession = publish_candidate_reuse_safety_supersession(
        ROOT,
        candidate,
        ROOT / relation["releaseManifestPath"],
    )
    catalog = _refresh_canonical_datum_catalog()
    authority = resolve_preferred_released_interface_authority(
        ROOT,
        str(pair_release["moduleDefinitionId"]),
        selected_slot_definition_id=str(pair_release["slotDefinitionId"]),
        allow_datum_fallback=True,
    )
    _require_exact_parameterized_authority(authority, relation, pair_release)
    binding = {
        "schemaVersion": "parameterized-datum-relation-release-binding/v1",
        "pairReleaseDigest": pair_release["releaseDigest"],
        "relationRelease": relation,
        "candidateReuseSafetySupersession": safety_supersession,
        "canonicalDatumCatalogDigest": catalog["catalogDigest"],
        "naturalLanguageAuthority": authority,
        "claimBoundary": (
            "This exact pair is authorized for datum-placement CAD execution. "
            "Physical fastening, collision and production approval remain separate."
        ),
    }
    _write(binding_path, binding)
    return binding


def _publish_direct_relation_authority(candidate: Path) -> dict:
    recovery = ensure_direct_interface_relation_release(
        ROOT,
        candidate,
        BASE_GLOBAL_CATALOG,
    )
    pair_release = recovery["pairRelease"]
    relation = recovery["relationRelease"]
    catalog = _refresh_canonical_datum_catalog()
    authority = resolve_preferred_released_interface_authority(
        ROOT,
        str(pair_release["moduleDefinitionId"]),
        selected_slot_definition_id=str(pair_release["slotDefinitionId"]),
        allow_datum_fallback=False,
    )
    if (
        authority.get("ready") is not True
        or authority.get("selectedMode") != "mechanical_interface"
        or authority.get("relationExecutionMode") != "direct_installation"
        or authority.get("releaseManifestPath")
        != relation.get("releaseManifestPath")
    ):
        raise RuntimeError(
            "Direct relation release was written but exact natural-language "
            "authority did not resolve: " + str(authority.get("status"))
        )
    binding = {
        "schemaVersion": "direct-interface-relation-release-binding/v1",
        "pairReleaseDigest": pair_release["releaseDigest"],
        "relationRelease": relation,
        "canonicalDatumCatalogDigest": catalog["catalogDigest"],
        "naturalLanguageAuthority": authority,
        "claimBoundary": (
            "This exact pair is authorized for direct mechanical CAD "
            "installation. Actual fastening, collision/B-rep and production "
            "approval remain separate."
        ),
    }
    binding_path = candidate / "relation-release-binding.json"
    if binding_path.exists():
        if _read(binding_path) != binding:
            raise RuntimeError(
                "Existing direct relation binding differs from authenticated evidence"
            )
    else:
        _write(binding_path, binding)
    return binding


def _recover_pending_publication(status: dict) -> dict | None:
    cad_pending = next(
        (
            row
            for row in status["pairs"]
            if row.get("runtimeState")
            in {
                "cad_succeeded_pending_pair_release",
                "cad_succeeded_pending_target_station_postcheck",
                "target_station_postcheck_succeeded_pending_pair_release",
            }
        ),
        None,
    )
    if cad_pending:
        candidate = Path(cad_pending["candidateDirectory"])
        _run_required_target_station_postcheck(candidate, cad_pending)
        package = _read(candidate / "validation-package.json")
        if package.get("schemaVersion") == DIRECT_PACKAGE_SCHEMA:
            return _publish_direct_relation_authority(candidate)
        result = _read(candidate / "cad-result.json")
        pair_release = publish_parameterized_datum_pair_release(package, result)
        _write(candidate / "pair-release.json", pair_release)
        return _publish_relation_authority(candidate)
    relation_pending = next(
        (
            row
            for row in status["pairs"]
            if row.get("runtimeState") == "pair_released_pending_relation_release"
        ),
        None,
    )
    if relation_pending:
        candidate = Path(relation_pending["candidateDirectory"])
        package = _read(candidate / "validation-package.json")
        return (
            _publish_direct_relation_authority(candidate)
            if package.get("schemaVersion") == DIRECT_PACKAGE_SCHEMA
            else _publish_relation_authority(candidate)
        )
    return None


def _write_successor_queue(queue_dir: Path, successor_dir: Path) -> dict:
    prior = _read(queue_dir / "validation-queue.json")
    successor = build_successor_parameterized_datum_validation_queue(ROOT, prior)
    write_parameterized_datum_validation_queue(
        successor_dir,
        successor,
        materialize_packages=True,
    )
    return {
        "queueDirectory": str(successor_dir.resolve()),
        "queueDigest": successor["queueDigest"],
        "sourceCatalogDigest": successor["sourceCatalogDigest"],
        "summary": successor["summary"],
        "lineage": successor["lineage"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=[
            "status",
            "plan-next",
            "run-next",
            "refresh-successor",
            "materialize-station-candidate",
        ],
    )
    parser.add_argument("queue_dir", type=Path)
    parser.add_argument("--session-check-timeout", type=float, default=120.0)
    parser.add_argument(
        "--successor-queue-dir",
        type=Path,
        help=(
            "After an exact pair publication advances the canonical catalog, "
            "write a materialized immutable successor queue with parent lineage."
        ),
    )
    parser.add_argument(
        "--candidate-package",
        type=Path,
        help=(
            "For materialize-station-candidate, the validation-package.json "
            "written by plan-stations --prepare-candidates."
        ),
    )
    args = parser.parse_args()

    queue_dir = args.queue_dir.resolve()
    if args.action == "materialize-station-candidate":
        if args.candidate_package is None:
            parser.error(
                "materialize-station-candidate requires --candidate-package"
            )
        result = materialize_station_candidate_validation_queue(
            ROOT,
            args.candidate_package.resolve(),
            queue_dir,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.action == "status":
        print(
            json.dumps(
                inspect_materialized_validation_queue(queue_dir),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.action == "refresh-successor":
        if args.successor_queue_dir is None:
            parser.error("refresh-successor requires --successor-queue-dir")
        result = _write_successor_queue(
            queue_dir, args.successor_queue_dir.resolve()
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    status = inspect_materialized_validation_queue(queue_dir)
    recoverable = [
        row
        for row in status["pairs"]
        if row.get("runtimeState")
        in {
            "cad_succeeded_pending_pair_release",
            "cad_succeeded_pending_target_station_postcheck",
            "target_station_postcheck_succeeded_pending_pair_release",
            "pair_released_pending_relation_release",
        }
    ]
    if args.action == "plan-next" and recoverable:
        print(
            json.dumps(
                {
                    "schemaVersion": "parameterized-datum-validation-recovery-plan/v1",
                    "action": (
                        "finish_target_station_postcheck_then_publication_without_"
                        "rerunning_cad"
                    ),
                    "pair": recoverable[0],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.action == "run-next":
        recovered = _recover_pending_publication(status)
        if recovered is not None:
            payload = {"relationReleaseBinding": recovered}
            if args.successor_queue_dir is not None:
                payload["successorQueue"] = _write_successor_queue(
                    queue_dir, args.successor_queue_dir.resolve()
                )
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0

    plan = plan_next_parameterized_datum_validation(ROOT, queue_dir)
    if args.action == "plan-next":
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    baseline = capture_open_document_baseline(timeout=args.session_check_timeout)
    if int(baseline.get("openDocumentCount") or 0) != 0:
        raise RuntimeError(
            "SolidWorks validation requires an empty document session; "
            f"observed {baseline.get('openDocumentCount')} open documents."
        )
    candidate = Path(plan["candidateDirectory"])
    attempt_path = candidate / "validation-execution-attempt.json"
    if attempt_path.exists():
        raise FileExistsError(f"Refusing to overwrite validation attempt: {attempt_path}")
    attempt = {
        "schemaVersion": "parameterized-datum-validation-execution-attempt/v1",
        "startedAtUtc": datetime.now(timezone.utc).isoformat(),
        "plan": plan,
        "solidWorksBaseline": baseline,
        "finishedAtUtc": None,
        "returnCode": None,
        "pairReleaseWritten": False,
    }
    _write(attempt_path, attempt)
    completed = subprocess.run(plan["command"], cwd=ROOT, check=False)
    attempt["finishedAtUtc"] = datetime.now(timezone.utc).isoformat()
    attempt["returnCode"] = completed.returncode
    if completed.returncode != 0:
        _write(attempt_path, attempt)
        return completed.returncode

    if plan.get("repeatCommand"):
        repeatability_kind = str(
            plan.get("repeatabilityKind") or "flexible_external_pose"
        )
        repeat_baseline = capture_open_document_baseline(
            timeout=args.session_check_timeout
        )
        attempt["repeatSolidWorksBaseline"] = repeat_baseline
        if int(repeat_baseline.get("openDocumentCount") or 0) != 0:
            attempt["returnCode"] = 2
            attempt["repeatFailure"] = (
                "External-placement repeatability run requires an empty document session"
            )
            _write(attempt_path, attempt)
            return 2
        repeated = subprocess.run(plan["repeatCommand"], cwd=ROOT, check=False)
        attempt["repeatReturnCode"] = repeated.returncode
        if repeated.returncode != 0:
            attempt["returnCode"] = repeated.returncode
            _write(attempt_path, attempt)
            return repeated.returncode
        primary_result_path = Path(plan["cadResultPath"])
        repeat_result_path = Path(plan["repeatCadResultPath"])
        primary_result = _read(primary_result_path)
        repeat_result = _read(repeat_result_path)
        primary_transform = list(
            (primary_result.get("toolResult") or {}).get(
                "ReopenedTargetRootTransform"
            )
            or []
        )
        repeat_transform = list(
            (repeat_result.get("toolResult") or {}).get(
                "ReopenedTargetRootTransform"
            )
            or []
        )
        translation_error, rotation_error = _compare_external_transforms(
            primary_transform, repeat_transform
        )
        tolerance_m = 1e-8
        rotation_tolerance = 1e-8
        repeatability = {
            "schemaVersion": "external-placement-repeatability/v1",
            "repeatabilityKind": repeatability_kind,
            "moduleDefinitionId": plan["moduleDefinitionId"],
            "slotDefinitionId": plan["slotDefinitionId"],
            "initialPlacementVariants": [1, 2],
            "primaryCadResultPath": str(primary_result_path.resolve()),
            "primaryEffectiveGraphSha256": plan["effectiveGraphSha256"],
            "repeatCadResultPath": str(repeat_result_path.resolve()),
            "repeatCadResultSha256": _sha256(repeat_result_path),
            "repeatEffectiveGraphSha256": plan[
                "repeatEffectiveGraphSha256"
            ],
            "translationErrorMeters": translation_error,
            "rotationResidual": rotation_error,
            "translationToleranceMeters": tolerance_m,
            "rotationTolerance": rotation_tolerance,
            "bothRunsSucceeded": primary_result.get("success") is True
            and repeat_result.get("success") is True,
            "passed": primary_result.get("success") is True
            and repeat_result.get("success") is True
            and translation_error <= tolerance_m
            and rotation_error <= rotation_tolerance,
            "claimBoundary": (
                "This witness proves only that two deterministic non-prototype "
                "initial poses converge to the same external module root pose. "
                "Internal motion, fastening, collision/B-rep and production "
                "approval remain outside this validation."
            ),
        }
        repeatability_path = Path(plan["repeatabilityEvidencePath"])
        _write(repeatability_path, repeatability)
        result_field = (
            "flexibleExternalPlacementRepeatability"
            if repeatability_kind == "flexible_external_pose"
            else "externalPlacementRepeatability"
        )
        primary_result[result_field] = {
            "path": str(repeatability_path.resolve()),
            "sha256": _sha256(repeatability_path),
            "passed": repeatability["passed"],
            "translationErrorMeters": translation_error,
            "rotationResidual": rotation_error,
        }
        if repeatability["passed"] is not True:
            primary_result["success"] = False
            primary_result["failureReason"] = (
                "flexible external placement was not repeatable from two "
                "non-prototype initial poses"
            )
        _write(primary_result_path, primary_result)
        attempt[result_field] = repeatability
        if repeatability["passed"] is not True:
            attempt["returnCode"] = 2
            _write(attempt_path, attempt)
            return 2

    package = _read(Path(plan["validationPackagePath"]))
    cad_result = _read(Path(plan["cadResultPath"]))
    station_postcheck = _run_required_target_station_postcheck(candidate, plan)
    if package.get("schemaVersion") == DIRECT_PACKAGE_SCHEMA:
        relation_binding = _publish_direct_relation_authority(candidate)
        pair_release = _read(candidate / "pair-release.json")
    else:
        pair_release = publish_parameterized_datum_pair_release(package, cad_result)
        release_path = Path(plan["pairReleasePath"])
        if release_path.exists():
            raise FileExistsError(f"Refusing to overwrite pair release: {release_path}")
        _write(release_path, pair_release)
        relation_binding = _publish_relation_authority(candidate)
    attempt["pairReleaseWritten"] = True
    attempt["targetStationPostcheck"] = station_postcheck
    attempt["pairReleaseDigest"] = pair_release["releaseDigest"]
    attempt["relationReleaseWritten"] = True
    attempt["relationReleaseId"] = relation_binding["relationRelease"]["releaseId"]
    attempt["naturalLanguageAuthorityReady"] = True
    _write(attempt_path, attempt)
    successor = None
    if args.successor_queue_dir is not None:
        successor = _write_successor_queue(
            queue_dir, args.successor_queue_dir.resolve()
        )
        attempt["successorQueueWritten"] = True
        attempt["successorQueueDirectory"] = successor["queueDirectory"]
        attempt["successorQueueDigest"] = successor["queueDigest"]
        _write(attempt_path, attempt)
    print(
        json.dumps(
            {
                "pairRelease": pair_release,
                "relationReleaseBinding": relation_binding,
                "successorQueue": successor,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
