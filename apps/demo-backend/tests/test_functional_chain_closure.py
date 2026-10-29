import copy
import hashlib
import json
from pathlib import Path

import pytest

from demo_backend.functional_chain_closure import (
    audit_nonprototype_insertion, build_functional_chain_closure,
)


ROOT = Path(__file__).resolve().parents[3]
IDENTITY = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]


def _write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _component(token, number):
    transform = IDENTITY.copy()
    transform[9] = number/10
    return {"name": f"{token}.001-1", "sourcePath": f"C:/fixtures/{token}.SLDASM", "transform": transform,
            "configuration": "Default", "solvingState": 0, "constrainedStatus": 3, "isFixed": token == "AA00"}


def _mates(token):
    return [{"name": f"MCP_{token}_{i}", "mateType": 0 if i == 0 else 1,
             "alignment": 1 if i == 0 else 0, "isSuppressed": False, "errorCode": 0,
             "dimensionSystemValue": None} for i in range(3)]


@pytest.fixture
def chain(tmp_path):
    """Synthetic files model runner fields, not genuine CAD artifacts."""
    initial = tmp_path / "initial.SLDASM"
    initial.write_bytes(b"synthetic initial checkpoint, not CAD")
    # Four reused components, followed by two actual runtime-stage records.
    components = [_component(t, i) for i, t in enumerate(("AA00", "SS00", "AI00", "BD00"))]
    mates = _mates("SS00") + _mates("AI00") + _mates("BD00")
    source = initial
    stages, cad_paths, state_paths = [], [], []
    for index, token in enumerate(("GN00", "P000")):
        before_observed = {"readOnly": True, "components": copy.deepcopy(components), "allTopLevelMates": copy.deepcopy(mates)}
        target = _component(token, len(components))
        components.append(target)
        created = _mates(token)
        mates.extend(created)
        output = tmp_path / f"{token}.SLDASM"
        output.write_bytes(f"synthetic output {token}, not CAD".encode())
        graph_path = _write(tmp_path / f"{token}-graph.json", {"CaseAnchor": None, "TargetLeafPoseAnchors": []})
        tool = {"Success": True, "IndependentComponentInserted": True, "TargetCaseAnchored": False,
                "RequestedTargetLeafPoseAnchorCount": 0, "AppliedTargetLeafPoseAnchorCount": 0,
                "InsertedComponentName": target["name"], "TargetModuleSourcePath": target["sourcePath"],
                "TargetModuleToken": token, "ReopenedTargetRootTransform": target["transform"],
                "RequestedMateCount": 3, "CreatedMateCount": 3, "Reopened": True,
                "ReopenedMateParametersMatch": True, "TargetFullyConstrained": True,
                "MateSolveClean": True, "ComponentSemanticsMatch": True,
                "MateResults": [{"Success": True} for _ in created],
                "MateVerifications": [{"ObservedMateName": r["name"], **{key: True for key in (
                    "Found", "TypeMatches", "AlignmentMatches", "DistanceMatches", "AngleMatches", "AdvancedOptionsMatch")}}
                    for r in created],
                "Diagnostics": ["Deterministic non-source placement variant=3, seed=30; the variant affects only the pre-mate pose and never drives final placement."]}
        cad = {"schemaVersion": "checkpoint-selected-face-context-insert-run/v1", "success": True,
               "sourceAssemblyPath": str(source), "sourceAssemblySha256Before": _sha(source),
               "sourceAssemblySha256After": _sha(source), "sourceAssemblyUnchanged": True,
               "executionEffectiveGraphPath": str(graph_path), "executionEffectiveGraphSha256": _sha(graph_path),
               "outputAssemblyPath": str(output), "outputAssemblySha256": _sha(output),
               "outputClosedAfterVerification": True, "toolResult": tool}
        cad_path = _write(tmp_path / f"{token}-cad.json", cad)
        state = {"success": True, "checks": {"filesUnchanged": True},
                 "assemblyPath": str(output), "assemblySha256": _sha(output),
                 "sourceCheckpointPath": str(source), "sourceCheckpointSha256Before": _sha(source),
                 "sourceCheckpointSha256After": _sha(source), "sourceObserved": before_observed,
                 "observed": {"readOnly": True, "components": copy.deepcopy(components), "allTopLevelMates": copy.deepcopy(mates)}}
        state_path = _write(tmp_path / f"{token}-state.json", state)
        stages.append({"stageId": f"stage-{index}", "cadResultPath": str(cad_path), "afterStatePath": str(state_path)})
        cad_paths.append(cad_path)
        state_paths.append(state_path)
        source = output
    return {"workspace": tmp_path, "stages": stages, "cad": cad_paths, "state": state_paths}


