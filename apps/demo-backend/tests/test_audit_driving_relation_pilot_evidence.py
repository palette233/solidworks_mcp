from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/audit_driving_relation_pilot_evidence.py"


def test_prior_project05_drive_is_audited_as_scoped_bundle_candidate(
    tmp_path, monkeypatch
):
    spec = importlib.util.spec_from_file_location(
        "audit_driving_relation_pilot_evidence", SCRIPT
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = tmp_path / "audit.json"
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--output", str(output)])

    assert module.main() == 0
    report = json.loads(output.read_text(encoding="utf-8"))

    assert report["status"] == "candidate_for_scoped_driving_release"
    assert report["scope"]["compoundPlacementBundle"] is True
    assert report["scope"]["standaloneRelation"] is False
    assert all(report["checks"].values())
    assert report["currentStrictPreflight"]["drivingDecision"] == (
        "candidate_for_driving_cad_trial"
    )
    assert report["releaseBoundary"]["published"] is False
