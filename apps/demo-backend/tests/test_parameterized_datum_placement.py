import copy
import json
from pathlib import Path

import pytest

import demo_backend.parameterized_datum_placement as placement

from demo_backend.finite_support_gate import evaluate_finite_support_gate
from demo_backend.global_interface_contract_planner import (
    plan_preferred_interface_connection,
    resolve_preferred_released_interface_authority,
)
from demo_backend.mechanical_interface_contracts import (
    MechanicalInterfaceContractError,
    validate_contract_catalog,
)
from demo_backend.parameterized_datum_placement import (
    build_parameterized_datum_placement_catalog,
    compile_parameterized_datum_validation_package,
    load_parameterized_datum_placement_catalog,
    plan_parameterized_datum_placement,
)


ROOT = Path(__file__).resolve().parents[3]


def test_base_wrapper_source_prefers_one_exact_normalized_token(tmp_path):
    cache = tmp_path / "demo/global_assembly_contexts/base_wrapper_cache"
    for name, token in (("current", "AA00"), ("legacy", "FL9A24D063AA00")):
        directory = cache / name
        directory.mkdir(parents=True)
        (directory / "base-context-wrapper.SLDASM").write_bytes(name.encode())
        (directory / "cache-entry.json").write_text(
            json.dumps(
                {
                    "inputs": {"baseContextModuleToken": token},
                    "assemblyFile": "base-context-wrapper.SLDASM",
                }
            ),
            encoding="utf-8",
        )

    entry, assembly = placement._base_wrapper_source(tmp_path, "AA00")

    assert entry.parent.name == "current"
    assert assembly.parent.name == "current"


def test_base_wrapper_source_rejects_multiple_exact_tokens(tmp_path):
    cache = tmp_path / "demo/global_assembly_contexts/base_wrapper_cache"
    for name in ("one", "two"):
        directory = cache / name
        directory.mkdir(parents=True)
        (directory / "base-context-wrapper.SLDASM").write_bytes(name.encode())
        (directory / "cache-entry.json").write_text(
            json.dumps(
                {
                    "inputs": {"baseContextModuleToken": "AA00"},
                    "assemblyFile": "base-context-wrapper.SLDASM",
                }
            ),
            encoding="utf-8",
        )

    with pytest.raises(MechanicalInterfaceContractError, match="found 2"):
        placement._base_wrapper_source(tmp_path, "AA00")


def test_generated_datum_catalog_is_bounded_and_has_no_false_release_claims():
    report = load_parameterized_datum_placement_catalog(ROOT)
    summary = report["summary"]
    assert summary["modulePortCount"] == 13
    assert summary["alternateRecipeModulePortCount"] == 1
    assert summary["totalRegisteredMovingModulePortCount"] == 14
    assert summary["baseSlotCount"] == 20
    assert summary["compatiblePairCount"] + summary["incompatiblePairCount"] == 260
    assert summary["genericRecipeCount"] == 2
    assert summary["explicitAxisSelectionRequiredCount"] >= 0
    assert summary["alternateRecipeReleasedNativePairCount"] == 1
    assert summary["alternateRecipeReleasedPairCount"] >= 3
    assert summary["captureGapCount"] == 0
    assert summary["cadValidationCandidateCount"] == (
        summary["compatiblePairCount"]
        - summary["releasedPairCount"]
        - summary["candidateReuseSafetyBlockedCount"]
    )
    released = {
        (row["moduleDefinitionId"], row["slotDefinitionId"])
        for row in report["compatibilityMatrix"]
        if row["existingPairReleaseReusable"] is True
    }
    assert {
        ("project03::AI00", "project01::JJ00"),
        ("project01::GN00", "project03::AA00"),
    } <= released
    assert len(released) == report["summary"]["releasedPairCount"]
    assert all(
        row["mechanicalBoundary"]["actualFasteningMethod"] == "not_verified"
        for row in report["contracts"]
    )
    assert all(
        row["mechanicalBoundary"]["productionReady"] is False
        for row in report["contracts"]
    )


def test_builder_reproduces_committed_catalog_digest():
    generated = build_parameterized_datum_placement_catalog(ROOT)
    committed = load_parameterized_datum_placement_catalog(ROOT)
    assert generated["catalogDigest"] == committed["catalogDigest"]
    assert len(generated["datumFrameAudit"]) == 33
    assert all(
        max(row["orthogonalityResiduals"].values()) < 1e-5
        for row in generated["datumFrameAudit"]
    )


