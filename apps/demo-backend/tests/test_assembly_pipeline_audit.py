from __future__ import annotations

from pathlib import Path

from demo_backend.assembly_pipeline_audit import audit_project02_assembly_pipeline


def test_real_project02_pipeline_is_ready_for_replay_and_live_execution() -> None:
    workspace = Path(__file__).resolve().parents[3]
    result = audit_project02_assembly_pipeline(workspace)
    assert result["blockingIssues"] == []
    assert result["readyForValidatedArtifactReplay"] is True
    assert result["readyForLiveCadExecution"] is True
    by_id = {row["id"]: row for row in result["checks"]}
    assert by_id["top-level-object-count"]["evidence"] == {
        "expected": 10,
        "observed": 10,
    }
    assert by_id["static-pair-gate-complete"]["evidence"]["acceptedPairCount"] == 45
    assert any("生产动态发布尚未通过" in value for value in result["warnings"])
