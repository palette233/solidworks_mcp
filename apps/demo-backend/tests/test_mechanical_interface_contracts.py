import copy
import json
from pathlib import Path

import pytest

from demo_backend.mechanical_interface_contracts import (
    MechanicalInterfaceContractError,
    build_plane_two_hole_contract,
    instantiate_connection_template,
    load_ccd_contract_catalog,
    load_native_wastecup_contract_catalog,
    load_calibration_contract_catalog,
    load_cleaning_weighing_contract_catalog,
    load_contextual_transport_contract_catalog,
    load_contextual_scanner_contract_catalog,
    load_scanner_contract_catalog,
    load_transport_contract_catalog,
    load_wastecup_contract_catalog,
    match_interface_contracts,
    plan_from_contract_catalog,
    plan_module_slot_connection,
    validate_contract_catalog,
)
from demo_backend.global_interface_contract_planner import (
    assess_global_assembly_context_interfaces,
    build_global_interface_contract_registry,
    plan_global_interface_connection,
)


ROOT = Path(__file__).resolve().parents[3]
GN00 = ROOT / "demo/cross_project_substitution/cleaning-weighing-base-only-v1/project01_GN00_project03_AG00/two-hole-candidate-v1"
AG00 = ROOT / "demo/global_assembly_catalog/coverage-v2/ag00-three-datum-candidate-v1"
RELEASES = ROOT / "demo/global_assembly_catalog/releases"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def port(catalog, token):
    return next(row for row in catalog["ports"] if token in row["moduleToken"])


def contracts():
    gn_s, gn_c = read(GN00 / "candidate_summary.json"), read(GN00 / "semantic_port_catalog.json")
    ag_s, ag_c = read(AG00 / "candidate_summary.json"), read(AG00 / "semantic_port_catalog.json")
    gn_r = read(RELEASES / "relation-v65-project01-gn00-base-only-two-hole-driving-20261022/release-manifest.json")
    ag_r = read(RELEASES / "relation-v54-project03-ag00-three-datum-driving-20261014/release-manifest.json")
    make = build_plane_two_hole_contract
    return {
        "GN00": make(port=port(gn_c, "GN00"), summary=gn_s, release_manifest=gn_r, side="moving_module", module_role="CleaningWeighing", module_definition_id="project01::GN00"),
        "JJ00": make(port=port(gn_c, "JJ00"), summary=gn_s, release_manifest=gn_r, side="base_slot", module_role="Base", module_definition_id="project01::JJ00", accepted_module_roles=["CleaningWeighing"]),
        "AG00": make(port=port(ag_c, "AG00"), summary=ag_s, release_manifest=ag_r, side="moving_module", module_role="CleaningWeighing", module_definition_id="project03::AG00"),
        "AA00": make(port=port(ag_c, "AA00"), summary=ag_s, release_manifest=ag_r, side="base_slot", module_role="Base", module_definition_id="project03::AA00", accepted_module_roles=["CleaningWeighing"]),
    }


def test_contracts_are_project_independent_and_released():
    rows = contracts()
    assert rows["GN00"]["geometrySignature"]["locatingAxisSpacingMeters"] == 0.204
    assert rows["AG00"]["geometrySignature"]["locatingAxisSpacingMeters"] == 0.17
    assert all(row["releaseEvidence"]["nonPrototypeCadValidated"] for row in rows.values())


@pytest.mark.parametrize("owner", ["GN00", "JJ00"])
def test_geometry_provenance_does_not_authorize_same_release_pair(owner):
    rows = contracts()
    rows[owner]["releaseEvidence"]["geometryProvenanceOnly"] = True
    result = match_interface_contracts(rows["GN00"], rows["JJ00"])
    assert result["compatible"] is True
    assert result["existingPairReleaseReusable"] is False
    assert result["requiresNewPairCadValidation"] is True
    released = match_interface_contracts(rows["GN00"], rows["JJ00"], pair_release_evidence={
        "moduleDefinitionId": "project01::GN00", "slotDefinitionId": "project01::JJ00",
        "nonPrototypeCadValidated": True, "releaseId": "exact-pair", "releaseDigest": "a" * 64,
    })
    assert released["existingPairReleaseReusable"] is True
    assert all(row["mechanicalBoundary"]["actualFasteningMethod"] == "not_inferred" for row in rows.values())


@pytest.mark.parametrize("module,slot", [("GN00", "JJ00"), ("AG00", "AA00")])
def test_native_contract_pair_instantiates_same_generic_recipe(module, slot):
    rows = contracts()
    match = match_interface_contracts(rows[module], rows[slot])
    template = instantiate_connection_template(match, rows[module], rows[slot])
    assert match["compatible"] is True
    assert match["projectIdentityUsedForCompatibility"] is False
    assert match["existingPairReleaseReusable"] is True
    assert template["recipeId"] == "recipe/plane-two-hole-rigid-mount/v1"
    assert [row["mateTypeName"] for row in template["mateSteps"]] == [
        "swMateCOINCIDENT", "swMateCONCENTRIC", "swMateCONCENTRIC"
    ]