@pytest.mark.parametrize(
    "module_id,slot_id",
    [
        ("project03::AI00", "project01::JJ00"),
        ("project01::SM00", "project03::AA00"),
        ("project01::GN00", "project03::AA00"),
        ("project03::AG00", "project01::JJ00"),
        ("project01::GN00", "project05::A000"),
        ("project05::N000", "project01::JJ00"),
        ("project05::N000", "project03::AA00"),
    ],
)
def test_cross_project_fallback_builds_three_datum_mates_but_requires_cad_release(
    module_id, slot_id
):
    plan = plan_parameterized_datum_placement(
        ROOT, module_id, selected_slot_definition_id=slot_id
    )
    report = load_parameterized_datum_placement_catalog(ROOT)
    released = any(
        row["moduleDefinitionId"] == module_id
        and row["slotDefinitionId"] == slot_id
        and row["existingPairReleaseReusable"] is True
        for row in report["compatibilityMatrix"]
    )
    assert plan["status"] == (
        "released_datum_placement_ready"
        if released
        else "datum_fallback_candidate_requires_cad_validation"
    )
    assert plan["readyForTemplateCompilation"] is True
    assert plan["readyForReleasedCadExecution"] is released
    assert plan["physicalFasteningVerified"] is False
    assert [
        row["mateTypeName"] for row in plan["instantiatedTemplate"]["mateSteps"]
    ] == ["swMateDISTANCE", "swMateDISTANCE", "swMateCOINCIDENT"]


def test_preferred_planner_keeps_released_native_interface_first():
    plan = plan_preferred_interface_connection(
        ROOT,
        "project03::AI00",
        selected_slot_definition_id="project03::AA00",
    )
    assert plan["status"] == "released_native_or_alternate_interface_ready"
    assert plan["selectedMode"] == "mechanical_interface"
    assert plan["readyForReleasedCadExecution"] is True
    assert plan["datumFallbackPlan"] is None


def test_preferred_planner_uses_bounded_fallback_after_native_spacing_failure():
    plan = plan_preferred_interface_connection(
        ROOT,
        "project03::AI00",
        selected_slot_definition_id="project01::JJ00",
    )
    assert plan["status"] == "released_datum_placement_ready"
    assert plan["selectedMode"] == "parameterized_datum_placement"
    assert plan["readyForReleasedCadExecution"] is True
    native_candidates = plan["nativePlan"]["candidates"]
    selected_native = next(
        row for row in native_candidates if row["slotDefinitionId"] == "project01::JJ00"
    )
    assert {row["code"] for row in selected_native["blockers"]} == {
        "LOCATING_FEATURE_SPACING_MISMATCH"
    }


def test_preferred_planner_can_disable_fallback_explicitly():
    plan = plan_preferred_interface_connection(
        ROOT,
        "project01::GN00",
        selected_slot_definition_id="project03::AA00",
        allow_datum_fallback=False,
    )
    assert plan["status"] == "native_interface_unavailable_datum_fallback_disabled"
    assert plan["readyForReleasedCadExecution"] is False


def test_f000_uses_distinct_plane_axis_recipe_and_requires_slot_confirmation():
    plan = plan_parameterized_datum_placement(ROOT, "project05::F000")
    assert plan["status"] == "hybrid_axis_slot_confirmation_required"
    assert plan["readyForTemplateCompilation"] is False
    assert plan["captureGap"] is None
    assert len(plan["alternateRecipeCandidates"]) == 4
    a600 = next(
        row
        for row in plan["alternateRecipeCandidates"]
        if row["slotDefinitionId"] == "project02::A600"
    )
    assert a600["requiresExplicitAxisSelection"] is False
    assert a600["readyForReleasedCadExecution"] is True
    assert a600["candidateAxisLineCount"] > 100


