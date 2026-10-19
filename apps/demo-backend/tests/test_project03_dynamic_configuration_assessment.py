from __future__ import annotations

import json
from pathlib import Path

from demo_backend.project03_dynamic_configuration_assessment import (
    assess_project03_dynamic_configuration_closure,
    default_baseline_path,
)


ROOT = Path(__file__).resolve().parents[3]
CLOSURE = ROOT / "demo/semantic_ports/project03_ad00_dynamic_configuration_closure_v4/project03_ad00_dynamic_configuration_closure.json"


def test_real_project03_dynamic_configuration_evidence_requires_full_context_recheck() -> None:
    result = assess_project03_dynamic_configuration_closure(
        json.loads(CLOSURE.read_text(encoding="utf-8-sig")),
        json.loads(default_baseline_path(ROOT).read_text(encoding="utf-8-sig")),
    )

    assert result["status"] == "PROJECT03_AD00_CONFIGURATION_STATES_VERIFIED_FULL_CONTEXT_BASELINE_RECHECK_REQUIRED"
    assert result["configurationSwitchVerified"] is True
    assert result["geometryStateChangeVerified"] is True
    assert result["nonAeCandidateGatePassed"] is True
    assert result["prototypeBaselineAd20AeBodyPairCount"] == 2
    assert result["productionReady"] is False
