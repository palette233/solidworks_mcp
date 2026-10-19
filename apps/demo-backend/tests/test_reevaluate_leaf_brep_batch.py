import json
import subprocess
import sys
from pathlib import Path


def test_reevaluation_accepts_same_logical_contact_across_copy_roots(tmp_path: Path):
    candidate = {
        "ExactCheckComplete": True,
        "FailedBodyPairCount": 0,
        "HasInterference": True,
        "InterferingBodyPairs": [
            {
                "FirstComponent": {"Path": r"D:\p2\frame.SLDPRT", "Name": "root/frame-1"},
                "SecondComponent": {"Path": r"D:\p2\ccd.SLDPRT", "Name": "root/ccd-1"},
            }
        ],
    }
    baseline = {
        **candidate,
        "InterferingBodyPairs": [
            {
                "FirstComponent": {"Path": r"D:\p1\frame.SLDPRT", "Name": "root/frame-1"},
                "SecondComponent": {"Path": r"D:\p1\ccd.SLDPRT", "Name": "root/ccd-1"},
            }
        ],
    }
    detail = tmp_path / "detail.json"
    baseline_path = tmp_path / "baseline.json"
    detail.write_text(json.dumps(candidate), encoding="utf-8")
    baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
    batch = tmp_path / "batch.json"
    batch.write_text(
        json.dumps({"pairs": [{"pair": ["A200", "A600"], "outputPath": str(detail)}]}),
        encoding="utf-8",
    )
    output = tmp_path / "reevaluated.json"
    workspace = Path(__file__).resolve().parents[3]
    result = subprocess.run(
        [
            sys.executable,
            str(workspace / "scripts/reevaluate_leaf_brep_batch.py"),
            "--batch",
            str(batch),
            "--output",
            str(output),
            "--accepted-baseline",
            "A200",
            "A600",
            str(baseline_path),
        ],
        cwd=workspace,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["hardFailureCount"] == 0
    assert payload["pairs"][0]["acceptance"]["addedInterferingPairs"] == []
    assert payload["reevaluation"]["solidWorksReopened"] is False