def test_f000_cross_base_axis_selection_is_explicit_and_native_a000_stays_released():
    cross = plan_parameterized_datum_placement(
        ROOT, "project05::F000", selected_slot_definition_id="project02::A600"
    )
    assert cross["status"] == "released_hybrid_pair_ready"
    assert cross["requiresExplicitAxisSelection"] is False
    assert cross["candidateAxisLineCount"] > 20
    assert cross["readyForReleasedCadExecution"] is True
    native = plan_parameterized_datum_placement(
        ROOT, "project05::F000", selected_slot_definition_id="project05::A000"
    )
    assert native["status"] == "released_hybrid_native_pair"
    assert native["requiresExplicitAxisSelection"] is False
    assert native["readyForReleasedCadExecution"] is True


def test_hybrid_pair_release_promotes_f000_cross_base_plan(monkeypatch):
    existing = placement._validated_pair_releases(ROOT)
    without_a600 = [
        row
        for row in existing
        if not (
            row.get("moduleDefinitionId") == "project05::F000"
            and row.get("slotDefinitionId") == "project02::A600"
        )
    ]
    monkeypatch.setattr(
        placement,
        "_validated_pair_releases",
        lambda _: list(without_a600),
    )
    baseline = placement.build_parameterized_datum_placement_catalog(ROOT)
    hybrid = baseline[
        "alternateRecipeCandidates"
    ]
    a600 = next(
        row for row in hybrid if row["slotDefinitionId"] == "project02::A600"
    )
    from demo_backend.hybrid_plane_axis_slot_selection import (
        build_f000_hybrid_axis_slot_catalog,
    )

    source = build_f000_hybrid_axis_slot_catalog(ROOT)
    source_slot = next(
        row
        for row in source["baseSlots"]
        if row["slotDefinitionId"] == "project02::A600"
    )
    selected_axis = next(
        row["endpointId"]
        for row in source_slot["axisCandidates"]
        if row["axisMateAlignmentCompatible"] is True
    )
    evidence = {
        "schemaVersion": "parameterized-datum-pair-release/v1",
        "releaseId": "synthetic-hybrid-f000-a600",
        "releaseDigest": "a" * 64,
        "moduleDefinitionId": "project05::F000",
        "slotDefinitionId": "project02::A600",
        "placementMode": "reviewed_hybrid_plane_axis_datum",
        "selectedAxisEndpointId": selected_axis,
        "nonPrototypeCadValidated": True,
    }
    monkeypatch.setattr(
        placement,
        "_validated_pair_releases",
        lambda _: [*without_a600, evidence],
    )
    report = placement.build_parameterized_datum_placement_catalog(ROOT)
    promoted = next(
        row
        for row in report["alternateRecipeCandidates"]
        if row["slotDefinitionId"] == a600["slotDefinitionId"]
    )
    assert promoted["status"] == "released_hybrid_pair"
    assert promoted["requiresExplicitAxisSelection"] is False
    assert promoted["readyForReleasedCadExecution"] is True
    assert promoted["selectedAxisEndpointId"] == selected_axis
    assert promoted["pairReleaseEvidence"] == evidence
    assert report["summary"]["explicitAxisSelectionRequiredCount"] == (
        baseline["summary"]["explicitAxisSelectionRequiredCount"] - 1
    )
    assert report["summary"]["alternateRecipeReleasedPairCount"] == (
        baseline["summary"]["alternateRecipeReleasedPairCount"] + 1
    )

    monkeypatch.setattr(
        placement, "load_parameterized_datum_placement_catalog", lambda _: report
    )
    plan = placement.plan_parameterized_datum_placement(
        ROOT, "project05::F000", selected_slot_definition_id="project02::A600"
    )
    assert plan["status"] == "released_hybrid_pair_ready"
    assert plan["readyForTemplateCompilation"] is True
    assert plan["readyForReleasedCadExecution"] is True
    assert plan["selectedMatch"]["pairReleaseEvidence"] == evidence


def test_a800_a000_pair_uses_authenticated_released_station_parameters():
    plan = plan_parameterized_datum_placement(
        ROOT, "project02::A800", selected_slot_definition_id="project05::A000"
    )
    assert plan["status"] == "released_datum_placement_ready"
    assert plan["acceptsExplicitPositionParameters"] is False
    assert plan["readyForTemplateCompilation"] is True
    assert plan["readyForReleasedCadExecution"] is True
    evidence = plan["catalogPlan"]["selectedMatch"]["pairReleaseEvidence"]
    assert evidence["nonPrototypeCadValidated"] is True
    assert evidence["prototypeTopLevelTargetPoseUsed"] is False
    assert evidence["checks"]["targetFullyConstrained"] is True
    assert evidence["catalogResolution"]["positionParametersMeters"] == {
        "longitudinal": 0.092,
        "lateral": 1.3635,
        "supportGap": 0.0,
    }


