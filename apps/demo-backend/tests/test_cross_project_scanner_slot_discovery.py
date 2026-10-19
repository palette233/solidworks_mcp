from __future__ import annotations

import json
from pathlib import Path

import pytest

from demo_backend.cross_project_scanner_slot_discovery import (
    CrossProjectScannerSlotDiscoveryError,
    build_scanner_slot_discovery,
)


ROOT = Path(__file__).resolve().parents[3]
MATRIX = (
    ROOT
    / "demo/cross_project_substitution/coverage-v1/"
    "cross_project_candidate_matrix.json"
)
CATALOG = (
    ROOT
    / "demo/cross_project_substitution/scanner-slot-discovery-v1/"
    "project03_AA00_project01_SM00/"
    "aa00-scanner-support-leaf-face-catalog.json"
)
LEAF = (
    "FL9A24D063AA10.001-1/FL9A24D063AA11.001-1/"
    "FL5A24D063AA11002.02-1"
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _build(**overrides):
    args = {
        "source_project": "project01",
        "source_token": "SM00",
        "target_project": "project03",
        "target_token": "AI00",
        "target_leaf_hierarchy_path": LEAF,
    }
    args.update(overrides)
    return build_scanner_slot_discovery(_read(MATRIX), _read(CATALOG), **args)


def test_native_support_leaf_near_pattern_is_not_direct_slot():
    report = _build(native_slot_center_local=[-0.462, 0.078, 0.00615])

    assert report["status"] == (
        "near_geometry_found_but_direct_installation_incompatible"
    )
    assert report["directCandidateCount"] == 0
    assert report["nearCandidateCount"] == 1
    candidate = report["candidates"][0]
    assert candidate["axisSpacingMeters"] == pytest.approx(0.022360679775)
    assert candidate["spacingResidualMeters"] == pytest.approx(0.000360679775)
    assert candidate["directFit"] is False
    assert report["engineeringDisposition"]["cadInsertionAllowed"] is False
    assert report["engineeringDisposition"]["project06Included"] is False


def test_result_is_deterministic():
    assert _build()["discoveryDigest"] == _build()["discoveryDigest"]


def test_reverse_direction_selects_closest_exact_200_mm_pattern():
    catalog = _read(
        ROOT
        / "demo/cross_project_substitution/scanner-slot-discovery-v1/"
        "project01_JJ00_project03_AI00/"
        "jj00-scanner-support-leaf-face-catalog.json"
    )
    report = build_scanner_slot_discovery(
        _read(MATRIX),
        catalog,
        source_project="project03",
        source_token="AI00",
        target_project="project01",
        target_token="SM00",
        target_leaf_hierarchy_path=(
            "FL9C24N074JA00.001-1/FL9C24N074JA10.001-1/"
            "FL5C24N074JA20001.01-1"
        ),
        native_slot_center_local=[-0.2915, 0.107, 0.01],
    )

    assert report["directCandidateCount"] == 6
    assert report["nearCandidateCount"] == 0
    assert report["selectedCandidate"]["locatingEndpointIds"] == [
        "face:jj00:c2da3af915900469",
        "face:jj00:ec5c90215b8a0fa3",
    ]
    assert report["selectedCandidate"]["nativeStationDisplacementMeters"] == (
        pytest.approx(0.349715598737)
    )
    assert report["engineeringDisposition"]["cadInsertionAllowed"] is False


def test_wrong_role_direction_fails_closed():
    with pytest.raises(CrossProjectScannerSlotDiscoveryError):
        _build(source_token="BD00", target_token="AH00")


def test_direct_tolerance_cannot_exceed_discovery_tolerance():
    with pytest.raises(CrossProjectScannerSlotDiscoveryError):
        _build(
            discovery_tolerance_meters=1e-6,
            direct_compatibility_tolerance_meters=0.0005,
        )