@pytest.mark.parametrize("module,slot", [("GN00", "AA00"), ("AG00", "JJ00")])
def test_cross_project_native_slots_fail_for_34mm_spacing_mismatch(module, slot):
    rows = contracts()
    match = match_interface_contracts(rows[module], rows[slot])
    assert match["compatible"] is False
    assert match["checks"]["spacingDifferenceMeters"] == pytest.approx(0.034)
    assert [row["code"] for row in match["blockers"]] == ["LOCATING_FEATURE_SPACING_MISMATCH"]
    with pytest.raises(MechanicalInterfaceContractError):
        instantiate_connection_template(match, rows[module], rows[slot])


def test_project_identity_does_not_block_an_otherwise_matching_pair():
    rows = contracts()
    synthetic = copy.deepcopy(rows["JJ00"])
    synthetic["projectId"] = "some-other-project"
    synthetic["moduleDefinitionId"] = "some-other-project::BASE"
    synthetic["releaseEvidence"]["releaseId"] = "other-release"
    match = match_interface_contracts(rows["GN00"], synthetic)
    assert match["compatible"] is True
    assert match["requiresNewPairCadValidation"] is True
    assert match["existingPairReleaseReusable"] is False
    assert match["directMechanicalCompatibilityClaimAllowed"] is False


def test_orientation_and_underconstraint_fail_before_template_instantiation():
    rows = contracts()
    wrong_direction = copy.deepcopy(rows["JJ00"])
    wrong_direction["geometrySignature"]["orientationConvention"] = "different"
    assert "ORIENTATION_CONVENTION_MISMATCH" in {
        row["code"] for row in match_interface_contracts(rows["GN00"], wrong_direction)["blockers"]
    }
    underconstrained = copy.deepcopy(rows["GN00"])
    underconstrained["constraintContract"].update(expectedResidualDof=1, fullyLocatesRigidModule=False)
    assert "INCOMPLETE_CONSTRAINT_CONTRACT" in {
        row["code"] for row in match_interface_contracts(underconstrained, rows["JJ00"])["blockers"]
    }


@pytest.mark.parametrize("module,expected", [("GN00", "project01::JJ00"), ("AG00", "project03::AA00")])
def test_planner_selects_the_unique_compatible_slot(module, expected):
    rows = contracts()
    plan = plan_module_slot_connection(rows[module], [rows["AA00"], rows["JJ00"]])
    assert plan["status"] == "selected_unique_compatible_slot"
    assert plan["compatibleCandidateCount"] == 1
    assert plan["selectedMatch"]["slotDefinitionId"] == expected
    assert len(plan["instantiatedTemplate"]["mateSteps"]) == 3


def test_planner_requires_confirmation_when_two_slots_match():
    rows = contracts()
    second = copy.deepcopy(rows["JJ00"])
    second["contractId"] = "interface-contract/second-compatible-slot"
    second["moduleDefinitionId"] = "project99::BASE"
    plan = plan_module_slot_connection(rows["GN00"], [rows["JJ00"], second])
    assert plan["status"] == "needs_slot_confirmation"
    assert plan["compatibleCandidateCount"] == 2
    assert plan["readyForTemplateCompilation"] is False
    chosen = plan_module_slot_connection(
        rows["GN00"], [rows["JJ00"], second], selected_slot_contract_id=second["contractId"]
    )
    assert chosen["status"] == "selected_explicit_compatible_slot"
    assert chosen["selectedMatch"]["slotDefinitionId"] == "project99::BASE"


def test_planner_fails_closed_when_only_incompatible_slot_exists():
    rows = contracts()
    plan = plan_module_slot_connection(rows["GN00"], [rows["AA00"]])
    assert plan["status"] == "no_compatible_slot"
    assert plan["readyForTemplateCompilation"] is False
    assert plan["instantiatedTemplate"] is None
    assert plan["candidates"][0]["blockers"][0]["code"] == "LOCATING_FEATURE_SPACING_MISMATCH"


def test_missing_endpoint_role_and_unreleased_evidence_are_rejected():
    summary = read(GN00 / "candidate_summary.json")
    catalog = read(GN00 / "semantic_port_catalog.json")
    release = read(RELEASES / "relation-v65-project01-gn00-base-only-two-hole-driving-20261022/release-manifest.json")
    incomplete = copy.deepcopy(port(catalog, "GN00"))
    incomplete["endpointBindings"].pop()
    with pytest.raises(MechanicalInterfaceContractError, match="exactly one endpoint"):
        build_plane_two_hole_contract(port=incomplete, summary=summary, release_manifest=release, side="moving_module", module_role="CleaningWeighing", module_definition_id="x")
    release["validationEvidence"][0]["drivingInitialPoseIndependent"] = False
    with pytest.raises(MechanicalInterfaceContractError, match="released non-prototype"):
        build_plane_two_hole_contract(port=port(catalog, "GN00"), summary=summary, release_manifest=release, side="moving_module", module_role="CleaningWeighing", module_definition_id="x")


def test_generated_catalog_loads_and_detects_tampering():
    report = load_cleaning_weighing_contract_catalog(ROOT)
    assert report["summary"]["compatiblePairCount"] == 3
    assert report["summary"]["incompatiblePairCount"] == 6
    assert report["summary"]["releasedPairCount"] == 3
    assert report["summary"]["genericRecipeCount"] == 2
    tampered = copy.deepcopy(report)
    tampered["summary"]["compatiblePairCount"] = 4
    with pytest.raises(MechanicalInterfaceContractError, match="digest"):
        validate_contract_catalog(tampered)


