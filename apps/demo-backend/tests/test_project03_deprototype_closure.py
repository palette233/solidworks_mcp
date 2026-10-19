from __future__ import annotations

import copy
import json
from pathlib import Path

from demo_backend.project03_deprototype_closure import (
    build_project03_deprototype_closure,
)


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "demo/semantic_ports/project03_deprototype_ablation_v1"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def build(ag_result: dict | None = None) -> dict:
    return build_project03_deprototype_closure(
        load(EVIDENCE / "project03_pose_anchor_ablation.json"),
        ROOT / "demo/semantic_ports/project03_calibrated_parameters_v1.json",
        ag_result or load(EVIDENCE / "live-cad/step04_AG00_calibrated_v2.result.json"),
        load(EVIDENCE / "live-cad/step07a_AB00_calibrated_v2.result.json"),
    )


def test_live_cad_closure_passes_but_keeps_production_blocked() -> None:
    closure = build()
    assert closure["status"] == "PROJECT03_RUNTIME_POSE_DEPENDENCY_REDUCED_CAD_VALIDATED"
    assert closure["runtimePrototypeTopLevelPoseReadRequired"] is False
    assert closure["productionReady"] is False
    assert closure["cadGates"]["AG00"]["success"] is True
    assert closure["cadGates"]["AB00"]["success"] is True
    assert closure["ab00DistanceValidationGate"] is True


def test_closure_rejects_reopen_failure() -> None:
    result = copy.deepcopy(load(EVIDENCE / "live-cad/step04_AG00_calibrated_v2.result.json"))
    result["toolResult"]["Reopened"] = False
    closure = build(result)
    assert closure["success"] is False
    assert closure["cadGates"]["AG00"]["checks"]["reopened"] is False
