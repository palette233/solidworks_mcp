import json
import hashlib
import importlib.util
from pathlib import Path

import pytest

from demo_backend.cross_project_module_substitution import build_module_role_overlay
from demo_backend.short_term_cross_project_scope import (
    build_short_term_cross_project_scope_readiness,
    load_short_term_cross_project_scope_readiness,
    validate_short_term_cross_project_scope_readiness,
)


WORKSPACE = Path(__file__).resolve().parents[3]


def _json(path: str):
    return json.loads((WORKSPACE / path).read_text(encoding="utf-8-sig"))


def _inputs():
    catalog = _json("demo/global_assembly_catalog/v1/global_module_catalog.json")
    return {
        "role_overlay": build_module_role_overlay(catalog),
        "gap_report": _json(
            "demo/global_assembly_catalog/coverage-v2/global_module_gap_report.json"
        ),
        "candidate_matrix": _json(
            "demo/cross_project_substitution/coverage-v1/"
            "cross_project_candidate_matrix.json"
        ),
        "chain_evidence": [
            {
                "chainId": "project05-complete-seven-addon-v2",
                "status": "passed",
                "evidenceKind": "released_cumulative_cad_chain",
                "groupIds": [
                    "base_environment",
                    "transport",
                    "scanner",
                    "calibration",
                    "cleaning_weighing",
                    "waste_handling",
                ],
                "collisionStatus": "not_evaluated",
            },
            {
                "chainId": "project02-project05-p000-datum-demo",
                "status": "passed",
                "evidenceKind": "datum_placement_demo",
                "roles": ["WasteCup"],
                "groupIds": ["waste_handling"],
                "directMechanicalInterfaceCompatible": False,
                "physicalInterfaceGapStatus": (
                    "source_slot_installation_confirmed_target_interface_pending"
                ),
                "missingPhysicalInterfaceEvidenceCount": 4,
                "sourceAttachmentCandidateStatus": (
                    "source_slot_installation_confirmed_target_interface_pending"
                ),
                "sourceAttachmentSlotWidthMeters": 0.0066,
                "sourceAttachmentSlotSpacingMeters": 0.082,
                "sourceAttachmentMechanicalMeaningConfirmed": True,
            },
        ],
        "mechanical_review_decisions": [
            {
                "caseId": "case02",
                "caseKind": "direct_installation_cross_project",
                "decision": "accepted_for_stage_demo",
            }
        ],
        "alternate_installation_routes": [
            {
                "schemaVersion": "cross-project-alternate-installation-route/v1",
                "routeId": "project03-ai00-to-project01-jj00-alternate-200mm",
                "role": "Scanner",
                "sourceProjectId": "project03",
                "sourceModuleToken": "AI00",
                "targetProjectId": "project01",
                "targetBaseToken": "JJ00",
                "nativeSlotCompatible": False,
                "status": "alternate_slot_process_semantics_pending",
                "candidateCount": 6,
                "selectedEndpointCount": 3,
                "selectedEndpointsRecovered": True,
                "candidatePoseSolved": False,
                "processSemanticsComplete": False,
                "cadValidated": False,
                "cadLaunchAllowed": False,
            }
        ],
    }


