from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from demo_backend.project03_semantic_assembly_cad_runner import (
    project03_live_cad_step_runner,
)
from demo_backend.semantic_assembly_jobs import AssemblyJobError, DurableAssemblyJobStore


def _workspace(tmp_path: Path) -> tuple[Path, Path]:
    workspace = tmp_path / "workspace"
    (workspace / "scripts").mkdir(parents=True)
    (workspace / "scripts/run_context_incremental_insert.py").write_text("# stub", encoding="utf-8")
    root = workspace / "demo/semantic_ports/project03_AE00_first_increment_v1"
    root.mkdir(parents=True)
    (root / "step00_AA00_AF00_context.SLDASM").write_bytes(b"base")
    (root / "assembly_plan_effective.json").write_text("{}", encoding="utf-8")
    ad_root = workspace / "demo/semantic_ports/project03_AD00_second_increment_v1"
    ad_root.mkdir(parents=True)
    (ad_root / "assembly_plan_effective.json").write_text("{}", encoding="utf-8")
    ai_root = workspace / "demo/semantic_ports/project03_AI00_third_increment_v1"
    ai_root.mkdir(parents=True)
    (ai_root / "assembly_plan_effective.json").write_text("{}", encoding="utf-8")
    ag_root = workspace / "demo/semantic_ports/project03_AG00_fourth_increment_anchored_v1"
    ag_root.mkdir(parents=True)
    (ag_root / "assembly_plan_effective.json").write_text("{}", encoding="utf-8")
    ah_root = workspace / "demo/semantic_ports/project03_AH00_fifth_increment_v1"
    ah_root.mkdir(parents=True)
    (ah_root / "assembly_plan_effective.json").write_text("{}", encoding="utf-8")
    aj_root = workspace / "demo/semantic_ports/project03_AJ00_sixth_increment_v1"
    aj_root.mkdir(parents=True)
    (aj_root / "assembly_plan_effective.json").write_text("{}", encoding="utf-8")
    ab_root = workspace / "demo/semantic_ports/project03_AB00_final_stage_action1_v1"
    ab_root.mkdir(parents=True)
    (ab_root / "assembly_plan_effective.json").write_text("{}", encoding="utf-8")
    full_root = workspace / "demo/semantic_ports/project03_full_hybrid_static_v1"
    full_root.mkdir(parents=True)
    (full_root / "assembly_plan_effective.json").write_text("{}", encoding="utf-8")
    executable = workspace / "SolidWorksMcpApp.exe"
    executable.write_bytes(b"exe")
    return workspace, executable


def test_project03_ae00_runner_builds_new_artifact_and_calls_gate(tmp_path: Path) -> None:
    workspace, executable = _workspace(tmp_path)
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    calls: list[list[str]] = []

    def command_runner(command: list[str], timeout: float):
        calls.append(command)
        output = Path(command[command.index("--output") + 1])
        result = Path(command[command.index("--result") + 1])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"assembly")
        result.write_text(json.dumps({"success": True}), encoding="utf-8")
        return SimpleNamespace(returncode=0, stderr="")

    gate_calls = []

    def gate(job, step, output, previous):
        gate_calls.append((step["moduleToken"], output, previous))
        evidence = tmp_path / "gate.json"
        evidence.write_text("{}", encoding="utf-8")
        return {"accepted": True, "evidencePath": str(evidence)}

    runner = project03_live_cad_step_runner(
        store=store,
        workspace=workspace,
        executable=executable,
        hard_gate=gate,
        command_runner=command_runner,
    )
    result = runner(
        {"jobId": "project03-job-test"},
        {"stepId": "step-01-ae00", "moduleToken": "AE00", "attemptCount": 1},
        None,
    )

    assert result["accepted"] is True
    assert Path(result["assemblyPath"]).is_file()
    assert "FL9A24D063AE00" in calls[0]
    assert gate_calls[0][0] == "AE00"


def test_project03_runner_rejects_unpublished_module(tmp_path: Path) -> None:
    workspace, executable = _workspace(tmp_path)
    runner = project03_live_cad_step_runner(
        store=DurableAssemblyJobStore(tmp_path / "jobs"),
        workspace=workspace,
        executable=executable,
        hard_gate=lambda *_: {"accepted": True},
    )
    with pytest.raises(AssemblyJobError, match="当前只实现AE00/AD00/AI00/AG00/AH00/AJ00/AB00"):
        runner(
            {"jobId": "project03-job-test"},
            {"stepId": "step-08-unknown", "moduleToken": "ZZ99", "attemptCount": 1},
            None,
        )


def test_project03_ab00_runner_executes_two_atomic_cad_actions(tmp_path: Path) -> None:
    workspace, executable = _workspace(tmp_path)
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    calls: list[list[str]] = []

    def command_runner(command: list[str], timeout: float):
        calls.append(command)
        output = Path(command[command.index("--output") + 1])
        result = Path(command[command.index("--result") + 1])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"assembly")
        result.write_text(json.dumps({"success": True}), encoding="utf-8")
        return SimpleNamespace(returncode=0, stderr="")

    previous = tmp_path / "aj00.SLDASM"
    previous.write_bytes(b"seed")
    runner = project03_live_cad_step_runner(
        store=store,
        workspace=workspace,
        executable=executable,
        hard_gate=lambda *_: {"accepted": True, "evidencePath": str(tmp_path / "gate.json")},
        command_runner=command_runner,
    )
    result = runner(
        {"jobId": "project03-job-test"},
        {"stepId": "step-07-ab00", "moduleToken": "AB00", "attemptCount": 1},
        previous,
    )
    assert result["accepted"] is True
    assert len(calls) == 2
    assert "FL9A24D063AB00" in calls[0]
    assert "FL9A24D063AC00_STATIC_SNAPSHOT" in calls[1]
    assert len(result["cadActionEvidencePaths"]) == 2


def test_project03_ad00_requires_previous_checkpoint(tmp_path: Path) -> None:
    workspace, executable = _workspace(tmp_path)
    runner = project03_live_cad_step_runner(
        store=DurableAssemblyJobStore(tmp_path / "jobs"),
        workspace=workspace,
        executable=executable,
        hard_gate=lambda *_: {"accepted": True},
    )
    with pytest.raises(AssemblyJobError, match="前一累计检查点"):
        runner(
            {"jobId": "project03-job-test"},
            {"stepId": "step-02-ad00", "moduleToken": "AD00", "attemptCount": 1},
            None,
        )


def test_project03_ai00_requires_previous_checkpoint(tmp_path: Path) -> None:
    workspace, executable = _workspace(tmp_path)
    runner = project03_live_cad_step_runner(
        store=DurableAssemblyJobStore(tmp_path / "jobs"),
        workspace=workspace,
        executable=executable,
        hard_gate=lambda *_: {"accepted": True},
    )
    with pytest.raises(AssemblyJobError, match="前一累计检查点"):
        runner(
            {"jobId": "project03-job-test"},
            {"stepId": "step-03-ai00", "moduleToken": "AI00", "attemptCount": 1},
            None,
        )
