import json
from pathlib import Path

from demo_backend.project01_gn00_base_only_datum import (
    build_project01_gn00_base_only_datum_candidate,
)


ROOT = Path(__file__).resolve().parents[3]


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _build(**overrides) -> dict:
    arguments = {
        "native_endpoint_catalog": _json(
            ROOT
            / "demo/semantic_ports/project01_GN00_fourth_increment_v1/"
            "face_endpoint_catalog.json"
        ),
        "jj00_support_leaf_catalog": _json(
            ROOT
            / "demo/cross_project_substitution/scanner-slot-discovery-v1/"
            "project01_JJ00_project03_AI00/"
            "jj00-scanner-support-leaf-face-catalog.json"
        ),
        "gn00_anti_rotation_endpoint_id": "face:gn00:2a78145c441c9159",
        "jj00_primary_support_endpoint_id": "face:jj00:cf4e0ac0baf70ae1",
    }
    arguments.update(overrides)
    return build_project01_gn00_base_only_datum_candidate(**arguments)


def test_real_jj00_leaf_contains_a_stable_base_only_orientation_candidate():
    report = _build()

    assert report["status"] == (
        "base_only_orientation_datum_candidate_pending_mechanical_meaning_and_cad"
    )
    assert report["candidateCount"] > 0
    assert report["selectedCandidate"]["endpointId"] == (
        "face:jj00:e44c72a6880619cd"
    )
    assert report["proposedArchitecture"][
        "semanticTransportDependencyRemoved"
    ] is True
    assert report["cadLaunchAllowed"] is False


def test_base_only_datum_does_not_claim_direct_ag00_compatibility():
    report = _build()
    comparison = report["comparisonToProject03Ag00"]

    assert comparison["providerArchitectureNowComparable"] is True
    assert comparison["directMechanicalTopologyCompatible"] is False
    assert "MATE_TOPOLOGY_MISMATCH" in comparison["remainingBlockers"]
    assert report["directCrossProjectCompatibilityProven"] is False
    assert report["semanticPortPublished"] is False


def test_candidate_search_fails_closed_when_robust_face_area_is_unavailable():
    report = _build(minimum_face_area_square_meters=1.0)

    assert report["status"] == "blocked_no_jj00_orientation_datum_candidate"
    assert report["candidateCount"] == 0
    assert report["cadLaunchAllowed"] is False
