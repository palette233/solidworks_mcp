import copy
import inspect
from pathlib import Path

import pytest

from demo_backend import cleaning_service_region as service
from demo_backend import role_station_geometry as geometry


ROOT = Path(__file__).resolve().parents[3]
LIVE_STATE = ROOT / "demo/role_station_strengthening_20261028/gn00-live-reopen-0413.json"


def test_prefixed_cad_target_token_matches_only_by_suffix_before_exact_identity_check():
    assert service._target_token_matches("FL9A24D063AG00", "AG00")
    assert service._target_token_matches("FL9C24N074GN00", "GN00", "OTHER")
    assert not service._target_token_matches("FL9A24D063AG00-X", "AG00")
    assert not service._target_token_matches(None, "AG00")


def test_missing_capture_anchor_is_not_replaced_by_native_graph(monkeypatch):
    original = geometry._read
    def without_anchor(path):
        payload = copy.deepcopy(original(path))
        if Path(path).name == "project01_module_occupancy.json":
            payload["modules"]["GN00"].pop("prototypeAnchorInstallationMeters", None)
        return payload
    monkeypatch.setattr(geometry, "_read", without_anchor)
    with pytest.raises(ValueError, match="capture-frame anchor is missing"):
        service.build_gn00_aa00_service_region_audit(ROOT)


def test_target_native_region_gives_explicit_demo_parameters_not_source_pose():
    report = service.build_gn00_aa00_service_region_audit(ROOT)
    assert report["candidateSuggestion"]["positionParameters"] == pytest.approx({
        "longitudinal": 0.35630906453119676, "lateral": 0.231, "supportGap": 0,
    })
    assert report["candidateSuggestion"]["prototypePoseUsedForPlacement"] is False
    assert report["candidateSuggestion"]["copySourceWorldPose"] is False
    assert report["serviceRegionDemoPassed"] is True
    assert report["serviceRegionEngineeringPassed"] is None
    assert report["capabilityCoverage"]["passed"] is True
    assert report["capabilityCoverage"]["missingCapabilities"] == []
    assert report["stationReady"] is False and report["cadExecutionAuthorized"] is False
    assert report["cadBinding"] is None and report["cadStarted"] is False
    assert report["serviceRegion"]["boundaryExpandedToFitCandidate"] is False
    assert report["serviceRegion"]["engineeringApproved"] is False
    envelope = report["fullEnvelope"]
    assert envelope["nativeRoleEnvelopeRelation"]["envelopeContained"] is False
    assert envelope["nativeRoleEnvelopeRelation"]["clearancesMeters"]["minV"] == pytest.approx(-0.012288501265013)
    assert envelope["nativeRoleEnvelopeRelation"]["clearancesMeters"]["maxV"] == pytest.approx(-0.012288501265013)
    assert envelope["supportFaceOuterBoundRelation"]["clearancesMeters"]["maxV"] == pytest.approx(-0.042988501265013)
    assert report["selectedSupportContact"]["outerBoundRelation"]["envelopeContained"] is True
    assert report["selectedSupportContact"]["trimmedContactAndOtherFeetVerified"] is None


def test_complete_leaf_subtree_union_capture_is_accepted_as_complete_geometry(monkeypatch):
    original = geometry._read

    def with_new_capture_source(path):
        payload = copy.deepcopy(original(path))
        if Path(path).name == "project01_module_occupancy.json":
            for row in payload["modules"]["GN00"]["occupancyBoxes"]:
                row["source"] = "complete-leaf-subtree-union"
        return payload

    monkeypatch.setattr(geometry, "_read", with_new_capture_source)
    report = service.build_gn00_aa00_service_region_audit(ROOT)
    assert report["serviceRegionDemoPassed"] is True
    assert report["candidateSuggestion"]["prototypePoseUsedForPlacement"] is False


def test_real_204mm_saved_candidate_fails_service_proxy_without_promoting_cad_success():
    report = service.build_gn00_aa00_service_region_audit(
        ROOT, cad_result_path=Path(geometry.GN00_CASE) / "cad-result.json",
        state_path=LIVE_STATE,
    )
    assert report["evaluationMode"] == "saved_cad_reopen_geometry"
    assert report["cadBinding"]["outputAssemblySha256"] == "c0c09d677b00a65054826111b85a2c6144603518bef2ae5000bf5cecc532acbc"
    assert report["serviceRegionDemoPassed"] is False
    assert report["fullEnvelope"]["supportFaceOuterBoundRelation"]["clearancesMeters"]["minV"] == pytest.approx(-0.65782347064267)
    assert report["slotMembership"] is None and report["transportContext"] is None
    assert report["stationReady"] is False


