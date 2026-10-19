import json
import subprocess
import sys
from pathlib import Path


def test_manifest_script_normalizes_and_versions_exact_evidence(tmp_path: Path):
    first = tmp_path / "a.SLDASM"
    second = tmp_path / "b.SLDASM"
    first.write_bytes(b"a")
    second.write_bytes(b"b")
    poses = tmp_path / "poses.json"
    axes = {
        "XAxis": [1, 0, 0],
        "YAxis": [0, 1, 0],
        "ZAxis": [0, 0, 1],
        "ReferencedConfiguration": "Default",
    }
    poses.write_text(
        json.dumps(
            {
                "components": [
                    {"Name": "A-1", "Path": str(first), "Translation": [0, 0, 0], **axes},
                    {"Name": "B-1", "Path": str(second), "Translation": [1, 0, 0], **axes},
                ]
            }
        ),
        encoding="utf-8",
    )
    detail = tmp_path / "detail.json"
    detail.write_text(
        json.dumps(
            {
                "ExactCheckComplete": True,
                "FailedBodyPairCount": 0,
                "HasInterference": True,
            }
        ),
        encoding="utf-8",
    )
    batch = tmp_path / "batch.json"
    batch.write_text(
        json.dumps(
            {
                "pairs": [
                    {
                        "pair": ["A-1", "B-1"],
                        "outputPath": str(detail),
                        "acceptance": {
                            "accepted": True,
                            "policy": "noNewInterferenceOverAcceptedBaseline",
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "cache.json"
    workspace = Path(__file__).resolve().parents[3]
    completed = subprocess.run(
        [
            sys.executable,
            str(workspace / "scripts/build_pair_brep_cache_manifest.py"),
            "--poses",
            str(poses),
            "--batch",
            str(batch),
            "--output",
            str(output),
        ],
        cwd=workspace,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["entryCount"] == 1
    assert len(payload["entries"][0]["cacheKey"]) == 64
    normalized = Path(payload["entries"][0]["evidencePath"])
    assert json.loads(normalized.read_text(encoding="utf-8"))["Acceptance"]["Accepted"] is True


def test_manifest_script_imports_effective_exact_pair_from_closure(tmp_path: Path):
    first = tmp_path / "a.SLDASM"
    second = tmp_path / "b.SLDASM"
    baseline = tmp_path / "baseline.json"
    first.write_bytes(b"a")
    second.write_bytes(b"b")
    baseline.write_text("{}", encoding="utf-8")
    axes = {
        "XAxis": [1, 0, 0],
        "YAxis": [0, 1, 0],
        "ZAxis": [0, 0, 1],
        "ReferencedConfiguration": "Default",
    }
    poses = tmp_path / "poses.json"
    poses.write_text(
        json.dumps(
            {
                "components": [
                    {"Name": "A-1", "Path": str(first), "Translation": [0, 0, 0], **axes},
                    {"Name": "B-1", "Path": str(second), "Translation": [1, 0, 0], **axes},
                ]
            }
        ),
        encoding="utf-8",
    )
    detail = tmp_path / "detail.json"
    detail.write_text(
        json.dumps(
            {
                "ExactCheckComplete": False,
                "FailedBodyPairCount": 1,
                "HasInterference": True,
            }
        ),
        encoding="utf-8",
    )
    closure = tmp_path / "closure.json"
    closure.write_text(
        json.dumps(
            {
                "interferenceGate": {
                    "pairs": [
                        {
                            "pair": ["A-1", "B-1"],
                            "accepted": True,
                            "acceptancePolicy": "noNewInterferenceOverAcceptedBaselineWithOfficialFallback",
                            "candidateDetailPath": str(detail),
                            "prototypeBaselineDetailPath": str(baseline),
                            "candidateFailureFallback": {"resolved": True},
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "cache.json"
    workspace = Path(__file__).resolve().parents[3]
    completed = subprocess.run(
        [
            sys.executable,
            str(workspace / "scripts/build_pair_brep_cache_manifest.py"),
            "--poses",
            str(poses),
            "--closure",
            str(closure),
            "--output",
            str(output),
        ],
        cwd=workspace,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["entryCount"] == 1
    assert payload["entries"][0]["policy"] == "noNewInterferenceOverAcceptedBaseline"
    normalized = json.loads(
        Path(payload["entries"][0]["evidencePath"]).read_text(encoding="utf-8")
    )
    assert normalized["EffectiveExactCheckComplete"] is True
    assert normalized["Acceptance"]["CandidateFailureFallback"]["resolved"] is True
