from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any


POSITIVE_CASES: tuple[dict[str, Any], ...] = (
    {
        "caseId": "A1-SS00-AA00",
        "route": "native_role_station",
        "classification": "DIRECT_NATIVE_SLOT_PASS",
        "role": "Transport",
        "source": "project01::SS00",
        "target": "project03::AA00",
        "nativeRole": "project03::AE00",
        "interface": "58 mm support-plane + two-axis station",
        "release": "demo/global_assembly_catalog/releases/relation-v46-project03-aa00-project01-ss00-transport-driving-20261012/release-manifest.json",
        "cad": "demo/global_assembly_contexts/manifest_jobs/project01-job-6e565f3f891c/packet-runs/packet-001-attempt-01/cad-result.json",
    },
    {
        "caseId": "A2-AE00-JJ00",
        "route": "native_role_station",
        "classification": "DIRECT_NATIVE_SLOT_PASS",
        "role": "Transport",
        "source": "project03::AE00",
        "target": "project01::JJ00",
        "nativeRole": "project01::SS00",
        "interface": "58 mm support-plane + two-axis station",
        "release": "demo/global_assembly_catalog/releases/relation-v50-project01-jj00-transport-scanner-calibration-driving-20261014/release-manifest.json",
        "cad": "demo/cross_project_substitution/transport-v1/jobs/project03-job-e64acfa17a55/packet-runs/packet-001-attempt-01/cad-result.json",
    },
    {
        "caseId": "A3-BD00-AA00",
        "route": "native_role_station",
        "classification": "DIRECT_NATIVE_SLOT_PASS",
        "role": "Calibration",
        "source": "project01::BD00",
        "target": "project03::AA00",
        "nativeRole": "project03::AH00",
        "interface": "50 mm support-plane + two-axis station",
        "release": "demo/global_assembly_catalog/releases/relation-v45-project03-aa00-project01-bd00-calibration-driving-20261012/release-manifest.json",
        "cad": "demo/global_assembly_contexts/manifest_jobs/project01-job-220a20fa0493/packet-runs/packet-001-attempt-01/cad-result.json",
    },
    {
        "caseId": "A4-AH00-JJ00",
        "route": "native_role_station",
        "classification": "DIRECT_NATIVE_SLOT_PASS",
        "role": "Calibration",
        "source": "project03::AH00",
        "target": "project01::JJ00",
        "nativeRole": "project01::BD00",
        "interface": "50 mm support-plane + two-axis station",
        "release": "demo/global_assembly_catalog/releases/relation-v44-project01-jj00-project03-ah00-calibration-driving-20261012/release-manifest.json",
        "cad": "demo/cross_project_substitution/mvp-v1/jobs/project03-job-d75711e079d8/packet-runs/packet-001-attempt-01/cad-result.json",
    },
    {
        "caseId": "B6-BD00-A600",
        "route": "matched_mechanical_interface",
        "classification": "MATCHED_ALTERNATE_SLOT_PASS",
        "role": "Calibration",
        "source": "project01::BD00",
        "target": "project02::A600",
        "nativeRole": None,
        "interface": "50 mm support-plane + matched two-axis slot",
        "release": "demo/global_assembly_catalog/releases/relation-direct-project01-bd00-project02-a600-9002a66dbc27/release-manifest.json",
        "cad": "demo/cross_project_substitution/calibration-project01-to-project02-v1/bd00-a600-validation-v3/cad-result.json",
    },
    {
        "caseId": "B7-SS00-A000",
        "route": "matched_mechanical_interface",
        "classification": "MATCHED_ALTERNATE_SLOT_PASS",
        "role": "Transport",
        "source": "project01::SS00",
        "target": "project05::A000",
        "nativeRole": None,
        "interface": "58 mm support-plane + selected two-axis slot",
        "release": "demo/global_assembly_catalog/releases/relation-direct-project01-ss00-project05-a000-092a0d656876/release-manifest.json",
        "cad": "demo/cross_project_substitution/parameterized-datum-placement-v1/validation-queue-20261026-v58-axis-orientation-fix/validation-ss00-a000-v1/cad-result.json",
    },
    {
        "caseId": "B8-GN00-AA00",
        "route": "matched_mechanical_interface",
        "classification": "MATCHED_ALTERNATE_SLOT_PASS",
        "role": "CleaningWeighing",
        "source": "project01::GN00",
        "target": "project03::AA00",
        "nativeRole": None,
        "interface": "204 mm support-plane + matched two-axis slot",
        "release": None,
        "cad": "demo/goal_role_station_and_matched_slot_cases_20261028/gn00-aa00-204mm/cad-result.json",
        "candidate": "demo/goal_role_station_and_matched_slot_cases_20261028/gn00-aa00-204mm/candidate-package.json",
        "firstFailure": "demo/goal_role_station_and_matched_slot_cases_20261028/gn00-aa00-204mm/cad-result.failed-axis-direction-v1.json",
    },
)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _repo_path(root: Path, value: str) -> Path:
    return (root / value).resolve()


