"""Registry/plan tests are offline and must never be reported as CAD evidence."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from demo_backend import station_rule_registry as registry
from demo_backend import station_rule_planner as planner


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


@pytest.mark.parametrize("failure", [None, "duplicate", "rule", "parameters", "geometry", "release", "unmatched"])
def test_parameter_variant_requires_exact_rule_current_geometry_and_release(setup, monkeypatch, failure):
    root, _, _, rule = setup
    params = {"longitudinal": .3, "lateral": .2, "supportGap": 0}
    row = {"ruleId": rule["ruleId"], "positionParametersMeters": params,
           "planPath": "variant-plan.json", "cadResultPath": "cad.json",
           "savedStatePath": "state.json", "releaseManifestPath": "release.json"}
    plan = {"ruleBinding": {"rule": deepcopy(rule)}, "effectivePositionParametersMeters": dict(params), "evidence": []}
    if failure == "rule": plan["ruleBinding"]["rule"]["targetBaseDefinitionId"] = "wrong"
    if failure == "parameters": plan["effectivePositionParametersMeters"]["longitudinal"] = .4
    write(root / "variant-plan.json", plan)
    for path in ("cad.json", "state.json", "release.json"):
        write(root / path, {})
    payload = registry.read(root / "registry.json")
    payload["parameterRecipes"] = [row, deepcopy(row)] if failure == "duplicate" else [row]
    write(root / "registry.json", payload)
    selected = binding(setup)
    monkeypatch.setattr(planner, "verify_station_stage", lambda *a, **kw: {"targetStationValidated": failure != "geometry"})
    import demo_backend.global_relation_catalog_release as releases
    monkeypatch.setattr(releases, "load_relation_catalog_release", lambda *a, **kw: ({}, {"releaseMetadata": {
        "relationExecutionMode": "datum_placement_demo", "parameterizedDatumPairBinding": {
            "moduleDefinitionId": rule["sourceModuleDefinitionId"],
            "slotDefinitionId": rule["targetBaseDefinitionId"],
            "cadResultSha256": "wrong" if failure == "release" else registry.sha(root / "cad.json")}}}))
    if failure == "unmatched":
        assert planner.resolve_parameter_recipe(root, selected, {**params, "longitudinal": .8}) == (None, [])
    elif failure:
        with pytest.raises(registry.StationRuleError):
            planner.resolve_parameter_recipe(root, selected, params)
    else:
        authority, evidence = planner.resolve_parameter_recipe(root, selected, params)
        assert authority["relationExecutionMode"] == "datum_placement_demo"
        assert len(evidence) == 4


@pytest.fixture
def setup(tmp_path):
    scope = {"bases": [{"moduleDefinitionId": "p::BASE", "cadModuleDefinitionId": "cad/base", "role": "Base"}],
        "movingModules": [{"moduleDefinitionId": "p::CLEAN", "cadModuleDefinitionId": "cad/clean", "role": "CleaningWeighing"},
                          {"moduleDefinitionId": "p::SCAN", "cadModuleDefinitionId": "cad/scan", "role": "Scanner"},
                          {"moduleDefinitionId": "p::TRANSPORT", "cadModuleDefinitionId": "cad/transport", "role": "Transport"}]}
    config = {"schemaVersion": "cleaning-service-region-rule/v1", "ruleId": "clean",
        "sourceModuleDefinitionId": "p::CLEAN", "targetBaseDefinitionId": "p::BASE", "inputs": {"geometry": "geometry.json"}}
    rule = {"ruleId": "clean", "role": "CleaningWeighing", "sourceModuleDefinitionId": "p::CLEAN",
        "targetBaseDefinitionId": "p::BASE", "evaluator": {"kind": "cleaning_service_region", "inputPath": "config.json"},
        "placement": {"strategy": "target_role_region"}, "requiresPrototypeEstimateAuthorization": True,
        "validation": {"status": "candidate"}}
    write(tmp_path / "scope.json", scope)
    write(tmp_path / "config.json", config)
    write(tmp_path / "geometry.json", {"measured": True})
    write(tmp_path / "registry.json", {"schemaVersion": "target-station-rule-registry/v1", "scopePath": "scope.json", "rules": [rule]})
    return tmp_path, scope, config, rule


def loaded(setup):
    return registry.load_station_registry(setup[0], "registry.json")


def binding(setup):
    return registry.select_station_rule(loaded(setup), source="cad/clean", target_base="cad/base", allow_prototype_estimate=True)


def instances():
    return [{"instanceId": "base", "moduleDefinitionId": "p::BASE", "role": "Base"},
            {"instanceId": "clean", "moduleDefinitionId": "p::CLEAN", "role": "CleaningWeighing"}]


def request():
    return {"chainId": "data-only", "stationRegistryPath": "registry.json", "allowPrototypeEstimate": True,
        "baseSelection": {"projectId": "p", "moduleToken": "BASE", "confirmed": True},
        "steps": [{"stageId": "clean", "moduleSelection": {"projectId": "p", "moduleToken": "CLEAN", "confirmed": True},
                   "allowDatumFallback": True}]}


def released_recipe_fixture(tmp_path, monkeypatch):
    write(tmp_path / "release.json", {"released": True})
    catalog = {
        "semanticPorts": [
            {"globalPortId": "global/source", "moduleDefinitionId": "cad/source",
             "aliases": ["SOURCE.installation"]},
            {"globalPortId": "global/base", "moduleDefinitionId": "cad/base",
             "aliases": ["BASE.installation"]},
        ],
        "connectionTemplates": [{
            "globalTemplateId": "template/exact",
            "candidatePortIdsA": ["global/source"],
            "candidatePortIdsB": ["global/base"],
            "constraintEffect": {"fullyLocatesAddedComponent": True},
        }],
    }
    manifest = {"scope": {"authorizedDrivingTemplateIds": ["template/exact"]}}
    import demo_backend.global_relation_catalog_release as releases
    monkeypatch.setattr(
        releases, "load_relation_catalog_release", lambda *_a, **_k: (catalog, manifest)
    )
    config = {
        "sourcePortId": "SOURCE.installation",
        "targetPortId": "BASE.installation",
        "expectedGlobalTemplateId": "template/exact",
        "inputs": {"referenceReleasePath": "release.json"},
    }
    authority = {
        "ready": True,
        "relationExecutionMode": "direct_installation",
        "releaseManifestPath": "release.json",
    }
    return config, authority, catalog, manifest


def test_registered_release_recipe_accepts_aliases_of_exact_released_ports(
    tmp_path, monkeypatch
):
    config, authority, _, _ = released_recipe_fixture(tmp_path, monkeypatch)

    release_path, recipe = planner._registered_release_recipe(
        tmp_path,
        config,
        authority,
        source_definition_id="cad/source",
        base_definition_id="cad/base",
    )

    assert release_path == tmp_path / "release.json"
    assert recipe["globalTemplateId"] == "template/exact"


def test_registered_release_recipe_accepts_explicit_unrevoked_release_when_current_catalog_omits_module(
    tmp_path, monkeypatch
):
    config, _, _, _ = released_recipe_fixture(tmp_path, monkeypatch)
    config["allowExplicitImmutableReleaseWhenCurrentCatalogMissing"] = True
    authority = {
        "ready": False,
        "preferredPlan": {"nativePlan": {"status": "module_not_registered"}},
    }
    import demo_backend.global_interface_contract_planner as contracts
    monkeypatch.setattr(contracts, "_released_template_safety_blockers", lambda *_a, **_k: [])

    release_path, recipe = planner._registered_release_recipe(
        tmp_path,
        config,
        authority,
        source_definition_id="cad/source",
        base_definition_id="cad/base",
    )

    assert release_path == tmp_path / "release.json"
    assert recipe["globalTemplateId"] == "template/exact"


def test_registered_release_recipe_rejects_explicit_release_when_runtime_safety_revokes_it(
    tmp_path, monkeypatch
):
    config, _, _, _ = released_recipe_fixture(tmp_path, monkeypatch)
    config["allowExplicitImmutableReleaseWhenCurrentCatalogMissing"] = True
    authority = {
        "ready": False,
        "preferredPlan": {"nativePlan": {"status": "module_not_registered"}},
    }
    import demo_backend.global_interface_contract_planner as contracts
    monkeypatch.setattr(
        contracts,
        "_released_template_safety_blockers",
        lambda *_a, **_k: [{"status": "blocked"}],
    )

    with pytest.raises(
        registry.StationRuleError,
        match="REGISTERED_TARGET_STATION_RELEASED_RECIPE_REVOKED",
    ):
        planner._registered_release_recipe(
            tmp_path,
            config,
            authority,
            source_definition_id="cad/source",
            base_definition_id="cad/base",
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("wrong_release", "TARGET_STATION_REFERENCE_RELEASE_CHANGED"),
        ("wrong_owner", "REGISTERED_TARGET_STATION_PORT_OWNER_MISMATCH"),
        ("not_authorized", "REGISTERED_TARGET_STATION_RELEASED_RECIPE_NOT_UNIQUE"),
        ("not_fully_locating", "REGISTERED_TARGET_STATION_RELEASED_RECIPE_NOT_UNIQUE"),
    ],
)
def test_registered_release_recipe_fails_closed(
    tmp_path, monkeypatch, mutation, message
):
    config, authority, catalog, manifest = released_recipe_fixture(tmp_path, monkeypatch)
    if mutation == "wrong_release":
        write(tmp_path / "other-release.json", {})
        authority["releaseManifestPath"] = "other-release.json"
    elif mutation == "wrong_owner":
        catalog["semanticPorts"][0]["moduleDefinitionId"] = "cad/other"
    elif mutation == "not_authorized":
        manifest["scope"]["authorizedDrivingTemplateIds"] = []
    elif mutation == "not_fully_locating":
        catalog["connectionTemplates"][0]["constraintEffect"][
            "fullyLocatesAddedComponent"
        ] = False

    with pytest.raises(registry.StationRuleError, match=message):
        planner._registered_release_recipe(
            tmp_path,
            config,
            authority,
            source_definition_id="cad/source",
            base_definition_id="cad/base",
        )


@pytest.fixture
def geometry(monkeypatch):
    from demo_backend import cleaning_service_region
    value = {"serviceRegionDemoPassed": True,
             "capabilityCoverage": {"passed": True},
             "candidateSuggestion": {"positionParameters": {"longitudinal": .3, "lateral": .2, "supportGap": 0}}, "evidence": []}
    monkeypatch.setattr(cleaning_service_region, "build_cleaning_service_region_audit", lambda *_a, **_k: deepcopy(value))
    return value


def test_candidate_configuration_is_not_validated_or_cad_authority(setup):
    review = loaded(setup)["reviews"][0]
    assert review["configuredStationRule"]
    assert not review["validatedStationRule"]
    assert not review["cadLaunchAllowed"]
    assert not review["mechanicalCompatibilityPromoted"]


def test_stage_candidate_rule_adds_configuration_without_cad_authority(setup):
    root, _, _, rule = setup
    base = registry.read(root / "registry.json")
    base["rules"] = []
    candidate_registry = {
        "schemaVersion": "target-station-rule-registry/v1",
        "scopePath": "scope.json",
        "rules": [deepcopy(rule)],
    }

    merged, report = registry.stage_candidate_rule(
        root, base, candidate_registry, rule_id="clean"
    )

    assert merged["rules"] == [rule]
    assert report["status"] == "candidate_staged_for_cad_validation"
    assert report["review"]["configuredStationRule"] is True
    assert report["review"]["validatedStationRule"] is False
    assert report["cadLaunchAllowed"] is False


def test_stage_candidate_rule_rejects_pair_conflict_and_validated_label(setup):
    root, _, _, rule = setup
    base = registry.read(root / "registry.json")
    other = deepcopy(rule)
    other["ruleId"] = "other"
    base["rules"] = [other]
    candidate_registry = {
        "schemaVersion": "target-station-rule-registry/v1",
        "scopePath": "scope.json",
        "rules": [deepcopy(rule)],
    }
    with pytest.raises(registry.StationRuleError, match="PAIR_ALREADY"):
        registry.stage_candidate_rule(root, base, candidate_registry, rule_id="clean")

    candidate_registry["rules"][0]["validation"] = {
        "status": "experimental_cad_verified"
    }
    with pytest.raises(registry.StationRuleError, match="ONLY_UNVALIDATED"):
        registry.stage_candidate_rule(root, {**base, "rules": []}, candidate_registry, rule_id="clean")


def test_estimate_requires_explicit_authorization(setup):
    with pytest.raises(ValueError, match="AUTHORIZATION_REQUIRED"):
        registry.select_station_rule(loaded(setup), source="p::CLEAN", target_base="p::BASE")


def test_duplicate_pair_requires_rule_selection(setup):
    root, _, _, rule = setup
    second = deepcopy(rule)
    second["ruleId"] = "other"
    config = deepcopy(setup[2]); config["ruleId"] = "other"
    write(root / "other.json", config)
    second["evaluator"]["inputPath"] = "other.json"
    data = registry.read(root / "registry.json"); data["rules"].append(second)
    write(root / "registry.json", data)
    with pytest.raises(ValueError, match="AMBIGUOUS"):
        binding(setup)
    result = registry.select_station_rule(loaded(setup), source="p::CLEAN", target_base="p::BASE", rule_id="other", allow_prototype_estimate=True)
    assert result["rule"]["ruleId"] == "other"


@pytest.mark.parametrize("changed", ["geometry.json", "config.json", "scope.json", "registry.json"])
def test_source_or_catalog_change_invalidates_old_binding(setup, changed):
    prior = binding(setup)
    path = setup[0] / changed
    path.write_text(path.read_text()+" ", encoding="utf-8")
    with pytest.raises(ValueError, match="CHANGED"):
        registry.revalidate_rule_binding(setup[0], prior)


def test_same_pair_wrong_config_is_invalid(setup):
    config = setup[2]; config["targetBaseDefinitionId"] = "p::OTHER"
    write(setup[0] / "config.json", config)
    review = loaded(setup)["reviews"][0]
    assert not review["configuredStationRule"]
    assert "MISMATCH" in review["blockingReasonCodes"][0]


def test_configured_input_pin_must_match(setup):
    config = setup[2]; config["inputSha256"] = {"geometry": "wrong"}
    write(setup[0] / "config.json", config)
    assert "RULE_CONFIG_INPUT_CHANGED:geometry" in loaded(setup)["reviews"][0]["blockingReasonCodes"]


def test_historical_closure_label_without_rule_binding_is_not_accepted(setup):
    rule = deepcopy(setup[3]); rule["validation"] = {"status": "released_demo", "kind": "functional_chain_closure"}
    result = registry.validate_rule(setup[0], rule, setup[1])
    assert not result["validatedStationRule"]
    assert "STATION_VALIDATION_RULE_NOT_BOUND" in result["blockingReasonCodes"]


def test_dependency_order_and_explicit_instance_choice(setup):
    selected = binding(setup)
    selected["rule"]["dependencies"] = [{"role": "Transport", "moduleDefinitionId": "p::TRANSPORT"}]
    with pytest.raises(ValueError, match="DEPENDENCY_MISSING"):
        registry.bind_rule_instances(selected, instances(), source_instance_id="clean", base_instance_id="base")
    context = instances()+[{"instanceId": name, "moduleDefinitionId": "p::TRANSPORT", "role": "Transport"} for name in ("t1", "t2")]
    with pytest.raises(ValueError, match="DEPENDENCY_AMBIGUOUS"):
        registry.bind_rule_instances(selected, context, source_instance_id="clean", base_instance_id="base")
    bound = registry.bind_rule_instances(selected, context, source_instance_id="clean", base_instance_id="base", dependency_selections={"Transport": "t2"})
    assert bound["instances"]["Transport"]["instanceId"] == "t2"


def test_registered_rule_derives_parameters_without_cad(setup, geometry):
    result = planner.plan_station_chain(setup[0], request())
    assert result["planningComplete"] and not result["cadLaunchAllowed"]
    plan = result["stages"][0]["plan"]
    assert plan["effectivePositionParametersMeters"]["longitudinal"] == .3
    assert plan["requiresFreshCadValidation"]
    assert plan["validationPackage"] is None
    assert not plan["targetStationValidated"]


def test_native_cleaning_station_reuses_direct_recipe_and_keeps_geometry_as_postcheck(
    setup, geometry, monkeypatch
):
    root, _, config, _ = setup
    config["nativeRoleModuleDefinitionId"] = "p::CLEAN"
    write(root / "config.json", config)
    write(root / "release.json", {"released": True})
    from demo_backend import global_interface_contract_planner as authority_planner
    from demo_backend import global_relation_catalog_release as releases

    monkeypatch.setattr(
        authority_planner,
        "resolve_preferred_released_interface_authority",
        lambda *_a, **_k: {
            "ready": True,
            "relationExecutionMode": "direct_installation",
            "releaseManifestPath": "release.json",
            "preferredPlan": {
                "nativePlan": {
                    "instantiatedTemplate": {
                        "constraintEffect": {"fullyLocatesAddedComponent": True}
                    }
                }
            },
        },
    )
    monkeypatch.setattr(releases, "load_relation_catalog_release", lambda *_a, **_k: ({}, {}))

    plan = planner.plan_station_chain(root, request())["stages"][0]["plan"]

    assert plan["executionUsesReleasedNativeRecipe"] is True
    assert plan["requiresFreshCadValidation"] is False
    assert plan["validationPackage"] is None
    assert plan["reusableExecutionAuthority"]["relationExecutionMode"] == "direct_installation"
    assert plan["effectivePositionParametersMeters"] == {
        "longitudinal": 0.3,
        "lateral": 0.2,
        "supportGap": 0.0,
    }


def test_native_cleaning_direct_recipe_does_not_require_datum_fallback_flag(
    setup, geometry, monkeypatch
):
    root, _, config, _ = setup
    config["nativeRoleModuleDefinitionId"] = "p::CLEAN"
    write(root / "config.json", config)
    write(root / "release.json", {"released": True})
    from demo_backend import global_interface_contract_planner as authority_planner
    from demo_backend import global_relation_catalog_release as releases

    monkeypatch.setattr(
        authority_planner,
        "resolve_preferred_released_interface_authority",
        lambda *_a, **_k: {
            "ready": True,
            "relationExecutionMode": "direct_installation",
            "releaseManifestPath": "release.json",
            "preferredPlan": {
                "nativePlan": {
                    "instantiatedTemplate": {
                        "constraintEffect": {"fullyLocatesAddedComponent": True}
                    }
                }
            },
        },
    )
    monkeypatch.setattr(releases, "load_relation_catalog_release", lambda *_a, **_k: ({}, {}))
    req = request()
    req["steps"][0].pop("allowDatumFallback")

    row = planner.plan_station_chain(root, req)["stages"][0]

    assert row["planned"] is True
    assert row["plan"]["executionUsesReleasedNativeRecipe"] is True
    assert row["plan"]["reusableExecutionAuthority"]["relationExecutionMode"] == "direct_installation"


def test_override_is_explicit_new_candidate_not_changed_old_release(setup, geometry):
    req = request()
    req["steps"][0]["positionParametersMeters"] = {"longitudinal": .31, "lateral": .2, "supportGap": 0}
    plan = planner.plan_station_chain(setup[0], req)["stages"][0]["plan"]
    assert plan["derivedPositionParametersMeters"]["longitudinal"] == .3
    assert plan["effectivePositionParametersMeters"]["longitudinal"] == .31
    assert plan["explicitPositionOverride"] and plan["requiresFreshCadValidation"]


@pytest.mark.parametrize("bad", [True, float("nan"), float("inf"), -.1, "10mm"])
def test_bad_units_values_do_not_reach_candidate_compiler(setup, geometry, bad):
    req = request(); req["steps"][0]["positionParametersMeters"] = {"longitudinal": bad, "lateral": .2, "supportGap": 0}
    row = planner.plan_station_chain(setup[0], req)["stages"][0]
    assert not row["planned"]
    assert "POSITION_REQUIRES" in row["blockingReasonCodes"][0]


def test_missing_station_and_unauthorized_datum_remain_visible(setup, geometry):
    req = request(); req["steps"][0]["allowDatumFallback"] = False
    assert "DATUM_FALLBACK_AUTHORIZATION_REQUIRED" in planner.plan_station_chain(setup[0], req)["stages"][0]["blockingReasonCodes"]
    req["steps"][0]["moduleSelection"]["moduleToken"] = "SCAN"
    assert "TARGET_STATION_RULE_MISSING" in planner.plan_station_chain(setup[0], req)["stages"][0]["blockingReasonCodes"]


def test_failed_predicted_service_region_is_not_planned(setup, geometry):
    geometry["serviceRegionDemoPassed"] = False
    assert "PREDICTED_CLEANING_SERVICE_REGION_FAILED" in planner.plan_station_chain(setup[0], request())["stages"][0]["blockingReasonCodes"]


def test_duplicate_instance_and_modified_instance_binding_are_rejected(setup, geometry):
    selected = binding(setup)
    bound = registry.bind_rule_instances(selected, instances(), source_instance_id="clean", base_instance_id="base")
    bound["instances"]["source"]["moduleDefinitionId"] = "p::WRONG"
    with pytest.raises(ValueError, match="STATION_INSTANCE_BINDING_CHANGED"):
        planner.plan_station_stage(setup[0], selected, bound)
    req = request(); req["steps"][0]["instanceId"] = "base"
    with pytest.raises(ValueError, match="IDS_MISSING_OR_DUPLICATE"):
        planner.plan_station_chain(setup[0], req)


def test_cup_direction_is_preserved_for_compile_and_postcheck():
    geometry = {"stationSuggestion": {"mateParameters": [
        {"parameter": "longitudinal", "suggestedDistanceFlipDimension": False},
        {"parameter": "lateral", "suggestedDistanceFlipDimension": True},
    ]}}
    assert planner.cup_distance_flips(geometry) == {"longitudinal": False, "lateral": True, "supportGap": False}
    geometry["stationSuggestion"]["mateParameters"][1]["parameter"] = "longitudinal"
    with pytest.raises(ValueError, match="CUP_DISTANCE_DIRECTION"):
        planner.cup_distance_flips(geometry)


def test_prepare_reuses_existing_parameterized_compiler(setup, geometry, monkeypatch):
    from demo_backend import parameterized_datum_placement
    calls = []
    def compile_package(*args, **kwargs):
        calls.append((args, kwargs))
        return {"effectiveGraph": {}, "selectedEndpointCatalog": {}, "readyForReleasedCadExecution": False}
    monkeypatch.setattr(parameterized_datum_placement, "compile_parameterized_datum_validation_package", compile_package)
    plan = planner.plan_station_chain(setup[0], request(), prepare_candidates=True)["stages"][0]["plan"]
    assert calls[0][0][1:] == ("p::CLEAN", "p::BASE")
    assert calls[0][1]["position_parameters"] == plan["effectivePositionParametersMeters"]
    assert not plan["validationPackage"]["readyForReleasedCadExecution"]


def test_real_registered_rules_remain_configuration_only():
    root = Path(__file__).resolve().parents[3]
    data = registry.load_station_registry(root)
    assert len(data["reviews"]) >= 5
    assert all(row["configuredStationRule"] and not row["validatedStationRule"] for row in data["reviews"])


def test_actual_mates_bound_by_geometry_and_parameter_not_just_names():
    mate = {"MateName": "template-long", "MateType": 5, "Alignment": 0, "Distance": .3,
            "Endpoints": [{"ModuleToken": "A", "FaceIndexInBody": 1, "FaceCenterLocal": [0, 0, 0]},
                          {"ModuleToken": "B", "FaceIndexInBody": 2, "FaceCenterLocal": [1, 0, 0]}]}
    actual = deepcopy(mate); actual["MateName"] = "actual-long"
    assert planner.bind_executed_candidate_parameters({"Mates": [mate]}, {"Mates": [actual]}) == {"template-long": "actual-long"}
    actual["Distance"] = .31
    with pytest.raises(ValueError, match="ENDPOINT_OR_PARAMETER"):
        planner.bind_executed_candidate_parameters({"Mates": [mate]}, {"Mates": [actual]})
    actual["Distance"] = .3; actual["Endpoints"][0]["FaceIndexInBody"] = 5
    with pytest.raises(ValueError, match="ENDPOINT_OR_PARAMETER"):
        planner.bind_executed_candidate_parameters({"Mates": [mate]}, {"Mates": [actual]})


def test_inserted_identity_accepts_exact_filename_not_foreign_suffix():
    path = "FL9A24D063AI00.001.SLDASM"
    assert planner.inserted_token_matches("AI00", "project03::AI00", path)
    assert planner.inserted_token_matches("FL9A24D063AI00", "project03::AI00", path)
    assert not planner.inserted_token_matches("OTHERAI00", "project03::AI00", path)
    assert not planner.inserted_token_matches("SS00", "project03::AI00", path)


def test_released_station_graph_checks_current_parameters_and_evidence(tmp_path, monkeypatch):
    from demo_backend import global_relation_catalog_release as releases
    graph = {"Mates": [{"MateName": "reference", "MateType": 5, "Distance": .05,
                        "Endpoints": [{"ModuleToken": "T", "FaceIndexInBody": 2}]}]}
    graph_path = write(tmp_path / "graph.json", graph)
    cad_path = write(tmp_path / "cad.json", {
        "toolResult": {"TargetModuleToken": "T"}, "effectiveGraphPath": str(graph_path),
        "effectiveGraphSha256": registry.sha(graph_path)})
    release = write(tmp_path / "release.json", {})
    manifest = {"validationEvidence": [{"path": str(cad_path), "fileSha256": registry.sha(cad_path)}]}
    monkeypatch.setattr(releases, "load_relation_catalog_release", lambda *a, **k: ({}, manifest))
    actual = deepcopy(graph); actual["Mates"][0]["MateName"] = "new-name"
    result = planner.verify_released_station_graph(tmp_path, release, "T", actual)
    assert result["proxyGeometryPassed"] and not result["processFunctionVerified"]
    actual["Mates"][0]["Distance"] = .06
    with pytest.raises(ValueError, match="CURRENT_MATES_DIFFER"):
        planner.verify_released_station_graph(tmp_path, release, "T", actual)
    with pytest.raises(ValueError, match="CURRENT_MATES_DIFFER"):
        planner.verify_released_station_graph(tmp_path, release, "OTHER", graph)
    write(graph_path, actual)
    with pytest.raises(ValueError, match="GRAPH_CHANGED"):
        planner.verify_released_station_graph(tmp_path, release, "T", actual)


def test_postcheck_rejects_plan_change_before_reading_cad(setup, geometry):
    plan = planner.plan_station_chain(setup[0], request())["stages"][0]["plan"]
    plan["effectivePositionParametersMeters"]["longitudinal"] = .9
    with pytest.raises(ValueError, match="STATION_PLAN_CHANGED"):
        planner.verify_station_stage(setup[0], plan, cad_result_path="not-present", saved_state_path="not-present")


def test_postcheck_does_not_credit_another_targets_cad_execution(setup, geometry, monkeypatch):
    from demo_backend import functional_chain_closure
    plan = planner.plan_station_chain(setup[0], request())["stages"][0]["plan"]
    monkeypatch.setattr(functional_chain_closure, "build_functional_chain_closure", lambda *_a, **_k: {"cadPassed": True})
    write(setup[0] / "cad.json", {"toolResult": {"TargetModuleToken": "OTHER"}})
    with pytest.raises(ValueError, match="CAD_INSERTED_TARGET_DIFFERS"):
        planner.verify_station_stage(setup[0], plan, cad_result_path="cad.json", saved_state_path="not-present")


def test_released_label_with_wrong_pair_removes_validated_claim(setup, monkeypatch):
    from demo_backend import global_relation_catalog_release
    rule = deepcopy(setup[3])
    rule["validation"] = {"status": "released_demo", "releaseManifestPath": "release.json", "cadResultPath": "cad.json"}
    write(setup[0] / "release.json", {})
    write(setup[0] / "cad.json", {})
    monkeypatch.setattr(registry, "_verified_experimental_closure", lambda *_a: True)
    monkeypatch.setattr(global_relation_catalog_release, "load_relation_catalog_release", lambda *_a, **_k: ({}, {
        "releaseMetadata": {"relationExecutionMode": "datum_placement_demo", "parameterizedDatumPairBinding": {"moduleDefinitionId": "wrong"}}}))
    review = registry.validate_rule(setup[0], rule, setup[1])
    assert not review["validatedStationRule"]
    assert "STATION_RELEASE_DOES_NOT_BIND_VALIDATED_PAIR" in review["blockingReasonCodes"]


def test_parameter_change_invalidates_reuse_of_published_station(setup, geometry, monkeypatch):
    selected = binding(setup)
    old = {"effectivePositionParametersMeters": {"longitudinal": .3, "lateral": .2, "supportGap": 0}}
    write(setup[0] / "verified-plan.json", old)
    # This isolated test supplies a trusted prevalidated review. Real loading
    # recomputes the CAD/geometry and immutable pair release before this point.
    selected["rule"]["validation"]["planPath"] = "verified-plan.json"
    selected["review"]["ruleDigest"] = registry.digest(selected["rule"])
    selected["review"]["releasedExecutionAuthority"] = {"releaseManifestPath": "release.json", "relationExecutionMode": "datum_placement_demo"}
    monkeypatch.setattr(planner, "revalidate_rule_binding", lambda *_a: selected["review"])
    bound = registry.bind_rule_instances(selected, instances(), source_instance_id="clean", base_instance_id="base")
    result = planner.plan_station_stage(setup[0], selected, bound)
    assert not result["requiresFreshCadValidation"]
    changed = planner.plan_station_stage(setup[0], selected, bound,
        position_override={"longitudinal": .31, "lateral": .2, "supportGap": 0})
    assert changed["requiresFreshCadValidation"] and changed["reusableExecutionAuthority"] is None


def test_self_signed_rule_or_review_cannot_override_current_registry(setup):
    selected = binding(setup)
    selected["rule"]["placement"]["strategy"] = "released_recipe"
    selected["review"]["ruleDigest"] = registry.digest(selected["rule"])
    with pytest.raises(ValueError, match="DIFFERS_FROM_REGISTERED_RULE"):
        registry.revalidate_rule_binding(setup[0], selected)
    selected = binding(setup)
    selected["review"]["releasedExecutionAuthority"] = {"releaseManifestPath": "invented.json"}
    with pytest.raises(ValueError, match="REVIEW_CHANGED"):
        registry.revalidate_rule_binding(setup[0], selected)


@pytest.mark.parametrize("failure", [None, "missing", "state_changed", "assembly_changed", "wrong_name", "wrong_definition", "configuration"])
def test_scanner_logical_dependency_selects_exact_observed_instance(setup, failure):
    root, scope, _, _ = setup
    path = str(root / "transport.SLDASM")
    rows = [{"name": name, "sourcePath": path, "configuration": "Default"} for name in ("transport-1", "transport-2")]
    state = {"observed": {"components": deepcopy(rows)}}
    assembly = root / "old.SLDASM"
    assembly.write_bytes(b"synthetic offline fixture, not CAD evidence")
    previous = {"success": True, "assemblyPath": str(assembly), "assemblySha256": registry.sha(assembly),
                "observed": {"readOnly": True, "components": rows}}
    saved = write(root / "old-state.json", previous)
    proof = {"savedStatePath": str(saved), "savedStateSha256": registry.sha(saved), "componentName": "transport-2"}
    plan = {"instanceBinding": {"instances": {"Transport": {"instanceId": "chosen", "moduleDefinitionId": "p::TRANSPORT"}}}}
    config = {"transportModuleDefinitionId": "p::TRANSPORT"}
    catalog = {"moduleDefinitions": [{"moduleDefinitionId": "cad/transport", "cadSources": [{"path": path}]}]}
    if failure == "state_changed": write(saved, {**previous, "changed": True})
    if failure == "assembly_changed": assembly.write_bytes(b"changed")
    if failure == "wrong_name": proof["componentName"] = "unknown"
    if failure == "wrong_definition": config["transportModuleDefinitionId"] = "p::OTHER"
    if failure == "configuration": state["observed"]["components"][1]["configuration"] = "Other"
    proofs = {} if failure == "missing" else {"chosen": proof}
    if failure:
        with pytest.raises(registry.StationRuleError):
            planner.scanner_dependency_selector(root, plan, config, state, scope, catalog, proofs)
    else:
        assert planner.scanner_dependency_selector(root, plan, config, state, scope, catalog, proofs) == {"transport": "transport-2"}


def test_scanner_point_pair_rule_is_configured_only_with_exact_transport_dependency(
    setup,
):
    root, scope, _, _ = setup
    measurement = write(root / "measurement.json", {"measured": True})
    config = {
        "schemaVersion": "scanner-local-point-pair-rule/v1",
        "ruleId": "scanner-point-pair",
        "sourceModuleDefinitionId": "p::SCAN",
        "transportModuleDefinitionId": "p::TRANSPORT",
        "targetBaseDefinitionId": "p::BASE",
        "inputs": {"measurementPath": "measurement.json"},
        "inputSha256": {"measurementPath": registry.sha(measurement)},
    }
    write(root / "scanner-point-pair.json", config)
    rule = {
        "ruleId": "scanner-point-pair",
        "role": "Scanner",
        "sourceModuleDefinitionId": "p::SCAN",
        "targetBaseDefinitionId": "p::BASE",
        "dependencies": [
            {"role": "Transport", "moduleDefinitionId": "p::TRANSPORT"}
        ],
        "evaluator": {
            "kind": "scanner_point_pair",
            "inputPath": "scanner-point-pair.json",
        },
        "placement": {"strategy": "target_function_points"},
        "validation": {"status": "candidate"},
    }

    review = registry.validate_rule(root, rule, scope)
    assert review["configuredStationRule"] is True
    assert review["validatedStationRule"] is False
    assert review["blockingReasonCodes"] == []

    wrong = deepcopy(rule)
    wrong["dependencies"][0]["moduleDefinitionId"] = "p::OTHER"
    rejected = registry.validate_rule(root, wrong, scope)
    assert rejected["configuredStationRule"] is False
    assert "SCANNER_TRANSPORT_DEPENDENCY_MISMATCH" in rejected[
        "blockingReasonCodes"
    ]