def test_saved_result_without_actual_base_state_fails_closed():
    with pytest.raises(ValueError, match="requires a readonly state with actual base pose"):
        service.build_gn00_aa00_service_region_audit(ROOT, cad_result_path=Path(geometry.GN00_CASE) / "cad-result.json")


def test_synthetic_whole_assembly_translation_uses_actual_base_pose_and_binds_ss00(monkeypatch):
    """Synthetic read model validates arithmetic only, not another live CAD run."""
    original = geometry._read
    delta = [0.3, -0.4, 0.5]
    native = original(ROOT / "demo/semantic_ports/project01_GN00_fourth_increment_v1/assembly_plan_effective.json")
    ss = geometry._module(native, "SS00")

    def changed(path):
        payload = copy.deepcopy(original(path))
        if path.name == "cad-result.json":
            for i in range(3):
                payload["toolResult"]["ReopenedTargetRootTransform"][9 + i] += delta[i]
        if path == LIVE_STATE:
            payload["observed"]["components"].append({"name": ss["Name"], "sourcePath": ss["Path"],
                "configuration": "Default", "transform": copy.deepcopy(ss["SourceTransform"]), "boundingBoxWorld": None})
            for row in payload["observed"]["components"]:
                for i in range(3):
                    row["transform"][9 + i] += delta[i]
        return payload

    monkeypatch.setattr(geometry, "_read", changed)
    report = service.build_gn00_aa00_service_region_audit(
        ROOT, cad_result_path=Path(geometry.GN00_CASE) / "cad-result.json", state_path=LIVE_STATE)
    assert report["fullEnvelope"]["supportFaceOuterBoundRelation"]["clearancesMeters"]["minV"] == pytest.approx(-0.65782347064267)
    assert report["transportContext"] is True
    assert report["transportContextCheck"]["component"]["sourcePath"] == ss["Path"]
    assert len(report["transportContextCheck"]["serviceSubtreeRelations"]) == 4
    assert report["transportContextCheck"]["collisionPassed"] is None
    assert report["stationReady"] is False


@pytest.mark.parametrize("change", ["sha", "base_source", "target_pose", "readonly"])
def test_readonly_output_context_mutations_fail_closed(monkeypatch, change):
    original = geometry._read

    def changed(path):
        payload = copy.deepcopy(original(path))
        if path == LIVE_STATE:
            if change == "sha":
                payload["assemblySha256"] = "0" * 64
            elif change == "base_source":
                payload["observed"]["components"][1]["sourcePath"] = "another-base.SLDASM"
            elif change == "target_pose":
                payload["observed"]["components"][0]["transform"][9] += 0.1
            else:
                payload["observed"]["readOnly"] = False
        return payload

    monkeypatch.setattr(geometry, "_read", changed)
    with pytest.raises(ValueError, match="readonly state"):
        service.build_gn00_aa00_service_region_audit(
            ROOT, cad_result_path=Path(geometry.GN00_CASE) / "cad-result.json", state_path=LIVE_STATE)


@pytest.mark.parametrize("change,error", [
    ("coverage", "complete captured leaf occupancy"),
    ("identity", "module identity mismatch"),
    ("frame", "coordinate frames disagree"),
    ("missing_subtree", "subtree grouping changed"),
    ("extra_subtree", "subtree grouping changed"),
    ("degenerate_datums", "not orthonormal"),
])
def test_service_region_missing_or_inconsistent_sources_fail_closed(monkeypatch, change, error):
    original = geometry._read

    def changed(path):
        payload = copy.deepcopy(original(path))
        if path.name == "project01_module_occupancy.json":
            moving = payload["modules"]["GN00"]
            if change == "coverage":
                moving["leafCoverageComplete"] = False
            elif change == "identity":
                moving["filePath"] = "different.SLDASM"
            elif change == "frame":
                payload["installationFrame"]["originWorldMeters"][0] += 0.1
            elif change == "missing_subtree":
                moving["occupancyBoxes"] = [row for row in moving["occupancyBoxes"] if row["subtree"] != "GN20"]
            elif change == "extra_subtree":
                extra = copy.deepcopy(moving["occupancyBoxes"][0])
                extra["subtree"] = "unreviewed_function"
                moving["occupancyBoxes"].append(extra)
        if path.name == "effective-mate-graph.json" and change == "degenerate_datums":
            payload["Mates"][1]["Endpoints"][0]["FaceNormalWorld"] = payload["Mates"][0]["Endpoints"][0]["FaceNormalWorld"]
        return payload

    monkeypatch.setattr(geometry, "_read", changed)
    with pytest.raises(ValueError, match=error):
        service.build_gn00_aa00_service_region_audit(ROOT)