def _parameterized_datum_queue():
    queue = {
        "schemaVersion": "parameterized-datum-validation-queue/v1",
        "sourceCatalogDigest": "1" * 64,
        "pairs": [
            {
                "moduleDefinitionId": "project03::AI00",
                "slotDefinitionId": "project01::JJ00",
                "moduleRole": "Scanner",
                "state": "released",
            },
            {
                "moduleDefinitionId": "project01::GN00",
                "slotDefinitionId": "project05::A000",
                "moduleRole": "CleaningWeighing",
                "state": "ready_for_nonprototype_cad_validation",
            },
            {
                "moduleDefinitionId": "project02::A180",
                "slotDefinitionId": "project03::AA00",
                "moduleRole": "Scanner",
                "state": "explicit_position_parameters_required",
            },
        ],
    }
    queue["queueDigest"] = hashlib.sha256(
        json.dumps(
            queue,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return queue


def test_current_evidence_is_stage_demo_ready_but_not_full_direct_interchange():
    report = build_short_term_cross_project_scope_readiness(**_inputs())

    assert report["overallStatus"] == (
        "stage_demo_ready_cross_project_expansion_in_progress"
    )
    assert report["modulePortCoverageComplete"] is True
    assert report["completeRoleChainEvidencePresent"] is True
    assert report["mechanicallyReviewedCrossProjectCasePresent"] is True
    assert report["directCrossProjectRoles"] == ["Calibration", "Transport"]
    assert report["claimBoundary"][
        "datumPlacementEqualsDirectMechanicalCompatibility"
    ] is False
    assert report["claimBoundary"][
        "collisionOrBrepRequiredForCurrentMilestone"
    ] is False
    assert report["claimBoundary"][
        "alternateSlotCandidateEqualsReleasedCompatibility"
    ] is False
    validate_short_term_cross_project_scope_readiness(report)


def test_wastecup_datum_demo_is_not_promoted_to_direct_compatibility():
    report = build_short_term_cross_project_scope_readiness(**_inputs())
    waste = next(row for row in report["groups"] if row["groupId"] == "waste_handling")

    assert waste["crossProjectState"] == "datum_demo_only"
    assert waste["releasedDirectExecutionCount"] == 0
    assert waste["datumPlacementCases"][0]["physicalInterfaceGapStatus"] == (
        "source_slot_installation_confirmed_target_interface_pending"
    )
    assert any(row["groupId"] == "waste_handling" for row in report["nextWorkQueue"])


def test_scanner_preserves_native_incompatibility_but_exposes_pending_alternate():
    report = build_short_term_cross_project_scope_readiness(**_inputs())
    scanner = next(row for row in report["groups"] if row["groupId"] == "scanner")

    assert scanner["nativeSlotDirectState"] == "direct_cross_project_incompatible"
    assert scanner["crossProjectState"] == "alternate_slot_pending_validation"
    assert scanner["pendingAlternateSlotCount"] == 1
    assert scanner["releasedAlternateSlotCount"] == 0
    route = scanner["alternateInstallationRoutes"][0]
    assert route["sourceProjectId"] == "project03"
    assert route["targetProjectId"] == "project01"
    assert route["selectedEndpointsRecovered"] is True
    assert route["cadLaunchAllowed"] is False


def test_parameterized_queue_updates_six_role_expansion_without_claiming_direct_fit():
    inputs = _inputs()
    inputs["parameterized_datum_queue"] = _parameterized_datum_queue()
    inputs["parameterized_datum_catalog_digest"] = "1" * 64

    report = build_short_term_cross_project_scope_readiness(**inputs)
    scanner = next(row for row in report["groups"] if row["groupId"] == "scanner")
    cleaning = next(
        row for row in report["groups"] if row["groupId"] == "cleaning_weighing"
    )

    assert report["parameterizedDatumPairCount"] == 3
    assert report["parameterizedDatumReleasedPairCount"] == 1
    assert report["parameterizedDatumCadReadyPairCount"] == 1
    assert report["parameterizedDatumDecisionRequiredPairCount"] == 1
    assert scanner["crossProjectState"] == "parameterized_datum_pair_released"
    assert scanner["parameterizedDatumReleasedPairCount"] == 1
    assert scanner["parameterizedDatumDecisionRequiredPairCount"] == 1
    assert scanner["releasedDirectExecutionCount"] == 0
    assert cleaning["crossProjectState"] == "parameterized_datum_cad_validation_ready"
    assert cleaning["parameterizedDatumCadReadyPairCount"] == 1
    assert report["directCrossProjectRoles"] == ["Calibration", "Transport"]


def test_parameterized_queue_digest_must_authenticate():
    inputs = _inputs()
    queue = _parameterized_datum_queue()
    queue["pairs"][0]["state"] = "ready_for_nonprototype_cad_validation"
    inputs["parameterized_datum_queue"] = queue
    inputs["parameterized_datum_catalog_digest"] = "1" * 64

    with pytest.raises(ValueError, match="摘要不匹配"):
        build_short_term_cross_project_scope_readiness(**inputs)


def test_parameterized_queue_must_match_current_canonical_catalog():
    inputs = _inputs()
    inputs["parameterized_datum_queue"] = _parameterized_datum_queue()
    inputs["parameterized_datum_catalog_digest"] = "2" * 64

    with pytest.raises(ValueError, match="来源已落后"):
        build_short_term_cross_project_scope_readiness(**inputs)


def test_unreleased_alternate_route_cannot_allow_cad_launch():
    inputs = _inputs()
    inputs["alternate_installation_routes"][0]["cadLaunchAllowed"] = True

    try:
        build_short_term_cross_project_scope_readiness(**inputs)
    except ValueError as exc:
        assert "不得允许启动CAD" in str(exc)
    else:
        raise AssertionError("pending alternate route must fail closed")


def test_process_proxy_mismatch_is_reported_as_blocked_not_pending():
    inputs = _inputs()
    route = inputs["alternate_installation_routes"][0]
    route.update(
        {
            "status": "alternate_slot_blocked_process_proxy_mismatch",
            "candidatePoseSolved": True,
            "processSemanticsComplete": True,
            "processProxyValidationPassed": False,
            "selectedCrossTrackErrorMeters": 0.0494,
        }
    )

    report = build_short_term_cross_project_scope_readiness(**inputs)
    scanner = next(row for row in report["groups"] if row["groupId"] == "scanner")

    assert scanner["crossProjectState"] == (
        "alternate_slot_blocked_process_proxy_mismatch"
    )
    action = next(
        row for row in report["engineeringDispositionQueue"]
        if row["groupId"] == "scanner"
    )["recommendedAction"]
    assert "条码通道代理验证不通过" in action


def test_locating_spacing_mismatch_requires_alternate_slot_without_cad():
    inputs = _inputs()
    inputs["alternate_installation_routes"] = [
        {
            "schemaVersion": "cross-project-alternate-installation-route/v1",
            "routeId": "project01-gn00-project03-ag00-plane-two-hole-comparison",
            "role": "CleaningWeighing",
            "sourceProjectId": "project01",
            "sourceModuleToken": "GN00",
            "targetProjectId": "project03",
            "targetModuleToken": "AG00",
            "nativeSlotCompatible": False,
            "nativeSlotBlocker": "LOCATING_FEATURE_SPACING_MISMATCH",
            "status": "alternate_slot_required_spacing_mismatch",
            "spacingDifferenceMeters": 0.034,
            "cadValidated": False,
            "cadLaunchAllowed": False,
        }
    ]

    report = build_short_term_cross_project_scope_readiness(**inputs)
    cleaning = next(
        row for row in report["groups"] if row["groupId"] == "cleaning_weighing"
    )

    assert cleaning["crossProjectState"] == (
        "alternate_slot_required_spacing_mismatch"
    )
    action = next(
        row for row in report["engineeringDispositionQueue"]
        if row["groupId"] == "cleaning_weighing"
    )["recommendedAction"]
    assert "定位孔距不一致" in action


def test_exact_spacing_candidate_still_requires_mechanical_review():
    inputs = _inputs()
    inputs["alternate_installation_routes"] = [
        {
            "schemaVersion": "cross-project-alternate-installation-route/v1",
            "routeId": "project01-gn00-project03-aa00-alternate-204mm",
            "role": "CleaningWeighing",
            "sourceProjectId": "project01",
            "sourceModuleToken": "GN00",
            "targetProjectId": "project03",
            "targetBaseToken": "AA00",
            "nativeSlotCompatible": False,
            "nativeSlotBlocker": "LOCATING_FEATURE_SPACING_MISMATCH",
            "status": (
                "alternate_slot_geometry_found_pending_mechanical_review"
            ),
            "candidateCount": 2,
            "exactSpacingCandidateCount": 2,
            "cadValidated": False,
            "cadLaunchAllowed": False,
        }
    ]

    report = build_short_term_cross_project_scope_readiness(**inputs)
    cleaning = next(
        row for row in report["groups"] if row["groupId"] == "cleaning_weighing"
    )

    assert cleaning["crossProjectState"] == (
        "alternate_slot_geometry_found_pending_mechanical_review"
    )
    action = next(
        row for row in report["engineeringDispositionQueue"]
        if row["groupId"] == "cleaning_weighing"
    )["recommendedAction"]
    assert "机械评审通过前" in action


def test_missing_mechanical_review_keeps_scope_below_stage_demo_ready():
    inputs = _inputs()
    inputs["mechanical_review_decisions"] = []
    report = build_short_term_cross_project_scope_readiness(**inputs)

    assert report["mechanicallyReviewedCrossProjectCasePresent"] is False
    assert report["overallStatus"] == "module_ports_ready_chain_evidence_incomplete"


def test_report_digest_detects_tampering():
    report = build_short_term_cross_project_scope_readiness(**_inputs())
    report["groups"][0]["displayName"] = "tampered"

    try:
        validate_short_term_cross_project_scope_readiness(report)
    except ValueError as exc:
        assert "摘要不匹配" in str(exc)
    else:
        raise AssertionError("tampered report must be rejected")


def test_generated_report_can_be_loaded_for_api_consumers():
    report = load_short_term_cross_project_scope_readiness(WORKSPACE)

    assert report["targetGroupCount"] == 6
    assert report["overallStatus"] == (
        "stage_demo_ready_cross_project_expansion_in_progress"
    )


def test_backend_exposes_short_term_scope_route():
    from demo_backend.main import app

    paths = {route.path for route in app.routes}
    assert "/api/demo/short-term-cross-project-scope" in paths


def _support_case(*, cumulative=False):
    return {
        "chainId": "support-chain" if cumulative else "support-demo",
        "status": "passed",
        "evidenceKind": "datum_placement_demo",
        "mode": "support_position_demo",
        "roles": ["WasteCup"],
        "groupIds": ["base_environment", "transport", "scanner", "calibration", "waste_handling"]
        if cumulative else ["base_environment", "waste_handling"],
        "actualFixationMethod": "not_verified",
        "holePatternMatchRequired": False,
        "directMechanicalCompatibilityClaim": False,
        "directMechanicalInterfaceCompatible": False,
        "cadEvidenceVerified": True,
        "cumulativeAssemblyVerified": cumulative,
        "moduleSequence": ["A600", "A800", "A180", "A500", "P000"]
        if cumulative else ["A600", "P000"],
        "topLevelModuleCount": 5 if cumulative else 2,
    }


def _waste_and_action(report):
    return (
        next(row for row in report["groups"] if row["groupId"] == "waste_handling"),
        next(row for row in report["engineeringDispositionQueue"] if row["groupId"] == "waste_handling")["recommendedAction"],
    )


def test_support_position_demo_recommends_cumulative_append_not_hole_matching():
    inputs = _inputs()
    inputs["chain_evidence"].append(_support_case())
    report = build_short_term_cross_project_scope_readiness(**inputs)
    waste, action = _waste_and_action(report)

    assert waste["crossProjectState"] == "support_position_demo_verified"
    assert waste["releasedDirectExecutionCount"] == 0
    assert waste["supportPositionCumulativeAssemblyVerified"] is False
    assert "追加到已有累计检查点" in action
    assert "不要求先匹配孔位" in action
    assert "实际固定方式暂未验证" in action
    assert report["directCrossProjectRoles"] == ["Calibration", "Transport"]


def test_support_chain_is_cumulative_but_not_full_six_family_coverage():
    inputs = _inputs()
    inputs["chain_evidence"] = [_support_case(), _support_case(cumulative=True)]
    report = build_short_term_cross_project_scope_readiness(**inputs)
    waste, action = _waste_and_action(report)

    assert waste["crossProjectState"] == "support_position_cumulative_demo_verified"
    assert waste["cumulativeSupportPositionDemoCount"] == 1
    assert waste["supportPositionCumulativeAssemblyVerified"] is True
    assert waste["releasedDirectExecutionCount"] == 0
    assert report["completeRoleChainEvidencePresent"] is False
    assert "不等于六类全覆盖或直接机械互换" in action
    assert report["claimBoundary"]["holePatternMatchRequiredForSupportPositionDemo"] is False


def test_failed_support_chain_does_not_upgrade_successful_single_demo():
    inputs = _inputs()
    chain = _support_case(cumulative=True)
    chain.update(status="failed", cadEvidenceVerified=False, cumulativeAssemblyVerified=False)
    inputs["chain_evidence"] = [_support_case(), chain]
    waste, _ = _waste_and_action(build_short_term_cross_project_scope_readiness(**inputs))
    assert waste["crossProjectState"] == "support_position_demo_verified"
    assert waste["cumulativeSupportPositionDemoCount"] == 0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("actualFixationMethod", "verified"),
        ("holePatternMatchRequired", True),
        ("directMechanicalCompatibilityClaim", True),
        ("directMechanicalInterfaceCompatible", True),
        ("evidenceKind", "released_cumulative_cad_chain"),
        ("cadEvidenceVerified", False),
    ],
)
def test_support_demo_rejects_unsupported_claims_or_missing_cad(field, value):
    inputs = _inputs()
    support = _support_case()
    support[field] = value
    inputs["chain_evidence"].append(support)
    with pytest.raises(ValueError, match="支承定位Demo"):
        build_short_term_cross_project_scope_readiness(**inputs)