def test_generated_catalog_can_plan_by_module_definition_without_pair_template():
    report = load_cleaning_weighing_contract_catalog(ROOT)
    plan = plan_from_contract_catalog(report, "project01::GN00")
    assert plan["status"] == "selected_unique_compatible_slot"
    assert plan["selectedMatch"]["slotDefinitionId"] == "project01::JJ00"
    assert plan["instantiatedTemplate"]["recipeId"] == "recipe/plane-two-hole-rigid-mount/v1"


def test_n000_cleaning_contract_builds_exact_four_relation_demo_recipe():
    report = load_cleaning_weighing_contract_catalog(ROOT)
    plan = plan_from_contract_catalog(report, "project05::N000")
    assert plan["status"] == "selected_unique_compatible_slot"
    assert plan["selectedMatch"]["slotDefinitionId"] == "project05::A000"
    steps = plan["instantiatedTemplate"]["mateSteps"]
    assert [row["mateTypeName"] for row in steps] == [
        "swMateCOINCIDENT", "swMatePARALLEL", "swMateDISTANCE", "swMateSLOT"
    ]
    assert steps[2]["distanceMeters"] == pytest.approx(0.465)
    module = next(row for row in report["contracts"] if row["moduleDefinitionId"] == "project05::N000")
    assert module["constraintContract"]["internalFlexibilityPreserved"] is False
    assert module["mechanicalBoundary"]["productionReady"] is False


def test_backend_exposes_cleaning_weighing_interface_contract_catalog():
    from demo_backend.main import app

    paths = {route.path for route in app.routes}
    assert "/api/demo/mechanical-interface-contracts/cleaning-weighing" in paths
    assert "/api/demo/mechanical-interface-contracts/cleaning-weighing/plan" in paths


def test_transport_catalog_has_four_released_project_independent_combinations():
    report = load_transport_contract_catalog(ROOT)
    assert report["summary"] == {
        "modulePortCount": 2,
        "baseSlotCount": 2,
        "compatiblePairCount": 4,
        "incompatiblePairCount": 0,
        "releasedPairCount": 4,
        "genericRecipeCount": 1,
        "projectIdentityUsedForCompatibility": False,
        "crossProjectPairReleaseCount": 2,
    }
    assert {row["checks"]["spacingDifferenceMeters"] for row in report["compatibilityMatrix"]} <= {1e-12, 0.0}
    assert all(row["existingPairReleaseReusable"] for row in report["compatibilityMatrix"])
    assert all(row["pairReleaseEvidence"]["nonPrototypeCadValidated"] for row in report["compatibilityMatrix"])


def test_transport_planner_requires_context_or_explicit_slot_confirmation():
    report = load_transport_contract_catalog(ROOT)
    plan = plan_from_contract_catalog(report, "project01::SS00")
    assert plan["status"] == "needs_slot_confirmation"
    assert plan["compatibleCandidateCount"] == 2
    aa00 = next(
        row for row in report["contracts"]
        if row["moduleDefinitionId"] == "project03::AA00"
    )
    chosen = plan_from_contract_catalog(
        report,
        "project01::SS00",
        selected_slot_contract_id=aa00["contractId"],
    )
    assert chosen["status"] == "selected_explicit_compatible_slot"
    assert chosen["selectedMatch"]["slotDefinitionId"] == "project03::AA00"
    assert chosen["selectedMatch"]["existingPairReleaseReusable"] is True
    assert chosen["instantiatedTemplate"]["recipeId"] == "recipe/transport-plane-two-hole-rigid-mount/v1"


def test_transport_contract_rejects_an_unregistered_60mm_slot_before_cad():
    report = load_transport_contract_catalog(ROOT)
    ss00 = next(row for row in report["contracts"] if row["moduleDefinitionId"] == "project01::SS00")
    jj00 = copy.deepcopy(next(row for row in report["contracts"] if row["moduleDefinitionId"] == "project01::JJ00"))
    jj00["moduleDefinitionId"] = "synthetic::BASE60"
    jj00["contractId"] = "interface-contract/synthetic-60mm"
    jj00["geometrySignature"]["locatingAxisSpacingMeters"] = 0.060
    match = match_interface_contracts(ss00, jj00)
    assert match["compatible"] is False
    assert match["checks"]["spacingDifferenceMeters"] == pytest.approx(0.002)
    assert {row["code"] for row in match["blockers"]} == {"LOCATING_FEATURE_SPACING_MISMATCH"}


def test_backend_exposes_transport_interface_contract_catalog():
    from demo_backend.main import app

    paths = {route.path for route in app.routes}
    assert "/api/demo/mechanical-interface-contracts/transport" in paths
    assert "/api/demo/mechanical-interface-contracts/transport/plan" in paths


