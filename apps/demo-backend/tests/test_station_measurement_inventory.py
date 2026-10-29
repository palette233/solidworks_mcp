import json
from pathlib import Path

import pytest

from demo_backend.station_measurement_inventory import (
    merge_native_role_station_measurements,
)


ROOT = Path(__file__).resolve().parents[3]
NATIVE = (
    ROOT
    / "demo/cross_project_substitution/parameterized-datum-placement-v1"
    / "engineering-decision-review-20261026-v75-zero-pending"
    / "native-role-station-evidence.json"
)


def test_native_station_inventory_merge_is_generic_and_preserves_boundaries():
    result = merge_native_role_station_measurements(
        ROOT,
        ROOT / "data/assembly_stations/measurement-reuse-index-v4.json",
        NATIVE,
    )
    assert result["generation"]["addedNativeStationCount"] == 7
    assert result["generation"]["cadExecuted"] is False
    rows = {
        (row["targetBaseDefinitionId"], row["role"], row["nativeRoleModuleDefinitionId"]): row
        for row in result["entries"]
    }
    transport = rows[("project01::JJ00", "Transport", "project01::SS00")]
    assert transport["nativeStationParametersMeters"] == {
        "longitudinal": 0.101,
        "lateral": 0.0185,
        "supportGap": 0.0,
    }
    assert any(value.startswith("bind_") for value in transport["stillRequired"])
    assert "prototype-pose execution authority" in transport["boundary"]
    assert all(Path(ROOT / path).is_file() for path in transport["paths"])


def test_existing_detailed_measurement_is_not_duplicated():
    result = merge_native_role_station_measurements(
        ROOT,
        ROOT / "data/assembly_stations/measurement-reuse-index-v4.json",
        NATIVE,
    )
    rows = [row for row in result["entries"]
            if row["targetBaseDefinitionId"] == "project02::A600"
            and row["role"] == "WasteCup"
            and row["nativeRoleModuleDefinitionId"] == "project02::A300"]
    assert len(rows) == 1
    assert "two_A300_cup_mouth_points_and_opening_directions" in rows[0]["available"]


def test_changed_native_execution_boundary_fails_closed(tmp_path):
    payload = json.loads(NATIVE.read_text(encoding="utf-8-sig"))
    row = next(
        value for value in payload["stations"]
        if value["moduleDefinitionId"] == "project01::GN00"
    )
    row["prototypePoseAllowedAsCadExecutionAuthority"] = True
    changed = tmp_path / "native.json"
    changed.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="execution boundary changed"):
        merge_native_role_station_measurements(
            ROOT,
            ROOT / "data/assembly_stations/measurement-reuse-index-v4.json",
            changed,
        )