def test_wastecup_family_uses_native_and_demo_projection_released_stations():
    known = plan_parameterized_datum_placement(
        ROOT, "project02::A300", selected_slot_definition_id="project02::A600"
    )
    assert known["status"] == "datum_fallback_candidate_requires_cad_validation"
    assert [
        row.get("distanceMeters")
        for row in known["instantiatedTemplate"]["mateSteps"]
    ] == [pytest.approx(0.080), pytest.approx(0.390), None]

    projected = plan_parameterized_datum_placement(
        ROOT, "project02::A300", selected_slot_definition_id="project01::JJ00"
    )
    assert projected["status"] == "released_datum_placement_ready"
    assert projected["readyForTemplateCompilation"] is True
    assert projected["readyForReleasedCadExecution"] is True
    assert projected["acceptsExplicitPositionParameters"] is False
    assert [
        row.get("distanceMeters")
        for row in projected["catalogPlan"]["instantiatedTemplate"]["mateSteps"]
    ] == [pytest.approx(0.080), pytest.approx(0.390), None]

    package = compile_parameterized_datum_validation_package(
        ROOT,
        "project02::A300",
        "project01::JJ00",
        position_parameters={
            "longitudinal": 0.120,
            "lateral": 0.280,
            "supportGap": 0.0,
        },
    )
    assert package["targetModuleToken"] == "A300"
    assert package["baseModuleToken"] == "JJ00"
    assert package["prototypeTopLevelTargetPoseUsed"] is False
    assert package["readyForReleasedCadExecution"] is False


@pytest.mark.parametrize("directions", [
    {"lateral": True},
    {"longitudinal": False, "lateral": 1, "supportGap": False},
    {"longitudinal": False, "lateral": "true", "supportGap": False},
])
def test_invalid_distance_direction_override_rejected(directions):
    with pytest.raises(ValueError, match="three boolean flips"):
        compile_parameterized_datum_validation_package(
            ROOT, "project05::P000", "project01::JJ00",
            position_parameters={"longitudinal": .54, "lateral": .47, "supportGap": 0},
            distance_flip_dimensions=directions,
        )


def test_explicit_position_direction_reaches_candidate_graph():
    package = compile_parameterized_datum_validation_package(
        ROOT, "project05::P000", "project01::JJ00",
        position_parameters={"longitudinal": .5440824749305696, "lateral": .471, "supportGap": 0},
        distance_flip_dimensions={"longitudinal": False, "lateral": True, "supportGap": False},
    )
    assert package["effectiveDistanceFlipDimensions"]["lateral"] is True
    graph = package["effectiveGraph"]
    lateral = next(m for m in graph["Mates"] if m["MateName"].endswith("LATERAL"))
    assert lateral["Distance"] == pytest.approx(.471)
    assert lateral["AdvancedOptions"]["DistanceFlipDimension"] is True
    assert package["readyForReleasedCadExecution"] is False


def test_module_specific_position_presets_are_used_for_same_scanner_slot():
    ai00 = plan_parameterized_datum_placement(
        ROOT, "project03::AI00", selected_slot_definition_id="project03::AA00"
    )
    sm00 = plan_parameterized_datum_placement(
        ROOT, "project01::SM00", selected_slot_definition_id="project03::AA00"
    )
    ai_steps = ai00["instantiatedTemplate"]["mateSteps"]
    sm_steps = sm00["instantiatedTemplate"]["mateSteps"]
    assert ai_steps[0]["distanceMeters"] == pytest.approx(0.070)
    assert ai_steps[1]["distanceMeters"] == pytest.approx(0.0435)
    assert sm_steps[0]["distanceMeters"] == pytest.approx(0.070)
    assert sm_steps[1]["distanceMeters"] == pytest.approx(0.102)


