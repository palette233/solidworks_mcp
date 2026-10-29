import json
from pathlib import Path
import subprocess
import sys

import demo_backend.parameterized_datum_engineering_review as engineering_review_module

from demo_backend.parameterized_datum_engineering_review import (
    build_axis_pair_confirmation_template,
    build_confirmation_templates,
    build_flexible_slot_confirmation_template,
    build_manual_input_barrier,
    build_parameterized_datum_engineering_review,
    build_prioritized_mixed_recommendation_batch,
)
from demo_backend.parameterized_datum_geometry_decisions import (
    REQUEST_SCHEMA as GEOMETRY_REQUEST_SCHEMA,
    compile_geometry_decision_requests,
    geometry_decision_evidence_maps,
)
from demo_backend.parameterized_datum_position_decisions import (
    REQUEST_SCHEMA as POSITION_REQUEST_SCHEMA,
    compile_position_decision_requests,
)
from demo_backend.parameterized_datum_validation_queue import (
    build_parameterized_datum_validation_queue,
)
from demo_backend.mechanical_interface_contracts import MechanicalInterfaceContractError
import pytest


ROOT = Path(__file__).resolve().parents[3]
HISTORICAL_REVIEW = (
    ROOT
    / "demo/cross_project_substitution/parameterized-datum-placement-v1"
    / "engineering-decision-review-20261026-v22/engineering-review.json"
)
THIRD_BATCH_REVIEW = (
    ROOT
    / "demo/cross_project_substitution/parameterized-datum-placement-v1"
    / "engineering-decision-review-20261026-v47/engineering-review.json"
)
NEXT_BATCH_REVIEW = (
    ROOT
    / "demo/cross_project_substitution/parameterized-datum-placement-v1"
    / "engineering-decision-review-20261026-v50/engineering-review.json"
)
FINAL_FIVE_REVIEW = (
    ROOT
    / "demo/cross_project_substitution/parameterized-datum-placement-v1"
    / "engineering-decision-review-20261026-v66-final-five/engineering-review.json"
)


def _historical_review() -> dict:
    """Frozen pre-publication packet for recommendation workflow tests."""

    return json.loads(HISTORICAL_REVIEW.read_text(encoding="utf-8-sig"))


def _decision(review: dict, module: str, slot: str) -> dict:
    return next(
        row
        for row in review["decisions"]
        if row["moduleDefinitionId"] == module
        and row["slotDefinitionId"] == slot
    )


def test_review_uses_each_target_bases_native_scanner_station():
    review = _historical_review()

    assert review["decisionCount"] == 25
    assert review["positionDecisionCount"] == 15
    assert review["axisDecisionCount"] == 3
    assert review["axisPairDecisionCount"] == 4
    assert review["flexibleSlotDecisionCount"] == 3
    assert review["allRecommendationsUnconfirmed"] is True
    a180_a000 = _decision(review, "project02::A180", "project05::A000")
    ai00_a000 = _decision(review, "project03::AI00", "project05::A000")
    assert a180_a000["reference"]["referenceModuleDefinitionId"] == "project01::SM00"
    assert a180_a000["recommendedParametersMeters"] == {
        "longitudinal": 0.070,
        "lateral": 0.102,
        "supportGap": 0.0,
    }
    assert ai00_a000["reference"]["referenceModuleDefinitionId"] == "project01::SM00"
    assert ai00_a000["recommendedParametersMeters"] == {
        "longitudinal": 0.070,
        "lateral": 0.102,
        "supportGap": 0.0,
    }
    waste_input = _decision(review, "project02::A300", "project01::JJ00")
    assert waste_input["status"] == "explicit_engineering_input_required"
    assert waste_input["recommendedParametersMeters"] is None
    assert waste_input["confirmationTemplate"]["parametersMeters"] is None


