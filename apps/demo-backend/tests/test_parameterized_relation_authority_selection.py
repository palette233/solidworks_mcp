from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))
sys.path.insert(0, str(ROOT / "scripts"))

from run_parameterized_datum_validation_queue import (  # noqa: E402
    _require_exact_parameterized_authority,
)


PAIR = {
    "moduleDefinitionId": "project03::AE00",
    "slotDefinitionId": "project03::AA00",
}
RELATION = {
    "releaseManifestPath": "releases/new-datum/release-manifest.json",
}


def test_exact_datum_authority_matches_validated_release():
    authority = {
        "ready": True,
        **PAIR,
        "selectedMode": "parameterized_datum_placement",
        "relationExecutionMode": "datum_placement_demo",
        "releaseManifestPath": RELATION["releaseManifestPath"],
    }

    _require_exact_parameterized_authority(authority, RELATION, PAIR)


def test_preferred_native_release_cannot_masquerade_as_new_datum_authority():
    authority = {
        "ready": True,
        **PAIR,
        "selectedMode": "mechanical_interface",
        "relationExecutionMode": "direct_installation",
        "releaseManifestPath": "releases/old-native/release-manifest.json",
    }

    with pytest.raises(RuntimeError, match="not the authority selected"):
        _require_exact_parameterized_authority(authority, RELATION, PAIR)