def test_support_cumulative_claim_requires_observed_module_count():
    inputs = _inputs()
    support = _support_case(cumulative=True)
    support["topLevelModuleCount"] = 6
    inputs["chain_evidence"].append(support)
    with pytest.raises(ValueError, match="模组清点"):
        build_short_term_cross_project_scope_readiness(**inputs)


def _scope_builder():
    spec = importlib.util.spec_from_file_location(
        "build_short_term_cross_project_scope_test",
        WORKSPACE / "scripts/build_short_term_cross_project_scope.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_discovery_queue(root: Path, version: int, source_digest: str) -> Path:
    payload = {
        "schemaVersion": "parameterized-datum-validation-queue/v1",
        "sourceCatalogDigest": source_digest,
        "summary": {"readyForCadValidationCount": version},
        "pairs": [],
        "captureGaps": [],
        "executionPolicy": {},
    }
    payload["queueDigest"] = hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    folder = root / f"validation-queue-20261026-v{version}"
    folder.mkdir()
    path = folder / "validation-queue.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_scope_builder_discovers_highest_queue_bound_to_current_catalog(tmp_path):
    digest = "a" * 64
    _write_discovery_queue(tmp_path, 1, digest)
    expected = _write_discovery_queue(tmp_path, 3, digest)
    _write_discovery_queue(tmp_path, 9, "b" * 64)

    path, payload = _scope_builder()._discover_current_parameterized_datum_queue(
        tmp_path, digest
    )

    assert path == expected.resolve()
    assert payload["summary"]["readyForCadValidationCount"] == 3


def test_scope_builder_rejects_tampered_current_queue(tmp_path):
    digest = "a" * 64
    path = _write_discovery_queue(tmp_path, 1, digest)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["summary"]["readyForCadValidationCount"] = 99
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="摘要不匹配"):
        _scope_builder()._discover_current_parameterized_datum_queue(
            tmp_path, digest
        )


