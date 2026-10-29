import copy
import json
from pathlib import Path

import pytest

from demo_backend.mechanical_interface_contracts import MechanicalInterfaceContractError
from demo_backend.parameterized_datum_engineering_review import (
    build_parameterized_datum_engineering_review,
    build_prioritized_mixed_recommendation_batch,
)
from demo_backend.parameterized_datum_position_decisions import (
    REQUEST_SCHEMA,
    build_prioritized_position_recommendation_batch,
    build_priority_batch_confirmation_template,
    build_position_decision_request_template,
    compile_position_decision_requests,
)
from demo_backend.parameterized_datum_validation_queue import (
    build_parameterized_datum_validation_queue,
)


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
FINAL_FIVE_REVIEW = (
    ROOT
    / "demo/cross_project_substitution/parameterized-datum-placement-v1"
    / "engineering-decision-review-20261026-v66-final-five/engineering-review.json"
)


def _historical_review():
    return json.loads(HISTORICAL_REVIEW.read_text(encoding="utf-8-sig"))


def _request(pair, *, action, instruction=None):
    return {
        "moduleDefinitionId": pair[0],
        "slotDefinitionId": pair[1],
        "action": action,
        "positionInstruction": instruction,
        "confirmed": True,
        "source": "mechanical-engineer-review",
        "confirmedBy": "test-engineer",
        "confirmedAt": "2026-10-26T05:00:00+08:00",
    }


def _requests(review, rows):
    return {
        "schemaVersion": REQUEST_SCHEMA,
        "sourceReviewDigest": review["reviewDigest"],
        "requests": rows,
    }


def test_template_covers_all_position_decisions_without_confirming_anything():
    review = build_parameterized_datum_engineering_review(ROOT)
    template = build_position_decision_request_template(review)
    assert len(template["requests"]) == review["positionDecisionCount"]
    assert all(row["confirmed"] is False for row in template["requests"])
    assert sum(
        row["recommendationAvailable"] for row in template["requests"]
    ) == sum(
        decision.get("recommendedParametersMeters") is not None
        for decision in review["decisions"]
        if decision["decisionKind"] == "position_parameters"
    )


def test_priority_batch_selects_all_remaining_strong_recommendations_without_confirmation():
    review = _historical_review()
    batch = build_prioritized_position_recommendation_batch(review)
    assert batch["availableRecommendationCount"] == 3
    assert batch["selectedRecommendationCount"] == 3
    assert batch["deferredRecommendationCount"] == 0
    assert all(
        row["confirmationRequest"]["confirmed"] is False
        for row in batch["selected"]
    )
    assert [
        (row["moduleDefinitionId"], row["slotDefinitionId"])
        for row in batch["selected"][:3]
    ] == [
        ("project02::A180", "project05::A000"),
        ("project03::AI00", "project05::A000"),
        ("project05::N000", "project02::A600"),
    ]


def test_priority_batch_is_bounded_and_rejects_stale_review():
    review = _historical_review()
    with pytest.raises(MechanicalInterfaceContractError, match="between 5 and 8"):
        build_prioritized_position_recommendation_batch(review, limit=4)
    with pytest.raises(MechanicalInterfaceContractError, match="between 5 and 8"):
        build_prioritized_position_recommendation_batch(review, limit=9)
    stale = copy.deepcopy(review)
    stale["decisions"][0]["status"] = "tampered"
    with pytest.raises(MechanicalInterfaceContractError, match="review digest mismatch"):
        build_prioritized_position_recommendation_batch(stale)


def test_priority_batch_confirmation_template_remains_unconfirmed_and_bound():
    review = _historical_review()
    batch = build_prioritized_position_recommendation_batch(review)
    template = build_priority_batch_confirmation_template(batch)
    assert template["schemaVersion"] == REQUEST_SCHEMA
    assert template["sourceReviewDigest"] == review["reviewDigest"]
    assert len(template["requests"]) == 3
    assert all(row["confirmed"] is False for row in template["requests"])
    tampered = copy.deepcopy(batch)
    tampered["selected"][0]["recommendedParametersMeters"]["lateral"] += 1
    with pytest.raises(MechanicalInterfaceContractError, match="batch digest mismatch"):
        build_priority_batch_confirmation_template(tampered)


def test_accept_recommendation_compiles_exact_pair_evidence():
    review = _historical_review()
    pair = ("project02::A180", "project05::A000")
    packet = compile_position_decision_requests(
        review,
        _requests(review, [_request(pair, action="accept_recommendation")]),
    )
    assert packet["confirmedPairCount"] == 1
    assert packet["pairs"][0]["parametersMeters"] == {
        "longitudinal": 0.07,
        "lateral": 0.102,
        "supportGap": 0.0,
    }
    assert packet["pairs"][0]["evidenceBasis"] == "accepted_review_recommendation"


