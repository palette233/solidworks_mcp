from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from demo_backend.native_service_semantic_binding import (
    build_native_service_semantic_binding_report,
)


ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "data/assembly_stations/gn00-jj00-native-service-binding-v1.json"


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_real_gn00_native_service_identity_binding() -> None:
    report = build_native_service_semantic_binding_report(ROOT, read(CONFIG))
    assert report["schemaVersion"] == "station-candidate-extension-report/v1"
    assert report["summary"] == {"candidateCount": 1, "identityBindingReadyCount": 1}
    row = report["candidates"][0]
    assert row["sourceModuleDefinitionId"] == "project01::GN00"
    assert row["targetBaseDefinitionId"] == "project01::JJ00"
    assert row["status"] == (
        "native_service_identity_binding_ready_for_station_rule_and_readonly_postcheck"
    )
    assert row["capabilityCoverage"]["passed"] is True
    assert row["cadLaunchAllowed"] is False
    assert set(row["serviceSubtreeMapping"]) == {"FJ00", "GN10", "GN20", "GN30"}


def test_native_service_binding_rejects_nonidentity_role() -> None:
    config = read(CONFIG)
    config["entries"][0]["nativeRoleModuleDefinitionId"] = "project03::AG00"
    with pytest.raises(ValueError, match="same source/native role"):
        build_native_service_semantic_binding_report(ROOT, config)


def test_native_service_binding_rejects_incomplete_subtree_partition() -> None:
    config = read(CONFIG)
    config["entries"][0]["serviceSubtrees"] = ["FJ00", "GN10"]
    with pytest.raises(ValueError, match="partition"):
        build_native_service_semantic_binding_report(ROOT, config)