def test_validation_package_derives_lateral_alignment_from_frame_handedness():
    parameters = {
        "longitudinal": 0.354,
        "lateral": 0.2535,
        "supportGap": 0.0,
    }
    a600 = compile_parameterized_datum_validation_package(
        ROOT,
        "project01::GN00",
        "project02::A600",
        position_parameters=parameters,
    )
    aa00 = compile_parameterized_datum_validation_package(
        ROOT,
        "project01::GN00",
        "project03::AA00",
        position_parameters=parameters,
    )

    assert [
        row["AlignmentName"] for row in a600["effectiveGraph"]["Mates"]
    ] == [
        "swMateAlignALIGNED",
        "swMateAlignANTI_ALIGNED",
        "swMateAlignANTI_ALIGNED",
    ]
    assert a600["alignmentDerivation"] == {
        "method": "proper_rotation_from_registered_datum_frame_handedness",
        "moduleFrameHandedness": -1,
        "slotFrameHandedness": -1,
        "longitudinalAlignmentSign": 1,
        "supportAlignmentSign": -1,
        "originalLateralAlignmentSign": 1,
        "derivedLateralAlignmentSign": -1,
        "lateralAlignmentChanged": True,
        "moduleOrthogonalityResiduals": pytest.approx(
            {
                "supportLongitudinal": 0.0,
                "supportLateral": 0.0,
                "longitudinalLateral": 0.0,
            },
            abs=1e-12,
        ),
        "slotOrthogonalityResiduals": pytest.approx(
            {
                "supportLongitudinal": 0.0,
                "supportLateral": 0.0,
                "longitudinalLateral": 0.0,
            },
            abs=1e-12,
        ),
    }
    assert [
        row["AlignmentName"] for row in aa00["effectiveGraph"]["Mates"]
    ] == [
        "swMateAlignALIGNED",
        "swMateAlignALIGNED",
        "swMateAlignANTI_ALIGNED",
    ]
    assert aa00["alignmentDerivation"]["lateralAlignmentChanged"] is False


def test_released_explicit_position_pair_resolves_against_current_catalog():
    plan = plan_parameterized_datum_placement(
        ROOT,
        "project01::GN00",
        selected_slot_definition_id="project02::A600",
    )
    evidence = plan["selectedMatch"]["pairReleaseEvidence"]
    assert plan["status"] == "released_datum_placement_ready"
    assert plan["readyForReleasedCadExecution"] is True
    assert evidence["catalogResolution"] == {
        "positionParametersMeters": {
            "longitudinal": 0.354,
            "lateral": 0.2535,
            "supportGap": 0.0,
        },
        "distanceFlipDimensions": {
            "longitudinal": False,
            "lateral": False,
            "supportGap": False,
        },
        "moduleEndpointReferencesMatch": True,
        "slotEndpointReferencesMatch": True,
        "currentCatalogBindingsMatch": True,
    }


def test_n000_a600_former_distance_direction_is_rejected_by_finite_support_gate():
    report = load_parameterized_datum_placement_catalog(ROOT)
    slot = next(
        row
        for row in report["contracts"]
        if row["side"] == "base_slot"
        and row["moduleDefinitionId"] == "project02::A600"
        and "CleaningWeighing" in row["acceptedModuleRoles"]
    )
    profile = slot["geometrySignature"][
        "finiteSupportProfilesByModuleDefinitionId"
    ]["project05::N000"]
    result = evaluate_finite_support_gate(
        module_definition_id="project05::N000",
        slot_definition_id="project02::A600",
        profile=profile,
        position_parameters={
            "longitudinal": 0.465,
            "lateral": 0.7125,
            "supportGap": 0.0,
        },
        distance_flip_dimensions={
            "longitudinal": False,
            "lateral": False,
            "supportGap": False,
        },
    )
    assert result["passed"] is False
    assert result["status"] == "FAIL_FOOTPRINT_OUTSIDE_SUPPORT"
    assert result["predictedFootprint"]["maxY"] < result["safeBoundary"]["minY"]


def test_n000_a600_transport_overlap_release_and_recipe_are_fail_closed():
    plan = plan_parameterized_datum_placement(
        ROOT,
        "project05::N000",
        selected_slot_definition_id="project02::A600",
    )
    assert plan["status"] == "datum_candidate_blocked_by_safety_policy"
    assert plan["readyForTemplateCompilation"] is False
    assert plan["readyForReleasedCadExecution"] is False
    assert plan["safetyBlocker"]["code"] == "TRANSPORT_OCCUPANCY_REGION_OVERLAP"
    assert plan["selectedMatch"]["candidateReuseBlocked"] is True

    with pytest.raises(
        MechanicalInterfaceContractError,
        match="TRANSPORT_OCCUPANCY_REGION_OVERLAP",
    ):
        compile_parameterized_datum_validation_package(
            ROOT,
            "project05::N000",
            "project02::A600",
            initial_placement_variant=2,
        )


