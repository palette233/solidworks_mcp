import json
import subprocess
import sys
from pathlib import Path


def test_real_project02_final_pose_cache_has_no_unresolved_pairs(tmp_path: Path):
    workspace = Path(__file__).resolve().parents[3]
    output = tmp_path / "coverage.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(workspace / "scripts/audit_project02_pair_cache_coverage.py"),
            "--output",
            str(output),
        ],
        cwd=workspace,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    # The cache is append-only: later verified CAD jobs may add valid pair
    # fingerprints.  Coverage, not the historical entry count, is the
    # invariant this test is meant to protect.
    assert payload["cacheEntryCount"] >= 32
    assert payload["summary"]["acceptedModuleGateCount"] == 8
    assert payload["summary"]["unresolvedExactPairCount"] == 0
    assert payload["summary"]["allCurrentFinalPosesClosedByAabbOrCache"] is True
