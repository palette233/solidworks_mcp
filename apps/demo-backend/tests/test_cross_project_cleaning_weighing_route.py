import json
from pathlib import Path

from demo_backend.cross_project_cleaning_weighing_route import (
    build_cross_project_cleaning_weighing_route,
)


ROOT = Path(__file__).resolve().parents[3]
GN00 = ROOT / (
    "demo/cross_project_substitution/cleaning-weighing-base-only-v1/"
    "project01_GN00_project03_AG00/two-hole-candidate-v1"
)
AG00 = ROOT / "demo/global_assembly_catalog/coverage-v2/ag00-three-datum-candidate-v1"


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _build():
    return build_cross_project_cleaning_weighing_route(
        gn00_summary=_read(GN00 / "candidate_summary.json"),
        gn00_checkpoint=_read(
            GN00 / "project01_GN00_base_only_two_hole_checkpoint_v1.result.json"
        ),
        gn00_release_manifest=_read(
            ROOT
            / "demo/global_assembly_catalog/releases/"
            "relation-v65-project01-gn00-base-only-two-hole-driving-20261022/"
            "release-manifest.json"
        ),
        ag00_summary=_read(AG00 / "candidate_summary.json"),
        ag00_checkpoint=_read(
            AG00 / "project03_AG00_three_datum_checkpoint_v2.result.json"
        ),
        ag00_release_manifest=_read(
            ROOT
            / "demo/global_assembly_catalog/releases/"
            "relation-v54-project03-ag00-three-datum-driving-20261014/"
            "release-manifest.json"
        ),
    )


def test_native_ports_are_individually_valid_but_cross_slot_spacing_mismatches():
    report = _build()

    assert report["source"]["nativePortCadValidated"] is True
    assert report["target"]["nativePortCadValidated"] is True
    assert report["interfaceComparison"]["topologyMatches"] is True
    assert report["interfaceComparison"]["spacingDifferenceMeters"] == 0.034
    assert report["interfaceComparison"]["locatingFeatureSpacingMatches"] is False
    assert report["nativeSlotCompatible"] is False
    assert report["nativeSlotBlocker"] == "LOCATING_FEATURE_SPACING_MISMATCH"


def test_spacing_mismatch_fails_closed_before_cross_project_cad():
    report = _build()

    assert report["status"] == "alternate_slot_required_spacing_mismatch"
    assert report["cadLaunchAllowed"] is False
    assert report["crossProjectCadValidated"] is False
    assert report["semanticPortPublished"] is False
    assert report["prototypePoseUsedAtRuntime"] is False
    assert report["nextAction"] == (
        "search-project03-base-for-204mm-slot-or-project01-base-for-170mm-slot"
    )