def _support_closure_file(tmp_path, *, cumulative=False):
    output = tmp_path / "demo.SLDASM"
    output.write_bytes(b"synthetic-cad-output")
    value = {
        "schemaVersion": "p000-support-position-chain-closure/v1" if cumulative
        else "cross-project-wastecup-datum-closure/v1",
        "status": "PASSED_SUPPORT_POSITION_CHAIN_DEMO" if cumulative else "PASSED_SUPPORT_POSITION_DEMO",
        "success": True,
        "mode": "support_position_demo",
        "holePatternMatchRequired": False,
        "actualFixationMethod": "not_verified",
        "directMechanicalCompatibilityClaim": False,
        "releaseEligibleForDirectMechanicalSubstitution": False,
        "directMechanicalInterfaceCompatible": "not_evaluated",
        "outputAssemblyPath": str(output),
        "outputAssemblySha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "checks": {"saveCloseReopenPassed": True},
    }
    if cumulative:
        value.update(
            moduleSequence=["A600", "A800", "A180", "A500", "P000"],
            topLevelModuleCount=5,
            sourceStageReused=True,
            reexecutedPacketCount=1,
        )
        value["checks"].update({name: True for name in (
            "fiveModulesReopened", "upstreamComponentsUnchanged", "upstreamMatesUnchanged",
            "threeActiveTargetMates", "targetNotFixed", "noPoseAnchors", "sourceCheckpointUnchanged",
        )})
    path = tmp_path / "closure.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path, value, output