def test_review_recommends_exact_module_station_only_from_cross_base_consensus():
    review = _historical_review()

    n000 = _decision(review, "project05::N000", "project02::A600")
    assert n000["status"] == "recommendation_pending_engineering_confirmation"
    assert n000["basis"] == "cross_base_module_station_consensus"
    assert n000["recommendedParametersMeters"] == {
        "longitudinal": 0.465,
        "lateral": 0.7125,
        "supportGap": 0.0,
    }
    assert n000["reference"]["selectionBasis"] == (
        "cross_base_module_station_consensus"
    )
    assert n000["reference"]["sourceBaseDefinitionIds"] == [
        "project01::JJ00",
        "project03::AA00",
        "project05::A000",
    ]
    assert n000["reference"]["sourceStationCount"] == 3
    assert n000["reference"]["targetEnvelopeVerified"] is False
    assert n000["confirmationTemplate"]["confirmed"] is False


def test_review_does_not_recommend_when_cross_base_stations_disagree():
    review = json.loads(FINAL_FIVE_REVIEW.read_text(encoding="utf-8-sig"))

    p000 = _decision(review, "project05::P000", "project01::JJ00")
    assert p000["status"] == "explicit_engineering_input_required"
    assert p000["recommendedParametersMeters"] is None
    assert p000["confirmationTemplate"]["parametersMeters"] is None
    assert p000["confirmationTemplate"]["confirmed"] is False


def test_f000_recommendations_are_ranked_but_remain_unconfirmed():
    review = _historical_review()

    for slot in ("project01::JJ00", "project03::AA00"):
        row = _decision(review, "project05::F000", slot)
        distances = [
            candidate["distanceFromRequestedPositionMeters"]
            for candidate in row["rankedAxisCandidates"]
        ]
        assert len(distances) >= 3
        assert distances == sorted(distances)
        assert row["recommendedAxisEndpointId"] == row["rankedAxisCandidates"][0][
            "endpointId"
        ]
        assert row["confirmationTemplate"]["confirmed"] is False
        assert row["recommendedAxisDistanceMeters"] == distances[0]

    # The frozen historical packet deliberately preserves the pre-native-
    # station state. Current behavior is covered by
    # test_native_role_station_evidence.py.
    a600 = _decision(review, "project05::F000", "project02::A600")
    assert a600["status"] == "explicit_engineering_position_and_axis_input_required"
    assert a600["availableAxisLineCount"] > 100
    assert a600["recommendedAxisEndpointId"] is None
    assert a600["rankedAxisCandidates"] == []
    assert a600["confirmationTemplate"]["selectedAxisEndpointId"] is None
    assert a600["reference"]["selectionBasis"] == (
        "multiple_registered_role_stations_require_choice"
    )
    assert {
        row["referenceModuleDefinitionId"]
        for row in a600["reference"]["candidateRoleStations"]
    } == {"project01::SM00", "project03::AI00"}
    assert "Multiple scanner stations" in a600["confirmationTemplate"]["notes"]


