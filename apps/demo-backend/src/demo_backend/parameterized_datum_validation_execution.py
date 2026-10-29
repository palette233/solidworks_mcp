"""Plan one safe CAD run from a materialized datum validation queue.

This module does not connect to SolidWorks.  It validates immutable inputs,
classifies on-disk evidence and emits the exact adapter command for the next
pending pair.  The CLI wrapper owns the explicit clean-session check and the
actual subprocess invocation.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any

from .direct_interface_relation_release import (
    plan_direct_interface_cad_validation,
)
from .mechanical_interface_contracts import MechanicalInterfaceContractError
from .parameterized_datum_placement import (
    compile_parameterized_datum_validation_package,
    load_parameterized_datum_placement_catalog,
)


QUEUE_SCHEMA = "parameterized-datum-validation-queue/v1"
PACKAGE_SCHEMA = "parameterized-datum-validation-package/v1"
DIRECT_PACKAGE_SCHEMA = "direct-interface-cad-validation-package/v1"
PAIR_RELEASE_SCHEMA = "parameterized-datum-pair-release/v1"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _slug(definition_id: str) -> str:
    return definition_id.replace("::", "-").lower()


def materialize_station_candidate_validation_queue(
    workspace: Path,
    candidate_package_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Materialize one planned station candidate for the existing CAD runner.

    ``plan-stations --prepare-candidates`` deliberately cannot authorize a
    normal cumulative run.  This bridge keeps that boundary: it copies the
    already compiled candidate into a one-item, immutable, stop-on-failure
    validation queue.  No pair-specific CAD adapter is introduced.
    """

    workspace = workspace.resolve()
    candidate_package_path = candidate_package_path.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite validation queue: {output_dir}")
    if not candidate_package_path.is_file():
        raise FileNotFoundError(candidate_package_path)

    package = _read(candidate_package_path)
    if package.get("schemaVersion") != PACKAGE_SCHEMA:
        raise MechanicalInterfaceContractError(
            "station candidate must use the parameterized datum validation package"
        )
    if (
        package.get("status") != "ready_for_explicit_nonprototype_cad_validation"
        or package.get("initialPlacementMode") != "deterministic"
        or package.get("prototypeTopLevelTargetPoseUsed") is not False
        or package.get("caseAnchorUsed") is not False
        or package.get("targetLeafPoseAnchorsUsed") is not False
        or package.get("readyForReleasedCadExecution") is not False
        or package.get("validationRequiredBeforeRelease") is not True
    ):
        raise MechanicalInterfaceContractError(
            "station candidate does not preserve the non-prototype validation boundary"
        )

    station_plan_path = candidate_package_path.parent / "station-plan.json"
    if not station_plan_path.is_file():
        raise MechanicalInterfaceContractError(
            "station candidate is missing its target-station plan"
        )
    station_plan = _read(station_plan_path)
    embedded_package = station_plan.get("validationPackage") or {}
    if (
        station_plan.get("schemaVersion") != "target-station-stage-plan/v1"
        or station_plan.get("sourceModuleDefinitionId")
        != package.get("moduleDefinitionId")
        or station_plan.get("targetBaseDefinitionId")
        != package.get("slotDefinitionId")
        or station_plan.get("requiresFreshCadValidation") is not True
        or station_plan.get("targetStationValidated") is not False
        or station_plan.get("cadLaunchAllowed") is not False
        or embedded_package.get("packageDigest") != package.get("packageDigest")
    ):
        raise MechanicalInterfaceContractError(
            "station plan does not bind the unreleased validation package"
        )

    source = Path(str(package.get("sourceAssemblyPath") or ""))
    if not source.is_file() or _sha256(source) != package.get("sourceAssemblySha256"):
        raise MechanicalInterfaceContractError("station candidate source assembly changed")
    artifacts = package.get("artifacts") or {}
    required_artifacts: dict[str, tuple[Path, str]] = {}
    for key, filename in (
        ("effectiveGraph", "effective-mate-graph.json"),
        ("selectedEndpointCatalog", "selected-face-endpoint-catalog.json"),
    ):
        binding = artifacts.get(key) or {}
        source_path = Path(str(binding.get("path") or ""))
        if not source_path.is_file() or _sha256(source_path) != binding.get("sha256"):
            raise MechanicalInterfaceContractError(
                f"station candidate artifact changed: {key}"
            )
        required_artifacts[key] = (source_path, filename)

    graph = _read(required_artifacts["effectiveGraph"][0])
    policy = graph.get("EditPolicy") or {}
    base_token = str(package.get("baseModuleToken") or "")
    target_token = str(package.get("targetModuleToken") or "")
    if (
        not base_token
        or not target_token
        or base_token == target_token
        or policy.get("initialPlacementMode") != "deterministic"
        or policy.get("fixedModuleTokens") != [base_token]
        or policy.get("caseAnchoredModuleTokens")
        or policy.get("targetLeafPoseAnchors")
        or graph.get("CaseAnchor")
        or graph.get("TargetLeafPoseAnchors")
        or target_token in (policy.get("fixedModuleTokens") or [])
    ):
        raise MechanicalInterfaceContractError(
            "station candidate graph uses a fixed target or prototype pose anchor"
        )

    repeat_effective_graph: dict[str, Any] | None = None
    if (package.get("finiteSupportGate") or {}).get("required") is True:
        repeat_package = compile_parameterized_datum_validation_package(
            workspace,
            str(package.get("moduleDefinitionId") or ""),
            str(package.get("slotDefinitionId") or ""),
            initial_placement_variant=2,
            position_parameters=package.get("effectivePositionParameters") or None,
            distance_flip_dimensions=(
                package.get("effectiveDistanceFlipDimensions") or None
            ),
            bounded_role_station_candidate=package.get(
                "boundedRoleStationCandidate"
            ),
        )
        repeat_effective_graph = repeat_package.get("effectiveGraph")
        repeat_policy = (repeat_effective_graph or {}).get("EditPolicy") or {}
        if (
            not isinstance(repeat_effective_graph, dict)
            or repeat_policy.get("initialPlacementVariant") != 2
            or repeat_policy.get("fixedModuleTokens") != [base_token]
            or repeat_policy.get("caseAnchoredModuleTokens")
            or repeat_policy.get("targetLeafPoseAnchors")
        ):
            raise MechanicalInterfaceContractError(
                "finite-support station candidate has no safe repeat-placement graph"
            )

    catalog = load_parameterized_datum_placement_catalog(workspace)
    module_definition_id = str(package.get("moduleDefinitionId") or "")
    slot_definition_id = str(package.get("slotDefinitionId") or "")
    module_contracts = [
        row
        for row in catalog.get("contracts") or []
        if row.get("side") == "moving_module"
        and row.get("moduleDefinitionId") == module_definition_id
    ]
    module_role = (
        str(module_contracts[0].get("moduleRole") or "")
        if len(module_contracts) == 1
        else ""
    )
    slot_contracts = [
        row
        for row in catalog.get("contracts") or []
        if row.get("side") == "base_slot"
        and row.get("moduleDefinitionId") == slot_definition_id
        and module_role in (row.get("acceptedModuleRoles") or [])
    ]
    if len(module_contracts) != 1 or len(slot_contracts) != 1:
        raise MechanicalInterfaceContractError(
            "station candidate pair is absent or ambiguous in the current datum catalog"
        )

    candidate_name = (
        "validation-"
        + _slug(module_definition_id)
        + "-"
        + _slug(slot_definition_id)
        + "-station-v1"
    )
    candidate_dir = output_dir / candidate_name
    output_dir.mkdir(parents=True)
    try:
        candidate_dir.mkdir()
        materialized_package = json.loads(json.dumps(package))
        materialized_package["artifacts"] = {}
        for key, (source_path, filename) in required_artifacts.items():
            destination = candidate_dir / filename
            shutil.copy2(source_path, destination)
            materialized_package["artifacts"][key] = {
                "path": str(destination.resolve()),
                "sha256": _sha256(destination),
            }
        if repeat_effective_graph is not None:
            repeat_destination = candidate_dir / "effective-mate-graph-repeat.json"
            repeat_destination.write_text(
                json.dumps(repeat_effective_graph, ensure_ascii=False, indent=2)
                + "\n",
                encoding="utf-8",
            )
            materialized_package["externalPlacementRepeatabilityRequired"] = True
            materialized_package["externalPlacementRepeatabilityKind"] = (
                "rigid_finite_support_pose"
            )
            materialized_package["artifacts"]["repeatEffectiveGraph"] = {
                "path": str(repeat_destination.resolve()),
                "sha256": _sha256(repeat_destination),
                "initialPlacementVariant": 2,
            }
        package_copy = candidate_dir / "validation-package.json"
        package_copy.write_text(
            json.dumps(materialized_package, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        station_plan_copy = candidate_dir / "station-plan.json"
        shutil.copy2(station_plan_path, station_plan_copy)
        row = {
            "moduleDefinitionId": module_definition_id,
            "slotDefinitionId": slot_definition_id,
            "moduleRole": module_role,
            "moduleToken": target_token,
            "baseToken": base_token,
            "crossProject": module_definition_id.split("::", 1)[0]
            != slot_definition_id.split("::", 1)[0],
            "interfaceFamily": (materialized_package.get("instantiatedTemplate") or {}).get(
                "interfaceFamily"
            ),
            "recipeId": (materialized_package.get("instantiatedTemplate") or {}).get(
                "recipeId"
            ),
            "candidateKind": "planned_target_station_parameterized_datum",
            "proposedValidationDirectory": candidate_name,
            "physicalFasteningVerified": False,
            "productionReady": False,
            "collisionOrBrep": "not_evaluated",
            "state": "ready_for_nonprototype_cad_validation",
            "readyForCadValidation": True,
            "readyForReleasedCadExecution": False,
            "validationPackageDigest": materialized_package.get("packageDigest"),
            "sourceStationCandidatePath": str(candidate_package_path),
            "sourceStationCandidateSha256": _sha256(candidate_package_path),
            "stationPlanPath": str(station_plan_copy.resolve()),
            "stationPlanSha256": _sha256(station_plan_copy),
            "requiresTargetStationPostcheckBeforePublication": True,
            "nextAction": (
                "run_nonprototype_cad_validate_save_reopen_then_target_station_"
                "postcheck_then_publish"
            ),
        }
        summary = {
            "listedPairCount": 1,
            "compatiblePairCount": 1,
            "catalogCompatiblePairCount": 1,
            "effectiveCompatiblePairCount": 1,
            "releasedPairCount": 0,
            "readyForCadValidationCount": 1,
            "blockedBeforeCadCount": 0,
            "explicitPositionParametersRequiredCount": 0,
            "confirmedExplicitPositionParameterCount": 1,
            "explicitAxisSelectionRequiredCount": 0,
            "confirmedExplicitAxisSelectionCount": 0,
            "explicitAxisPairSelectionRequiredCount": 0,
            "confirmedExplicitAxisPairSelectionCount": 0,
            "explicitFlexibleSlotSelectionRequiredCount": 0,
            "confirmedExplicitFlexibleSlotSelectionCount": 0,
            "axisPairNotFoundInAuthoritativeCatalogCount": 0,
            "flexibleSlotAxisNotFoundInAuthoritativeCatalogCount": 0,
            "crossProjectCompatiblePairCount": int(row["crossProject"]),
            "crossProjectReadyForCadValidationCount": int(row["crossProject"]),
            "crossProjectExplicitPositionParametersRequiredCount": 0,
            "crossProjectExplicitAxisSelectionRequiredCount": 0,
            "crossProjectExplicitAxisPairSelectionRequiredCount": 0,
            "crossProjectExplicitFlexibleSlotSelectionRequiredCount": 0,
            "crossProjectAxisPairNotFoundInAuthoritativeCatalogCount": 0,
            "crossProjectFlexibleSlotAxisNotFoundInAuthoritativeCatalogCount": 0,
            "captureGapCount": 0,
        }
        queue = {
            "schemaVersion": QUEUE_SCHEMA,
            "sourceCatalogDigest": catalog["catalogDigest"],
            "summary": summary,
            "pairs": [row],
            "captureGaps": [],
            "explicitPositionParameterEvidence": [],
            "explicitAxisSelectionEvidence": [],
            "explicitAxisPairSelectionEvidence": [],
            "explicitFlexibleSlotSelectionEvidence": [],
            "executionPolicy": {
                "cadConcurrency": 1,
                "requireCleanSolidWorksSession": True,
                "candidateDoesNotAuthorizeNormalExecution": True,
                "releaseRequiresSaveCloseReopen": True,
                "releaseRequiresNonPrototypeInitialPose": True,
                "releaseRequiresTargetStationPostcheck": True,
                "continueAfterFailure": False,
            },
            "claimBoundary": (
                "This one-item queue validates a planned target-station candidate. "
                "It does not authorize cumulative execution before exact pair and "
                "relation publication. Fastening, collision/B-rep and production "
                "approval remain separate."
            ),
        }
        queue["queueDigest"] = _digest(queue)
        queue_path = output_dir / "validation-queue.json"
        queue_path.write_text(
            json.dumps(queue, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (output_dir / "README-CN.md").write_text(
            "# 单项工位候选CAD验证队列\n\n"
            f"- 模组：`{module_definition_id}`\n"
            f"- 基座：`{slot_definition_id}`\n"
            "- 策略：单并发、失败即停、非原型初始位姿、保存重开并完成目标工位后检后发布。\n"
            "- 边界：不证明实际紧固、碰撞/B-rep或生产可用性。\n",
            encoding="utf-8",
        )
    except Exception:
        # Preserve any partial evidence for diagnosis.  Never silently delete
        # an output directory after materialization has started.
        raise
    return {
        "schemaVersion": "station-candidate-validation-queue-materialization/v1",
        "queueDirectory": str(output_dir),
        "queueDigest": queue["queueDigest"],
        "candidateDirectory": str(candidate_dir),
        "moduleDefinitionId": module_definition_id,
        "slotDefinitionId": slot_definition_id,
        "cadStarted": False,
    }


def derive_parameterized_datum_relation_release_id(
    pair_release: dict[str, Any]
) -> str:
    """Return a deterministic filesystem-safe relation release identity."""

    if pair_release.get("schemaVersion") != PAIR_RELEASE_SCHEMA:
        raise MechanicalInterfaceContractError("unsupported datum pair release schema")
    digest = str(pair_release.get("releaseDigest") or "")
    module = str(pair_release.get("moduleDefinitionId") or "")
    slot = str(pair_release.get("slotDefinitionId") or "")
    if len(digest) != 64 or not module or not slot:
        raise MechanicalInterfaceContractError("datum pair release identity is incomplete")
    release_id = f"relation-datum-{_slug(module)}-{_slug(slot)}-{digest[:12]}"
    if any(
        char
        not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
        for char in release_id
    ):
        raise MechanicalInterfaceContractError("derived relation release id is unsafe")
    return release_id


def load_materialized_validation_queue(queue_dir: Path) -> dict[str, Any]:
    """Load and authenticate one immutable, materialized queue directory."""

    root = queue_dir.resolve()
    manifest = root / "validation-queue.json"
    if not manifest.is_file():
        raise FileNotFoundError(manifest)
    queue = _read(manifest)
    if queue.get("schemaVersion") != QUEUE_SCHEMA:
        raise MechanicalInterfaceContractError("unsupported validation queue schema")
    expected = _digest(
        {key: value for key, value in queue.items() if key != "queueDigest"}
    )
    if queue.get("queueDigest") != expected:
        raise MechanicalInterfaceContractError("validation queue digest mismatch")
    policy = queue.get("executionPolicy") or {}
    if policy.get("cadConcurrency") != 1 or policy.get("continueAfterFailure") is not False:
        raise MechanicalInterfaceContractError(
            "validation queue must require single CAD concurrency and stop on failure"
        )
    return queue


def inspect_materialized_validation_queue(queue_dir: Path) -> dict[str, Any]:
    """Classify runtime evidence without changing the queue or starting CAD."""

    root = queue_dir.resolve()
    queue = load_materialized_validation_queue(root)
    rows: list[dict[str, Any]] = []
    for source in queue.get("pairs") or []:
        row = dict(source)
        candidate = root / str(row.get("proposedValidationDirectory") or "")
        if row.get("state") != "ready_for_nonprototype_cad_validation":
            row["runtimeState"] = row.get("state")
            rows.append(row)
            continue
        package = candidate / "validation-package.json"
        result = candidate / "cad-result.json"
        release = candidate / "pair-release.json"
        relation_binding = candidate / "relation-release-binding.json"
        station_postcheck = candidate / "station-postcheck.json"
        station_postcheck_error = candidate / "station-postcheck-error.json"
        if relation_binding.is_file():
            runtime_state = "relation_released_for_cumulative_execution"
        elif release.is_file():
            runtime_state = "pair_released_pending_relation_release"
        elif result.is_file():
            if _read(result).get("success") is not True:
                runtime_state = "cad_failed_stop_queue"
            elif row.get("requiresTargetStationPostcheckBeforePublication") is True:
                if station_postcheck.is_file():
                    runtime_state = (
                        "target_station_postcheck_succeeded_pending_pair_release"
                        if _read(station_postcheck).get("targetStationValidated") is True
                        else "target_station_postcheck_failed_stop_queue"
                    )
                elif station_postcheck_error.is_file():
                    runtime_state = "target_station_postcheck_failed_stop_queue"
                else:
                    runtime_state = "cad_succeeded_pending_target_station_postcheck"
            else:
                runtime_state = "cad_succeeded_pending_pair_release"
        elif package.is_file():
            runtime_state = "pending_cad_validation"
        else:
            runtime_state = "materialized_package_missing"
        row.update(
            {
                "runtimeState": runtime_state,
                "candidateDirectory": str(candidate),
            }
        )
        rows.append(row)
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get("runtimeState") or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return {
        "schemaVersion": "parameterized-datum-validation-runtime-status/v1",
        "queueDirectory": str(root),
        "queueDigest": queue["queueDigest"],
        "runtimeStateCounts": counts,
        "pairs": rows,
        "executionPolicy": queue["executionPolicy"],
    }


def plan_next_parameterized_datum_validation(
    workspace: Path, queue_dir: Path
) -> dict[str, Any]:
    """Return the authenticated adapter command for the next pending pair."""

    workspace = workspace.resolve()
    root = queue_dir.resolve()
    queue = load_materialized_validation_queue(root)
    canonical_path = workspace / (
        "demo/cross_project_substitution/parameterized-datum-placement-v1/"
        "interface-contract-catalog.json"
    )
    if not canonical_path.is_file():
        raise FileNotFoundError(canonical_path)
    canonical = _read(canonical_path)
    canonical_digest = str(canonical.get("catalogDigest") or "")
    expected_canonical_digest = _digest(
        {key: value for key, value in canonical.items() if key != "catalogDigest"}
    )
    if not canonical_digest or canonical_digest != expected_canonical_digest:
        raise MechanicalInterfaceContractError(
            "canonical datum catalog digest mismatch"
        )
    if queue.get("sourceCatalogDigest") != canonical_digest:
        raise MechanicalInterfaceContractError(
            "validation queue was compiled from a stale datum catalog"
        )
    status = inspect_materialized_validation_queue(root)
    failed = [
        row for row in status["pairs"] if row.get("runtimeState") == "cad_failed_stop_queue"
    ]
    if failed:
        raise MechanicalInterfaceContractError(
            "validation queue contains a failed CAD pair and is stop-on-failure"
        )
    pending = [
        row for row in status["pairs"] if row.get("runtimeState") == "pending_cad_validation"
    ]
    if not pending:
        raise MechanicalInterfaceContractError("validation queue has no pending CAD pair")
    row = pending[0]
    candidate = Path(row["candidateDirectory"])
    if row.get("requiresTargetStationPostcheckBeforePublication") is True:
        station_plan_path = Path(str(row.get("stationPlanPath") or ""))
        if (
            not station_plan_path.is_file()
            or station_plan_path.parent.resolve() != candidate.resolve()
            or _sha256(station_plan_path) != row.get("stationPlanSha256")
        ):
            raise MechanicalInterfaceContractError(
                "target-station plan changed before CAD validation"
            )
    package_path = candidate / "validation-package.json"
    package = _read(package_path)
    package_schema = package.get("schemaVersion")
    if package_schema == DIRECT_PACKAGE_SCHEMA:
        direct = plan_direct_interface_cad_validation(workspace, candidate)
        for key in ("moduleDefinitionId", "slotDefinitionId"):
            if direct.get(key) != row.get(key):
                raise MechanicalInterfaceContractError(
                    f"direct validation package identity differs from queue row: {key}"
                )
        return {
            "schemaVersion": "parameterized-datum-validation-execution-plan/v1",
            "queueDirectory": str(root),
            "queueDigest": status["queueDigest"],
            "packageKind": "direct_interface",
            "moduleDefinitionId": direct["moduleDefinitionId"],
            "slotDefinitionId": direct["slotDefinitionId"],
            "targetModuleToken": None,
            "candidateDirectory": str(candidate),
            "validationPackagePath": direct["validationPackagePath"],
            "sourceAssemblyPath": direct["sourceAssemblyPath"],
            "sourceAssemblySha256": direct["sourceAssemblySha256"],
            "effectiveGraphPath": direct["effectiveGraphPath"],
            "effectiveGraphSha256": direct["effectiveGraphSha256"],
            "outputAssemblyPath": direct["outputAssemblyPath"],
            "cadResultPath": direct["cadResultPath"],
            "pairReleasePath": direct["pairReleasePath"],
            "command": direct["command"],
            "preconditions": direct["preconditions"],
            "claimBoundary": (
                "This plan validates one exact direct mechanical-interface pair "
                "from a deterministic non-prototype pose. Normal cumulative "
                "execution still requires immutable pair and relation publication; "
                "fastening, collision/B-rep and production approval remain separate."
            ),
        }
    if package_schema != PACKAGE_SCHEMA:
        raise MechanicalInterfaceContractError("unsupported validation package schema")
    for key in ("moduleDefinitionId", "slotDefinitionId"):
        if package.get(key) != row.get(key):
            raise MechanicalInterfaceContractError(
                f"validation package identity differs from queue row: {key}"
            )
    source = Path(str(package.get("sourceAssemblyPath") or ""))
    if not source.is_file() or _sha256(source) != package.get("sourceAssemblySha256"):
        raise MechanicalInterfaceContractError("validation source assembly changed")
    artifacts = package.get("artifacts") or {}
    graph_binding = artifacts.get("effectiveGraph") or {}
    graph = Path(str(graph_binding.get("path") or ""))
    if not graph.is_file() or _sha256(graph) != graph_binding.get("sha256"):
        raise MechanicalInterfaceContractError("validation effective graph changed")
    endpoint_binding = (package.get("artifacts") or {}).get("selectedEndpointCatalog") or {}
    endpoint_catalog = Path(str(endpoint_binding.get("path") or ""))
    if not endpoint_catalog.is_file() or _sha256(endpoint_catalog) != endpoint_binding.get("sha256"):
        raise MechanicalInterfaceContractError("selected endpoint catalog changed")

    output = candidate / (
        _slug(str(package["slotDefinitionId"]))
        + "-"
        + _slug(str(package["moduleDefinitionId"]))
        + "-datum-validation-v1.SLDASM"
    )
    result = candidate / "cad-result.json"
    release = candidate / "pair-release.json"
    for path in (output, result, release):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite validation evidence: {path}")
    adapter = workspace / "scripts/run_context_mate_graph_insert.py"
    if not adapter.is_file():
        raise FileNotFoundError(adapter)
    command = [
        sys.executable,
        str(adapter),
        "--source",
        str(source),
        "--effective",
        str(graph),
        "--output",
        str(output),
        "--target",
        str(package["targetModuleToken"]),
        "--expected-source-sha256",
        str(package["sourceAssemblySha256"]),
        "--expected-effective-sha256",
        str(graph_binding["sha256"]),
        "--result",
        str(result),
        "--direct-stdio",
    ]
    plan = {
        "schemaVersion": "parameterized-datum-validation-execution-plan/v1",
        "queueDirectory": str(root),
        "queueDigest": status["queueDigest"],
        "packageKind": "parameterized_datum",
        "moduleDefinitionId": package["moduleDefinitionId"],
        "slotDefinitionId": package["slotDefinitionId"],
        "targetModuleToken": package["targetModuleToken"],
        "candidateDirectory": str(candidate),
        "validationPackagePath": str(package_path),
        "sourceAssemblyPath": str(source),
        "sourceAssemblySha256": package["sourceAssemblySha256"],
        "effectiveGraphPath": str(graph),
        "effectiveGraphSha256": graph_binding["sha256"],
        "outputAssemblyPath": str(output),
        "cadResultPath": str(result),
        "pairReleasePath": str(release),
        "command": command,
        "preconditions": {
            "solidWorksOpenDocumentCountMustEqual": 0,
            "nonPrototypeInitialPoseRequired": True,
            "saveCloseReopenRequired": True,
            "stopQueueOnFailure": True,
            "targetStationPostcheckRequiredBeforePublication": row.get(
                "requiresTargetStationPostcheckBeforePublication"
            )
            is True,
        },
        "stationPlanPath": row.get("stationPlanPath"),
        "stationPlanSha256": row.get("stationPlanSha256"),
        "requiresTargetStationPostcheckBeforePublication": row.get(
            "requiresTargetStationPostcheckBeforePublication"
        )
        is True,
        "claimBoundary": (
            "This plan validates one exact module/base pair. It does not authorize "
            "normal cumulative execution until pair release is written and the relation "
            "catalog is published. Collision and physical fastening remain separate."
        ),
    }
    repeatability_kind = None
    if package.get("placementMode") == "reviewed_flexible_calibration_slot":
        repeatability_kind = "flexible_external_pose"
    elif package.get("externalPlacementRepeatabilityRequired") is True:
        repeatability_kind = str(
            package.get("externalPlacementRepeatabilityKind")
            or "rigid_external_pose"
        )
    if repeatability_kind:
        repeat_binding = artifacts.get("repeatEffectiveGraph") or {}
        repeat_graph = Path(str(repeat_binding.get("path") or ""))
        if (
            not repeat_graph.is_file()
            or _sha256(repeat_graph) != repeat_binding.get("sha256")
            or repeat_binding.get("initialPlacementVariant") != 2
        ):
            raise MechanicalInterfaceContractError(
                "external-placement repeat graph changed or is missing"
            )
        repeat_output = candidate / (
            _slug(str(package["slotDefinitionId"]))
            + "-"
            + _slug(str(package["moduleDefinitionId"]))
            + "-datum-validation-repeat-v2.SLDASM"
        )
        repeat_result = candidate / "cad-result-repeat-v2.json"
        repeatability = candidate / "external-placement-repeatability.json"
        for path in (repeat_output, repeat_result, repeatability):
            if path.exists():
                raise FileExistsError(
                    f"Refusing to overwrite placement-repeatability evidence: {path}"
                )
        plan.update(
            {
                "repeatEffectiveGraphPath": str(repeat_graph),
                "repeatEffectiveGraphSha256": str(repeat_binding["sha256"]),
                "repeatOutputAssemblyPath": str(repeat_output),
                "repeatCadResultPath": str(repeat_result),
                "repeatabilityEvidencePath": str(repeatability),
                "repeatabilityKind": repeatability_kind,
                "repeatCommand": [
                    sys.executable,
                    str(adapter),
                    "--source",
                    str(source),
                    "--effective",
                    str(repeat_graph),
                    "--output",
                    str(repeat_output),
                    "--target",
                    str(package["targetModuleToken"]),
                    "--expected-source-sha256",
                    str(package["sourceAssemblySha256"]),
                    "--expected-effective-sha256",
                    str(repeat_binding["sha256"]),
                    "--result",
                    str(repeat_result),
                    "--direct-stdio",
                ],
            }
        )
    return plan
