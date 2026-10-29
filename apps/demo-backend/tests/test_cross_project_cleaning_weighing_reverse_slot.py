import json
from pathlib import Path

from demo_backend.cross_project_cleaning_weighing_reverse_slot import (
    build_cleaning_weighing_reverse_slot_discovery,
)


ROOT = Path(__file__).resolve().parents[3]
CATALOG = ROOT / (
    "demo/cross_project_substitution/scanner-slot-discovery-v1/"
    "project01_JJ00_project03_AI00/jj00-scanner-support-leaf-face-catalog.json"
)


def _build():
    return build_cleaning_weighing_reverse_slot_discovery(
        target_leaf_catalog=json.loads(CATALOG.read_text(encoding="utf-8-sig"))
    )


def test_project01_bounded_leaf_has_no_170mm_slot_inside_engineering_tolerance():
    report = _build()

    assert report["status"] == "no_strict_slot_relaxed_near_match_rejected"
    assert report["strictCandidateCount"] == 0
    assert report["captureScope"]["wholeAssemblyBlindScanPerformed"] is False


def test_relaxed_near_match_is_reported_but_never_promoted():
    report = _build()
    candidate = report["relaxedNearMatches"][0]

    assert report["relaxedNearMatchCount"] == 1
    assert candidate["axisSpacingMeters"] == 0.17023806859806798
    assert candidate["locatingRadiusMeters"] == 0.006
    assert report["toleranceRelaxationAccepted"] is False
    assert report["semanticPortPublished"] is False
    assert report["cadLaunchAllowed"] is False