def test_g000_ranks_native_station_projection_but_keeps_confirmation_closed():
    review = json.loads(NEXT_BATCH_REVIEW.read_text(encoding="utf-8-sig"))
    for slot in ("project01::JJ00", "project02::A600", "project03::AA00"):
        row = _decision(review, "project05::G000", slot)
        assert row["decisionKind"] == "flexible_slot_selection"
        assert row["status"] == "recommendation_pending_engineering_confirmation"
        assert row["recommendedAxisEndpointId"] == row["rankedAxisCandidates"][0][
            "endpointId"
        ]
        assert row["recommendedLongitudinalOffsetMeters"] == pytest.approx(0.482)
        assert row["recommendedAxisDistanceMeters"] == pytest.approx(
            row["rankedAxisCandidates"][0][
                "distanceFromNativeSemanticAxisMeters"
            ]
        )
        assert row["reference"]["candidateAxisLineCount"] > 100
        native = row["reference"]["nativeStationReference"]
        assert native["semanticAxisPositionMeters"] == {
            "longitudinal": pytest.approx(0.5),
            "lateral": pytest.approx(0.492),
        }
        assert native["prototypePoseAllowedAsCadExecutionAuthority"] is False
        assert row["confirmationTemplate"]["confirmed"] is False
        assert row["confirmationTemplate"]["selectedAxisEndpointId"] == row[
            "recommendedAxisEndpointId"
        ]
        assert row["confirmationTemplate"]["longitudinalOffsetMeters"] == (
            pytest.approx(0.482)
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
def test_two_axis_pairs_are_ranked_by_exact_native_primary_secondary_station(
    module_definition_id: str, expected_candidate_id: str
):
    review = json.loads(NEXT_BATCH_REVIEW.read_text(encoding="utf-8-sig"))
    row = _decision(review, module_definition_id, "project05::A000")
    assert row["decisionKind"] == "axis_pair_selection"
    assert row["status"] == "recommendation_pending_engineering_confirmation"
    assert row["recommendedCandidatePairId"] == expected_candidate_id
    assert row["recommendedAxisAssignment"] == "direct"
    assert row["recommendedPairRmsMeters"] == pytest.approx(
        row["axisPairCandidates"][0]["twoPointRmsFromNativeStationMeters"]
    )
    assert row["confirmationTemplate"]["confirmed"] is False
    assert row["confirmationTemplate"]["selectedCandidatePairId"] == (
        expected_candidate_id
    )
    assert row["reference"]["nativeStationReference"][
        "prototypePoseAllowedAsCadExecutionAuthority"
    ] is False


def test_confirmation_templates_cannot_silently_authorize_execution():
    review = _historical_review()
    positions, axes = build_confirmation_templates(review)

    assert positions["schemaVersion"] == "parameterized-datum-position-parameters/v1"
    assert axes["schemaVersion"] == "hybrid-plane-axis-selection-evidence/v1"
    assert len(positions["pairs"]) == 15
    assert len(axes["pairs"]) == 3
    assert all(row["confirmed"] is False for row in positions["pairs"])
    assert all(row["confirmed"] is False for row in axes["pairs"])
    axis_pairs = build_axis_pair_confirmation_template(review)
    assert axis_pairs["schemaVersion"] == "two-axis-slot-selection-evidence/v1"
    assert len(axis_pairs["pairs"]) == 4
    assert all(row["confirmed"] is False for row in axis_pairs["pairs"])
    flexible = build_flexible_slot_confirmation_template(review)
    assert flexible["schemaVersion"] == (
        "flexible-calibration-slot-selection-evidence/v1"
    )
    assert len(flexible["pairs"]) == 3
    assert all(row["confirmed"] is False for row in flexible["pairs"])
    assert all(row["selectedAxisEndpointId"] is None for row in flexible["pairs"])
    assert all(row["longitudinalOffsetMeters"] is None for row in flexible["pairs"])

    position_map = {
        (row["moduleDefinitionId"], row["slotDefinitionId"]): {
            key: value
            for key, value in row.items()
            if key not in {"moduleDefinitionId", "slotDefinitionId", "moduleRole"}
        }
        for row in positions["pairs"]
    }
    with pytest.raises(MechanicalInterfaceContractError, match="not confirmed"):
        build_parameterized_datum_validation_queue(
            ROOT, explicit_position_parameters=position_map
        )


def test_mixed_batch_reaches_five_without_authorizing_any_decision():
    review = _historical_review()
    batch = build_prioritized_mixed_recommendation_batch(review)
    assert batch["status"] == "ready_for_engineering_review"
    assert batch["availableRecommendationCount"] == 5
    assert batch["selectedRecommendationCount"] == 5
    assert batch["deferredRecommendationCount"] == 0
    assert batch["allRecommendationsUnconfirmed"] is True
    assert [row["decisionKind"] for row in batch["selected"]].count(
        "position_parameters"
    ) == 3
    assert [row["decisionKind"] for row in batch["selected"]].count(
        "axis_selection"
    ) == 2
    assert all(
        row["confirmationTemplate"]["confirmed"] is False
        for row in batch["selected"]
    )


def test_mixed_batch_rejects_tampered_review_and_invalid_limit():
    review = json.loads(FINAL_FIVE_REVIEW.read_text(encoding="utf-8-sig"))
    with pytest.raises(MechanicalInterfaceContractError, match="between 5 and 8"):
        build_prioritized_mixed_recommendation_batch(review, limit=4)
    tampered = json.loads(json.dumps(review))
    tampered["decisions"][0]["status"] = "tampered"
    with pytest.raises(MechanicalInterfaceContractError, match="digest mismatch"):
        build_prioritized_mixed_recommendation_batch(tampered)


def test_current_recommendations_split_into_two_disjoint_eight_item_batches():
    review = json.loads(THIRD_BATCH_REVIEW.read_text(encoding="utf-8-sig"))
    first = build_prioritized_mixed_recommendation_batch(review, limit=8)
    first_pairs = {
        (row["moduleDefinitionId"], row["slotDefinitionId"])
        for row in first["selected"]
    }
    following = build_prioritized_mixed_recommendation_batch(
        review,
        limit=8,
        exclude_pairs=first_pairs,
    )
    following_pairs = {
        (row["moduleDefinitionId"], row["slotDefinitionId"])
        for row in following["selected"]
    }
    assert len(first_pairs) == 8
    assert len(following_pairs) == 8
    assert first_pairs.isdisjoint(following_pairs)
    assert following["availableRecommendationCount"] == 9
    assert following["deferredRecommendationCount"] == 1
    assert [row["decisionKind"] for row in following["selected"]].count(
        "position_parameters"
    ) == 1
    assert [row["decisionKind"] for row in following["selected"]].count(
        "axis_selection"
    ) == 1
    assert [row["decisionKind"] for row in following["selected"]].count(
        "axis_pair_selection"
    ) == 4
    assert [row["decisionKind"] for row in following["selected"]].count(
        "flexible_slot_selection"
    ) == 2
    assert following["allRecommendationsUnconfirmed"] is True


def test_v50_next_batch_evidence_now_resolves_to_eight_released_pairs():
    """Keep the frozen v50 confirmation bundle valid after CAD publication."""

    review = json.loads(NEXT_BATCH_REVIEW.read_text(encoding="utf-8-sig"))
    batch = build_prioritized_mixed_recommendation_batch(review, limit=8)
    selected_pairs = {
        (row["moduleDefinitionId"], row["slotDefinitionId"])
        for row in batch["selected"]
    }
    assert len(selected_pairs) == 8
    assert [row["decisionKind"] for row in batch["selected"]].count(
        "position_parameters"
    ) == 1
    assert [row["decisionKind"] for row in batch["selected"]].count(
        "axis_selection"
    ) == 1
    assert [row["decisionKind"] for row in batch["selected"]].count(
        "axis_pair_selection"
    ) == 4
    assert [row["decisionKind"] for row in batch["selected"]].count(
        "flexible_slot_selection"
    ) == 2

    provenance = {
        "confirmed": True,
        "source": "in-memory-v50-preflight-only",
        "confirmedBy": "automated-dry-run",
        "confirmedAt": "2026-10-26T13:00:00+08:00",
    }
    position_requests = []
    geometry_requests = []
    decisions = {
        (row["moduleDefinitionId"], row["slotDefinitionId"]): row
        for row in review["decisions"]
    }
    for selected in batch["selected"]:
        pair = (
            selected["moduleDefinitionId"],
            selected["slotDefinitionId"],
        )
        if selected["decisionKind"] == "position_parameters":
            position_requests.append(
                {
                    "moduleDefinitionId": pair[0],
                    "slotDefinitionId": pair[1],
                    "action": "accept_recommendation",
                    "positionInstruction": None,
                    **provenance,
                }
            )
        else:
            geometry_requests.append(
                {
                    "moduleDefinitionId": pair[0],
                    "slotDefinitionId": pair[1],
                    "decisionKind": selected["decisionKind"],
                    "action": "accept_recommendation",
                    "sourceDecisionDigest": decisions[pair]["decisionDigest"],
                    **provenance,
                }
            )

    position_packet = compile_position_decision_requests(
        review,
        {
            "schemaVersion": POSITION_REQUEST_SCHEMA,
            "sourceReviewDigest": review["reviewDigest"],
            "requests": position_requests,
        },
    )
    position_map = {
        (row["moduleDefinitionId"], row["slotDefinitionId"]): {
            key: value
            for key, value in row.items()
            if key not in {"moduleDefinitionId", "slotDefinitionId"}
        }
        for row in position_packet["pairs"]
    }
    geometry_packet = compile_geometry_decision_requests(
        ROOT,
        review,
        {
            "schemaVersion": GEOMETRY_REQUEST_SCHEMA,
            "sourceReviewDigest": review["reviewDigest"],
            "requests": geometry_requests,
        },
    )
    geometry_maps = geometry_decision_evidence_maps(geometry_packet)
    queue = build_parameterized_datum_validation_queue(
        ROOT,
        explicit_position_parameters=position_map,
        explicit_axis_selections=geometry_maps["axisSelections"],
        explicit_axis_pair_selections=geometry_maps["axisPairSelections"],
        explicit_flexible_slot_selections=geometry_maps[
            "flexibleSlotSelections"
        ],
    )
    released = {
        (row["moduleDefinitionId"], row["slotDefinitionId"]): row
        for row in queue["pairs"]
        if row["state"] == "released"
    }
    assert selected_pairs <= set(released)
    assert all(
        released[pair]["readyForReleasedCadExecution"] is True
        for pair in selected_pairs
    )
    assert queue["summary"]["readyForCadValidationCount"] == 0


def test_manual_input_barrier_lists_only_the_five_pairs_without_reliable_station():
    review = json.loads(FINAL_FIVE_REVIEW.read_text(encoding="utf-8-sig"))
    barrier = build_manual_input_barrier(review)

    assert barrier["status"] == "mechanical_confirmation_required"
    assert barrier["pairCount"] == 5
    assert {
        (row["moduleDefinitionId"], row["slotDefinitionId"])
        for row in barrier["pairs"]
    } == {
        ("project02::A300", "project01::JJ00"),
        ("project02::A500", "project01::JJ00"),
        ("project02::A500", "project03::AA00"),
        ("project02::A500", "project05::A000"),
        ("project05::P000", "project01::JJ00"),
    }
    assert all(row["cadLaunchAllowed"] is False for row in barrier["pairs"])
    assert all(
        row["prototypeTopLevelPoseAllowed"] is False for row in barrier["pairs"]
    )


def test_explicit_demo_projection_recommends_exact_native_station_for_final_five(
    monkeypatch,
):
    final_pairs = [
        ("project02::A300", "project01::JJ00", "WasteCup"),
        ("project02::A500", "project01::JJ00", "Calibration"),
        ("project02::A500", "project03::AA00", "Calibration"),
        ("project02::A500", "project05::A000", "Calibration"),
        ("project05::P000", "project01::JJ00", "WasteCup"),
    ]
    monkeypatch.setattr(
        engineering_review_module,
        "build_parameterized_datum_validation_queue",
        lambda workspace: {
            "queueDigest": "test-final-five-before-publication",
            "pairs": [
                {
                    "moduleDefinitionId": module,
                    "slotDefinitionId": slot,
                    "moduleRole": role,
                    "state": "explicit_position_parameters_required",
                }
                for module, slot, role in final_pairs
            ],
        },
    )
    monkeypatch.setattr(
        engineering_review_module,
        "_target_role_station",
        lambda catalog, slot_definition_id, module_role, **kwargs: {
            "targetSlotContractId": f"test-slot/{slot_definition_id}/{module_role}",
            "referenceModuleDefinitionId": None,
            "parametersMeters": None,
            "selectionBasis": "stable_datum_frame_without_registered_role_station",
        },
    )
    monkeypatch.setattr(
        engineering_review_module,
        "_cross_base_module_station_consensus",
        lambda *args, **kwargs: None,
    )
    review = build_parameterized_datum_engineering_review(
        ROOT,
        allow_exact_module_native_station_demo_projection=True,
    )
    expected = {
        ("project02::A300", "project01::JJ00"): {
            "longitudinal": 0.08,
            "lateral": 0.39,
            "supportGap": 0.0,
        },
        ("project02::A500", "project01::JJ00"): {
            "longitudinal": 0.09,
            "lateral": 0.65,
            "supportGap": 0.018,
        },
        ("project02::A500", "project03::AA00"): {
            "longitudinal": 0.09,
            "lateral": 0.65,
            "supportGap": 0.018,
        },
        ("project02::A500", "project05::A000"): {
            "longitudinal": 0.09,
            "lateral": 0.65,
            "supportGap": 0.018,
        },
        ("project05::P000", "project01::JJ00"): {
            "longitudinal": 0.34512253526,
            "lateral": 1.036,
            "supportGap": 0.0,
        },
    }
    assert review["exactModuleNativeStationDemoProjectionEnabled"] is True
    for pair, parameters in expected.items():
        row = _decision(review, *pair)
        assert row["status"] == "recommendation_pending_engineering_confirmation"
        assert row["basis"] == (
            "exact_module_native_station_semantic_coordinate_projection_demo"
        )
        assert row["recommendedParametersMeters"] == parameters
        assert row["reference"]["referenceModuleDefinitionId"] == pair[0]
        assert row["reference"]["prototypePoseAllowedAsCadExecutionAuthority"] is False
        assert row["reference"]["semanticCoordinateValuesCopiedWithoutPrototypeTransform"] is True
        assert row["reference"]["mechanicallyUniqueStationProven"] is False
        assert row["reference"]["demoOnly"] is True
        assert row["confirmationTemplate"]["confirmed"] is False
    barrier = build_manual_input_barrier(review)
    assert barrier["status"] == "no_manual_input_barrier"
    assert barrier["pairCount"] == 0


def test_review_script_requires_explicit_flag_for_native_station_demo_projection(
    tmp_path: Path,
):
    output = tmp_path / "projection-review"
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/build_parameterized_datum_engineering_review.py"),
            "--output-dir",
            str(output),
            "--allow-exact-module-native-station-demo-projection",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    review = json.loads(
        (output / "engineering-review.json").read_text(encoding="utf-8")
    )
    assert review["exactModuleNativeStationDemoProjectionEnabled"] is True
    # All five exact pairs are now published in the authoritative workspace, so
    # a fresh review correctly contains no duplicate decisions. The unit test
    # above exercises the pre-publication opt-in projection behavior.
    assert review["decisionCount"] == 0
    assert review["decisions"] == []
    barrier = json.loads(
        (output / "manual-input-barrier.json").read_text(encoding="utf-8")
    )
    assert barrier["pairCount"] == 0


def test_review_script_writes_human_and_machine_readable_packet(tmp_path: Path):
    output = tmp_path / "review"
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/build_parameterized_datum_engineering_review.py"),
            "--output-dir",
            str(output),
            "--axis-candidate-limit",
            "3",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    review = json.loads(
        (output / "engineering-review.json").read_text(encoding="utf-8")
    )
    assert review["decisionCount"] == len(review["decisions"])
    assert (output / "README-CN.md").is_file()
    assert (output / "manual-input-barrier.json").is_file()
    assert (output / "MECHANICAL-INPUT-REQUIRED-CN.md").is_file()
    native_stations = json.loads(
        (output / "native-role-station-evidence.json").read_text(encoding="utf-8")
    )
    assert native_stations["schemaVersion"] == (
        "native-role-station-review-evidence/v1"
    )
    assert all(row["reviewOnly"] is True for row in native_stations["stations"])
    assert (output / "position-confirmation-template.json").is_file()
    assert (output / "axis-confirmation-template.json").is_file()
    assert (output / "axis-pair-confirmation-template.json").is_file()
    assert (output / "flexible-slot-confirmation-template.json").is_file()
    assert (output / "two-axis-native-station-evidence.json").is_file()
    assert (output / "following-batch-mixed-recommendations.json").is_file()
    assert (
        output / "following-batch-geometry-decision-request-template.json"
    ).is_file()
    assert (output / "FOLLOWING-BATCH-REVIEW-CN.md").is_file()
    position_language = json.loads(
        (output / "position-language-request-template.json").read_text(
            encoding="utf-8"
        )
    )
    assert len(position_language["requests"]) == review["positionDecisionCount"]
    assert all(row["confirmed"] is False for row in position_language["requests"])
    first_batch = json.loads(
        (output / "first-batch-position-recommendations.json").read_text(
            encoding="utf-8"
        )
    )
    assert first_batch["selectedRecommendationCount"] == min(
        8, first_batch["availableRecommendationCount"]
    )
    assert first_batch["deferredRecommendationCount"] == (
        first_batch["availableRecommendationCount"]
        - first_batch["selectedRecommendationCount"]
    )
    assert all(
        row["confirmationRequest"]["confirmed"] is False
        for row in first_batch["selected"]
    )
    first_batch_confirmation = json.loads(
        (output / "first-batch-position-confirmation-template.json").read_text(
            encoding="utf-8"
        )
    )
    assert len(first_batch_confirmation["requests"]) == first_batch[
        "selectedRecommendationCount"
    ]
    assert all(
        row["confirmed"] is False
        for row in first_batch_confirmation["requests"]
    )
    assert (output / "FIRST-BATCH-REVIEW-CN.md").is_file()
    mixed = json.loads(
        (output / "next-batch-mixed-recommendations.json").read_text(
            encoding="utf-8"
        )
    )
    assert mixed["selectedRecommendationCount"] <= mixed[
        "availableRecommendationCount"
    ]
    assert mixed["allRecommendationsUnconfirmed"] is True
    assert (output / "NEXT-BATCH-REVIEW-CN.md").is_file()
    next_positions = json.loads(
        (output / "next-batch-position-confirmation-template.json").read_text(
            encoding="utf-8"
        )
    )
    next_axes = json.loads(
        (output / "next-batch-axis-confirmation-template.json").read_text(
            encoding="utf-8"
        )
    )
    next_axis_pairs = json.loads(
        (output / "next-batch-axis-pair-confirmation-template.json").read_text(
            encoding="utf-8"
        )
    )
    next_flexible = json.loads(
        (output / "next-batch-flexible-slot-confirmation-template.json").read_text(
            encoding="utf-8"
        )
    )
    assert (
        len(next_positions["requests"])
        + len(next_axes["pairs"])
        + len(next_axis_pairs["pairs"])
        + len(next_flexible["pairs"])
        == mixed["selectedRecommendationCount"]
    )
    assert all(row["confirmed"] is False for row in next_positions["requests"])
    assert all(row["confirmed"] is False for row in next_axes["pairs"])
    recommended = json.loads(
        (output / "position-recommendation-acceptance-template.json").read_text(
            encoding="utf-8"
        )
    )
    manual = json.loads(
        (output / "position-manual-input-template.json").read_text(
            encoding="utf-8"
        )
    )
    assert recommended["templateSubset"] == "recommendation_acceptance_review"
    assert len(recommended["requests"]) == first_batch[
        "availableRecommendationCount"
    ]
    assert all(row["recommendationAvailable"] for row in recommended["requests"])
    assert all(row["confirmed"] is False for row in recommended["requests"])
    assert manual["templateSubset"] == "explicit_position_input_required"
    assert len(manual["requests"]) == (
        review["positionDecisionCount"]
        - first_batch["availableRecommendationCount"]
    )
    assert all(not row["recommendationAvailable"] for row in manual["requests"])
    assert all(row["confirmed"] is False for row in manual["requests"])
    assert (output / "A180-position-confirmation-template.json").is_file()
    assert (output / "F000-axis-confirmation-template.json").is_file()
