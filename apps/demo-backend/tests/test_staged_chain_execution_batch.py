from pathlib import Path

from demo_backend.staged_chain_execution_batch import (
    build_staged_chain_execution_batch_status,
)


ROOT = Path(__file__).resolve().parents[3]
BATCH = (
    ROOT
    / "demo/station_gap_batch_20261028/scanner-context-chain-recompile-v34-v3/batch-report.json"
)


def test_scanner_context_chains_form_one_serial_resume_safe_execution_batch():
    status = build_staged_chain_execution_batch_status(ROOT, BATCH)
    assert status["chainCount"] == 6
    assert sum(status["runtimeStateCounts"].values()) == 6
    assert status["executionPolicy"] == {
        "serial": True,
        "stopAfterUnresolvedFailure": True,
        "resumeBeforeStartingNextChain": True,
        "skipCommittedStages": True,
        "cleanSolidWorksSessionRequired": True,
    }
    assert len({row["chainId"] for row in status["chains"]}) == 6


def test_scanner_context_chain_batch_selects_exactly_one_next_action():
    status = build_staged_chain_execution_batch_status(ROOT, BATCH)
    assert status["status"] in {"ready_for_next_chain_action", "complete"}
    if status["status"] == "complete":
        assert status["completedChainCount"] == 6
        assert status["nextAction"] is None
    else:
        assert status["nextAction"]
        rows = [
            row
            for row in status["chains"]
            if row["chainId"] == status["nextAction"]["chainId"]
        ]
        assert len(rows) == 1
        assert rows[0]["nextAction"] == status["nextAction"]["action"]
