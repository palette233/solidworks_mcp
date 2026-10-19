import json
from pathlib import Path

import pytest

from demo_backend.cross_project_interface_triage import (
    CrossProjectInterfaceTriageError,
    build_adapter_requirement,
    build_blocked_substitution_disposition,
    build_incompatibility_triage,
)


ROOT = Path(__file__).resolve().parents[3]


def _matrix():
    return json.loads(
        (
            ROOT
            / "demo/cross_project_substitution/coverage-v1/"
            "cross_project_candidate_matrix.json"
        ).read_text(encoding="utf-8-sig")
    )


def test_active_incompatibilities_are_collapsed_and_classified():
    triage = build_incompatibility_triage(_matrix())

    assert triage["directionalIncompatibleCount"] == 66
    assert triage["undirectedPairCount"] == 33
    assert triage["classificationCounts"] == {
        "context_architecture_mismatch": 2,
        "known_pattern_mismatch_adapter_candidate": 3,
        "topology_mismatch_adapter_or_slot_redesign": 28,
    }
    assert all(row["directCombinationAllowed"] is False for row in triage["pairs"])
    assert triage["policy"]["adapterGeometryInvented"] is False


def test_scanner_pattern_mismatch_builds_fail_closed_adapter_requirement():
    triage = build_incompatibility_triage(_matrix())
    requirement = build_adapter_requirement(
        triage,
        source_project="project03",
        source_token="AI00",
        target_project="project01",
        target_token="SM00",
    )

    assert requirement["status"] == "engineering_geometry_required"
    assert requirement["moduleSide"]["locatingPairSpacingsMeters"] == [0.2]
    assert requirement["baseSide"]["locatingPairSpacingsMeters"] == [0.022]
    assert requirement["requiredArtifact"]["cadFilePath"] is None
    assert requirement["executionPolicy"] == {
        "directCadExecutionAllowed": False,
        "failClosedReason": "ADAPTER_GEOMETRY_NOT_AVAILABLE",
        "collisionOrBrepRequired": False,
    }


def test_topology_only_mismatch_cannot_be_promoted_to_adapter_automatically():
    triage = build_incompatibility_triage(_matrix())

    with pytest.raises(CrossProjectInterfaceTriageError, match="已量化定位图案"):
        build_adapter_requirement(
            triage,
            source_project="project03",
            source_token="AH00",
            target_project="project02",
            target_token="A500",
        )


def test_blocked_substitution_gets_actionable_fail_closed_disposition():
    report = {
        "status": "blocked",
        "blockers": [{"code": "LOCATING_FEATURE_SPACING_MISMATCH"}],
        "locatingFeatureGeometry": {
            "differences": [
                {
                    "roles": ["locating_hole_1", "locating_hole_2"],
                    "sourceDistanceMeters": 0.2,
                    "targetDistanceMeters": 0.022,
                    "absoluteDifferenceMeters": 0.178,
                }
            ]
        },
    }

    disposition = build_blocked_substitution_disposition(report)

    assert disposition["classification"] == (
        "known_pattern_mismatch_adapter_candidate"
    )
    assert disposition["cadLaunchDecision"] == "fail_closed_before_cad"
    assert disposition["knownLocatingDifferences"][0]["absoluteDifferenceMeters"] == 0.178
    assert len(disposition["requiredNextEvidence"]) == 3