def test_changed_functional_proxy_is_not_accepted_by_padding_the_region(monkeypatch):
    original = geometry._read

    def changed(path):
        payload = copy.deepcopy(original(path))
        if path.name == "project01_module_occupancy.json":
            row = next(row for row in payload["modules"]["GN00"]["occupancyBoxes"] if row["subtree"] == "GN20")
            row["installationBoundsMeters"]["maxV"] += 1
        return payload

    monkeypatch.setattr(geometry, "_read", changed)
    report = service.build_gn00_aa00_service_region_audit(ROOT)
    assert report["serviceRegionDemoPassed"] is False
    assert report["serviceRegion"]["boundaryExpandedToFitCandidate"] is False
    assert report["serviceRegion"]["boundsInstallationMeters"]["maxV"] == pytest.approx(0.5747)


def test_second_combination_runs_by_changing_rule_data_only():
    first = geometry._read(ROOT / service.DEFAULT_RULE)
    second = geometry._read(ROOT / "data/assembly_stations/cleaning-ag00-aa00-native-v1.json")
    original = copy.deepcopy(second)
    before = service.build_cleaning_service_region_audit(ROOT, first)
    after = service.build_cleaning_service_region_audit(ROOT, second)
    assert second == original
    assert before["source"] == "project01::GN00" and after["source"] == "project03::AG00"
    assert before["ruleDigest"] != after["ruleDigest"]
    assert after["sourceRole"] == "CleaningWeighing"
    assert after["candidateSuggestion"]["positionParameters"] == pytest.approx({"longitudinal": 0.54, "lateral": 0.2385, "supportGap": 0})
    assert after["serviceRegionDemoPassed"] is True
    assert after["fullEnvelope"]["nativeRoleEnvelopeRelation"]["envelopeContained"] is True
    assert after["cadBinding"] is None and after["cadStarted"] is False
    assert after["serviceRegionEngineeringPassed"] is None and after["stationReady"] is False
    assert after["transportContext"] is None
    implementation = inspect.getsource(service.build_cleaning_service_region_audit)
    assert not any(token in implementation for token in ("GN00", "AG00", "AA00", "SS00"))


@pytest.mark.parametrize("rule_name,target,expected", [
    ("cleaning-n000-jj00-v1.json", "project01::JJ00", {
        "longitudinal": 0.4425650858068385,
        "lateral": 0.44961658939928106,
        "supportGap": 0.0,
    }),
    ("cleaning-n000-aa00-v1.json", "project03::AA00", {
        "longitudinal": 0.4448741503380953,
        "lateral": 0.4271165893992572,
        "supportGap": 0.0,
    }),
])
def test_n000_cross_base_rules_derive_target_station_candidates_without_promoting_cad(
        rule_name, target, expected):
    """Real catalog rules remain analytical candidates until fresh CAD passes."""
    rule = geometry._read(ROOT / "data/assembly_stations" / rule_name)
    report = service.build_cleaning_service_region_audit(ROOT, rule)
    assert report["source"] == "project05::N000"
    assert report["target"] == target
    assert report["candidateSuggestion"]["positionParameters"] == pytest.approx(expected)
    assert report["candidateSuggestion"]["prototypePoseUsedForPlacement"] is False
    assert report["candidateSuggestion"]["copySourceWorldPose"] is False
    assert report["capabilityCoverage"]["passed"] is True
    assert report["serviceRegionDemoPassed"] is True
    assert report["fullEnvelope"]["nativeRoleEnvelopeRelation"]["envelopeContained"] is True
    assert report["cadStarted"] is False
    assert report["stationReady"] is False
    assert report["cadExecutionAuthorized"] is False


@pytest.mark.parametrize("rule_name", [
    "cleaning-gn00-a000-v1.json",
    "cleaning-ag00-a000-v1.json",
])
def test_cleaning_only_native_region_does_not_cover_composite_source_capabilities(rule_name):
    rule = geometry._read(ROOT / "data/assembly_stations" / rule_name)
    report = service.build_cleaning_service_region_audit(ROOT, rule)
    coverage = report["capabilityCoverage"]
    assert coverage["passed"] is False
    assert coverage["targetProvidedCapabilities"] == ["cleaning"]
    assert set(coverage["missingCapabilities"]) == {
        "inspection", "weighing", "waste_collection",
    }
    assert report["cadExecutionAuthorized"] is False
    assert report["stationReady"] is False
    assert report["requiredReview"][0]["code"] == "TARGET_SERVICE_CAPABILITIES_INCOMPLETE"


