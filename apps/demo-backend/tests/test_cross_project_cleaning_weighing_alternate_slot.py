import json
from pathlib import Path

from demo_backend.cross_project_cleaning_weighing_alternate_slot import (
    build_cleaning_weighing_alternate_slot_discovery,
)


ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / (
    "demo/cross_project_substitution/cleaning-weighing-base-only-v1/"
    "project01_GN00_project03_AG00"
)


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _build():
    return build_cleaning_weighing_alternate_slot_discovery(
        route_report=_read(PACKAGE / "cleaning_weighing_cross_project_route.json"),
        target_leaf_catalog=_read(
            ROOT
            / "demo/global_assembly_catalog/coverage-v2/"
            "ag00-datum-discovery-v1/aa00_ag00_mount_leaf_faces.json"
        ),
        native_primary_target_endpoint_id=(
            "face:fl9a24d063aa00:81af5e2652843d2e"
        ),
        native_secondary_target_endpoint_id=(
            "face:fl9a24d063aa00:9218e31bdc9fd1db"
        ),
    )


def test_bounded_project03_leaf_contains_two_exact_204mm_candidates():
    report = _build()

    assert report["status"] == (
        "alternate_slot_geometry_found_pending_mechanical_review"
    )
    assert report["captureScope"]["wholeAssemblyBlindScanPerformed"] is False
    assert report["candidateCount"] == 2
    assert report["exactSpacingCandidateCount"] == 2
    assert all(row["directSpacingFit"] is True for row in report["candidates"])
    assert all(row["locatingRadiusMeters"] == 0.005 for row in report["candidates"])


def test_candidates_remain_blocked_before_mechanical_meaning_and_cad():
    report = _build()
    preferred = report["preferredForMechanicalReview"]

    assert preferred["distanceFromNativeAg00SlotMeters"] == 0.551576377304
    assert preferred["mechanicalMeaningConfirmed"] is False
    assert report["nativeSlotCompatible"] is False
    assert report["cadLaunchAllowed"] is False
    assert report["cadValidated"] is False
    assert report["semanticPortPublished"] is False
    assert len(report["mechanicalReviewRequired"]) == 4
