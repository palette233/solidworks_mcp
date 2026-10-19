from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from demo_backend.project03_dynamic_sweep import build_project03_ad00_dynamic_sweep


ROOT = Path(__file__).resolve().parents[3]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def build(parameters: dict | None = None) -> dict:
    return build_project03_ad00_dynamic_sweep(
        load(ROOT / "demo/layout_previews/project03_work_positions.json"),
        load(ROOT / "demo/layout_previews/project03_first_stage_geometry.json"),
        load(ROOT / "demo/layout_previews/project03_module_occupancy.json"),
        parameters or load(ROOT / "demo/semantic_ports/project03_dynamic_estimates_v1.json"),
    )


def test_real_project03_builds_two_conservative_sweeps() -> None:
    result = build()
    assert result["success"] is True
    assert result["angleDegrees"] == 25.0
    assert len(result["workPositionSweeps"]) == 2
    assert all(row["sampleCount"] == 51 for row in result["workPositionSweeps"])
    assert result["engineeringConfirmed"] is False
    assert result["productionDynamicReady"] is False
    for row in result["workPositionSweeps"]:
        static = row["staticBoundsInstallationMeters"]
        swept = row["sweepBoundsInstallationMeters"]
        assert swept["minU"] <= static["minU"] and swept["maxU"] >= static["maxU"]
        assert swept["minV"] < static["minV"] and swept["maxV"] > static["maxV"]
        assert swept["minN"] <= static["minN"] and swept["maxN"] >= static["maxN"]


def test_invalid_angle_is_rejected() -> None:
    parameters = copy.deepcopy(load(ROOT / "demo/semantic_ports/project03_dynamic_estimates_v1.json"))
    parameters["ad00Flip"]["angleDegrees"] = 0.0
    with pytest.raises(ValueError, match="angle"):
        build(parameters)