@pytest.mark.parametrize("source", ["project01::GN00", "project03::AG00"])
def test_project02_combined_providers_still_lack_explicit_inspection_semantics(source):
    report = service.build_cleaning_service_capability_audit(
        ROOT,
        source,
        "project02::A600",
        ["project02::A700", "project02::A300", "project02::A200"],
    )
    coverage = report["capabilityCoverage"]
    assert coverage["passed"] is False
    assert coverage["missingCapabilities"] == ["inspection"]
    assert coverage["targetProvidedCapabilities"] == [
        "cleaning", "vision_alignment", "waste_collection", "weighing",
    ]
    assert report["cadStarted"] is False
    assert report["stationReady"] is False
    assert report["auditDigest"]


@pytest.mark.parametrize("source", ["project01::GN00", "project03::AG00"])
def test_project05_provider_discovery_collects_all_exact_capabilities_without_synonyms(source):
    discovery = service.discover_target_project_capability_providers(
        ROOT, source, "project05::A000"
    )
    token_sets = {tuple(row["projectModuleTokens"]) for row in discovery["providers"]}
    assert {("G000",), ("N000",), ("P000",)}.issubset(token_sets)
    assert discovery["providedRequiredCapabilities"] == [
        "cleaning", "waste_collection", "weighing",
    ]
    assert discovery["unresolvedCapabilities"] == ["inspection"]
    assert discovery["nearMatchProvidersRequiringEngineeringDecision"][0][
        "projectModuleTokens"
    ] == ["M000"]
    assert discovery["nearMatchProvidersRequiringEngineeringDecision"][0][
        "countsAsCoverage"
    ] is False
    assert discovery["cadStarted"] is False

    audit = service.build_cleaning_service_capability_audit(
        ROOT,
        source,
        "project05::A000",
        discovery["providerModuleDefinitionIds"],
    )
    assert audit["capabilityCoverage"]["missingCapabilities"] == ["inspection"]
    assert "vision_alignment" not in audit["capabilityCoverage"][
        "targetProvidedCapabilities"
    ]
    discovered_audit = service.build_discovered_cleaning_service_capability_audit(
        ROOT, source, "project05::A000"
    )
    assert discovered_audit["capabilityCoverage"]["missingCapabilities"] == [
        "inspection"
    ]
    assert discovered_audit["providerDiscovery"]["cadStarted"] is False
    assert discovered_audit["auditDigest"]


def test_provider_discovery_rejects_non_composite_source_and_implicit_base_reference():
    with pytest.raises(ValueError, match="explicit project::token"):
        service.discover_target_project_capability_providers(
            ROOT, "project01::GN00", "A000"
        )
    with pytest.raises(ValueError, match="CleaningWeighing"):
        service.discover_target_project_capability_providers(
            ROOT, "project05::N000", "project02::A600"
        )


def test_semantic_capability_decisions_are_deduplicated_by_target_project():
    request = service.build_cleaning_capability_semantic_decision_request(
        ROOT,
        "data/assembly_stations/cleaning-service-capability-coverage-index-v3.json",
    )
    assert request["summary"] == {
        "decisionCount": 2,
        "affectedPairCount": 4,
        "confirmedCount": 0,
    }
    assert {row["targetProjectId"] for row in request["decisions"]} == {
        "project02", "project05",
    }
    assert all(row["requiredCapability"] == "inspection" for row in request["decisions"])
    assert all(row["offeredCapabilities"] == ["vision_alignment"] for row in request["decisions"])
    assert all(row["confirmed"] is False for row in request["decisions"])
    assert request["cadStarted"] is False


def test_capability_audit_does_not_infer_synonyms_or_accept_duplicate_providers():
    with pytest.raises(ValueError, match="nonempty unique"):
        service.build_cleaning_service_capability_audit(
            ROOT,
            "project01::GN00",
            "project02::A600",
            ["project02::A700", "project02::A700"],
        )
    with pytest.raises(ValueError, match="CleaningWeighing"):
        service.build_cleaning_service_capability_audit(
            ROOT,
            "project05::N000",
            "project02::A600",
            ["project02::A700"],
        )


