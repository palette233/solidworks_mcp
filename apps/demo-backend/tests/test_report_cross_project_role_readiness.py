from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_report_keeps_datum_demo_separate_from_direct_roles(tmp_path: Path) -> None:
    matrix = {
        "matrixDigest": "matrix-digest",
        "releasedDirectExecutionCount": 2,
        "roleSummaries": [
            {
                "group": "Transport",
                "statusCounts": {"released_direct_execution": 2},
            },
            {
                "group": "WasteCup",
                "statusCounts": {"incompatible": 2},
            },
        ],
    }
    closure = {
        "schemaVersion": "cross-project-wastecup-datum-closure/v1",
        "success": True,
        "releaseEligibleForDatumPlacementDemo": True,
        "releaseEligibleForDirectMechanicalSubstitution": False,
        "moduleRole": "WasteCup",
        "sourceProjectId": "project05",
        "sourceModuleToken": "P000",
        "targetProjectId": "project02",
        "targetBaseToken": "A600",
    }
    matrix_path = tmp_path / "matrix.json"
    closure_path = tmp_path / "closure.json"
    json_output = tmp_path / "report.json"
    markdown_output = tmp_path / "report.md"
    matrix_path.write_text(json.dumps(matrix), encoding="utf-8")
    closure_path.write_text(json.dumps(closure), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/report_cross_project_role_readiness.py"),
            str(matrix_path),
            "--json-output",
            str(json_output),
            "--markdown-output",
            str(markdown_output),
            "--datum-demo-closure",
            str(closure_path),
        ],
        check=True,
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    report = json.loads(json_output.read_text(encoding="utf-8"))
    assert report["readyRoleCount"] == 1
    assert report["thirdDirectRoleAvailable"] is False
    assert report["datumPlacementDemoRoleCount"] == 1
    assert report["datumPlacementDemoRoles"][0]["role"] == "WasteCup"
