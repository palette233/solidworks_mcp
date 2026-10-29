from pathlib import Path

import pytest

from demo_backend.flexible_calibration_slot_selection import (
    build_g000_flexible_slot_candidate_catalog,
    build_g000_native_station_reference,
    compile_g000_flexible_slot_selection,
    compile_g000_flexible_slot_validation_package,
    rank_g000_flexible_slot_candidates,
)
from demo_backend.mechanical_interface_contracts import MechanicalInterfaceContractError


ROOT = Path(__file__).resolve().parents[3]


def _candidate(slot_definition_id: str) -> str:
    catalog = build_g000_flexible_slot_candidate_catalog(ROOT)
    slot = next(
        row
        for row in catalog["baseSlots"]
        if row["slotDefinitionId"] == slot_definition_id
    )
    return str(slot["axisCandidates"][0]["endpointId"])


def test_catalog_preserves_native_pair_and_exposes_three_reviewed_bases():
    catalog = build_g000_flexible_slot_candidate_catalog(ROOT)
    by_slot = {row["slotDefinitionId"]: row for row in catalog["baseSlots"]}
    native = by_slot["project05::A000"]
    assert native["state"] == "released_native_pair"
    assert native["releasedSlotLocatorEndpointId"] == (
        "face:a000:aabecbe1ad0e7c8b"
    )
    assert native["releasedLongitudinalOffsetMeters"] == pytest.approx(0.482)
    for slot_id in ("project01::JJ00", "project02::A600", "project03::AA00"):
        row = by_slot[slot_id]
        assert row["state"] == "explicit_flexible_slot_selection_required"
        assert row["candidateAxisLineCount"] > 100
        assert row["readyForReleasedCadExecution"] is False
        assert all(
            candidate["diameterCompatibility"] == "not_evaluated"
            for candidate in row["axisCandidates"]
        )
    assert catalog["summary"]["releasedNativePairCount"] == 1
    assert catalog["summary"]["explicitFlexibleSlotSelectionRequiredCount"] == 3
    assert catalog["summary"]["axisNotFoundCount"] == 0


def test_catalog_is_deterministic_and_does_not_auto_select_an_axis():
    first = build_g000_flexible_slot_candidate_catalog(ROOT)
    second = build_g000_flexible_slot_candidate_catalog(ROOT)
    assert first == second
    for row in first["baseSlots"]:
        assert "selectedAxisEndpointId" not in row
        assert "recommendedAxisEndpointId" not in row


def test_native_station_reference_is_review_only_and_uses_semantic_base_frame():
    reference = build_g000_native_station_reference(ROOT)
    assert reference["semanticAxisPositionMeters"] == {
        "longitudinal": pytest.approx(0.5),
        "lateral": pytest.approx(0.492),
    }
    assert reference["longitudinalOffsetMeters"] == pytest.approx(0.482)
    assert reference["prototypePoseUsedForMeasurement"] is True
    assert reference["prototypePoseAllowedAsCadExecutionAuthority"] is False
    assert reference["reviewOnly"] is True
    assert reference["targetEnvelopeVerified"] is False


@pytest.mark.parametrize(
    "slot_definition_id",
    ("project01::JJ00", "project02::A600", "project03::AA00"),
)
def test_flexible_axis_ranking_is_deterministic_and_does_not_authorize_cad(
    slot_definition_id: str,
):
    catalog = build_g000_flexible_slot_candidate_catalog(ROOT)
    first = rank_g000_flexible_slot_candidates(
        ROOT, catalog, slot_definition_id, limit=5
    )
    second = rank_g000_flexible_slot_candidates(
        ROOT, catalog, slot_definition_id, limit=5
    )
    assert first == second
    assert len(first) == 5
    distances = [row["distanceFromNativeSemanticAxisMeters"] for row in first]
    assert distances == sorted(distances)
    authoritative = {
        row["endpointId"]
        for slot in catalog["baseSlots"]
        if slot["slotDefinitionId"] == slot_definition_id
        for row in slot["axisCandidates"]
    }
    assert {row["endpointId"] for row in first}.issubset(authoritative)
    assert all("readyForReleasedCadExecution" not in row for row in first)


