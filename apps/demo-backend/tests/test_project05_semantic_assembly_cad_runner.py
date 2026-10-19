from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from demo_backend.project05_semantic_assembly_cad_runner import (
    project05_live_cad_step_runner,
)
from demo_backend.semantic_assembly_jobs import AssemblyJobError, DurableAssemblyJobStore


def dependencies(tmp_path: Path) -> tuple[Path, dict]:
    for relative in (
        "scripts/build_ordered_project05_eleven_module_solution.py",
        "demo/layout_previews/project05_selected_solution_replay.json",
        "demo/layout_previews/project05_selected_solution_direct_poses.json",
    ):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
    executable = tmp_path / "mcp.exe"
    executable.write_bytes(b"exe")
    base = tmp_path / "A000.SLDASM"
    base.write_bytes(b"base")
    return executable, {
        "steps": [{"moduleToken": "A000", "assemblyPath": str(base)}]
    }


def fake_builder(command: list[str], _: float):
    def value(flag: str) -> str:
        return command[command.index(flag) + 1]

    output_root = Path(value("--output-root"))
    stage = int(value("--start-stage"))
    token_by_stage = {1: "D000", 2: "K000"}
    token = token_by_stage[stage]
    output_root.mkdir(parents=True, exist_ok=True)
    assembly = output_root / f"step0{stage}_{token}_cumulative.SLDASM"
    assembly.write_bytes(token.encode())
    evidence = assembly.with_suffix(".stage-result.json")
    stage_row = {"moduleToken": token, "accepted": True}
    evidence.write_text(json.dumps(stage_row), encoding="utf-8")
    (output_root / "project05_ordered_direct_execution.json").write_text(
        json.dumps(
            {
                "success": True,
                "stages": [stage_row],
                "finalAssemblyPath": str(assembly),
            }
        ),
        encoding="utf-8",
    )
    return SimpleNamespace(returncode=0, stderr="", stdout="")


def test_project05_single_step_adapter_chains_base_and_previous_checkpoint(
    tmp_path: Path,
) -> None:
    executable, closure = dependencies(tmp_path)
    store = DurableAssemblyJobStore(tmp_path / "jobs")
    commands: list[list[str]] = []

    def recording_builder(command: list[str], timeout: float):
        commands.append(command)
        return fake_builder(command, timeout)

    def gate(job, step, output, previous):
        evidence = tmp_path / f"{step['moduleToken']}-gate.json"
        evidence.write_text("{}", encoding="utf-8")
        return {"accepted": True, "evidencePath": str(evidence)}

    runner = project05_live_cad_step_runner(
        store=store,
        closure=closure,
        workspace=tmp_path,
        executable=executable,
        hard_gate=gate,
        command_runner=recording_builder,
    )
    job = {"jobId": "project05-job-test"}
    first = runner(job, {"stepId": "step-01-d000", "moduleToken": "D000", "attemptCount": 1}, None)
    first_path = Path(first["assemblyPath"])
    second = runner(job, {"stepId": "step-02-k000", "moduleToken": "K000", "attemptCount": 1}, first_path)
    assert first["accepted"] is True and second["accepted"] is True
    assert commands[0][commands[0].index("--start-stage") + 1] == "1"
    assert commands[0][commands[0].index("--end-stage") + 1] == "2"
    assert commands[1][commands[1].index("--resume-checkpoint") + 1] == str(first_path)
    assert len(second["cadActionEvidencePaths"]) == 2


def test_project05_single_step_adapter_rejects_unknown_stage(tmp_path: Path) -> None:
    executable, closure = dependencies(tmp_path)
    runner = project05_live_cad_step_runner(
        store=DurableAssemblyJobStore(tmp_path / "jobs"),
        closure=closure,
        workspace=tmp_path,
        executable=executable,
        hard_gate=lambda *_: {"accepted": True},
        command_runner=fake_builder,
    )
    with pytest.raises(AssemblyJobError, match="没有登记T401"):
        runner(
            {"jobId": "project05-job-test"},
            {"stepId": "step-x", "moduleToken": "T401", "attemptCount": 1},
            None,
        )