@pytest.mark.parametrize("change,error", [
    ("missing_path", "missing cleaning service inputs"),
    ("missing_input", "missing required geometry input paths"),
    ("empty_service", "subtree groups"),
    ("duplicate_service", "subtree groups"),
    ("unknown_identity", "occupancy is missing"),
])
def test_rule_data_gaps_fail_closed_without_special_module_branches(change, error):
    rule = geometry._read(ROOT / "data/assembly_stations/cleaning-ag00-aa00-native-v1.json")
    if change == "missing_path":
        rule["inputs"]["movingFaces"] = "demo/intentionally-missing-cleaning-faces.json"
    elif change == "missing_input":
        del rule["inputs"]["movingFaces"]
    elif change == "empty_service":
        rule["serviceSubtrees"] = []
    elif change == "duplicate_service":
        rule["serviceSubtrees"].append(rule["serviceSubtrees"][0])
    else:
        rule["moduleTokens"]["source"] = "UNKNOWN00"
    with pytest.raises(ValueError, match=error):
        service.build_cleaning_service_region_audit(ROOT, rule)


def test_datum_case_path_is_supported_without_a_graph_path():
    rule = geometry._read(ROOT / service.DEFAULT_RULE)
    rule["datumCase"] = str(Path(rule["inputs"].pop("datumGraph")).parent)
    result = service.build_cleaning_service_region_audit(ROOT, rule)
    assert result["candidateSuggestion"]["positionParameters"]["lateral"] == pytest.approx(0.231)


@pytest.mark.parametrize("which", ["moving", "base", "transport"])
def test_duplicate_source_instances_are_not_silently_selected(monkeypatch, which):
    original = geometry._read
    directory = ROOT / "demo/role_station_strengthening_20261028/functional-chain-v1/s05-gn00"
    state_path = directory / "reopened-state.json"
    token = {"moving": "GN00", "base": "AA00", "transport": "SS00"}[which]
    def changed(path):
        payload = copy.deepcopy(original(path))
        if path == state_path:
            rows = payload["observed"]["components"]
            duplicate = copy.deepcopy(next(row for row in rows if token in row["name"]))
            duplicate["name"] = "a-second-instance-with-the-same-source"
            rows.append(duplicate)
        return payload
    monkeypatch.setattr(geometry, "_read", changed)
    with pytest.raises(ValueError, match="identity/configuration mismatch"):
        service.build_cleaning_service_region_audit(ROOT, original(ROOT / service.DEFAULT_RULE),
            cad_result_path=directory / "cad-result.json", saved_state_path=state_path)


def test_consistent_source_world_translation_does_not_change_proposed_target_placement(monkeypatch):
    """Synthetic read-model perturbation: source world pose is only a bridge."""
    original = geometry._read
    rule = original(ROOT / service.DEFAULT_RULE)
    baseline = service.build_cleaning_service_region_audit(ROOT, rule)
    delta = [0.37, -0.28, 0.19]
    paths = {key: ROOT / value for key, value in rule["inputs"].items()}
    def translate(values):
        return [value + delta[i] for i, value in enumerate(values)]
    def changed(path):
        payload = copy.deepcopy(original(path))
        if path == paths["movingOccupancy"]:
            payload["installationFrame"]["originWorldMeters"] = translate(payload["installationFrame"]["originWorldMeters"])
        if path in (paths["movingNativeGraph"], paths["movingFaces"]):
            for module in payload["Modules"]:
                module["SourceTransform"][9:12] = translate(module["SourceTransform"][9:12])
        if path == paths["datumGraph"]:
            for mate in payload["Mates"]:
                for endpoint in mate["Endpoints"]:
                    if endpoint["ModuleToken"] == rule["moduleTokens"]["source"]:
                        endpoint["FaceCenterWorld"] = translate(endpoint["FaceCenterWorld"])
        if path == paths["movingFaces"]:
            for row in payload["Endpoints"]:
                row["Endpoint"]["FaceCenterWorld"] = translate(row["Endpoint"]["FaceCenterWorld"])
        return payload
    monkeypatch.setattr(geometry, "_read", changed)
    report = service.build_cleaning_service_region_audit(ROOT, rule)
    assert report["candidateSuggestion"]["positionParameters"] == pytest.approx(baseline["candidateSuggestion"]["positionParameters"])
    assert report["candidateSuggestion"]["predictedRootTransformMeasurementOnly"] == pytest.approx(
        baseline["candidateSuggestion"]["predictedRootTransformMeasurementOnly"], abs=1e-12)


def test_changed_target_native_coordinate_frame_is_rejected(monkeypatch):
    original = geometry._read
    rule = original(ROOT / service.DEFAULT_RULE)
    def changed(path):
        payload = copy.deepcopy(original(path))
        if path == ROOT / rule["inputs"]["targetOccupancy"]:
            payload["installationFrame"]["originWorldMeters"][2] += 0.25
        return payload
    monkeypatch.setattr(geometry, "_read", changed)
    with pytest.raises(ValueError, match="coordinate frames disagree"):
        service.build_cleaning_service_region_audit(ROOT, rule)
