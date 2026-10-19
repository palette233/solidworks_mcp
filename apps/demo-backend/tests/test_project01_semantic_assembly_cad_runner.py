from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from demo_backend.project01_semantic_assembly_cad_runner import (
    project01_live_cad_step_runner,
)
from demo_backend.semantic_assembly_jobs import AssemblyJobError, DurableAssemblyJobStore


TOKENS = ("SS00", "FF00", "SM00", "GN00", "BD00", "GJ00", "LM00")


def _workspace(tmp_path: Path) -> tuple[Path, Path]:
    workspace = tmp_path / "workspace"
    (workspace / "scripts").mkdir(parents=True)
    (workspace / "scripts/run_context_incremental_insert.py").write_text(
        "# stub\n", encoding="utf-8"
    )
    roots = {
        "SS00": "project01_SS00_first_increment_v1",
        "FF00": "project01_FF00_second_increment_v1",
        "SM00": "project01_SM00_third_increment_v1",
        "GN00": "project01_GN00_fourth_increment_v1",
        "BD00": "project01_BD00_fifth_increment_v1",
        "GJ00": "project01_GJ00_sixth_increment_v1",
        "LM00": "project01_final_static_snapshot_increment_v1",
    }
    for directory in roots.values():
        root = workspace / "demo/semantic_ports" / directory
        root.mkdir(parents=True)
        (root / "assembly_plan_effective.json").write_text("{}\n", encoding="utf-8")
    (
        workspace
        / "demo/semantic_ports/project01_SS00_first_increment_v1/step00_JJ00_HL00_context.SLDASM"
    ).write_bytes(b"base")
    executable = workspace / "SolidWorksMcpApp.exe"
    executable.write_bytes(b"exe")
    return workspace, executable


def _successful_runner(calls: list[list[str]]):
    def run(command: list[str], timeout: float):
        calls.append(command)
        output = Path(command[command.index("--output") + 1])
        result = Path(command[command.index("--result") + 1])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"assembly")
        result.write_text(
            json.dumps(
                {
                    "success": True,
                    "toolResult": {
                        "Reopened": True,
                        "TargetConstraintStateAccepted": True,
                    },
                }
            ),
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=0, stderr="")

    return run


def test_project01_runner_chains_every_registered_static_action(tmp_path: Path) -> None:
    workspace, executable = _workspace(tmp_path)
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    calls: list[list[str]] = []
    gate_inputs: list[tuple[str, Path | None]] = []

    def gate(job, step, output, previous):
        gate_inputs.append((step["moduleToken"], previous))
        evidence = tmp_path / f"{step['moduleToken']}-gate.json"
        evidence.write_text("{}\n", encoding="utf-8")
        return {"accepted": True, "evidencePath": str(evidence)}

    runner = project01_live_cad_step_runner(
        store=store,
        workspace=workspace,
        executable=executable,
        hard_gate=gate,
        command_runner=_successful_runner(calls),
    )
    previous = None
    for index, token in enumerate(TOKENS, start=1):
        result = runner(
            {"jobId": "project01-job-test"},
            {
                "stepId": f"step-{index:02d}-{token.lower()}",
                "moduleToken": token,
                "attemptCount": 1,
            },
            previous,
        )
        previous = Path(result["assemblyPath"])

    assert len(calls) == len(TOKENS)
    assert calls[0][calls[0].index("--target") + 1] == "SS00"
    assert calls[-1][calls[-1].index("--target") + 1] == "LM00_ZZ00_STATIC"
    for index in range(1, len(calls)):
        assert calls[index][calls[index].index("--source") + 1] == calls[index - 1][calls[index - 1].index("--output") + 1]
    assert gate_inputs[0][1] is None
    assert all(previous is not None for _, previous in gate_inputs[1:])


def test_project01_runner_rejects_missing_previous_checkpoint(tmp_path: Path) -> None:
    workspace, executable = _workspace(tmp_path)
    runner = project01_live_cad_step_runner(
        store=DurableAssemblyJobStore(tmp_path / "jobs"),
        workspace=workspace,
        executable=executable,
        hard_gate=lambda *_: {"accepted": True},
    )
    with pytest.raises(AssemblyJobError, match="前一累计检查点"):
        runner(
            {"jobId": "project01-job-test"},
            {"stepId": "step-02-ff00", "moduleToken": "FF00", "attemptCount": 1},
            None,
        )


def test_project01_runner_fails_closed_when_reopen_evidence_is_missing(
    tmp_path: Path,
) -> None:
    workspace, executable = _workspace(tmp_path)

    def incomplete(command: list[str], timeout: float):
        output = Path(command[command.index("--output") + 1])
        result = Path(command[command.index("--result") + 1])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"assembly")
        result.write_text(json.dumps({"success": True, "toolResult": {}}), encoding="utf-8")
        return SimpleNamespace(returncode=0, stderr="")

    runner = project01_live_cad_step_runner(
        store=DurableAssemblyJobStore(tmp_path / "jobs"),
        workspace=workspace,
        executable=executable,
        hard_gate=lambda *_: {"accepted": True},
        command_runner=incomplete,
    )
    with pytest.raises(AssemblyJobError, match="保存重开"):
        runner(
            {"jobId": "project01-job-test"},
            {"stepId": "step-01-ss00", "moduleToken": "SS00", "attemptCount": 1},
            None,
        )