def test_calibration_catalog_tracks_bd00_a600_exact_pair_release_state():
    report = load_calibration_contract_catalog(ROOT)
    direct_release_exists = any(
        ((json.loads(path.read_text(encoding="utf-8-sig")).get("releaseMetadata") or {})
         .get("directInterfacePairBinding") or {}).get("moduleDefinitionId")
        == "project01::BD00"
        and ((json.loads(path.read_text(encoding="utf-8-sig")).get("releaseMetadata") or {})
             .get("directInterfacePairBinding") or {}).get("slotDefinitionId")
        == "project02::A600"
        for path in (ROOT / "demo/global_assembly_catalog/releases").glob(
            "*/release-manifest.json"
        )
    )
    assert report["summary"]["compatiblePairCount"] == 8
    assert report["summary"]["incompatiblePairCount"] == 12
    native_release_exists = any(
        row["moduleDefinitionId"] == "project01::BD00"
        and row["slotDefinitionId"] == "project01::JJ00"
        for row in report["releasedPairEvidence"]
    )
    assert report["summary"]["releasedPairCount"] == 6 + int(direct_release_exists) + int(native_release_exists)
    assert report["summary"]["crossProjectPairReleaseCount"] == (
        4 if direct_release_exists else 3
    )
    assert report["summary"]["locatingAxisSpacingMeters"] == pytest.approx(0.05)
    compatible = [row for row in report["compatibilityMatrix"] if row["compatible"]]
    assert {
        (row["moduleDefinitionId"], row["slotDefinitionId"])
        for row in compatible
    } == {
        ("project01::BD00", "project01::JJ00"),
        ("project01::BD00", "project03::AA00"),
        ("project03::AH00", "project01::JJ00"),
        ("project03::AH00", "project03::AA00"),
        ("project03::AH00", "project02::A600"),
        ("project01::BD00", "project02::A600"),
        ("project02::A500", "project02::A600"),
        ("project05::G000", "project05::A000"),
    }
    pending = next(
        row
        for row in compatible
        if row["moduleDefinitionId"] == "project01::BD00"
        and row["slotDefinitionId"] == "project02::A600"
    )
    assert pending["existingPairReleaseReusable"] is direct_release_exists
    assert pending["mateInstantiationAllowed"] is True
    assert pending["requiresNewPairCadValidation"] is (not direct_release_exists)
    assert pending["status"] == (
        "released_pair_contract_match"
        if direct_release_exists
        else "compatible_contract_pending_pair_cad"
    )
    assert all(
        row["existingPairReleaseReusable"]
        for row in compatible
        if row is not pending
        and (row["moduleDefinitionId"], row["slotDefinitionId"]) != ("project01::BD00", "project01::JJ00")
    )
    native = next(row for row in compatible if
        (row["moduleDefinitionId"], row["slotDefinitionId"]) == ("project01::BD00", "project01::JJ00"))
    assert native["existingPairReleaseReusable"] is native_release_exists


def test_a500_calibration_context_builds_support_width_distance_recipe():
    report = load_calibration_contract_catalog(ROOT)
    plan = plan_from_contract_catalog(report, "project02::A500")
    assert plan["status"] == "selected_unique_compatible_slot"
    assert plan["selectedMatch"]["slotDefinitionId"] == "project02::A600"
    steps = plan["instantiatedTemplate"]["mateSteps"]
    assert [row["mateTypeName"] for row in steps] == [
        "swMateCOINCIDENT", "swMateDISTANCE", "swMateWIDTH"
    ]
    assert steps[1]["distanceMeters"] == pytest.approx(0.06)


def test_g000_calibration_context_preserves_flexible_four_relation_bundle():
    report = load_calibration_contract_catalog(ROOT)
    plan = plan_from_contract_catalog(report, "project05::G000")
    assert plan["status"] == "selected_unique_compatible_slot"
    assert plan["selectedMatch"]["slotDefinitionId"] == "project05::A000"
    steps = plan["instantiatedTemplate"]["mateSteps"]
    assert [row["mateTypeName"] for row in steps] == [
        "swMateCOINCIDENT", "swMatePARALLEL", "swMateDISTANCE", "swMateSLOT"
    ]
    assert steps[2]["distanceMeters"] == pytest.approx(0.482)
    module = next(row for row in report["contracts"] if row["moduleDefinitionId"] == "project05::G000")
    assert module["constraintContract"]["internalFlexibilityPreserved"] is True
    assert module["mechanicalBoundary"]["productionReady"] is False


def test_calibration_planner_requires_slot_confirmation_then_builds_generic_recipe():
    report = load_calibration_contract_catalog(ROOT)
    plan = plan_from_contract_catalog(report, "project03::AH00")
    assert plan["status"] == "needs_slot_confirmation"
    jj00 = next(row for row in report["contracts"] if row["moduleDefinitionId"] == "project01::JJ00")
    chosen = plan_from_contract_catalog(
        report,
        "project03::AH00",
        selected_slot_contract_id=jj00["contractId"],
    )
    assert chosen["status"] == "selected_explicit_compatible_slot"
    assert chosen["selectedMatch"]["slotDefinitionId"] == "project01::JJ00"
    assert chosen["selectedMatch"]["pairReleaseEvidence"]["releaseId"].startswith("relation-v44-")
    assert chosen["instantiatedTemplate"]["recipeId"] == "recipe/calibration-plane-two-hole-rigid-mount/v1"