def _close(chain, **kwargs):
    return build_functional_chain_closure(chain["workspace"], stages=chain["stages"], **kwargs)


def test_actual_stage_bindings_support_embedded_before_and_reused_checkpoint(chain):
    result = _close(chain)
    assert result["cadPassed"] is True
    assert result["functionalPassed"] is None
    assert result["unknownFunctionalRoles"] == ["Scanner", "CleaningWeighing", "WasteCup"]
    assert result["initialCheckpointComponentCount"] == 4
    assert result["finalComponentCount"] == 6
    assert result["executedStageCount"] == 2
    assert result["completeFromBlankChainClaim"] is False
    assert result["newCadExecutedByThisAudit"] is False
    assert result["automaticPublicationAllowed"] is False
    assert result["stages"][0]["beforeStateSection"] == "sourceObserved"


def test_separate_before_state_is_also_supported(chain):
    after = _read(chain["state"][0])
    before = {"success": True, "checks": {"fileUnchanged": True},
              "assemblyPath": after["sourceCheckpointPath"], "assemblySha256": after["sourceCheckpointSha256Before"],
              "observed": after["sourceObserved"]}
    path = _write(chain["workspace"] / "separate-before.json", before)
    chain["stages"][0]["beforeStatePath"] = str(path)
    assert _close(chain)["cadPassed"] is True


def test_measurement_only_snapshot_cannot_replace_cad_acceptance(chain):
    state = _read(chain["state"][1])
    state["cadAcceptanceEvaluated"] = False
    _write(chain["state"][1], state)
    assert _close(chain)["cadPassed"] is False


@pytest.mark.parametrize("field,value", [
    ("Reopened", False), ("TargetCaseAnchored", True), ("AppliedTargetLeafPoseAnchorCount", 1),
    ("CreatedMateCount", 2), ("MateSolveClean", False), ("TargetFullyConstrained", False), ("Diagnostics", []),
])
def test_actual_cad_failures_or_missing_initial_evidence_block_cad_closure(chain, field, value):
    cad = _read(chain["cad"][0])
    cad["toolResult"][field] = value
    _write(chain["cad"][0], cad)
    assert _close(chain)["cadPassed"] is False


@pytest.mark.parametrize("change", ["moved_context", "changed_mate", "wrong_source_sha", "wrong_output_sha", "missing_mate_inventory", "fixed_new_target"])
def test_current_observation_changes_cannot_be_hidden_by_success_flags(chain, change):
    state = _read(chain["state"][1])
    if change == "moved_context":
        state["observed"]["components"][0]["transform"][9] += 0.01
    elif change == "changed_mate":
        state["observed"]["allTopLevelMates"][0]["alignment"] = 0
    elif change == "wrong_source_sha":
        state["sourceCheckpointSha256After"] = "0"*64
    elif change == "wrong_output_sha":
        state["assemblySha256"] = "0"*64
    elif change == "missing_mate_inventory":
        state["sourceObserved"].pop("allTopLevelMates")
    elif change == "fixed_new_target":
        state["observed"]["components"][-1]["isFixed"] = True
    _write(chain["state"][1], state)
    assert _close(chain)["cadPassed"] is False


def _cleaning_report(chain):
    cad = _read(chain["cad"][0])
    return {"schemaVersion": "cleaning-service-region-audit/v1", "evaluationMode": "saved_cad_reopen_geometry",
            "cadBinding": {"cadResultSha256": _sha(chain["cad"][0]), "outputAssemblySha256": cad["outputAssemblySha256"]},
            "evidence": [{"path": str(chain["cad"][0]), "sha256": _sha(chain["cad"][0])}],
            "capabilityCoverage": {"passed": True},
            "serviceRegionDemoPassed": True, "serviceRegionEngineeringPassed": None}