def _cad_checks(cad: dict[str, Any]) -> dict[str, bool]:
    tool = cad.get("toolResult") or {}
    requested = int(tool.get("RequestedMateCount", -1))
    created = int(tool.get("CreatedMateCount", -2))
    return {
        "cadSucceeded": cad.get("success") is True and tool.get("Success") is True,
        "independentTargetInserted": tool.get("IndependentComponentInserted") is True,
        "deterministicNonPrototypeStart": any(
            "Deterministic non-source placement" in str(item)
            for item in (tool.get("Diagnostics") or [])
        ),
        "noCaseAnchor": tool.get("TargetCaseAnchored") is False,
        "noLeafPoseAnchors": int(tool.get("AppliedTargetLeafPoseAnchorCount") or 0) == 0,
        "allRequestedMatesCreated": requested > 0 and requested == created,
        "targetConstraintAccepted": tool.get("TargetConstraintStateAccepted") is True,
        "targetFullyConstrained": tool.get("TargetFullyConstrained") is True,
        "mateSolveClean": tool.get("MateSolveClean") is True,
        "saveCloseReopenPassed": (
            tool.get("Reopened") is True
            and tool.get("ReopenedMateParametersMatch") is True
            and cad.get("outputClosedAfterVerification") is True
        ),
        "sourceAssemblyUnchanged": cad.get("sourceAssemblyUnchanged") is True,
        "targetSourceSessionClean": cad.get("targetSourceSessionClean") is True,
    }


