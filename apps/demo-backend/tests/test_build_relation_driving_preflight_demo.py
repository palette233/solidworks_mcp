from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/build_relation_driving_preflight_demo.py"


def test_demo_report_uses_real_graph_and_separates_three_preflight_outcomes(
    tmp_path, monkeypatch
):
    spec = importlib.util.spec_from_file_location(
        "build_relation_driving_preflight_demo", SCRIPT
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = tmp_path / "report.json"
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--output", str(output)])

    assert module.main() == 0
    report = json.loads(output.read_text(encoding="utf-8"))

    assert report["sourceGraphIsRealCadDerived"] is True
    assert report["solidWorksExecuted"] is False
    assert report["summary"] == {
        "closedGraphConstraintRank": 6,
        "closedGraphResidualDof": 0,
        "closedGraphMechanicalDecision": "candidate_for_driving_cad_trial",
        "closedGraphOverallDecision": "verification_only",
        "redundantDecision": "verification_only",
        "unsupportedDecision": "blocked",
    }
