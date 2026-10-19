from __future__ import annotations

from demo_backend.project05_glue_supply import build_project05_glue_supply_scope


def test_unmapped_glue_supply_is_explicitly_external_to_coarse_top3() -> None:
    manifest = {"projects": [{
        "projectId": "05",
        "modules": [{"cadId": None, "capabilities": ["glue_supply"], "confidence": "pending"}],
    }]}
    result = build_project05_glue_supply_scope(manifest)
    assert result["scopeDecision"]["partOfNineObjectTop3Solve"] is False
    assert result["releaseDecision"]["coarseNineObjectLayoutMayProceed"] is True
    assert result["releaseDecision"]["fullMachineProductionReleaseMayProceed"] is False