def test_n000_a600_exact_replacement_release_is_authorized_without_reenabling_recipe():
    authority = resolve_preferred_released_interface_authority(
        ROOT,
        "project05::N000",
        selected_slot_definition_id="project02::A600",
        allow_datum_fallback=True,
    )

    assert authority["ready"] is True
    assert authority["status"] == "released_exact_datum_interface_authority_ready"
    assert authority["selectedMode"] == "parameterized_datum_placement"
    assert authority["releaseManifestPath"].endswith(
        "relation-datum-project05-n000-project02-a600-75ad80ddd63f/"
        "release-manifest.json"
    )
    assert authority["pairReleaseEvidence"]["releaseId"] == (
        "datum-placement-e6cc7db2ffed27d9"
    )


@pytest.mark.parametrize(
    "module_id,slot_id,target_token,base_token",
    [
        ("project03::AI00", "project01::JJ00", "AI00", "JJ00"),
        ("project01::GN00", "project03::AA00", "GN00", "AA00"),
    ],
)
def test_validation_package_compiles_nonprototype_graph_without_releasing_pair(
    module_id, slot_id, target_token, base_token
):
    package = compile_parameterized_datum_validation_package(
        ROOT, module_id, slot_id, initial_placement_variant=2
    )
    graph = package["effectiveGraph"]
    assert package["status"] == "released_pair_ready_for_explicit_revalidation"
    assert package["readyForReleasedCadExecution"] is True
    assert package["prototypeTopLevelTargetPoseUsed"] is False
    assert package["physicalFasteningVerified"] is False
    assert Path(package["sourceAssemblyPath"]).is_file()
    assert len(package["sourceAssemblySha256"]) == 64
    assert graph["EditPolicy"] == {
        "baseModuleToken": base_token,
        "initialPlacementMode": "deterministic",
        "initialPlacementVariant": 2,
        "sourceGraphImmutable": True,
        "fixedModuleTokens": [base_token],
        "caseAnchoredModuleTokens": [],
        "targetLeafPoseAnchors": [],
        "fixCaseAnchorBeforeMates": False,
    }
    target = next(row for row in graph["Modules"] if row["ModuleToken"] == target_token)
    assert target["SourceTransform"] == [
        1.0, 0.0, 0.0, 0.0,
        1.0, 0.0, 0.0, 0.0,
        1.0, 0.0, 0.0, 0.0,
        1.0, 0.0, 0.0, 0.0,
    ]
    assert len(graph["Mates"]) == 3
    assert {row["MateTypeName"] for row in graph["Mates"]} == {
        "swMateDISTANCE",
        "swMateCOINCIDENT",
    }
    assert all(row["ModuleTokens"] == [target_token, base_token] for row in graph["Mates"])
    assert all(
        endpoint.get("SourceAssemblyPersistentReferenceBase64")
        for row in graph["Mates"]
        for endpoint in row["Endpoints"]
    )


def test_validation_package_rejects_role_incompatible_pair():
    with pytest.raises(MechanicalInterfaceContractError, match="compatible unreleased"):
        compile_parameterized_datum_validation_package(
            ROOT, "project99::UNKNOWN", "project05::A000"
        )


def test_tampering_is_detected():
    report = load_parameterized_datum_placement_catalog(ROOT)
    changed = copy.deepcopy(report)
    changed["summary"]["releasedPairCount"] = 1
    with pytest.raises(MechanicalInterfaceContractError, match="digest"):
        validate_contract_catalog(changed)


def test_backend_exposes_datum_catalog_plan_and_preferred_plan():
    from demo_backend.main import app

    paths = {route.path for route in app.routes}
    assert "/api/demo/mechanical-interface-contracts/datum-placement" in paths
    assert "/api/demo/mechanical-interface-contracts/datum-placement/plan" in paths
    assert "/api/demo/mechanical-interface-contracts/preferred-plan" in paths
