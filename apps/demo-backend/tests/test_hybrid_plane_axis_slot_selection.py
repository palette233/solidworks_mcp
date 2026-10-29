from pathlib import Path

import pytest

from demo_backend.hybrid_plane_axis_slot_selection import (
    build_f000_hybrid_axis_slot_catalog,
    compile_f000_hybrid_axis_selection,
    compile_f000_hybrid_axis_validation_package,
    rank_f000_hybrid_axis_candidates,
)
from demo_backend.mechanical_interface_contracts import (
    MechanicalInterfaceContractError,
)


ROOT = Path(__file__).resolve().parents[3]


def test_catalog_turns_f000_gap_into_explicit_axis_selection():
    catalog = build_f000_hybrid_axis_slot_catalog(ROOT)
    assert catalog["moduleDefinitionId"] == "project05::F000"
    by_slot = {row["slotDefinitionId"]: row for row in catalog["baseSlots"]}
    assert by_slot["project05::A000"]["state"] == "released_native_pair"
    assert by_slot["project05::A000"]["releasedAxisEndpointId"] == (
        "face:a000:0fe1c632c1c9959a"
    )
    for slot_id in ("project01::JJ00", "project02::A600", "project03::AA00"):
        row = by_slot[slot_id]
        assert row["state"] == "explicit_axis_selection_required"
        assert row["candidateAxisLineCount"] > 20
        assert row["readyForReleasedCadExecution"] is False
        assert all(
            item["diameterCompatibility"] == "not_evaluated"
            and item["supportAxisAlignment"] >= 1.0 - 1e-5
            and isinstance(item["axisMateAlignmentCompatible"], bool)
            and item["orientationAxisResidual"] <= 1e-5
            for item in row["axisCandidates"]
        )
    assert catalog["summary"]["releasedNativePairCount"] == 1
    a600 = by_slot["project02::A600"]
    assert a600["candidateCoordinateSpace"] == "world"
    assert a600["candidateAxisLineCount"] > 100
    assert a600["axisCandidateCatalogPath"].endswith(
        "a600-native-service-leaf-face-catalog-v1.json"
    )
    assert all(
        row["coordinateSpace"] == "world"
        and "axisOriginWorld" in row
        and "axisDirectionWorld" in row
        for row in a600["axisCandidates"]
    )
    assert catalog["summary"]["explicitAxisSelectionRequiredCount"] == 3


def test_axis_line_candidates_are_deduplicated_and_deterministic():
    first = build_f000_hybrid_axis_slot_catalog(ROOT)
    second = build_f000_hybrid_axis_slot_catalog(ROOT)
    assert first == second
    for slot in first["baseSlots"]:
        candidates = slot["axisCandidates"]
        keys = [
            (
                row["axisLineKey"]["longitudinalMeters"],
                row["axisLineKey"]["lateralMeters"],
            )
            for row in candidates
        ]
        assert len(keys) == len(set(keys))


def test_position_ranking_recommends_but_does_not_confirm_axis():
    catalog = build_f000_hybrid_axis_slot_catalog(ROOT)
    ranked = rank_f000_hybrid_axis_candidates(
        catalog,
        "project03::AA00",
        longitudinal_meters=0.078,
        lateral_meters=0.2115,
        limit=3,
    )
    assert len(ranked) == 3
    assert ranked[0]["axisMateAlignmentCompatible"] is True
    assert ranked[0]["selectionStatus"] == (
        "recommended_for_review_not_confirmed"
    )
    assert all(
        (
            not ranked[index]["axisMateAlignmentCompatible"],
            ranked[index]["distanceFromRequestedPositionMeters"],
        )
        <= (
            not ranked[index + 1]["axisMateAlignmentCompatible"],
            ranked[index + 1]["distanceFromRequestedPositionMeters"],
        )
        for index in range(len(ranked) - 1)
    )