def test_all_review_recommendations_compile_to_exact_cad_candidates_only():
    review = _historical_review()
    template = build_position_decision_request_template(review)
    recommendation_pairs = [
        (row["moduleDefinitionId"], row["slotDefinitionId"])
        for row in template["requests"]
        if row["recommendationAvailable"]
    ]
    packet = compile_position_decision_requests(
        review,
        _requests(
            review,
            [
                _request(pair, action="accept_recommendation")
                for pair in recommendation_pairs
            ],
        ),
    )
    assert packet["confirmedPairCount"] == len(recommendation_pairs) == 3
    evidence = {
        (row["moduleDefinitionId"], row["slotDefinitionId"]): {
            key: value
            for key, value in row.items()
            if key not in {"moduleDefinitionId", "slotDefinitionId"}
        }
        for row in packet["pairs"]
    }
    queue = build_parameterized_datum_validation_queue(
        ROOT, explicit_position_parameters=evidence
    )
    queue_by_pair = {
        (row["moduleDefinitionId"], row["slotDefinitionId"]): row
        for row in queue["pairs"]
    }
    # The historical N000->A600 release was later proven to place the module
    # outside A600's finite platform.  Its recommendation remains a valid
    # engineering input, but the revoked release must not be silently reused.
    # A later system-level review proved that the corrected finite-support pose
    # still overlaps the transport occupancy region.  Both the immutable
    # release and the identical 465/712.5 mm recipe must therefore fail closed.
    assert queue_by_pair[("project02::A180", "project05::A000")]["state"] == "released"
    assert queue_by_pair[("project03::AI00", "project05::A000")]["state"] == "released"
    repaired = queue_by_pair[("project05::N000", "project02::A600")]
    assert repaired["state"] == "blocked_before_cad"
    assert repaired["readyForReleasedCadExecution"] is False
    assert repaired["readyForCadValidation"] is False
    assert repaired["candidateReuseBlocked"] is True
    assert repaired["blocker"]["code"] == "TRANSPORT_OCCUPANCY_REGION_OVERLAP"
    # Two safe recommendations are confirmed; the unsafe N000 recipe remains
    # traceable in the blocked row but is deliberately excluded from the
    # executable confirmed-parameter count.
    assert queue["summary"]["confirmedExplicitPositionParameterCount"] == 2


def test_confirmed_third_batch_positions_are_now_exact_released_pairs():
    review = json.loads(THIRD_BATCH_REVIEW.read_text(encoding="utf-8-sig"))
    batch = build_prioritized_mixed_recommendation_batch(review, limit=8)
    assert len(batch["selected"]) == 8
    assert all(row["decisionKind"] == "position_parameters" for row in batch["selected"])
    pair_order = [
        (row["moduleDefinitionId"], row["slotDefinitionId"])
        for row in batch["selected"]
    ]
    packet = compile_position_decision_requests(
        review,
        _requests(
            review,
            [
                _request(pair, action="accept_recommendation")
                for pair in pair_order
            ],
        ),
    )
    evidence = {
        (row["moduleDefinitionId"], row["slotDefinitionId"]): {
            key: value
            for key, value in row.items()
            if key not in {"moduleDefinitionId", "slotDefinitionId"}
        }
        for row in packet["pairs"]
    }
    queue = build_parameterized_datum_validation_queue(
        ROOT, explicit_position_parameters=evidence
    )
    selected = {
        (row["moduleDefinitionId"], row["slotDefinitionId"]): row
        for row in queue["pairs"]
        if (row["moduleDefinitionId"], row["slotDefinitionId"]) in evidence
    }
    assert set(selected) == set(pair_order)
    assert all(row["state"] == "released" for row in selected.values())
    assert all(
        row["readyForReleasedCadExecution"] is True
        and row["nextAction"] == "reuse_released_pair"
        for row in selected.values()
    )


def test_semantic_position_instruction_can_create_explicit_release_supersession_candidate():
    review = json.loads(FINAL_FIVE_REVIEW.read_text(encoding="utf-8-sig"))
    pair = ("project02::A500", "project01::JJ00")
    packet = compile_position_decision_requests(
        review,
        _requests(
            review,
            [
                _request(
                    pair,
                    action="provide_position_instruction",
                    instruction=(
                        "基座纵向350毫米，基座横向240毫米，支承间隙0毫米。"
                    ),
                )
            ],
        ),
    )
    evidence = {
        (row["moduleDefinitionId"], row["slotDefinitionId"]): {
            key: value
            for key, value in row.items()
            if key not in {"moduleDefinitionId", "slotDefinitionId"}
        }
        for row in packet["pairs"]
    }
    queue = build_parameterized_datum_validation_queue(
        ROOT, explicit_position_parameters=evidence
    )
    promoted = next(
        row
        for row in queue["pairs"]
        if (row["moduleDefinitionId"], row["slotDefinitionId"]) == pair
    )
    assert packet["pairs"][0]["parametersMeters"] == {
        "longitudinal": 0.35,
        "lateral": 0.24,
        "supportGap": 0.0,
    }
    assert promoted["state"] == "ready_for_nonprototype_cad_validation"
    assert promoted["positionParametersOverride"] == {
        "longitudinal": 0.35,
        "lateral": 0.24,
        "supportGap": 0.0,
    }
    assert promoted["supersedesExistingPairRelease"] is True


def test_recommendation_cannot_be_accepted_when_review_has_none():
    review = json.loads(FINAL_FIVE_REVIEW.read_text(encoding="utf-8-sig"))
    pair = ("project02::A500", "project01::JJ00")
    with pytest.raises(MechanicalInterfaceContractError, match="no recommendation"):
        compile_position_decision_requests(
            review,
            _requests(review, [_request(pair, action="accept_recommendation")]),
        )


def test_requests_fail_closed_on_duplicate_unconfirmed_or_stale_review():
    review = _historical_review()
    pair = ("project02::A180", "project05::A000")
    row = _request(pair, action="accept_recommendation")
    with pytest.raises(MechanicalInterfaceContractError, match="duplicated"):
        compile_position_decision_requests(
            review, _requests(review, [row, copy.deepcopy(row)])
        )
    unconfirmed = copy.deepcopy(row)
    unconfirmed["confirmed"] = False
    with pytest.raises(MechanicalInterfaceContractError, match="not explicitly confirmed"):
        compile_position_decision_requests(
            review, _requests(review, [unconfirmed])
        )
    stale = copy.deepcopy(review)
    stale["decisions"][0]["status"] = "tampered"
    with pytest.raises(MechanicalInterfaceContractError, match="review digest mismatch"):
        compile_position_decision_requests(stale, _requests(review, [row]))
