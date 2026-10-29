import json
from pathlib import Path


from demo_backend.native_role_station_evidence import (
    build_native_role_station_evidence,
    index_native_role_stations,
)
from demo_backend.parameterized_datum_engineering_review import (
    build_parameterized_datum_engineering_review,
    build_prioritized_mixed_recommendation_batch,
)


ROOT = Path(__file__).resolve().parents[3]
PRE_PUBLICATION_REVIEW = (
    ROOT
    / "demo/cross_project_substitution/parameterized-datum-placement-v1"
    / "engineering-decision-review-20261026-v47/engineering-review.json"
)


def _pre_publication_review() -> dict:
    return json.loads(PRE_PUBLICATION_REVIEW.read_text(encoding="utf-8-sig"))


def _decision(review: dict, module: str, slot: str) -> dict:
    return next(
        row
        for row in review["decisions"]
        if row["moduleDefinitionId"] == module
        and row["slotDefinitionId"] == slot
    )


def test_native_station_evidence_reproduces_registered_station_measurements():
    evidence = build_native_role_station_evidence(ROOT)
    stations = {
        (row["moduleDefinitionId"], row["baseDefinitionId"]): row
        for row in evidence["stations"]
    }

    assert evidence["schemaVersion"] == "native-role-station-review-evidence/v1"
    assert evidence["summary"] == {
        "stationCount": 13,
        "baseCount": 4,
        "roleCount": 5,
    }
    assert stations[("project01::SM00", "project01::JJ00")][
        "parametersMeters"
    ] == {"longitudinal": 0.07, "lateral": 0.102, "supportGap": 0.0}
    assert stations[("project03::AG00", "project03::AA00")][
        "parametersMeters"
    ] == {"longitudinal": 0.54, "lateral": 0.2385, "supportGap": 0.0}
    assert stations[("project02::A800", "project02::A600")][
        "parametersMeters"
    ] == {"longitudinal": 0.3095, "lateral": 1.59, "supportGap": 0.0}
    p000 = stations[("project05::P000", "project05::A000")]
    assert p000["parametersMeters"] == {
        "longitudinal": 0.34512253526,
        "lateral": 1.036,
        "supportGap": 0.0,
    }
    assert p000["moduleCoordinateBridge"]["matchedPersistentRoles"] == [
        "lateral_datum",
        "support_datum",
    ]
    assert p000["moduleCoordinateBridge"]["derivedSameLeafRoles"] == [
        "longitudinal_datum"
    ]
    assert p000["moduleCoordinateBridge"][
        "prototypeTransformUsedForCadExecution"
    ] is False
    assert all(row["reviewOnly"] is True for row in evidence["stations"])
    assert all(
        row["prototypePoseUsedForMeasurement"] is True
        and row["prototypePoseAllowedAsCadExecutionAuthority"] is False
        for row in evidence["stations"]
    )
    assert len(index_native_role_stations(evidence)) == 13


def test_p000_native_station_recommends_a300_a000_but_not_execution_authority():
    review = _pre_publication_review()
    decision = _decision(review, "project02::A300", "project05::A000")

    assert decision["status"] == "recommendation_pending_engineering_confirmation"
    assert decision["basis"] == "prototype_native_role_station_projection"
    assert decision["recommendedParametersMeters"] == {
        "longitudinal": 0.34512253526,
        "lateral": 1.036,
        "supportGap": 0.0,
    }
    assert decision["confirmationTemplate"]["confirmed"] is False
    assert decision["reference"][
        "prototypePoseAllowedAsCadExecutionAuthority"
    ] is False
    native = decision["reference"]["nativeStationEvidence"]
    assert native["moduleDefinitionId"] == "project05::P000"
    assert native["moduleCoordinateBridge"]["reviewOnly"] is True


def test_transport_gaps_gain_unconfirmed_target_native_station_recommendations():
    review = _pre_publication_review()
    expected = {
        ("project01::SS00", "project02::A600"): {
            "longitudinal": 0.3095,
            "lateral": 1.59,
            "supportGap": 0.0,
        },
        ("project02::A800", "project01::JJ00"): {
            "longitudinal": 0.101,
            "lateral": 0.0185,
            "supportGap": 0.0,
        },
        ("project02::A800", "project05::A000"): {
            "longitudinal": 0.092,
            "lateral": 1.3635,
            "supportGap": 0.0,
        },
        ("project05::D000", "project03::AA00"): {
            "longitudinal": 0.101,
            "lateral": 0.0185,
            "supportGap": 0.0,
        },
    }
    for pair, parameters in expected.items():
        decision = _decision(review, *pair)
        assert decision["status"] == (
            "recommendation_pending_engineering_confirmation"
        )
        assert decision["basis"] == "prototype_native_role_station_projection"
        assert decision["recommendedParametersMeters"] == parameters
        assert decision["confirmationTemplate"]["confirmed"] is False
        assert decision["reference"][
            "prototypePoseAllowedAsCadExecutionAuthority"
        ] is False


def test_a600_scanner_prefers_same_project_native_station_over_cross_project_presets():
    # Use the immutable pre-publication packet: the live pair is now released
    # and therefore correctly disappears from the current decision queue.
    review = _pre_publication_review()
    decision = _decision(review, "project05::F000", "project02::A600")

    assert decision["status"] == "recommendation_pending_engineering_confirmation"
    assert decision["basis"] == (
        "nearest_stable_axis_to_target_base_native_scanner_station"
    )
    assert decision["reference"]["referenceModuleDefinitionId"] == (
        "project02::A180"
    )
    assert decision["requestedPositionMeters"] == {
        "longitudinal": 0.37475,
        "lateral": 1.328,
    }
    assert decision["recommendedAxisEndpointId"]
    assert decision["confirmationTemplate"]["confirmed"] is False


def test_native_station_recommendations_enter_review_batch_but_not_execution():
    review = _pre_publication_review()
    batch = build_prioritized_mixed_recommendation_batch(review, limit=8)

    assert batch["status"] == "ready_for_engineering_review"
    assert batch["selectedRecommendationCount"] == 8
    assert all(
        row["confirmationTemplate"]["confirmed"] is False
        for row in batch["selected"]
    )
    assert any(
        row["evidenceClass"]
        == "prototype_native_role_station_review_evidence"
        for row in batch["selected"]
    )
