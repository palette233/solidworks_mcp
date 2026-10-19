from pathlib import Path

from demo_backend.project03_segmented_live_adapter_closure import (
    build_project03_segmented_full_live_adapter_closure,
)


def test_real_project03_segmented_full_action_chain_is_closed() -> None:
    workspace = Path(__file__).resolve().parents[3]
    result = build_project03_segmented_full_live_adapter_closure(
        four_step_closure_path=workspace / "demo/semantic_ports/project03_live_adapter_four_step_jobs/project03_four_step_live_adapter_closure.json",
        ah00_summary_path=workspace / "demo/semantic_ports/project03_live_adapter_ah00_tail_jobs/latest_ah00_tail.json",
        aj00_summary_path=workspace / "demo/semantic_ports/project03_live_adapter_aj00_tail_jobs/latest_aj00_tail.json",
        ab00_summary_path=workspace / "demo/semantic_ports/project03_live_adapter_ab00_tail_jobs/latest_ab00_tail.json",
    )
    assert result["success"] is True
    assert result["allActionsLiveCadValidated"] is True
    assert result["singleUninterruptedJob"] is False
    assert result["checks"]["crossJobCheckpointContinuity"] is True
    assert len(result["tails"][-1]["cadActionEvidencePaths"]) == 2
    assert Path(result["assemblyPath"]).is_file()
