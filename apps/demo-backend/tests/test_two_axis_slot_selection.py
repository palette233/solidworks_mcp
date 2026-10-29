from pathlib import Path

import pytest

from demo_backend.mechanical_interface_contracts import MechanicalInterfaceContractError
from demo_backend.two_axis_slot_selection import (
    build_two_axis_native_station_references,
    build_two_axis_slot_candidate_catalog,
    compile_two_axis_slot_selection,
    compile_two_axis_slot_validation_package,
    rank_two_axis_candidates_from_native_station,
)


ROOT = Path(__file__).resolve().parents[3]


def _candidate(role: str) -> dict:
    catalog = build_two_axis_slot_candidate_catalog(ROOT)
    family = next(row for row in catalog["families"] if row["moduleRole"] == role)
    return family["axisPairCandidates"][0]


def test_A000_inventory_has_reviewable_50_and_58mm_pairs_without_auto_selection():
    catalog = build_two_axis_slot_candidate_catalog(ROOT)
    assert catalog["slotDefinitionId"] == "project05::A000"
    assert catalog["candidateAxisLineCount"] > 100
    by_role = {row["moduleRole"]: row for row in catalog["families"]}
    assert by_role["Calibration"]["candidatePairCount"] == 9
    assert by_role["Transport"]["candidatePairCount"] == 6
    assert by_role["Calibration"]["requiredSpacingMeters"] == pytest.approx(0.05)
    assert by_role["Transport"]["requiredSpacingMeters"] == pytest.approx(0.058)
    assert all(
        row["state"] == "explicit_axis_pair_selection_required"
        and row["readyForReleasedCadExecution"] is False
        for row in by_role.values()
    )
    assert all(
        candidate["installationPurpose"] == "not_confirmed"
        and candidate["diameterAndFastenerFit"] == "not_evaluated"
        for family in by_role.values()
        for candidate in family["axisPairCandidates"]
    )
    assert {
        (row["moduleDefinitionId"], row["slotDefinitionId"])
        for row in catalog["verifiedIncompatibilities"]
    } == {
        ("project01::SS00", "project02::A600"),
        ("project03::AE00", "project02::A600"),
    }
    assert all(
        row["candidateAxisLineCount"] > 100
        and row["matchingAxisPairCount"] == 0
        and row["requiredSpacingMeters"] == pytest.approx(0.058)
        for row in catalog["verifiedIncompatibilities"]
    )


def test_native_axis_pair_stations_are_review_only_and_preserve_primary_order():
    evidence = build_two_axis_native_station_references(ROOT)
    assert evidence["schemaVersion"] == (
        "two-axis-native-station-review-evidence/v1"
    )
    assert evidence["summary"]["stationCount"] == 4
    by_module = {row["moduleDefinitionId"]: row for row in evidence["stations"]}
    assert by_module["project01::BD00"]["semanticAxisPointsMeters"] == {
        "primary": [pytest.approx(0.81), pytest.approx(0.5685)],
        "secondary": [pytest.approx(0.81), pytest.approx(0.6185)],
    }
    assert by_module["project01::SS00"]["semanticAxisPointsMeters"] == {
        "primary": [pytest.approx(0.096), pytest.approx(0.0095)],
        "secondary": [pytest.approx(0.096), pytest.approx(0.0675)],
    }
    assert by_module["project01::BD00"]["nativeConcentricAlignments"] == {
        "primary": 0,
        "secondary": 0,
    }
    assert by_module["project01::SS00"]["nativeConcentricAlignments"] == {
        "primary": 1,
        "secondary": 1,
    }
    assert all(row["reviewOnly"] is True for row in evidence["stations"])
    assert all(
        row["prototypePoseAllowedAsCadExecutionAuthority"] is False
        for row in evidence["stations"]
    )
    assert all(
        row["baseSupportNormalWorld"] == [pytest.approx(0), pytest.approx(-1), pytest.approx(0)]
        for row in evidence["stations"]
    )