@pytest.mark.parametrize("cumulative", [False, True])
def test_builder_reads_bound_support_evidence(tmp_path, cumulative):
    path, _, _ = _support_closure_file(tmp_path, cumulative=cumulative)
    evidence = _scope_builder()._support_position_evidence(path, cumulative=cumulative)
    assert evidence["status"] == "passed"
    assert evidence["mode"] == "support_position_demo"
    assert evidence["relationExecutionMode"] == "datum_placement_demo"
    assert evidence["cumulativeAssemblyVerified"] is cumulative
    assert evidence["actualFixationMethod"] == "not_verified"
    assert evidence["directMechanicalInterfaceCompatible"] is False
    assert "cleaning_weighing" not in evidence["groupIds"]


def test_builder_keeps_absent_new_evidence_optional(tmp_path):
    assert _scope_builder()._support_position_evidence(tmp_path / "absent.json") is None


@pytest.mark.parametrize("defect", ["sha", "output", "check", "count", "missing_check", "fixation", "reexecute"])
def test_builder_rejects_invalid_support_chain_closure(tmp_path, defect):
    path, closure, output = _support_closure_file(tmp_path, cumulative=True)
    if defect == "sha":
        closure["outputAssemblySha256"] = "0" * 64
    elif defect == "output":
        output.write_bytes(b"changed")
    elif defect == "check":
        closure["checks"]["targetNotFixed"] = False
    elif defect == "count":
        closure["topLevelModuleCount"] = 6
    elif defect == "missing_check":
        del closure["checks"]["upstreamMatesUnchanged"]
    elif defect == "fixation":
        closure["actualFixationMethod"] = "verified"
    elif defect == "reexecute":
        closure["reexecutedPacketCount"] = 4
    path.write_text(json.dumps(closure), encoding="utf-8")
    with pytest.raises(ValueError, match="支承定位"):
        _scope_builder()._support_position_evidence(path, cumulative=True)