def test_confirmed_axis_and_offset_compile_exact_four_relation_bundle():
    endpoint = _candidate("project01::JJ00")
    evidence = {
        "confirmed": True,
        "source": "test_engineering_review",
        "selectedAxisEndpointId": endpoint,
        "longitudinalOffsetMeters": 0.321,
    }
    selection = compile_g000_flexible_slot_selection(
        ROOT,
        slot_definition_id="project01::JJ00",
        selected_axis_endpoint_id=endpoint,
        longitudinal_offset_meters=0.321,
        evidence=evidence,
    )
    assert selection["status"] == "ready_for_nonprototype_cad_validation"
    assert selection["readyForReleasedCadExecution"] is False
    assert selection["longitudinalOffsetMeters"] == pytest.approx(0.321)
    assert selection["moduleContract"]["constraintContract"][
        "internalFlexibilityPreserved"
    ] is True
    assert [
        row["mateTypeName"]
        for row in selection["instantiatedTemplate"]["mateSteps"]
    ] == ["swMateCOINCIDENT", "swMatePARALLEL", "swMateDISTANCE", "swMateSLOT"]


def test_confirmed_selection_compiles_nonprototype_four_mate_graph():
    endpoint = _candidate("project02::A600")
    package = compile_g000_flexible_slot_validation_package(
        ROOT,
        slot_definition_id="project02::A600",
        selected_axis_endpoint_id=endpoint,
        longitudinal_offset_meters=0.250,
        evidence={
            "confirmed": True,
            "source": "test_engineering_review",
            "selectedAxisEndpointId": endpoint,
            "longitudinalOffsetMeters": 0.250,
        },
    )
    assert package["placementMode"] == "reviewed_flexible_calibration_slot"
    assert package["prototypeTopLevelTargetPoseUsed"] is False
    assert package["caseAnchorUsed"] is False
    assert package["targetLeafPoseAnchorsUsed"] is False
    assert package["readyForReleasedCadExecution"] is False
    assert package["effectiveGraph"]["InterModuleMateCount"] == 4
    assert [row["MateTypeName"] for row in package["effectiveGraph"]["Mates"]] == [
        "swMateCOINCIDENT",
        "swMatePARALLEL",
        "swMateDISTANCE",
        "swMateSLOT",
    ]
    assert package["effectiveGraph"]["Mates"][-1]["AdvancedOptions"] == {
        "SlotConstraint": 0,
        "SlotDistance": 0,
        "SlotPercent": 0,
        "SlotFlipDirection": False,
    }
    assert package["slotFrameEndpointCatalogPath"] != (
        package["slotAxisEndpointCatalogPath"]
    )
    target = next(
        row
        for row in package["effectiveGraph"]["Modules"]
        if row["ModuleToken"] == "G000"
    )
    assert target["SolvingState"] == 1
    assert target["SolvingStateName"] == "swComponentFlexibleSolving"

    repeat = compile_g000_flexible_slot_validation_package(
        ROOT,
        slot_definition_id="project02::A600",
        selected_axis_endpoint_id=endpoint,
        longitudinal_offset_meters=0.250,
        evidence={
            "confirmed": True,
            "source": "test_engineering_review",
            "selectedAxisEndpointId": endpoint,
            "longitudinalOffsetMeters": 0.250,
        },
        initial_placement_variant=2,
    )
    repeat_target = next(
        row
        for row in repeat["effectiveGraph"]["Modules"]
        if row["ModuleToken"] == "G000"
    )
    assert repeat_target["SolvingState"] == 1
    # The source transform remains a neutral graph value; the executor applies
    # the deterministic non-source pose selected by EditPolicy.
    assert package["effectiveGraph"]["EditPolicy"]["initialPlacementVariant"] == 1
    assert repeat["effectiveGraph"]["EditPolicy"]["initialPlacementVariant"] == 2


@pytest.mark.parametrize(
    "evidence,endpoint,offset",
    [
        ({"confirmed": False, "source": "review"}, "valid", 0.1),
        ({"confirmed": True, "source": ""}, "valid", 0.1),
        ({"confirmed": True, "source": "review"}, "face:not-real", 0.1),
        ({"confirmed": True, "source": "review"}, "valid", -0.1),
    ],
)
def test_unconfirmed_unknown_or_invalid_selection_fails_closed(
    evidence: dict, endpoint: str, offset: float
):
    actual_endpoint = (
        _candidate("project03::AA00") if endpoint == "valid" else endpoint
    )
    with pytest.raises(MechanicalInterfaceContractError):
        compile_g000_flexible_slot_selection(
            ROOT,
            slot_definition_id="project03::AA00",
            selected_axis_endpoint_id=actual_endpoint,
            longitudinal_offset_meters=offset,
            evidence=evidence,
        )