def _endpoint_ids(graph: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for mate in graph.get("Mates") or graph.get("mates") or []:
        for endpoint in mate.get("Endpoints") or mate.get("endpoints") or []:
            for endpoint_id in endpoint.get("SemanticEndpointIds") or endpoint.get("semanticEndpointIds") or []:
                if endpoint_id not in result:
                    result.append(str(endpoint_id))
    return result


STATION_CHECKS = (
    "slotMembership",
    "supportAndDirectionBound",
    "installationSideBound",
    "transportContext",
)


def _station_evidence(
    root: Path,
    spec: dict[str, Any],
    cad_path: Path,
    graph_path: Path,
    witness_path: Path | None,
) -> dict[str, Any]:
    """Consume measured station evidence without inventing missing checks.

    CAD success and a matching axis pair do not prove membership in a service
    station. A witness must bind the exact pair and the CAD result/graph, and
    each evaluated check must name its calculation and hash-bound inputs.
    This reporter authenticates that binding; it does not replace the geometry
    evaluator or grant CAD execution authority.
    """
    result: dict[str, Any] = {
        "schemaVersion": "role-station-report-evidence/v1",
        "status": "not_evaluated",
        "passed": None,
        "bindingVerified": False,
        "checks": {
            name: {
                "passed": None,
                "status": "not_evaluated",
                "method": "no_bound_station_measurement",
                "evidence": [],
            }
            for name in STATION_CHECKS
        },
        "validationErrors": [],
        "witnessPath": None,
        "collisionOrBrep": "not_evaluated",
        "actualFastening": "not_verified",
        "readOnly": True,
        "cadExecutionAuthorized": False,
        "scope": "station_evidence_validation_only",
    }
    if witness_path is None:
        return result
    path = _repo_path(root, str(witness_path))
    result["witnessPath"] = str(path)
    try:
        witness = _read_json(path)
        result["witnessSha256"] = _sha256(path)
        expected = {
            "schemaVersion": "role-station-witness/v1",
            "caseId": spec["caseId"],
            "source": spec["source"],
            "target": spec["target"],
            "cadResultSha256": _sha256(cad_path),
            "effectiveGraphSha256": _sha256(graph_path),
        }
        errors = [f"binding_mismatch:{key}" for key, value in expected.items() if witness.get(key) != value]
        # The witness digest alone is insufficient: a copied result can point
        # at another execution graph, or its output can have changed on disk.
        # Follow the CAD envelope and check both the recorded and current bytes.
        cad = _read_json(cad_path)
        graph_key = "executionEffectiveGraph" if cad.get("executionEffectiveGraphPath") else "effectiveGraph"
        envelope_graph_value = cad.get(f"{graph_key}Path")
        envelope_graph = _repo_path(root, str(envelope_graph_value)) if envelope_graph_value else None
        if envelope_graph is None or not envelope_graph.is_file():
            errors.append("cad_execution_graph_missing")
        else:
            actual_graph_digest = _sha256(envelope_graph)
            if cad.get(f"{graph_key}Sha256") != actual_graph_digest:
                errors.append("cad_execution_graph_digest_mismatch")
            if actual_graph_digest != expected["effectiveGraphSha256"]:
                errors.append("cad_execution_graph_not_witness_graph")
        output_value = cad.get("outputAssemblyPath")
        output_path = _repo_path(root, str(output_value)) if output_value else None
        if output_path is None or not output_path.is_file():
            errors.append("cad_output_assembly_missing")
        else:
            actual_output_digest = _sha256(output_path)
            if cad.get("outputAssemblySha256") != actual_output_digest:
                errors.append("cad_output_assembly_digest_mismatch")
            if "outputAssemblySha256" in witness and witness["outputAssemblySha256"] != actual_output_digest:
                errors.append("binding_mismatch:outputAssemblySha256")
        for name in STATION_CHECKS:
            check = (witness.get("checks") or {}).get(name)
            if not isinstance(check, dict):
                errors.append(f"missing_check:{name}")
                continue
            passed = check.get("passed")
            if passed is not None and type(passed) is not bool:
                errors.append(f"invalid_check_result:{name}")
                continue
            allowed_statuses = {"not_evaluated", "review_required"} if passed is None else ({"passed"} if passed else {"failed"})
            if check.get("status") not in allowed_statuses:
                errors.append(f"inconsistent_check_status:{name}")
            if not isinstance(check.get("method"), str) or not check["method"].strip():
                errors.append(f"missing_check_method:{name}")
            evidence = check.get("evidence")
            if not isinstance(evidence, list) or (passed is not None and not evidence):
                errors.append(f"missing_check_evidence:{name}")
                continue
            for item in evidence:
                if not isinstance(item, dict) or not item.get("path") or not item.get("sha256"):
                    errors.append(f"malformed_check_evidence:{name}")
                    continue
                source_path = _repo_path(root, str(item["path"]))
                if not source_path.is_file() or _sha256(source_path) != item["sha256"]:
                    errors.append(f"check_evidence_digest_mismatch:{name}:{source_path}")
        if errors:
            result.update(status="invalid_evidence", passed=False, validationErrors=errors)
            return result
        result["bindingVerified"] = True
        result["checks"] = {name: witness["checks"][name] for name in STATION_CHECKS}
        outcomes = [check["passed"] for check in result["checks"].values()]
        result["passed"] = False if False in outcomes else (True if all(value is True for value in outcomes) else None)
        result["status"] = (
            "failed" if result["passed"] is False
            else "passed" if result["passed"] is True
            else "partially_evaluated" if any(value is not None for value in outcomes)
            else "not_evaluated"
        )
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        result.update(status="invalid_evidence", passed=False, validationErrors=[str(exc)])
    return result


def validate_role_station_witness(
    workspace: Path,
    *,
    case_id: str,
    source: str,
    target: str,
    cad_result_path: Path,
    effective_graph_path: Path,
    witness_path: Path | None,
) -> dict[str, Any]:
    """Read-only shared preflight; passing never grants CAD execution authority.

    Absolute input/evidence paths may point outside the repository (for example
    the original CAD-data directory). Identity, current bytes and recorded
    hashes are checked, not membership in a workspace directory.
    """
    root = workspace.resolve()
    return _station_evidence(
        root,
        {"caseId": case_id, "source": source, "target": target},
        _repo_path(root, str(cad_result_path)),
        _repo_path(root, str(effective_graph_path)),
        witness_path,
    )


def _positive_case(
    root: Path, spec: dict[str, Any], station_witness_path: Path | None = None
) -> dict[str, Any]:
    cad_path = _repo_path(root, spec["cad"])
    cad = _read_json(cad_path)
    checks = _cad_checks(cad)
    tool = cad.get("toolResult") or {}
    graph_path = Path(cad.get("executionEffectiveGraphPath") or cad.get("effectiveGraphPath") or "")
    graph = _read_json(graph_path)
    edit_policy = graph.get("EditPolicy") or graph.get("editPolicy") or {}
    fixed_tokens = [str(value) for value in edit_policy.get("fixedModuleTokens") or []]
    target_token = str(tool.get("TargetModuleToken") or "")
    checks["exactlyOneBaseFixedByGraph"] = len(fixed_tokens) == 1
    checks["targetNotFixedByGraph"] = bool(target_token) and all(
        target_token.lower() not in token.lower() for token in fixed_tokens
    )
    checks["graphDeclaresDeterministicInitialPlacement"] = str(
        edit_policy.get("initialPlacementMode") or ""
    ).startswith("deterministic")
    output_path = Path(cad.get("outputAssemblyPath") or "")
    output_exists = output_path.is_file()
    checks["outputAssemblyExists"] = output_exists
    release_path = _repo_path(root, spec["release"]) if spec.get("release") else None
    if release_path is not None and release_path.is_file():
        release = _read_json(release_path)
        release_validation = release.get("validationEvidence") or []
        # Older context-insert results predate the human-readable diagnostic
        # sentence used by the current adapter.  Their immutable release binds
        # the same fact explicitly as drivingInitialPoseIndependent=true.
        checks["deterministicNonPrototypeStart"] = (
            checks["deterministicNonPrototypeStart"]
            or any(
                item.get("passed") is True
                and item.get("drivingInitialPoseIndependent") is True
                for item in release_validation
            )
        )
        checks["immutableReleasePassed"] = (
            release.get("status") == "released_for_demo_relation_execution"
            and any(item.get("passed") is True for item in release_validation)
        )
    else:
        checks["immutableReleasePassed"] = False

    cad_passed = all(
        value
        for key, value in checks.items()
        if key != "immutableReleasePassed"
    )
    station = _station_evidence(root, spec, cad_path, graph_path, station_witness_path)
    release_available = checks["immutableReleasePassed"] is True
    reuse_ready = cad_passed and station["passed"] is True and release_available
    layout_gate = {
        **{name: station["checks"][name]["passed"] for name in STATION_CHECKS},
        "status": station["status"],
        "passed": station["passed"],
        "transportOverlap": "not_inferred_from_pair_level_cad",
        "basis": "separate_hash_bound_station_witness_required",
        "collisionOrBrep": "not_evaluated",
    }
    return {
        **{key: value for key, value in spec.items() if key not in {"cad", "release", "candidate", "firstFailure"}},
        "status": (
            "ready_for_station_reuse" if reuse_ready
            else "cad_failed" if not cad_passed
            else "cad_passed_station_failed" if station["passed"] is False
            else "station_validated_unreleased" if station["passed"] is True
            else "cad_passed_station_not_fully_evaluated"
        ),
        "historicalClassification": spec["classification"],
        "classification": "CAD_POSITIONING_PASS" if cad_passed else "CAD_POSITIONING_FAIL",
        "cadPositioningPassed": cad_passed,
        "stationValidationPassed": station["passed"],
        "stationEvidence": station,
        "releaseAvailability": "present_with_validation" if release_available else "not_available",
        "reuseReady": reuse_ready,
        "checks": checks,
        "layoutGate": layout_gate,
        "requestedMateCount": tool.get("RequestedMateCount"),
        "createdMateCount": tool.get("CreatedMateCount"),
        "semanticEndpointIds": _endpoint_ids(graph),
        "durationSeconds": cad.get("durationSeconds"),
        "phaseDurationsSeconds": tool.get("PhaseDurationsSeconds") or {},
        "cadResultPath": str(cad_path),
        "cadResultSha256": _sha256(cad_path),
        "effectiveGraphPath": str(graph_path),
        "effectiveGraphSha256": _sha256(graph_path),
        "outputAssemblyPath": str(output_path),
        "outputAssemblySha256": _sha256(output_path) if output_exists else None,
        "releaseManifestPath": str(release_path) if release_path else None,
        "candidatePackagePath": str(_repo_path(root, spec["candidate"])) if spec.get("candidate") else None,
        "diagnosticFirstFailurePath": str(_repo_path(root, spec["firstFailure"])) if spec.get("firstFailure") else None,
        "claimBoundary": "Exact-pair CAD positioning only; collision/B-rep, real fasteners, dynamic motion and production release are excluded.",
    }


def _negative_cases(root: Path) -> list[dict[str, Any]]:
    n000_path = _repo_path(
        root,
        "demo/goal_role_station_and_matched_slot_cases_20261028/n000-a600-a700-role-station-audit.json",
    )
    n000 = _read_json(n000_path)
    safety_path = _repo_path(
        root,
        "demo/cross_project_substitution/parameterized-datum-placement-v1/release-safety-registry.json",
    )
    safety = _read_json(safety_path)
    unsafe_release = next(
        (
            row
            for row in safety.get("revokedReleases") or []
            if row.get("releaseId") == "datum-placement-769a24f2e2d41429"
        ),
        {},
    )
    scanner_path = _repo_path(
        root,
        "demo/cross_project_substitution/scanner-slot-discovery-v1/project01_JJ00_project03_AI00/alternate_route_evaluation.json",
    )
    scanner = _read_json(scanner_path)
    selected = scanner.get("selectedCandidate") or {}
    return [
        {
            "caseId": "A5-N000-A600-A700-role-station",
            "route": "native_role_station",
            "classification": "REVIEW_REQUIRED",
            "source": "project05::N000",
            "target": "project02::A600",
            "nativeRole": "project02::A700",
            "status": n000.get("status"),
            "blockedBeforeCad": n000.get("cadLaunchAllowed") is False,
            "runtimeCandidateReuseBlocked": unsafe_release.get("blockCandidateReuse") is True,
            "replacementEnvelopeFitsRoleStation": n000.get("replacementEnvelopeFitsRoleStation"),
            "forbiddenFallback": n000.get("forbiddenFallback"),
            "blockers": n000.get("blockers") or [],
            "evidencePath": str(n000_path),
            "evidenceSha256": _sha256(n000_path),
            "safetyRegistryPath": str(safety_path),
            "safetyRegistrySha256": _sha256(safety_path),
        },
        {
            "caseId": "B9-AI00-JJ00-process-gate",
            "route": "matched_mechanical_interface",
            "classification": "GEOMETRIC_MATCH_PASS_PROCESS_PROXY_FAIL",
            "evidenceLevel": "offline_geometric_prediction",
            "realCadExecuted": False,
            "actualBarcodeReadabilityVerified": False,
            "source": "project03::AI00",
            "target": "project01::JJ00",
            "status": scanner.get("status"),
            "blockedBeforeCad": scanner.get("processProxyValidationPassed") is False,
            "mechanicalChecks": selected.get("mechanicalChecks") or {},
            "processProxyChecks": selected.get("processProxyChecks") or {},
            "evidencePath": str(scanner_path),
            "evidenceSha256": _sha256(scanner_path),
        },
    ]


def _cumulative_cases(root: Path) -> list[dict[str, Any]]:
    first_path = _repo_path(
        root,
        "demo/cross_project_substitution/six-role-project03-base-v1/standard/chain-closure.json",
    )
    first = _read_json(first_path)
    timing_path = _repo_path(
        root,
        "demo/cross_project_substitution/six-role-project03-base-v1/timing-summary.json",
    )
    timing = _read_json(timing_path)
    second_source_path = _repo_path(
        root,
        "demo/cross_project_substitution/cumulative-project01-v1/complete-demo-chain-closure.json",
    )
    second_source = _read_json(second_source_path)
    second_append_path = _repo_path(
        root,
        "demo/goal_role_station_and_matched_slot_cases_20261028/cumulative-project01/cad-result.json",
    )
    second_append = _read_json(second_append_path)
    second_checks = _cad_checks(second_append)
    second_output = Path(second_append.get("outputAssemblyPath") or "")
    second_passed = all(second_checks.values()) and all(
        bool(value) for value in (second_source.get("checks") or {}).values()
    ) and second_output.is_file()
    return [
        {
            "caseId": "C1-project03-base-six-role",
            "stationValidationPassed": None,
            "stationValidationStatus": "not_evaluated_in_historical_cad_closure",
            "moduleSequence": first.get("moduleSequence"),
            "status": first.get("status"),
            "passed": first.get("success") is True and all(bool(v) for v in (first.get("checks") or {}).values()),
            "saveCloseReopenPassed": (first.get("checks") or {}).get("saveCloseReopenPassed") is True,
            "outputAssemblyPath": first.get("outputAssemblyPath"),
            "evidencePath": str(first_path),
            "evidenceSha256": _sha256(first_path),
            "wallSeconds": ((timing.get("cases") or {}).get("standard") or {}).get("elapsedWallSeconds"),
            "measuredExecutionSeconds": ((timing.get("cases") or {}).get("standard") or {}).get("measuredOuterExecutionTotalSeconds"),
        },
        {
            "caseId": "C2-project01-base-five-role",
            "stationValidationPassed": None,
            "stationValidationStatus": "not_evaluated_in_historical_cad_closure",
            "moduleSequence": [*(second_source.get("moduleSequence") or []), "GN00"],
            "status": "passed_project01_cumulative_with_gn00" if second_passed else "failed",
            "passed": second_passed,
            "saveCloseReopenPassed": second_checks.get("saveCloseReopenPassed") is True,
            "outputAssemblyPath": str(second_output),
            "sourceClosurePath": str(second_source_path),
            "appendCadResultPath": str(second_append_path),
            "appendCadResultSha256": _sha256(second_append_path),
            "appendDurationSeconds": second_append.get("durationSeconds"),
            "appendPhaseDurationsSeconds": (second_append.get("toolResult") or {}).get("PhaseDurationsSeconds") or {},
        },
    ]


def build_goal_report(
    repo_root: Path, *, station_witness_paths: dict[str, Path] | None = None
) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc).isoformat()
    started = perf_counter()
    root = repo_root.resolve()
    witness_paths = station_witness_paths or {}
    unknown_cases = set(witness_paths) - {spec["caseId"] for spec in POSITIVE_CASES}
    if unknown_cases:
        raise ValueError(f"unknown station witness cases: {', '.join(sorted(unknown_cases))}")
    positives = [_positive_case(root, spec, witness_paths.get(spec["caseId"])) for spec in POSITIVE_CASES]
    negatives = _negative_cases(root)
    cumulative = _cumulative_cases(root)
    positive_roles = sorted({row["role"] for row in positives if row["cadPositioningPassed"]})
    target_bases = sorted({row["target"] for row in positives if row["cadPositioningPassed"]})
    n000_closed = any(
        row["caseId"].startswith("A5-")
        and row.get("blockedBeforeCad") is True
        and row.get("runtimeCandidateReuseBlocked") is True
        and (row.get("forbiddenFallback") or {}).get("longitudinalMeters") == 0.465
        for row in negatives
    )
    cad_acceptance = {
        "atLeastFivePositiveCadClosures": sum(row["cadPositioningPassed"] for row in positives) >= 5,
        "atLeastThreeFunctionalRoles": len(positive_roles) >= 3,
        "atLeastThreeTargetBases": len(target_bases) >= 3,
        "atLeastTwoCumulativeAssemblies": sum(row.get("passed") is True for row in cumulative) >= 2,
        "atLeastTwoCorrectlyBlockedNegativeCases": sum(row.get("blockedBeforeCad") is True for row in negatives) >= 2,
        "n000A600UnsafeFallbackClosed": n000_closed,
        "allPositiveCadChecksPassed": all(row["cadPositioningPassed"] for row in positives),
    }
    acceptance = {
        **cad_acceptance,
        "allPositiveStationChecksPassed": all(row["stationValidationPassed"] is True for row in positives),
        "allPositiveReleasesAvailable": all(row["releaseAvailability"] == "present_with_validation" for row in positives),
        # Historic cumulative closures bind CAD execution only. Pair witnesses
        # cannot establish the multi-module spatial context of those assemblies.
        "cumulativeStationContextValidated": all(row.get("stationValidationPassed") is True for row in cumulative),
    }
    return {
        "schemaVersion": "role-station-matched-slot-goal-report/v2",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "goalStatus": "PASSED" if all(acceptance.values()) else "INCOMPLETE",
        "cadEvidenceStatus": "PASSED" if all(cad_acceptance.values()) else "INCOMPLETE",
        "cadAcceptance": cad_acceptance,
        "summary": {
            "positiveCadClosureCount": sum(row["cadPositioningPassed"] for row in positives),
            "stationValidatedCount": sum(row["stationValidationPassed"] is True for row in positives),
            "stationUnknownCount": sum(row["stationValidationPassed"] is None for row in positives),
            "stationFailedOrInvalidCount": sum(row["stationValidationPassed"] is False for row in positives),
            "existingReleaseCount": sum(row["releaseAvailability"] == "present_with_validation" for row in positives),
            "stationReuseReadyCount": sum(row["reuseReady"] for row in positives),
            "positiveRoles": positive_roles,
            "targetBases": target_bases,
            "cumulativeAssemblyPassCount": sum(row.get("passed") is True for row in cumulative),
            "correctlyBlockedNegativeCount": sum(row.get("blockedBeforeCad") is True for row in negatives),
        },
        "acceptance": acceptance,
        "positiveCases": positives,
        "negativeCases": negatives,
        "cumulativeCases": cumulative,
        "reportGenerationTiming": {
            "startedAtUtc": started_at,
            "finishedAtUtc": datetime.now(timezone.utc).isoformat(),
            "durationSeconds": round(perf_counter() - started, 6),
            "cadExecutedDuringReport": False,
        },
        "scopeBoundary": {
            "collisionOrBrep": "not_evaluated",
            "actualFastening": "not_verified",
            "dynamicMotion": "not_evaluated",
            "productionRelease": False,
            "pairLevelTransportOverlap": "unknown when the exact-pair CAD context omits transport; absence of context never proves layout safety",
            "existingReleaseIsNotStationValidation": True,
            "reportDoesNotGrantExecutionAuthority": True,
        },
    }