def _six_role_closure_file(tmp_path, variant="standard"):
    folder = tmp_path / variant
    folder.mkdir()
    output = folder / "six-module.SLDASM"
    output.write_bytes(("six-modules-"+variant).encode())
    state = folder / "read-only-chain-verification.json"
    state.write_text('{"success":true}', encoding="utf-8")
    sha = hashlib.sha256(output.read_bytes()).hexdigest()
    order = ["AA00", "SS00", "AI00", "BD00", "AG00", "P000"]
    if variant == "reordered":
        order = ["AA00", "AG00", "BD00", "SS00", "AI00", "P000"]
    value = {
        "schemaVersion": "six-role-support-position-chain-closure/v1",
        "status": "PASSED_SIX_ROLE_SUPPORT_POSITION_CHAIN_DEMO", "success": True,
        "chainId": "six-role-"+variant,
        "mode": "support_position_demo", "actualFixationMethod": "not_verified",
        "holePatternMatchRequired": False, "directMechanicalCompatibilityClaim": False,
        "moduleSequence": order, "topLevelModuleCount": 6, "executedPacketCount": 5,
        "crossProjectIds": ["project01", "project03", "project05"],
        "roleCoverage": ["Base", "Transport", "Scanner", "Calibration", "CleaningWeighing", "WasteCup"],
        "outputAssemblyPath": str(output), "outputAssemblySha256": sha,
        "readOnlyVerificationPath": str(state),
        "checks": {name: True for name in (
            "sixModulesReopened", "upstreamComponentsUnchanged", "upstreamMatesUnchanged",
            "threeActiveTargetMates", "targetNotFixedAndFullyConstrained", "noPoseAnchors",
            "sourceCheckpointUnchanged", "fourDirectPacketsAndOneAppend", "actualOrderBound",
            "supportPolicyPreserved", "signedSupportPositionMatches",
        )},
        "signedSupportGeometryVerification": {"success": True, "assemblySha256": sha,
                                               "checks": {"signedPositionsMatchDesignSide": True}},
    }
    path = folder / "chain-closure.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path, value, output