def test_calibration_contract_blocks_52mm_slot_before_cad():
    report = load_calibration_contract_catalog(ROOT)
    bd00 = next(row for row in report["contracts"] if row["moduleDefinitionId"] == "project01::BD00")
    slot = copy.deepcopy(next(row for row in report["contracts"] if row["moduleDefinitionId"] == "project03::AA00"))
    slot["moduleDefinitionId"] = "synthetic::CALIBRATION52"
    slot["contractId"] = "interface-contract/synthetic-calibration-52mm"
    slot["geometrySignature"]["locatingAxisSpacingMeters"] = 0.052
    match = match_interface_contracts(bd00, slot)
    assert match["compatible"] is False
    assert match["checks"]["spacingDifferenceMeters"] == pytest.approx(0.002)
    assert {row["code"] for row in match["blockers"]} == {"LOCATING_FEATURE_SPACING_MISMATCH"}


def test_backend_exposes_calibration_interface_contract_catalog():
    from demo_backend.main import app

    paths = {route.path for route in app.routes}
    assert "/api/demo/mechanical-interface-contracts/calibration" in paths
    assert "/api/demo/mechanical-interface-contracts/calibration/plan" in paths


def test_scanner_catalog_separates_mechanical_and_process_ports():
    report = load_scanner_contract_catalog(ROOT)
    assert report["summary"]["compatiblePairCount"] == 2
    assert report["summary"]["incompatiblePairCount"] == 2
    assert report["summary"]["releasedPairCount"] == 2
    assert report["summary"]["sm00SpacingMeters"] == pytest.approx(0.022)
    assert report["summary"]["ai00SpacingMeters"] == pytest.approx(0.2)
    assert len(report["processPorts"]) == 2
    assert all(row["drivesMechanicalPlacement"] is False for row in report["processPorts"])
    assert all(len(row["endpointBindings"]) == 3 for row in report["contracts"])


@pytest.mark.parametrize(
    "module,slot,compatible,difference",
    [
        ("project01::SM00", "project01::JJ00", True, 0.0),
        ("project03::AI00", "project03::AA00", True, 0.0),
        ("project01::SM00", "project03::AA00", False, 0.178),
        ("project03::AI00", "project01::JJ00", False, 0.178),
    ],
)
def test_scanner_matrix_matches_geometry_not_project_identity(module, slot, compatible, difference):
    report = load_scanner_contract_catalog(ROOT)
    row = next(
        item for item in report["compatibilityMatrix"]
        if item["moduleDefinitionId"] == module and item["slotDefinitionId"] == slot
    )
    assert row["compatible"] is compatible
    assert row["checks"]["spacingDifferenceMeters"] == pytest.approx(difference)
    if compatible:
        assert row["existingPairReleaseReusable"] is True
    else:
        assert {blocker["code"] for blocker in row["blockers"]} == {"LOCATING_FEATURE_SPACING_MISMATCH"}


def test_scanner_planner_selects_only_native_geometry_and_keeps_three_driving_mates():
    report = load_scanner_contract_catalog(ROOT)
    plan = plan_from_contract_catalog(report, "project03::AI00")
    assert plan["status"] == "selected_unique_compatible_slot"
    assert plan["selectedMatch"]["slotDefinitionId"] == "project03::AA00"
    assert len(plan["instantiatedTemplate"]["mateSteps"]) == 3
    assert {row["mateTypeName"] for row in plan["instantiatedTemplate"]["mateSteps"]} == {
        "swMateCOINCIDENT", "swMateCONCENTRIC"
    }


def test_backend_exposes_scanner_interface_contract_catalog():
    from demo_backend.main import app

    paths = {route.path for route in app.routes}
    assert "/api/demo/mechanical-interface-contracts/scanner" in paths
    assert "/api/demo/mechanical-interface-contracts/scanner/plan" in paths


def test_wastecup_catalog_keeps_datum_demo_boundary_explicit():
    report = load_wastecup_contract_catalog(ROOT)
    assert report["summary"]["compatiblePairCount"] == 3
    assert report["summary"]["releasedPairCount"] == 3
    assert report["summary"]["actualFixationMethodVerified"] is False
    assert report["summary"]["directMechanicalCompatibilityClaim"] is False
    assert all(
        row["mechanicalBoundary"]["actualFasteningMethod"] == "not_verified"
        for row in report["contracts"]
    )


def test_wastecup_planner_requires_base_selection_and_uses_slot_parameters():
    report = load_wastecup_contract_catalog(ROOT)
    plan = plan_from_contract_catalog(report, "project05::P000")
    assert plan["status"] == "needs_slot_confirmation"
    slots = {
        row["moduleDefinitionId"]: row for row in report["contracts"]
        if row["side"] == "base_slot"
        and row["interfaceFamily"] == "support_plane_two_offset_position/v1"
    }
    expectations = {
        "project02::A600": (0.08, 0.39),
        "project03::AA00": (0.4, 0.2),
    }
    for slot_id, expected in expectations.items():
        chosen = plan_from_contract_catalog(
            report,
            "project05::P000",
            selected_slot_contract_id=slots[slot_id]["contractId"],
        )
        steps = chosen["instantiatedTemplate"]["mateSteps"]
        assert chosen["selectedMatch"]["slotDefinitionId"] == slot_id
        assert [row["mateTypeName"] for row in steps] == [
            "swMateDISTANCE", "swMateDISTANCE", "swMateCOINCIDENT"
        ]
        assert (steps[0]["distanceMeters"], steps[1]["distanceMeters"]) == expected