def write_goal_artifacts(
    repo_root: Path, output_dir: Path, *, station_witness_paths: dict[str, Path] | None = None
) -> dict[str, Path]:
    report = build_goal_report(repo_root, station_witness_paths=station_witness_paths)
    output_dir.mkdir(parents=True, exist_ok=True)
    compatibility = {
        "schemaVersion": "role-station-matched-slot-compatibility-matrix/v2",
        "generatedAtUtc": report["generatedAtUtc"],
        "positiveCases": report["positiveCases"],
        "negativeCases": report["negativeCases"],
    }
    evidence_rows: list[dict[str, Any]] = []
    for row in report["positiveCases"]:
        for key in ("cadResultPath", "effectiveGraphPath", "outputAssemblyPath", "releaseManifestPath", "candidatePackagePath", "diagnosticFirstFailurePath"):
            value = row.get(key)
            if value and Path(value).is_file():
                evidence_rows.append({"caseId": row["caseId"], "kind": key, "path": value, "sha256": _sha256(Path(value))})
        witness_path = row["stationEvidence"].get("witnessPath")
        if witness_path and Path(witness_path).is_file():
            evidence_rows.append({"caseId": row["caseId"], "kind": "stationWitness", "path": witness_path, "sha256": _sha256(Path(witness_path))})
    for row in report["negativeCases"]:
        evidence_rows.append({"caseId": row["caseId"], "kind": "negativeEvidence", "path": row["evidencePath"], "sha256": row["evidenceSha256"]})
        safety_path = row.get("safetyRegistryPath")
        if safety_path and Path(safety_path).is_file():
            evidence_rows.append(
                {
                    "caseId": row["caseId"],
                    "kind": "runtimeSafetyRegistry",
                    "path": safety_path,
                    "sha256": row["safetyRegistrySha256"],
                }
            )
    for row in report["cumulativeCases"]:
        for key in ("evidencePath", "sourceClosurePath", "appendCadResultPath", "outputAssemblyPath"):
            value = row.get(key)
            if value and Path(value).is_file():
                evidence_rows.append({"caseId": row["caseId"], "kind": key, "path": value, "sha256": _sha256(Path(value))})
    timings = {
        "schemaVersion": "role-station-matched-slot-timing-report/v1",
        "generatedAtUtc": report["generatedAtUtc"],
        "reportGeneration": report["reportGenerationTiming"],
        "pairCases": [
            {
                "caseId": row["caseId"],
                "durationSeconds": row.get("durationSeconds"),
                "phaseDurationsSeconds": row.get("phaseDurationsSeconds") or {},
            }
            for row in report["positiveCases"]
        ],
        "cumulativeCases": [
            {
                "caseId": row["caseId"],
                "wallSeconds": row.get("wallSeconds"),
                "measuredExecutionSeconds": row.get("measuredExecutionSeconds"),
                "appendDurationSeconds": row.get("appendDurationSeconds"),
                "appendPhaseDurationsSeconds": row.get("appendPhaseDurationsSeconds") or {},
            }
            for row in report["cumulativeCases"]
        ],
    }
    paths = {
        "summary": output_dir / "goal-acceptance-summary.json",
        "compatibility": output_dir / "compatibility-matrix.json",
        "evidence": output_dir / "evidence-index.json",
        "timings": output_dir / "timing-report.json",
        "markdown": output_dir / "progress-CN.md",
    }
    paths["summary"].write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    paths["compatibility"].write_text(json.dumps(compatibility, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    paths["evidence"].write_text(
        json.dumps({"schemaVersion": "goal-evidence-index/v1", "generatedAtUtc": report["generatedAtUtc"], "items": evidence_rows}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    paths["timings"].write_text(json.dumps(timings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# 同角色原生工位与匹配机械接口 Goal 进展",
        "",
        f"- 生成时间（UTC）：`{report['generatedAtUtc']}`",
        f"- 验收状态：`{report['goalStatus']}`",
        f"- CAD 定位证据状态：`{report['cadEvidenceStatus']}`（不等于工位合理性通过）",
        f"- 正向真实 CAD 闭环：**{report['summary']['positiveCadClosureCount']}** 项",
        f"- 已验证目标工位：**{report['summary']['stationValidatedCount']}** 项；待补证据：**{report['summary']['stationUnknownCount']}** 项",
        f"- 既有关系发布：**{report['summary']['existingReleaseCount']}** 项；达到本轮工位复用条件：**{report['summary']['stationReuseReadyCount']}** 项",
        f"- 功能角色：`{', '.join(report['summary']['positiveRoles'])}`",
        f"- 目标基座：`{', '.join(report['summary']['targetBases'])}`",
        f"- 累计装配闭环：**{report['summary']['cumulativeAssemblyPassCount']}** 项",
        f"- 正确阻断负向案例：**{report['summary']['correctlyBlockedNegativeCount']}** 项",
        "",
        "## 正向精确配对",
        "",
        "| 案例 | 路线 | 角色 | CAD定位 | 工位核验 | 发布 | CAD耗时(s) | 结果装配体 |",
        "|---|---|---|---|---|---|---:|---|",
    ]
    for row in report["positiveCases"]:
        lines.append(
            f"| {row['caseId']} | {row['route']} | {row['role']} | {row['classification']} | {row['stationEvidence']['status']} | {row['releaseAvailability']} | {float(row['durationSeconds']):.3f} | `{row['outputAssemblyPath']}` |"
        )
    lines += [
        "",
        "## 负向与待确认案例",
        "",
        "| 案例 | 分类 | 结果 | 关键原因 |",
        "|---|---|---|---|",
    ]
    for row in report["negativeCases"]:
        if row["caseId"].startswith("A5-"):
            reason = "; ".join(item.get("code", "") for item in row.get("blockers") or [])
        else:
            process = row.get("processProxyChecks") or {}
            reason = f"工作距离={process.get('requiredWorkingDistanceMeters')} m；横向偏差={process.get('crossTrackErrorMeters')} m"
        lines.append(f"| {row['caseId']} | {row['classification']} | {row['status']} | {reason} |")
    lines += [
        "",
        "## 累计装配",
        "",
        "| 案例 | 模组顺序 | 保存重开 | 结果装配体 |",
        "|---|---|---|---|",
    ]
    for row in report["cumulativeCases"]:
        lines.append(
            f"| {row['caseId']} | {' → '.join(row['moduleSequence'])} | {'通过' if row['saveCloseReopenPassed'] else '失败'} | `{row['outputAssemblyPath']}` |"
        )
    lines += [
        "",
        "## 本轮修改的意义",
        "",
        "1. 移除工位归属、支承方向和安装侧的预设通过值；缺少测量证据保持未评估。",
        "2. 分开报告 CAD 定位成功、目标工位核验、关系发布及可复用状态；GN00→AA00 未发布不能计为可复用。",
        "3. 保留 N000→A600 旧配方撤销、GN00→AA00 历史配合成功事实，不以这些事实替代累计环境的工位核验。",
        "4. 工位见证必须绑定精确组合、CAD 结果和配合图摘要，逐项记录计算方法及带摘要的证据来源。",
        "",
        "## 能力边界",
        "",
        "- 本报告证明精确配对、真实配合、非原型初始位姿以及保存重开闭环。",
        "- 两组件配对上下文不包含传输模组时，传输关系保持未知，不能把不在上下文内当作空间通过。",
        "- 碰撞/B-rep、实际紧固、动态行程和生产放行仍为独立后验工作。",
        "- B9 扫描案例仅为离线机械几何匹配及工艺代理计算，未执行该候选真实 CAD，也未验证实际扫码。",
        "- 本次报告生成没有启动 CAD；历史 CAD 耗时与本次报告生成耗时分别记录。",
        "",
        "## 尚未完成的工位验证",
        "",
        "1. 捕获并登记A700/A600原生支承、方向和位置端点束后，再重新评估N000角色工位替换；端点缺失期间继续保持启动CAD前阻断。",
        "2. 将GN00→AA00候选放入包含传输模组的工程评审上下文，补充多模组俯视占用复核；不改变本轮精确机械配对结论。",
        "3. 按需单独执行碰撞/B-rep、实际紧固、动态行程及生产参数签认。",
        "",
        "## 关联机器可读产物",
        "",
        f"- 兼容矩阵：`{paths['compatibility']}`",
        f"- 证据索引：`{paths['evidence']}`",
        f"- 耗时报告：`{paths['timings']}`",
        f"- 验收摘要：`{paths['summary']}`",
    ]
    paths["markdown"].write_text("\n".join(lines) + "\n", encoding="utf-8")
    return paths