def test_six_role_cross_project_demo_keeps_old_evidence_and_direct_count(tmp_path):
    path, _, _ = _six_role_closure_file(tmp_path)
    item = _scope_builder()._six_role_support_evidence(path)
    inputs = _inputs()
    old = _support_case(cumulative=True)
    inputs["chain_evidence"].extend([old, item])
    report = build_short_term_cross_project_scope_readiness(**inputs)
    waste, action = _waste_and_action(report)
    assert report["completeCrossProjectRoleChainEvidencePresent"] is True
    assert report["directCrossProjectRoles"] == ["Calibration", "Transport"]
    assert report["directCrossProjectRoleCount"] == 2
    assert waste["releasedDirectExecutionCount"] == 0
    assert waste["cumulativeSupportPositionDemoCount"] == 2
    assert old in waste["datumPlacementCases"]
    assert "六类齐全" in action and "实际固定方式暂未验证" in action
    assert report["verifiedCrossProjectAssemblyOrders"] == [item["moduleSequence"]]
    assert report["crossProjectOrderVariationVerified"] is False


def test_absent_six_role_and_order_evidence_remains_optional(tmp_path):
    builder = _scope_builder()
    assert builder._six_role_support_evidence(tmp_path/"none.json") is None
    assert builder._six_role_order_comparison(tmp_path/"none.json", []) is None
    report = build_short_term_cross_project_scope_readiness(**_inputs())
    assert report["completeCrossProjectRoleChainEvidencePresent"] is False
    assert report["crossProjectOrderVariationVerified"] is False


@pytest.mark.parametrize("defect", ["hash", "output", "missing_check", "failed_check", "roles", "projects", "sequence", "count", "packets", "fixation", "geometry_hash", "geometry_missing"])
def test_six_role_reader_rejects_incomplete_or_unbound_success(tmp_path, defect):
    path, value, output = _six_role_closure_file(tmp_path)
    if defect == "hash": value["outputAssemblySha256"] = "0"*64
    elif defect == "output": output.write_bytes(b"changed")
    elif defect == "missing_check": value["checks"].pop("signedSupportPositionMatches")
    elif defect == "failed_check": value["checks"]["sixModulesReopened"] = False
    elif defect == "roles": value["roleCoverage"].remove("CleaningWeighing")
    elif defect == "projects": value["crossProjectIds"] = ["project03"]
    elif defect == "sequence": value["moduleSequence"][2] = "A180"
    elif defect == "count": value["topLevelModuleCount"] = 5
    elif defect == "packets": value["executedPacketCount"] = 1
    elif defect == "fixation": value["actualFixationMethod"] = "verified"
    elif defect == "geometry_hash": value["signedSupportGeometryVerification"]["assemblySha256"] = "0"*64
    elif defect == "geometry_missing": value.pop("signedSupportGeometryVerification")
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="六类"):
        _scope_builder()._six_role_support_evidence(path)


