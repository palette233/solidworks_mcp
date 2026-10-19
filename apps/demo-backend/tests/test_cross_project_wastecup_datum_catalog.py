from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_real_catalog_policy_comparison_builds_in_temp_root(tmp_path: Path) -> None:
    source = ROOT / "demo/cross_project_substitution/wastecup-project05-to-project02-v1"
    for name in ("candidate_effective_mate_graph.json", "candidate_audit.json"):
        (tmp_path / name).write_bytes((source / name).read_bytes())
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/build_cross_project_wastecup_datum_demo_catalog.py"),
            "--root",
            str(tmp_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    comparison = json.loads(
        (tmp_path / "semantic-package-v1/policy-compilation-comparison.json").read_text(
            encoding="utf-8"
        )
    )
    assert comparison["defaultDirectInstallation"]["status"] == "blocked"
    assert comparison["explicitDatumPlacementDemo"]["status"] == "ready"
    assert (
        comparison["explicitDatumPlacementDemo"]["manifestStatus"]
        == "ready_for_project_adapter"
    )
    graph = json.loads(
        (tmp_path / "semantic-package-v1/base_wastecup_datum_graph.json").read_text(
            encoding="utf-8"
        )
    )
    assert {row["ModuleToken"] for row in graph["Modules"]} == {"A600", "P000"}
    assert len(graph["Mates"]) == 3
    assert graph["CaseAnchor"] is None
    assert graph["TargetLeafPoseAnchors"] == []
    assert graph["BaseGraphPolicy"]["moduleTokens"] == ["A600"]
    assert graph["BaseGraphPolicy"]["executionGraphComplete"] is True
