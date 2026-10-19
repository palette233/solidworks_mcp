"""Single-step live-CAD adapter for Project05's ordered cumulative builder.

This adapter is intentionally not enabled by the HTTP API until a complete
on-site long-chain run proves every step together with the collision hard
gate.  Unit tests validate command construction, checkpoint chaining and
failure behavior without claiming a new SolidWorks run.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

from .semantic_assembly_jobs import AssemblyJobError, DurableAssemblyJobStore, StepRunner
from .semantic_assembly_cad_runner import validate_cad_step
from .semantic_assembly_cad_runner import HardGate


PROJECT05_STAGE_INDEX = {
    "D000": 1,
    "K000": 2,
    "F000": 3,
    "M000": 4,
    "G000": 5,
    "N000": 6,
    "P000": 7,
    "B000": 8,
}


def default_command_runner(command: list[str], timeout_seconds: float) -> Any:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )


def project05_live_cad_step_runner(
    *,
    store: DurableAssemblyJobStore,
    closure: dict[str, Any],
    workspace: Path,
    executable: Path,
    hard_gate: HardGate,
    timeout_seconds: float = 1800.0,
    command_runner: Callable[[list[str], float], Any] = default_command_runner,
) -> StepRunner:
    workspace = workspace.resolve()
    executable = executable.resolve()
    builder = workspace / "scripts" / "build_ordered_project05_eleven_module_solution.py"
    layout = workspace / "demo" / "layout_previews" / "project05_selected_solution_replay.json"
    poses = workspace / "demo" / "layout_previews" / "project05_selected_solution_direct_poses.json"
    for required in (builder, executable, layout, poses):
        if not required.is_file():
            raise AssemblyJobError(f"项目05现场CAD执行依赖不存在：{required}")
    base = next(
        (row for row in closure.get("steps") or [] if row.get("moduleToken") == "A000"),
        None,
    )
    base_path = Path(str((base or {}).get("assemblyPath") or "")).resolve()
    if not base_path.is_file():
        raise AssemblyJobError(f"项目05 A000基座检查点不存在：{base_path}")

    def run(
        job: dict[str, Any], step: dict[str, Any], previous: Path | None
    ) -> dict[str, Any]:
        token = str(step["moduleToken"])
        stage_index = PROJECT05_STAGE_INDEX.get(token)
        if stage_index is None:
            raise AssemblyJobError(f"项目05没有登记{token}的现场CAD阶段。")
        source = previous.resolve() if previous else base_path
        working = (
            store.root
            / str(job["jobId"])
            / "cad-working"
            / f"{step['stepId']}-attempt{step['attemptCount']}"
        ).resolve()
        result_path = working / "project05_ordered_direct_execution.json"
        command = [
            sys.executable,
            str(builder),
            "--layout",
            str(layout),
            "--poses",
            str(poses),
            "--output-root",
            str(working),
            "--mcp",
            str(executable),
            "--request-timeout",
            str(timeout_seconds),
            "--start-stage",
            str(stage_index),
            "--end-stage",
            str(stage_index + 1),
            "--resume-checkpoint",
            str(source),
        ]
        completed = command_runner(command, timeout_seconds + 120.0)
        if int(getattr(completed, "returncode", 1)) != 0 or not result_path.is_file():
            raise AssemblyJobError(
                f"{token}项目05单步CAD动作失败；returnCode="
                f"{int(getattr(completed, 'returncode', 1))}; "
                f"stderr={str(getattr(completed, 'stderr', ''))[-1000:]}"
            )
        execution = json.loads(result_path.read_text(encoding="utf-8"))
        stages = execution.get("stages") or []
        if execution.get("success") is not True or len(stages) != 1:
            raise AssemblyJobError(f"{token}没有形成唯一通过的项目05 CAD阶段结果。")
        stage = stages[0]
        output = Path(str(execution.get("finalAssemblyPath") or "")).resolve()
        stage_evidence = output.with_suffix(".stage-result.json")
        if (
            stage.get("moduleToken") != token
            or stage.get("accepted") is not True
            or not output.is_file()
            or not stage_evidence.is_file()
        ):
            raise AssemblyJobError(f"{token}项目05 CAD阶段未通过保存重开和几何审计。")
        evidence_paths = [str(result_path), str(stage_evidence)]
        gate = validate_cad_step(
            job=job,
            step=step,
            output=output,
            previous=previous,
            cad_action_evidence_paths=evidence_paths,
            hard_gate=hard_gate,
        )
        return {
            "accepted": gate.get("accepted") is True,
            "assemblyPath": str(output),
            "evidencePath": gate.get("evidencePath"),
            "message": gate.get("message"),
            "cadActionEvidencePaths": evidence_paths,
            "validationProfile": gate.get("validationProfile"),
            "assemblyStatus": gate.get("assemblyStatus"),
            "collisionStatus": gate.get("collisionStatus"),
            "validationEvidenceKind": gate.get("validationEvidenceKind"),
        }

    return run