@pytest.mark.parametrize(
    "module_definition_id,expected_candidate_id",
    [
        ("project01::BD00", "axis-pair/d540d23a06a33af1"),
        ("project03::AH00", "axis-pair/d540d23a06a33af1"),
        ("project01::SS00", "axis-pair/fd5c65bc67c31b92"),
        ("project03::AE00", "axis-pair/fd5c65bc67c31b92"),
    ],
)
def test_native_station_pair_ranking_is_deterministic_and_keeps_axis_assignment(
    module_definition_id: str, expected_candidate_id: str
):
    catalog = build_two_axis_slot_candidate_catalog(ROOT)
    first = rank_two_axis_candidates_from_native_station(
        ROOT, catalog, module_definition_id, limit=5
    )
    second = rank_two_axis_candidates_from_native_station(
        ROOT, catalog, module_definition_id, limit=5
    )
    assert first == second
    assert first[0]["candidatePairId"] == expected_candidate_id
    assert first[0]["axisAssignment"] == "direct"
    distances = [row["twoPointRmsFromNativeStationMeters"] for row in first]
    assert distances == sorted(distances)


@pytest.mark.parametrize(
    "module_definition_id,role,mate_types",
    [
        (
            "project01::BD00",
            "Calibration",
            ["swMateCOINCIDENT", "swMateCONCENTRIC", "swMateCONCENTRIC"],
        ),
        (
            "project01::SS00",
            "Transport",
            ["swMateCOINCIDENT", "swMateCONCENTRIC", "swMateCONCENTRIC"],
        ),
    ],
)
def test_confirmed_pair_compiles_to_three_mate_nonprototype_candidate(
    module_definition_id: str, role: str, mate_types: list[str]
):
    candidate = _candidate(role)
    evidence = {
        "confirmed": True,
        "source": "test_engineering_confirmation",
        "selectedCandidatePairId": candidate["candidatePairId"],
    }
    selection = compile_two_axis_slot_selection(
        ROOT,
        module_definition_id=module_definition_id,
        selected_candidate_pair_id=candidate["candidatePairId"],
        evidence=evidence,
    )
    assert selection["status"] == "ready_for_nonprototype_cad_validation"
    assert selection["match"]["compatible"] is True
    assert selection["readyForReleasedCadExecution"] is False
    package = compile_two_axis_slot_validation_package(
        ROOT,
        module_definition_id=module_definition_id,
        selected_candidate_pair_id=candidate["candidatePairId"],
        evidence=evidence,
    )
    assert package["prototypeTopLevelTargetPoseUsed"] is False
    assert package["caseAnchorUsed"] is False
    assert package["normalExecutionAuthorized"] is False
    assert [
        row["MateTypeName"] for row in package["effectiveMateGraph"]["Mates"]
    ] == mate_types
    orientation = selection["axisOrientationEvidence"]
    assert orientation["supportNormalDotProduct"] == pytest.approx(-1)
    expected_alignment = 1 if role == "Calibration" else 0
    assert orientation["concentricAlignments"] == {
        "primary": expected_alignment,
        "secondary": expected_alignment,
    }
    concentric = [
        row
        for row in package["effectiveMateGraph"]["Mates"]
        if row["MateTypeName"] == "swMateCONCENTRIC"
    ]
    expected_name = (
        "swMateAlignANTI_ALIGNED"
        if expected_alignment == 1
        else "swMateAlignALIGNED"
    )
    assert [row["AlignmentName"] for row in concentric] == [
        expected_name,
        expected_name,
    ]


def test_spacing_match_cannot_silently_become_execution_authority():
    candidate = _candidate("Calibration")
    with pytest.raises(MechanicalInterfaceContractError, match="confirmed evidence"):
        compile_two_axis_slot_selection(
            ROOT,
            module_definition_id="project01::BD00",
            selected_candidate_pair_id=candidate["candidatePairId"],
            evidence={
                "confirmed": False,
                "source": "",
                "selectedCandidatePairId": candidate["candidatePairId"],
            },
        )


def test_candidate_from_wrong_spacing_family_is_rejected():
    transport_candidate = _candidate("Transport")
    with pytest.raises(MechanicalInterfaceContractError, match="not a candidate"):
        compile_two_axis_slot_selection(
            ROOT,
            module_definition_id="project01::BD00",
            selected_candidate_pair_id=transport_candidate["candidatePairId"],
            evidence={
                "confirmed": True,
                "source": "test",
                "selectedCandidatePairId": transport_candidate[
                    "candidatePairId"
                ],
            },
        )