def test_wastecup_catalog_reuses_a300_a600_native_three_mate_release():
    report = load_wastecup_contract_catalog(ROOT)
    plan = plan_from_contract_catalog(report, "project02::A300")
    assert plan["status"] == "selected_unique_compatible_slot"
    assert plan["selectedMatch"]["slotDefinitionId"] == "project02::A600"
    assert plan["selectedMatch"]["existingPairReleaseReusable"] is True
    steps = plan["instantiatedTemplate"]["mateSteps"]
    assert [row["mateTypeName"] for row in steps] == [
        "swMateDISTANCE",
        "swMateDISTANCE",
        "swMateCOINCIDENT",
    ]
    assert [row.get("distanceMeters") for row in steps] == [0.08, 0.39, None]


def test_global_planner_resolves_a300_a600_as_released_mechanical_interface():
    plan = plan_global_interface_connection(
        ROOT,
        "project02::A300",
        selected_slot_definition_id="project02::A600",
    )
    assert plan["catalogKey"] == "wastecup"
    assert plan["status"] == "selected_explicit_compatible_slot"
    assert plan["selectedMatch"]["existingPairReleaseReusable"] is True


def test_wastecup_missing_position_parameter_fails_before_template_instantiation():
    report = load_wastecup_contract_catalog(ROOT)
    module = next(row for row in report["contracts"] if row["side"] == "moving_module")
    slot = copy.deepcopy(next(row for row in report["contracts"] if row["side"] == "base_slot"))
    slot["geometrySignature"]["positionParametersMeters"].pop("lateral")
    match = match_interface_contracts(module, slot)
    assert match["compatible"] is False
    assert "POSITION_PARAMETERS_MISSING" in {row["code"] for row in match["blockers"]}
    with pytest.raises(MechanicalInterfaceContractError):
        instantiate_connection_template(match, module, slot)


def test_backend_exposes_wastecup_interface_contract_catalog():
    from demo_backend.main import app

    paths = {route.path for route in app.routes}
    assert "/api/demo/mechanical-interface-contracts/wastecup" in paths
    assert "/api/demo/mechanical-interface-contracts/wastecup/plan" in paths


def test_aggregate_interface_contract_coverage_is_consistent_and_prioritized():
    from demo_backend.interface_contract_coverage import load_interface_contract_coverage

    report = load_interface_contract_coverage(ROOT)
    assert report["totals"] == {
        "familyCount": 9,
        "movingModuleContractCount": 20,
        "baseSlotContractCount": 22,
        "candidatePairCount": 56,
        "compatiblePairCount": 27,
        "incompatiblePairCount": 29,
        "releasedPairCount": 27,
        "readOnlyProcessPortCount": 4,
    }
    assert report["remainingPriorityGaps"] == []
    assert "Project06" in report["excludedFromCurrentMainline"]


def test_aggregate_interface_contract_coverage_detects_tampering():
    from demo_backend.interface_contract_coverage import (
        InterfaceContractCoverageError,
        load_interface_contract_coverage,
        validate_interface_contract_coverage,
    )

    report = copy.deepcopy(load_interface_contract_coverage(ROOT))
    report["totals"]["compatiblePairCount"] = 99
    with pytest.raises(InterfaceContractCoverageError, match="digest"):
        validate_interface_contract_coverage(report)


def test_backend_exposes_interface_contract_coverage():
    from demo_backend.main import app

    assert "/api/demo/mechanical-interface-contracts/coverage" in {
        route.path for route in app.routes
    }


def test_contextual_transport_catalog_releases_d000_and_a800_without_pose_anchor():
    report = load_contextual_transport_contract_catalog(ROOT)
    assert report["summary"]["compatiblePairCount"] == 2
    assert report["summary"]["releasedPairCount"] == 2
    assert report["summary"]["incompleteModulePortCount"] == 0
    d000 = plan_from_contract_catalog(report, "project05::D000")
    assert d000["status"] == "selected_unique_compatible_slot"
    assert d000["selectedMatch"]["slotDefinitionId"] == "project05::A000"
    assert [step["mateTypeName"] for step in d000["instantiatedTemplate"]["mateSteps"]] == [
        "swMateCOINCIDENT", "swMateDISTANCE", "swMateWIDTH"
    ]
    assert d000["instantiatedTemplate"]["mateSteps"][1]["distanceMeters"] == pytest.approx(0.312)
    a800 = plan_from_contract_catalog(report, "project02::A800")
    assert a800["status"] == "selected_unique_compatible_slot"
    assert a800["selectedMatch"]["slotDefinitionId"] == "project02::A600"
    assert [step["mateTypeName"] for step in a800["instantiatedTemplate"]["mateSteps"]] == [
        "swMateCOINCIDENT", "swMateDISTANCE", "swMateWIDTH"
    ]
    assert a800["instantiatedTemplate"]["mateSteps"][1]["distanceMeters"] == pytest.approx(0.0495)


def test_contextual_transport_catalog_detects_variant_mismatch_before_cad():
    report = load_contextual_transport_contract_catalog(ROOT)
    module = next(row for row in report["contracts"] if row["moduleDefinitionId"] == "project05::D000")
    slot = copy.deepcopy(next(row for row in report["contracts"] if row["moduleDefinitionId"] == "project05::A000"))
    slot["geometrySignature"]["interfaceVariantKey"] = "synthetic-width-context"
    match = match_interface_contracts(module, slot)
    assert match["compatible"] is False
    assert "INTERFACE_VARIANT_MISMATCH" in {item["code"] for item in match["blockers"]}