def test_failed_six_role_closure_does_not_claim_cross_project_completion(tmp_path):
    path, value, _ = _six_role_closure_file(tmp_path)
    value.update(success=False, status="FAILED")
    path.write_text(json.dumps(value), encoding="utf-8")
    item = _scope_builder()._six_role_support_evidence(path)
    inputs = _inputs()
    inputs["chain_evidence"].append(item)
    report = build_short_term_cross_project_scope_readiness(**inputs)
    assert report["completeCrossProjectRoleChainEvidencePresent"] is False


def _order_comparison_files(tmp_path):
    builder = _scope_builder()
    chains = [builder._six_role_support_evidence(_six_role_closure_file(tmp_path, variant)[0]) for variant in ("standard", "reordered")]
    value = {
        "schemaVersion": "six-role-support-order-comparison/v1", "success": True,
        "status": "PASSED_SIX_ROLE_ORDER_EQUIVALENCE",
        "checks": {key: True for key in ("relativePosesEquivalent", "moduleSourceIdentitiesMatch", "fifteenNamedMatesEach",
                                        "mateTypesParametersStatesEquivalent", "actualOrdersDiffer", "bothOutputFilesBoundIndependently")},
        "standardOrder": chains[0]["moduleSequence"], "reorderedOrder": chains[1]["moduleSequence"],
        "inputEvidence": [{"variant": variant, "path": row[field], "sha256": hashlib.sha256(Path(row[field]).read_bytes()).hexdigest()}
                          for variant, row in zip(("standard", "reordered"), chains)
                          for field in ("closurePath", "readOnlyVerificationPath")],
        "outputBindings": [{"variant": variant, "path": row["outputAssemblyPath"], "sha256": row["outputAssemblySha256"], "bound": True}
                           for variant, row in zip(("standard", "reordered"), chains)],
    }
    path = tmp_path / "comparison.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path, value, chains


def test_two_bound_orders_show_order_variation_without_direct_compatibility_promotion(tmp_path):
    path, _, chains = _order_comparison_files(tmp_path)
    comparison = _scope_builder()._six_role_order_comparison(path, chains)
    for chain in chains:
        chain.update(orderEquivalenceVerified=True, orderComparisonEvidence=comparison)
    inputs = _inputs()
    inputs["chain_evidence"].extend(chains)
    report = build_short_term_cross_project_scope_readiness(**inputs)
    assert report["crossProjectOrderVariationVerified"] is True
    assert len(report["verifiedCrossProjectAssemblyOrders"]) == 2
    assert len(report["crossProjectOrderComparisons"]) == 1
    assert report["directCrossProjectRoleCount"] == 2


@pytest.mark.parametrize("defect", ["check", "input_hash", "changed_closure", "output_hash", "changed_output", "missing_output", "wrong_order"])
def test_order_reader_rejects_unbound_or_invalid_comparison(tmp_path, defect):
    path, value, chains = _order_comparison_files(tmp_path)
    if defect == "check": value["checks"]["relativePosesEquivalent"] = False
    elif defect == "input_hash": value["inputEvidence"][0]["sha256"] = "0"*64
    elif defect == "changed_closure": Path(chains[0]["closurePath"]).write_text('{}', encoding="utf-8")
    elif defect == "output_hash": value["outputBindings"][0]["sha256"] = "0"*64
    elif defect == "changed_output": Path(chains[0]["outputAssemblyPath"]).write_bytes(b"changed")
    elif defect == "missing_output": value["outputBindings"].pop()
    elif defect == "wrong_order": value["standardOrder"] = value["reorderedOrder"]
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="六类变序"):
        _scope_builder()._six_role_order_comparison(path, chains)


def test_failed_order_comparison_keeps_individual_chain_success(tmp_path):
    path, value, chains = _order_comparison_files(tmp_path)
    value.update(success=False, status="FAILED_SIX_ROLE_ORDER_EQUIVALENCE")
    path.write_text(json.dumps(value), encoding="utf-8")
    comparison = _scope_builder()._six_role_order_comparison(path, chains)
    assert comparison["status"] == "failed" and comparison["cadEvidenceVerified"] is False
    assert all(row["status"] == "passed" for row in chains)