def _cup_report(chain):
    return {"schemaVersion": "wastecup-target-station-audit/v1", "targetDatumPositionVerified": True,
            "measurements": {"cupMouthPositionVerified": None},
            "evidence": [{"path": str(chain["state"][-1]), "sha256": _sha(chain["state"][-1])}]}


def test_measured_proxy_pass_does_not_become_functional_success(chain):
    cleaning = _write(chain["workspace"] / "cleaning.json", _cleaning_report(chain))
    cup = _write(chain["workspace"] / "cup.json", _cup_report(chain))
    reports = [{"role": "CleaningWeighing", "reportPath": str(cleaning)}, {"role": "WasteCup", "reportPath": str(cup)}]
    result = _close(chain, functional_reports=reports, required_roles=["CleaningWeighing", "WasteCup"])
    assert result["cadPassed"] is True
    assert result["proxyGeometryPassed"] is True
    assert result["functionalPassed"] is None
    assert result["functionalReports"][0]["propagatedThroughPreservedAppends"] is True
    assert result["functionalReports"][0]["measuredAtStageId"] == "stage-0"


def test_functional_failure_does_not_rewrite_cad_success(chain):
    report = _cup_report(chain)
    report["targetDatumPositionVerified"] = False
    path = _write(chain["workspace"] / "cup.json", report)
    result = _close(chain, functional_reports=[{"role": "WasteCup", "reportPath": str(path)}], required_roles=["WasteCup"])
    assert result["cadPassed"] is True
    assert result["functionalPassed"] is False
    assert result["status"] == "cad_passed_functional_failed"


def test_stale_functional_evidence_is_unknown_not_pass(chain):
    report = _cup_report(chain)
    report["evidence"][0]["sha256"] = "0"*64
    path = _write(chain["workspace"] / "cup.json", report)
    result = _close(chain, functional_reports=[{"role": "WasteCup", "reportPath": str(path)}], required_roles=["WasteCup"])
    assert result["cadPassed"] is True
    assert result["functionalPassed"] is None
    assert result["functionalReports"][0]["bindingVerified"] is False


def test_real_run_context_nonprototype_audit_reads_diagnostic_not_graph_guess():
    folder = ROOT / "demo/goal_role_station_and_matched_slot_cases_20261028/gn00-aa00-204mm"
    result = audit_nonprototype_insertion(_read(folder / "cad-result.json"), _read(folder / "effective-mate-graph.json"))
    assert result["passed"] is True
    assert result["initialPlacementVariant"] == 1
    assert result["initialPlacementSeed"] == 30
    assert result["numericInitialPoseObserved"] is False


def _signed(value, name):
    value[name] = hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return value


def _scanner_evidence(chain, *, geometry_passed=True, stale=False):
    state = _read(chain["state"][-1])
    association = {"schemaVersion": "scanner-target-association/v1", "coarseGeometryEvaluationReady": True,
                   "blockingReasonCodes": [], "evidenceGrade": "prototype_measured_proxy", "prototypeEstimateAuthorized": True,
                   "currentContextEvidence": {"sourcePath": str(chain["state"][-1]),
                                              "sourceSha256": "0"*64 if stale else _sha(chain["state"][-1]),
                                              "assemblySha256": state["assemblySha256"]},
                   "coordinateFrame": {"worldFrameId": state["assemblyPath"], "frameId": "transport-frame",
                                       "bridgeVerifiedByRigidModuleReprojection": True},
                   "opticalRay": {"axisSignKnown": True}}
    for role, index, definition in (("targetBase", 0, "project03::AA00"), ("transport", 1, "project01::SS00"), ("scanner", 2, "project03::AI00")):
        component = state["observed"]["components"][index]
        association[role] = {"moduleDefinitionId": definition, "instanceId": component["name"], "installedTransform": component["transform"]}
    association["workpieceTarget"] = {"targetId": "synthetic-lane", "ownerTransportInstanceId": association["transport"]["instanceId"],
                                     "coordinateFrameId": "transport-frame"}
    _signed(association, "associationDigest")
    evaluation = {"schemaVersion": "scanner-current-context-process-evaluation/v1", "currentContextPoseBound": True,
                  "targetAssociationDigest": association["associationDigest"], "targetAssociationCheck": {"passed": True},
                  "processProxyValidationPassed": geometry_passed,
                  "selectedCandidate": {"candidateTransform": association["scanner"]["installedTransform"]}}
    _signed(evaluation, "evaluationDigest")
    return {"role": "Scanner", "associationPath": str(_write(chain["workspace"] / "association.json", association)),
            "evaluationPath": str(_write(chain["workspace"] / "evaluation.json", evaluation))}