def test_backend_exposes_contextual_transport_contract_catalog():
    from demo_backend.main import app

    paths = {route.path for route in app.routes}
    assert "/api/demo/mechanical-interface-contracts/contextual-transport" in paths
    assert "/api/demo/mechanical-interface-contracts/contextual-transport/plan" in paths


def test_contextual_scanner_catalog_keeps_exact_mechanics_and_process_semantics_separate():
    report = load_contextual_scanner_contract_catalog(ROOT)
    assert report["summary"]["compatiblePairCount"] == 2
    assert report["summary"]["releasedPairCount"] == 2
    assert report["summary"]["missingOpticalProcessPortCount"] == 1
    assert all(row["drivesMechanicalPlacement"] is False for row in report["processPorts"])
    expectations = {
        "project02::A180": ["swMateCOINCIDENT", "swMateDISTANCE", "swMateSLOT"],
        "project05::F000": ["swMateCOINCIDENT", "swMatePARALLEL", "swMateCONCENTRIC"],
    }
    for module_id, mate_types in expectations.items():
        plan = plan_from_contract_catalog(report, module_id)
        assert plan["status"] == "selected_unique_compatible_slot"
        assert [step["mateTypeName"] for step in plan["instantiatedTemplate"]["mateSteps"]] == mate_types


def test_contextual_scanner_cross_project_topologies_fail_before_cad():
    report = load_contextual_scanner_contract_catalog(ROOT)
    cross = [
        row for row in report["compatibilityMatrix"]
        if row["moduleProjectId"] != row["slotProjectId"]
    ]
    assert len(cross) == 2
    assert all(row["compatible"] is False for row in cross)
    assert all("INTERFACE_FAMILY_MISMATCH" in {item["code"] for item in row["blockers"]} for row in cross)


def test_backend_exposes_contextual_scanner_contract_catalog():
    from demo_backend.main import app

    paths = {route.path for route in app.routes}
    assert "/api/demo/mechanical-interface-contracts/contextual-scanner" in paths
    assert "/api/demo/mechanical-interface-contracts/contextual-scanner/plan" in paths


def test_global_interface_registry_unifies_all_seven_catalogs():
    report = build_global_interface_contract_registry(ROOT)
    direct_release_exists = any(
        row["moduleDefinitionId"] == "project01::BD00"
        and row["slotDefinitionId"] == "project02::A600"
        and row["released"] is True
        for row in report["connections"]
    )
    native_release_exists = any(
        row["moduleDefinitionId"] == "project01::BD00"
        and row["slotDefinitionId"] == "project01::JJ00"
        and row["released"] is True
        for row in report["connections"]
    )
    assert report["summary"] == {
        "catalogCount": 9,
            "modulePortCount": 20,
                "baseSlotCount": 22,
                "candidatePairCount": 56,
                "compatiblePairCount": 27,
                "releasedPairCount": 25 + int(direct_release_exists) + int(native_release_exists),
    }
    assert {row["moduleDefinitionId"] for row in report["modules"]} >= {
        "project01::SS00",
        "project02::A800",
        "project03::AI00",
        "project05::P000",
    }


def test_global_interface_planner_resolves_a800_without_family_hint():
    plan = plan_global_interface_connection(ROOT, "project02::A800")
    assert plan["schemaVersion"] == "global-interface-contract-plan/v1"
    assert plan["catalogKey"] == "contextual-transport"
    assert plan["status"] == "selected_unique_compatible_slot"
    assert plan["selectedMatch"]["slotDefinitionId"] == "project02::A600"
    assert plan["instantiatedTemplate"]["mateSteps"][1]["distanceMeters"] == pytest.approx(0.0495)


def test_global_interface_planner_accepts_human_readable_slot_definition():
    plan = plan_global_interface_connection(
        ROOT,
        "project01::SS00",
        selected_slot_definition_id="project03::AA00",
    )
    assert plan["catalogKey"] == "transport"
    assert plan["status"] == "selected_explicit_compatible_slot"
    assert plan["selectedMatch"]["slotDefinitionId"] == "project03::AA00"


def test_global_interface_planner_bridges_global_cad_definition_ids():
    plan = plan_global_interface_connection(
        ROOT,
        "cad/fl9c24n074ss00-001/ced014a7837b",
        selected_slot_definition_id="cad/fl9a24d063aa00-001/dc4bbec17218",
    )
    assert plan["requestedModuleDefinitionId"] == "cad/fl9c24n074ss00-001/ced014a7837b"
    assert plan["moduleDefinitionId"] == "project01::SS00"
    assert plan["selectedMatch"]["slotDefinitionId"] == "project03::AA00"


def test_global_interface_planner_reports_unknown_module_without_starting_cad():
    plan = plan_global_interface_connection(ROOT, "project99::UNKNOWN")
    assert plan["status"] == "module_not_registered"
    assert plan["readyForTemplateCompilation"] is False


def test_backend_exposes_global_interface_registry_and_planner():
    from demo_backend.main import app

    paths = {route.path for route in app.routes}
    assert "/api/demo/mechanical-interface-contracts" in paths
    assert "/api/demo/mechanical-interface-contracts/plan" in paths
    assert "/api/demo/mechanical-interface-contracts/context-preflight" in paths


