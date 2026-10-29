import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from demo_backend.scanner_target_association import (
    bind_scanner_target_to_current_context,
    build_scanner_target_association,
    evaluate_scanner_target_in_current_context,
    preflight_scanner_target_for_cumulative_chain,
    validate_scanner_target_association,
)


ROOT = Path(__file__).resolve().parents[3]
IDENTITY = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]


def _digest(report, key):
    report[key] = hashlib.sha256(json.dumps(
        {k: v for k, v in report.items() if k != key}, ensure_ascii=False,
        sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()
    return report


@pytest.fixture
def inputs():
    return {
        "prior_process_evidence": {
            "sourceScanner": {"projectId": "p3", "moduleToken": "AI00",
                              "opticalOriginWorldMeters": [0, 0, 0],
                              "opticalDirectionWorld": [0, 1, 0],
                              "cadBeamEndpointProxyWorldMeters": [0, 0.1, 0]},
            "targetTransport": {"projectId": "p1", "moduleToken": "SS00",
                                "sourceTransform": IDENTITY.copy(), "installedTransform": IDENTITY.copy(),
                                "installationFrameWorld": {"origin": [0, 0, 0], "flowAxis": [1, 0, 0],
                                                           "transverseAxis": [0, 1, 0], "upAxis": [0, 0, 1]},
                                "conservativeFlowEnvelopeMeters": [-1, 1],
                                "barcodeLaneReference": {"source": "synthetic CAD beam proxy",
                                                         "transverseCoordinateMeters": 0.1,
                                                         "normalCoordinateMeters": 0,
                                                         "engineeringConfirmedBarcodeSurface": False}},
            "readOnlyChecks": {"workingDistanceRangeEvidence": {"minimumMeters": 0.07, "maximumMeters": 1,
                                                                   "authority": "synthetic fixture", "sourceUrl": "fixture://distance"}},
        },
        "scanner_graph": {"SourceAssemblyPath": "source-world",
                          "Modules": [{"ModuleToken": "AI00", "HierarchyPath": "scanner-1", "SourceTransform": IDENTITY.copy()}],
                          "SemanticAssemblyPlanAudit": {"opticalValidation": {"modeledWorkingDistanceMeters": 0.1,
                                                                                  "opticalDirectionWorld": [0, 1, 0],
                                                                                  "targetProxyWorldMeters": [0, 0.1, 0]}}},
        "target_transport_graph": {"SourceAssemblyPath": "target-world", "Modules": [
            {"ModuleToken": "SS00", "HierarchyPath": "transport-1", "SourceTransform": IDENTITY.copy()},
            {"ModuleToken": "JJ00", "HierarchyPath": "base-1", "SourceTransform": IDENTITY.copy()}]},
        "target_face_catalog": {"SourceAssemblyPath": "target-world"},
        "prototype_estimate_authorized": True,
    }


def _chain(association):
    evaluation = _digest({
        "candidatePoseTransformSolved": True, "processProxyValidationPassed": True,
        "targetAssociationDigest": association["associationDigest"],
        "targetAssociationCheck": {"passed": True},
        "selectedCandidate": {"candidateTransform": IDENTITY.copy()},
    }, "evaluationDigest")
    components = [{"instanceId": association[role]["instanceId"],
                   "moduleDefinitionId": association[role]["moduleDefinitionId"],
                   "transform": IDENTITY.copy()} for role in ("scanner", "transport", "targetBase")]
    return dict(evaluation=evaluation, association=association, planned_components=components,
                world_frame_id="target-world", allow_prototype_proxy=True)


def test_proxy_association_preserves_unknown_real_target_and_cad(inputs):
    association = build_scanner_target_association(**inputs)
    assert association["coarseGeometryEvaluationReady"] is True
    assert association["opticalRay"]["axisSignKnown"] is True
    assert association["opticalRay"]["axisSignEngineeringConfirmed"] is False
    assert association["workpieceTarget"]["physicalBarcodeFaceId"] is None
    assert association["cadEvidence"]["performed"] is False
    assert association["engineeringProcessValidationPassed"] is False
    assert association["measuredScanSuccess"] is False
    assert validate_scanner_target_association(association, prior_process_evidence=inputs["prior_process_evidence"]) == []


@pytest.mark.parametrize("change,reason", [
    ("no_authorization", "PROTOTYPE_ESTIMATE_NOT_AUTHORIZED"),
    ("opposite_axis", "OPTICAL_AXIS_SIGN_EVIDENCE_MISSING_OR_INCONSISTENT"),
    ("nominal_only", "WORKING_DISTANCE_RANGE_EVIDENCE_MISSING"),
    ("wrong_frame", "TARGET_COORDINATE_FRAME_BRIDGE_UNPROVEN"),
    ("moved_transport", "TARGET_COORDINATE_FRAME_BRIDGE_UNPROVEN"),
    ("duplicate_instance", "TRANSPORT_INSTANCE_NOT_UNIQUE"),
    ("bad_basis", "TRANSPORT_INSTALLATION_FRAME_INVALID"),
    ("missing_target", "WORKPIECE_BARCODE_TARGET_PROXY_MISSING"),
])
def test_missing_or_inconsistent_semantics_fail_closed(inputs, change, reason):
    process = inputs["prior_process_evidence"]
    if change == "no_authorization":
        inputs["prototype_estimate_authorized"] = False
    elif change == "opposite_axis":
        process["sourceScanner"]["opticalDirectionWorld"] = [0, -1, 0]
    elif change == "nominal_only":
        process["readOnlyChecks"]["workingDistanceRangeEvidence"] = {"modeledNominalMeters": 0.1}
    elif change == "wrong_frame":
        inputs["target_face_catalog"]["SourceAssemblyPath"] = "another-world"
    elif change == "moved_transport":
        process["targetTransport"]["installedTransform"][9] = 0.5
    elif change == "duplicate_instance":
        inputs["target_transport_graph"]["Modules"].append(copy.deepcopy(inputs["target_transport_graph"]["Modules"][0]))
    elif change == "bad_basis":
        process["targetTransport"]["installationFrameWorld"]["transverseAxis"] = [1, 0, 0]
    elif change == "missing_target":
        process["targetTransport"].pop("barcodeLaneReference")
    association = build_scanner_target_association(**inputs)
    assert reason in association["blockingReasonCodes"]
    assert association["coarseGeometryEvaluationReady"] is False
    assert association["cadLaunchAllowed"] is False


def test_legacy_confirmed_flag_cannot_promote_proxy(inputs):
    inputs["prior_process_evidence"]["targetTransport"]["barcodeLaneReference"]["engineeringConfirmedBarcodeSurface"] = True
    association = build_scanner_target_association(**inputs)
    assert association["workpieceTarget"]["engineeringConfirmedBarcodeSurface"] is False
    assert association["evidenceGrade"] == "prototype_measured_proxy"


def test_association_digest_and_process_input_staleness(inputs):
    association = build_scanner_target_association(**inputs)
    inputs["prior_process_evidence"]["sourceScanner"]["opticalOriginWorldMeters"][0] = 0.1
    assert "SCANNER_TARGET_PROCESS_EVIDENCE_STALE" in validate_scanner_target_association(
        association, prior_process_evidence=inputs["prior_process_evidence"])
    association["transport"]["instanceId"] = "different"
    assert "SCANNER_TARGET_ASSOCIATION_DIGEST_INVALID" in validate_scanner_target_association(association)


def test_synthetic_proxy_candidate_compile_does_not_authorize_cad(inputs):
    result = preflight_scanner_target_for_cumulative_chain(**_chain(build_scanner_target_association(**inputs)))
    assert result["processCandidateCompileAllowed"] is True
    assert result["cadLaunchAllowed"] is False
    assert result["measuredScanSuccess"] is False


@pytest.mark.parametrize("change,reason", [
    ("transport_instance", "SCANNER_TRANSPORT_INSTANCE_BINDING_MISMATCH"),
    ("transport_definition", "SCANNER_TRANSPORT_INSTANCE_BINDING_MISMATCH"),
    ("transport_pose", "SCANNER_TRANSPORT_POSE_CHANGED_REEVALUATION_REQUIRED"),
    ("scanner_pose", "SCANNER_SCANNER_POSE_CHANGED_REEVALUATION_REQUIRED"),
    ("base_pose", "SCANNER_TARGETBASE_POSE_CHANGED_REEVALUATION_REQUIRED"),
    ("world", "SCANNER_TARGET_WORLD_FRAME_MISMATCH"),
    ("default_mode", "SCANNER_PROXY_REQUIRES_EXPLICIT_DEMO_MODE"),
    ("proxy_failed", "SCANNER_TARGET_GEOMETRY_FAILED"),
    ("stale_evaluation", "SCANNER_EVALUATION_ASSOCIATION_MISMATCH"),
])
def test_chain_rejects_changed_context_or_unapproved_proxy(inputs, change, reason):
    args = _chain(build_scanner_target_association(**inputs))
    if change == "transport_instance":
        args["planned_components"][1]["instanceId"] = "transport-2"
    elif change == "transport_definition":
        args["planned_components"][1]["moduleDefinitionId"] = "p3::AE00"
    elif change in ("transport_pose", "scanner_pose"):
        args["planned_components"][int(change == "transport_pose")]["transform"][9] = 1
    elif change == "base_pose":
        args["planned_components"][2]["transform"][9] = 1
    elif change == "world":
        args["world_frame_id"] = "elsewhere"
    elif change == "default_mode":
        args["allow_prototype_proxy"] = False
    elif change == "proxy_failed":
        args["evaluation"]["processProxyValidationPassed"] = False
    elif change == "stale_evaluation":
        args["evaluation"]["targetAssociationDigest"] = "stale"
    _digest(args["evaluation"], "evaluationDigest")
    result = preflight_scanner_target_for_cumulative_chain(**args)
    assert result["processCandidateCompileAllowed"] is False
    assert reason in result["blockingReasonCodes"]


def test_real_inputs_recalculated_in_fresh_directory_without_cad(tmp_path):
    output = tmp_path / "scanner-audit"
    args = [sys.executable, str(ROOT / "scripts/build_scanner_target_association.py"),
            "--output", str(output), "--authorize-prototype-estimate"]
    subprocess.run(args, check=True, capture_output=True)
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["associationReady"] is True
    assert summary["evaluatedPoseCount"] == 22
    assert summary["workingDistanceMeters"] == pytest.approx(0.0565)
    assert summary["crossTrackErrorMeters"] == pytest.approx(0.04940236747648302)
    assert summary["processCandidateCompileAllowed"] is False
    assert summary["blockingReasonCodes"] == ["SCANNER_TARGET_GEOMETRY_FAILED"]
    assert summary["cadPerformed"] is False
    assert json.loads((output / "timing-report.json").read_text())["cadSeconds"] == 0
    assert subprocess.run(args, capture_output=True).returncode != 0


def _current_context(inputs, transform=None):
    reference = build_scanner_target_association(**inputs)
    current = [{"instanceId": f"current-{role}",
                "moduleDefinitionId": reference[role]["moduleDefinitionId"],
                "transform": copy.deepcopy(transform or IDENTITY)}
               for role in ("scanner", "transport", "targetBase")]
    return {"reference_association": reference, "scanner_reference_graph": inputs["scanner_graph"],
            "current_components": current,
            "selection": {role: f"current-{role}" for role in ("scanner", "transport", "targetBase")},
            "world_frame_id": "current-chain-world",
            "context_evidence": {"kind": "explicit_planned_context", "sourcePath": "fixture://current-plan",
                                 "sourceSha256": "a"*64}}


def test_current_pose_reprojection_preserves_common_rigid_motion(inputs):
    baseline = evaluate_scanner_target_in_current_context(
        association=bind_scanner_target_to_current_context(**_current_context(inputs)))
    rotated = [0, 1, 0, -1, 0, 0, 0, 0, 1, 0.5, 0.6, 0.7, 1, 0, 0, 0]
    args = _current_context(inputs, rotated)
    association = bind_scanner_target_to_current_context(**args)
    result = evaluate_scanner_target_in_current_context(association=association)
    checks = result["selectedCandidate"]["processProxyChecks"]
    assert checks["requiredWorkingDistanceMeters"] == pytest.approx(0.1)
    assert checks["crossTrackErrorMeters"] == pytest.approx(0)
    assert result["processProxyValidationPassed"] is True
    assert result["candidatePoseTransformSolved"] is False
    assert result["cadEvidence"]["performed"] is False
    assert result["measuredScanSuccess"] is False
    assert association["coordinateFrame"]["bridgeVerifiedByRigidModuleReprojection"] is True
    assert checks["requiredWorkingDistanceMeters"] == pytest.approx(
        baseline["selectedCandidate"]["processProxyChecks"]["requiredWorkingDistanceMeters"])
    preflight = preflight_scanner_target_for_cumulative_chain(
        evaluation=result, association=association, planned_components=args["current_components"],
        world_frame_id=args["world_frame_id"], allow_prototype_proxy=True)
    assert preflight["processCandidateCompileAllowed"] is True
    assert preflight["cadLaunchAllowed"] is False


def test_current_transport_motion_recomputes_distance(inputs):
    args = _current_context(inputs)
    args["current_components"][1]["transform"][10] = 0.05
    association = bind_scanner_target_to_current_context(**args)
    result = evaluate_scanner_target_in_current_context(association=association)
    assert result["selectedCandidate"]["processProxyChecks"]["requiredWorkingDistanceMeters"] == pytest.approx(0.15)
    assert result["calculationEvidence"]["historicalProcessPassFlagReused"] is False


def test_current_bad_scanner_pose_does_not_reuse_historical_success(inputs):
    args = _current_context(inputs)
    args["current_components"][0]["transform"][10] = 0.08
    association = bind_scanner_target_to_current_context(**args)
    evaluation = evaluate_scanner_target_in_current_context(association=association)
    assert evaluation["selectedCandidate"]["processProxyChecks"]["requiredWorkingDistanceMeters"] == pytest.approx(0.02)
    assert evaluation["processProxyValidationPassed"] is False
    result = preflight_scanner_target_for_cumulative_chain(
        evaluation=evaluation, association=association, planned_components=args["current_components"],
        world_frame_id=args["world_frame_id"], allow_prototype_proxy=True)
    assert "SCANNER_TARGET_GEOMETRY_FAILED" in result["blockingReasonCodes"]


@pytest.mark.parametrize("change", ["mirror", "nan", "wrong_module", "duplicate", "wrong_reference", "no_context_evidence"])
def test_current_context_requires_valid_explicit_identity_and_rigid_pose(inputs, change):
    args = _current_context(inputs)
    if change == "mirror":
        args["current_components"][0]["transform"][0] = -1
    elif change == "nan":
        args["current_components"][0]["transform"][9] = float("nan")
    elif change == "wrong_module":
        args["current_components"][1]["moduleDefinitionId"] = "project03::AE00"
    elif change == "duplicate":
        args["current_components"].append(copy.deepcopy(args["current_components"][0]))
    elif change == "wrong_reference":
        args["scanner_reference_graph"]["SourceAssemblyPath"] = "different-reference"
    elif change == "no_context_evidence":
        args["context_evidence"] = {}
    with pytest.raises(ValueError):
        bind_scanner_target_to_current_context(**args)


def test_parallel_current_ray_lane_is_finite_json_and_fails_closed(inputs):
    args = _current_context(inputs)
    args["current_components"][0]["transform"] = [0, 1, 0, -1, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]
    association = bind_scanner_target_to_current_context(**args)
    evaluation = evaluate_scanner_target_in_current_context(association=association)
    assert evaluation["processProxyValidationPassed"] is False
    assert evaluation["selectedCandidate"]["processProxyChecks"]["requiredWorkingDistanceMeters"] is None
    json.dumps(evaluation, allow_nan=False)


def test_real_positive_aa00_ss00_ai00_current_saved_context(tmp_path):
    state = ROOT / "demo/cross_project_substitution/six-role-project03-base-v1/standard/read-only-chain-verification.json"
    output = tmp_path / "positive-scanner"
    command = [sys.executable, str(ROOT / "scripts/build_current_scanner_target.py"),
               "--state", str(state), "--output", str(output), "--authorize-prototype-estimate"]
    subprocess.run(command, check=True, capture_output=True)
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["processCandidateCompileAllowed"] is True
    assert summary["processProxyChecks"]["requiredWorkingDistanceMeters"] == pytest.approx(0.0745)
    assert summary["processProxyChecks"]["crossTrackErrorMeters"] == pytest.approx(0.0004023674739763172)
    assert summary["newCadExecuted"] is False
    assert summary["measuredScanSuccess"] is False
    association = json.loads((output / "association.json").read_text(encoding="utf-8"))
    assert association["targetBase"]["moduleDefinitionId"] == "project03::AA00"
    assert association["workpieceTarget"]["engineeringConfirmedBarcodeSurface"] is False
    changed = json.loads(state.read_text(encoding="utf-8-sig"))
    changed["assemblySha256"] = "0"*64
    bad_state = tmp_path / "bad-state.json"
    bad_state.write_text(json.dumps(changed), encoding="utf-8")
    command[command.index("--state")+1] = str(bad_state)
    command[command.index("--output")+1] = str(tmp_path / "bad-scanner")
    result = subprocess.run(command, capture_output=True)
    assert result.returncode != 0
    assert b"assembly hash changed" in result.stderr
