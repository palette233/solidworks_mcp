from pathlib import Path

from demo_backend.project03_live_adapter_closure import (
    build_project03_ae00_ad00_ai00_live_adapter_closure,
    build_project03_four_step_live_adapter_closure,
    build_project03_ae00_ad00_live_adapter_closure,
    build_project03_ae00_live_adapter_closure,
)


def test_real_project03_ae00_pilot_closure_is_releasable() -> None:
    workspace = Path(__file__).resolve().parents[3]
    summary = workspace / "demo/semantic_ports/project03_live_adapter_pilot_jobs/latest_ae00_pilot.json"
    result = build_project03_ae00_live_adapter_closure(summary)
    assert result["success"] is True
    assert result["liveCadApiMayStartForTokens"] == ["AE00"]
    assert result["fullProjectLiveCadReady"] is False
    assert Path(result["assemblyPath"]).is_file()


def test_real_project03_ae00_ad00_chain_closure_is_releasable() -> None:
    workspace = Path(__file__).resolve().parents[3]
    summary = workspace / (
        "demo/semantic_ports/project03_live_adapter_chain_jobs/"
        "latest_ae00_ad00_pilot.json"
    )
    result = build_project03_ae00_ad00_live_adapter_closure(summary)
    assert result["success"] is True
    assert result["singleUninterruptedJob"] is True
    assert result["liveCadApiMayStartForTokens"] == ["AE00", "AD00"]
    assert [step["moduleToken"] for step in result["steps"]] == ["AE00", "AD00"]
    assert all(step["success"] for step in result["steps"])
    assert Path(result["assemblyPath"]).is_file()


def test_real_project03_ae00_ad00_ai00_chain_closure_is_releasable() -> None:
    workspace = Path(__file__).resolve().parents[3]
    summary = workspace / (
        "demo/semantic_ports/project03_live_adapter_three_step_jobs/"
        "latest_ae00_ad00_ai00_pilot.json"
    )
    result = build_project03_ae00_ad00_ai00_live_adapter_closure(summary)
    assert result["success"] is True
    assert result["singleUninterruptedJob"] is True
    assert result["liveCadApiMayStartForTokens"] == ["AE00", "AD00", "AI00"]
    assert [step["moduleToken"] for step in result["steps"]] == [
        "AE00",
        "AD00",
        "AI00",
    ]
    assert all(step["success"] for step in result["steps"])
    assert Path(result["assemblyPath"]).is_file()


def test_real_project03_four_step_chain_closure_is_releasable() -> None:
    workspace = Path(__file__).resolve().parents[3]
    summary = workspace / (
        "demo/semantic_ports/project03_live_adapter_four_step_jobs/"
        "latest_four_step_pilot.json"
    )
    result = build_project03_four_step_live_adapter_closure(summary)
    assert result["success"] is True
    assert result["singleUninterruptedJob"] is True
    assert result["liveCadApiMayStartForTokens"] == [
        "AE00",
        "AD00",
        "AI00",
        "AG00",
    ]
    assert result["steps"][-1]["checks"]["ag00ResidualPoseAnchorDeclared"] is True
    assert Path(result["assemblyPath"]).is_file()