def test_ccd_catalog_releases_native_exact_bundles_and_blocks_cross_topology():
    report = load_ccd_contract_catalog(ROOT)
    assert report["summary"]["compatiblePairCount"] == 2
    assert report["summary"]["incompatiblePairCount"] == 2
    assert report["summary"]["releasedPairCount"] == 2
    m000 = plan_from_contract_catalog(report, "project05::M000")
    assert m000["status"] == "selected_unique_compatible_slot"
    assert [row["mateTypeName"] for row in m000["instantiatedTemplate"]["mateSteps"]] == [
        "swMateCOINCIDENT", "swMatePARALLEL", "swMateCONCENTRIC"
    ]
    a200 = plan_from_contract_catalog(report, "project02::A200")
    assert a200["status"] == "selected_unique_compatible_slot"
    assert [row["mateTypeName"] for row in a200["instantiatedTemplate"]["mateSteps"]] == [
        "swMateCOINCIDENT", "swMateSLOT", "swMateSLOT"
    ]
    assert a200["instantiatedTemplate"]["mateSteps"][1]["advancedOptions"]["SlotDistance"] == pytest.approx(1.0)
    assert a200["instantiatedTemplate"]["mateSteps"][2]["advancedOptions"]["SlotDistance"] == pytest.approx(0.5)


def test_backend_exposes_ccd_contract_catalog():
    from demo_backend.main import app

    paths = {route.path for route in app.routes}
    assert "/api/demo/mechanical-interface-contracts/ccd" in paths
    assert "/api/demo/mechanical-interface-contracts/ccd/plan" in paths


def test_native_wastecup_contract_preserves_four_relation_bundle():
    report = load_native_wastecup_contract_catalog(ROOT)
    plan = plan_from_contract_catalog(report, "project05::P000")
    assert plan["status"] == "selected_unique_compatible_slot"
    assert [row["mateTypeName"] for row in plan["instantiatedTemplate"]["mateSteps"]] == [
        "swMateCOINCIDENT", "swMatePARALLEL", "swMateSLOT", "swMateDISTANCE"
    ]
    assert plan["instantiatedTemplate"]["mateSteps"][3]["distanceMeters"] == pytest.approx(
        0.3451225352603192
    )


def test_global_planner_disambiguates_p000_interface_from_target_base():
    native = plan_global_interface_connection(
        ROOT,
        "project05::P000",
        selected_slot_definition_id="project05::A000",
    )
    assert native["catalogKey"] == "native-wastecup"
    assert native["status"] == "selected_explicit_compatible_slot"
    datum = plan_global_interface_connection(
        ROOT,
        "project05::P000",
        selected_slot_definition_id="project03::AA00",
    )
    assert datum["catalogKey"] == "wastecup"
    assert datum["status"] == "selected_explicit_compatible_slot"


def test_backend_exposes_native_wastecup_contract_catalog():
    from demo_backend.main import app

    paths = {route.path for route in app.routes}
    assert "/api/demo/mechanical-interface-contracts/native-wastecup" in paths
    assert "/api/demo/mechanical-interface-contracts/native-wastecup/plan" in paths


def test_global_interface_context_preflight_accepts_released_four_module_chain():
    context = json.loads(
        (ROOT / "demo/global_assembly_contexts/cross-project-aa00-bd00-ss00-ai00-portable-v1.json")
        .read_text(encoding="utf-8-sig")
    )
    report = assess_global_assembly_context_interfaces(ROOT, context)
    assert report["status"] == "ready"
    assert report["connectionCount"] == 3
    assert report["readyConnectionCount"] == 3
    assert {row["catalogKey"] for row in report["connections"]} == {
        "calibration",
        "transport",
        "scanner",
    }


def test_global_interface_context_preflight_blocks_unregistered_slot():
    context = {
        "contextId": "synthetic-bad-slot",
        "instances": [
            {
                "instanceId": "transport",
                "moduleDefinitionId": "cad/fl9c24n074ss00-001/ced014a7837b",
            },
            {
                "instanceId": "base",
                "moduleDefinitionId": "cad/fl9a24d062a600-001-1/66606c07c8cf",
            },
        ],
        "connections": [
            {
                "connectionId": "bad-connection",
                "instanceAId": "transport",
                "instanceBId": "base",
            }
        ],
    }
    report = assess_global_assembly_context_interfaces(ROOT, context)
    assert report["status"] == "blocked"
    assert report["connections"][0]["status"] == "slot_interface_not_registered"
    assert report["cadStarted"] is False


@pytest.mark.parametrize(
    "name",
    [
        "six-role-project03-direct-20261023-v1-standard",
        "six-role-project03-direct-20261023-v1-reordered",
    ],
)
def test_six_role_direct_stage_contexts_pass_unified_interface_preflight(name):
    context = json.loads(
        (ROOT / "demo/global_assembly_contexts" / f"{name}.json").read_text(
            encoding="utf-8-sig"
        )
    )
    report = assess_global_assembly_context_interfaces(ROOT, context)
    assert report["status"] == "ready"
    assert report["readyConnectionCount"] == 4
    assert report["blockedConnectionCount"] == 0
