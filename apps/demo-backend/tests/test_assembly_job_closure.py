from __future__ import annotations

import json
from pathlib import Path

from demo_backend.assembly_job_closure import build_assembly_job_static_closure


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _job(tmp_path: Path, *, accept_last: bool = True) -> Path:
    final = tmp_path / "final.SLDASM"
    final.write_bytes(b"cad")
    action1 = tmp_path / "a1.json"
    action2 = tmp_path / "a2.json"
    _write(action1, {"success": True})
    _write(action2, {"success": True})
    gate1 = tmp_path / "g1.json"
    gate2 = tmp_path / "g2.json"
    _write(gate1, {"accepted": True, "pairs": [{"pair": ["base", "a"], "accepted": True}]})
    _write(
        gate2,
        {
            "accepted": accept_last,
            "pairs": [
                {"pair": ["base", "b"], "accepted": True},
                {"pair": ["a", "b"], "accepted": accept_last},
            ],
        },
    )
    _write(
        tmp_path / "job.json",
        {
            "jobId": "job",
            "status": "succeeded",
            "lastCommittedCheckpoint": {"assemblyPath": str(final)},
            "steps": [
                {
                    "stepId": "s1",
                    "checkpoint": {
                        "evidencePath": str(gate1),
                        "cadActionEvidencePaths": [str(action1)],
                    },
                },
                {
                    "stepId": "s2",
                    "checkpoint": {
                        "evidencePath": str(gate2),
                        "cadActionEvidencePaths": [str(action2)],
                    },
                },
            ],
        },
    )
    return tmp_path


def test_complete_pair_cover_closes_static_job(tmp_path: Path) -> None:
    closure = build_assembly_job_static_closure(
        _job(tmp_path), expected_top_level_object_count=3, expected_cad_action_count=2
    )
    assert closure["staticFullChainAccepted"] is True
    assert closure["observedTopLevelObjectCountFromPairEvidence"] == 3
    assert closure["acceptedPairCount"] == 3
    assert closure["cadActionEvidenceCount"] == 2


def test_rejected_pair_prevents_static_closure(tmp_path: Path) -> None:
    closure = build_assembly_job_static_closure(
        _job(tmp_path, accept_last=False), expected_top_level_object_count=3
    )
    assert closure["staticFullChainAccepted"] is False
    assert closure["rejectedEvidence"]