def test_current_scanner_pass_is_proxy_only_and_final_state_bound(chain):
    result = _close(chain, functional_reports=[_scanner_evidence(chain)], required_roles=["Scanner"])
    assert result["cadPassed"] is True
    assert result["proxyGeometryPassed"] is True
    assert result["functionalPassed"] is None
    assert result["functionalReports"][0]["bindingVerified"] is True


def test_current_scanner_geometric_failure_is_independent_of_cad(chain):
    result = _close(chain, functional_reports=[_scanner_evidence(chain, geometry_passed=False)], required_roles=["Scanner"])
    assert result["cadPassed"] is True
    assert result["proxyGeometryPassed"] is False
    assert result["functionalPassed"] is False


def test_stale_scanner_association_cannot_reuse_same_pose_success(chain):
    result = _close(chain, functional_reports=[_scanner_evidence(chain, stale=True)], required_roles=["Scanner"])
    assert result["cadPassed"] is True
    assert result["proxyGeometryPassed"] is None
    assert result["functionalPassed"] is None
    assert result["functionalReports"][0]["bindingVerified"] is False


def _saved_cup_report(chain, *, same_height=False):
    cad = _read(chain["cad"][-1])
    return {"schemaVersion": "cup-saved-cad-projection-verification/v1",
            "outputAssemblyPath": cad["outputAssemblyPath"], "outputAssemblySha256": cad["outputAssemblySha256"],
            "cadResultSha256": _sha(chain["cad"][-1]),
            "targetCupProjectionPassed": True, "threeDimensionalCupMouthAlignmentPassed": same_height,
            "actualDischargeValidated": False,
            "comparison": {"measurements": [{"planeErrorMeters": 0 if same_height else 0.0715,
                                                "radialErrorMeters": 1e-15, "directionErrorDegrees": 0}]},
            "evidence": [{"path": str(chain["state"][-1]), "sha256": _sha(chain["state"][-1])}]}


def test_saved_cup_planar_pass_does_not_hide_71_5mm_height_mismatch(chain):
    path = _write(chain["workspace"] / "saved-cup.json", _saved_cup_report(chain))
    result = _close(chain, functional_reports=[{"role": "WasteCup", "reportPath": str(path)}], required_roles=["WasteCup"])
    cup = result["functionalReports"][0]
    assert result["cadPassed"] is True
    assert result["proxyGeometryPassed"] is True
    assert result["functionalPassed"] is None
    assert cup["targetCupProjectionPassed"] is True
    assert cup["threeDimensionalCupMouthAlignmentPassed"] is False
    assert cup["cupMouthMeasurements"][0]["planeErrorMeters"] == pytest.approx(0.0715)
    assert cup["actualDischargeValidated"] is False
    assert cup["heightAcceptanceCriterionDeclared"] is False
    assert cup["heightDifferenceRequiresReview"] is True
    assert cup["functionalPendingReason"] == "allowed_cup_height_and_actual_discharge_target_not_registered"


def test_saved_cup_3d_pass_still_does_not_claim_real_discharge(chain):
    path = _write(chain["workspace"] / "saved-cup.json", _saved_cup_report(chain, same_height=True))
    result = _close(chain, functional_reports=[{"role": "WasteCup", "reportPath": str(path)}], required_roles=["WasteCup"])
    assert result["proxyGeometryPassed"] is True
    assert result["functionalPassed"] is None


def test_saved_cup_wrong_cad_digest_cannot_reuse_projection_pass(chain):
    report = _saved_cup_report(chain)
    report["cadResultSha256"] = "0"*64
    path = _write(chain["workspace"] / "saved-cup.json", report)
    result = _close(chain, functional_reports=[{"role": "WasteCup", "reportPath": str(path)}], required_roles=["WasteCup"])
    assert result["proxyGeometryPassed"] is None
    assert result["functionalReports"][0]["bindingVerified"] is False