def test_confirmed_axis_compiles_pending_three_mate_candidate():
    catalog = build_f000_hybrid_axis_slot_catalog(ROOT)
    ranked = rank_f000_hybrid_axis_candidates(
        catalog,
        "project01::JJ00",
        longitudinal_meters=0.096,
        lateral_meters=0.122,
        limit=1,
    )
    result = compile_f000_hybrid_axis_selection(
        ROOT,
        slot_definition_id="project01::JJ00",
        selected_axis_endpoint_id=ranked[0]["endpointId"],
        evidence={
            "confirmed": True,
            "source": "engineer_reviewed_demo_axis_candidate",
            "confirmedBy": "test-engineer",
        },
    )
    assert result["status"] == "ready_for_nonprototype_cad_validation"
    assert result["readyForReleasedCadExecution"] is False
    assert result["match"]["requiresNewPairCadValidation"] is True
    assert [
        row["mateTypeName"]
        for row in result["instantiatedTemplate"]["mateSteps"]
    ] == ["swMateCOINCIDENT", "swMatePARALLEL", "swMateCONCENTRIC"]
    assert result["moduleContract"]["mechanicalBoundary"][
        "requiresExplicitPairRelease"
    ] is True
    assert result["slotContract"]["mechanicalBoundary"][
        "diameterCompatibility"
    ] == "not_evaluated"


def test_confirmed_axis_compiles_common_nonprototype_validation_package():
    catalog = build_f000_hybrid_axis_slot_catalog(ROOT)
    endpoint = rank_f000_hybrid_axis_candidates(
        catalog,
        "project03::AA00",
        longitudinal_meters=0.078,
        lateral_meters=0.2115,
        limit=1,
    )[0]["endpointId"]
    package = compile_f000_hybrid_axis_validation_package(
        ROOT,
        slot_definition_id="project03::AA00",
        selected_axis_endpoint_id=endpoint,
        evidence={
            "confirmed": True,
            "source": "engineer_reviewed_demo_axis_candidate",
        },
    )
    assert package["placementMode"] == "reviewed_hybrid_plane_axis_datum"
    assert package["prototypeTopLevelTargetPoseUsed"] is False
    assert package["caseAnchorUsed"] is False
    assert package["targetLeafPoseAnchorsUsed"] is False
    assert package["readyForReleasedCadExecution"] is False
    assert package["effectiveGraph"]["ModuleCount"] == 2
    assert package["effectiveGraph"]["InterModuleMateCount"] == 3
    assert [
        row["MateTypeName"] for row in package["effectiveGraph"]["Mates"]
    ] == ["swMateCOINCIDENT", "swMatePARALLEL", "swMateCONCENTRIC"]
    assert package["selectedEndpointCatalog"]["EndpointCount"] == 6
    axis_rows = [
        row
        for row in package["selectedEndpointCatalog"]["Endpoints"]
        if (row.get("Endpoint") or {}).get("SurfaceType") == "Cylinder"
    ]
    assert len(axis_rows) == 2


def test_a600_separate_frame_and_axis_catalogs_compile_one_candidate():
    catalog = build_f000_hybrid_axis_slot_catalog(ROOT)
    slot = next(
        row
        for row in catalog["baseSlots"]
        if row["slotDefinitionId"] == "project02::A600"
    )
    endpoint = next(
        row["endpointId"]
        for row in slot["axisCandidates"]
        if row["axisMateAlignmentCompatible"] is True
    )
    package = compile_f000_hybrid_axis_validation_package(
        ROOT,
        slot_definition_id="project02::A600",
        selected_axis_endpoint_id=endpoint,
        evidence={
            "confirmed": True,
            "source": "engineer_reviewed_demo_axis_candidate",
        },
    )
    assert package["slotFrameEndpointCatalogPath"] != (
        package["slotAxisEndpointCatalogPath"]
    )
    assert package["effectiveGraph"]["InterModuleMateCount"] == 3
    base_rows = [
        row
        for row in package["selectedEndpointCatalog"]["Endpoints"]
        if (row.get("Endpoint") or {}).get("ModuleToken") != "F000"
    ]
    assert any(
        (row.get("Endpoint") or {}).get("SurfaceType") == "Cylinder"
        for row in base_rows
    )


@pytest.mark.parametrize(
    "evidence,endpoint",
    [
        ({"confirmed": False, "source": "review"}, "face:jj00:26f0947dd4eb797d"),
        ({"confirmed": True, "source": ""}, "face:jj00:26f0947dd4eb797d"),
        ({"confirmed": True, "source": "review"}, "face:jj00:not-real"),
    ],
)
def test_unconfirmed_or_unknown_axis_fails_closed(evidence, endpoint):
    with pytest.raises(MechanicalInterfaceContractError):
        compile_f000_hybrid_axis_selection(
            ROOT,
            slot_definition_id="project01::JJ00",
            selected_axis_endpoint_id=endpoint,
            evidence=evidence,
        )
