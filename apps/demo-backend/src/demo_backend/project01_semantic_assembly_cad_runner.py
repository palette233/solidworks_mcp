"""Project01 live-CAD adapter for the evidence-backed static assembly chain.

The final LM00 step inserts the previously verified rigid LM00/ZZ00 context
snapshot as one atomic static object.  This closes static assembly only; it
does not claim FF00 or LM00/ZZ00 motion validation.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

from .semantic_assembly_cad_runner import HardGate
from .semantic_assembly_jobs import AssemblyJobError, DurableAssemblyJobStore, StepRunner
from .semantic_assembly_cad_runner import validate_cad_step


def default_command_runner(command: list[str], timeout_seconds: float) -> Any:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )


def project01_live_cad_step_runner(
    *,
    store: DurableAssemblyJobStore,
    workspace: Path,
    executable: Path,
    hard_gate: HardGate,
    timeout_seconds: float = 1800.0,
    command_runner: Callable[[list[str], float], Any] = default_command_runner,
) -> StepRunner:
    workspace = workspace.resolve()
    executable = executable.resolve()
    script = workspace / "scripts/run_context_incremental_insert.py"
    evidence_root = workspace / "demo/semantic_ports"
    base = evidence_root / "project01_SS00_first_increment_v1/step00_JJ00_HL00_context.SLDASM"
    specs = {
        "SS00": {
            "graph": evidence_root / "project01_SS00_first_increment_v1/assembly_plan_effective.json",
            "target": "SS00",
            "output": "step01_JJ00_HL00_SS00_increment.SLDASM",
            "requiresPrevious": False,
        },
        "FF00": {
            "graph": evidence_root / "project01_FF00_second_increment_v1/assembly_plan_effective.json",
            "target": "FF00",
            "output": "step02_JJ00_HL00_SS00_FF00_increment.SLDASM",
            "requiresPrevious": True,
        },
        "SM00": {
            "graph": evidence_root / "project01_SM00_third_increment_v1/assembly_plan_effective.json",
            "target": "SM00",
            "output": "step03_JJ00_HL00_SS00_FF00_SM00_increment.SLDASM",
            "requiresPrevious": True,
        },
        "GN00": {
            "graph": evidence_root / "project01_GN00_fourth_increment_v1/assembly_plan_effective.json",
            "target": "GN00",
            "output": "step04_JJ00_HL00_SS00_FF00_SM00_GN00_increment.SLDASM",
            "requiresPrevious": True,
        },
        "BD00": {
            "graph": evidence_root / "project01_BD00_fifth_increment_v1/assembly_plan_effective.json",
            "target": "BD00",
            "output": "step05_JJ00_HL00_SS00_FF00_SM00_GN00_BD00_increment.SLDASM",
            "requiresPrevious": True,
        },
        "GJ00": {
            "graph": evidence_root / "project01_GJ00_sixth_increment_v1/assembly_plan_effective.json",
            "target": "GJ00",
            "output": "step06_JJ00_HL00_SS00_FF00_SM00_GN00_BD00_GJ00_increment.SLDASM",
            "requiresPrevious": True,
        },
        "LM00": {
            "graph": evidence_root / "project01_final_static_snapshot_increment_v1/assembly_plan_effective.json",
            "target": "LM00_ZZ00_STATIC",
            "output": "step07_project01_full_10_functional_object_static.SLDASM",
            "requiresPrevious": True,
        },
    }
    for required in (script, executable, base, *(row["graph"] for row in specs.values())):
        if not Path(required).is_file():
            raise AssemblyJobError(f"项目01现场CAD执行依赖不存在：{required}")

    def run(
        job: dict[str, Any], step: dict[str, Any], previous: Path | None
    ) -> dict[str, Any]:
        token = str(step.get("moduleToken") or "")
        spec = specs.get(token)
        if spec is None:
            raise AssemblyJobError(
                f"项目01现场适配器只实现SS00/FF00/SM00/GN00/BD00/GJ00/LM00，{token}尚未登记。"
            )
        if spec["requiresPrevious"] and previous is None:
            raise AssemblyJobError(f"{token}必须以前一累计检查点为输入。")
        source = previous.resolve() if previous else base.resolve()
        working = (
            store.root
            / str(job["jobId"])
            / "cad-working"
            / f"{step['stepId']}-attempt{step['attemptCount']}"
        ).resolve()
        working.mkdir(parents=True, exist_ok=True)
        output = working / str(spec["output"])
        result_path = output.with_suffix(".context-insert.result.json")
        command = [
            sys.executable,
            str(script),
            "--source",
            str(source),
            "--effective",
            str(spec["graph"]),
            "--output",
            str(output),
            "--target",
            str(spec["target"]),
            "--result",
            str(result_path),
            "--exe",
            str(executable),
            "--timeout",
            str(timeout_seconds),
            "--direct-stdio",
        ]
        completed = command_runner(command, timeout_seconds + 60.0)
        if (
            int(getattr(completed, "returncode", 1)) != 0
            or not output.is_file()
            or not result_path.is_file()
        ):
            raise AssemblyJobError(
                f"{token}项目01单步CAD动作失败；returnCode="
                f"{int(getattr(completed, 'returncode', 1))}; "
                f"stderr={str(getattr(completed, 'stderr', ''))[-1000:]}"
            )
        action = json.loads(result_path.read_text(encoding="utf-8-sig"))
        tool_result = action.get("toolResult") or {}
        if (
            action.get("success") is not True
            or tool_result.get("Reopened") is not True
            or tool_result.get("TargetConstraintStateAccepted") is not True
        ):
            raise AssemblyJobError(
                f"{token}未通过项目01配合创建、保存重开和约束状态验证。"
            )
        gate = validate_cad_step(
            job=job,
            step=step,
            output=output,
            previous=previous,
            cad_action_evidence_paths=[str(result_path)],
            hard_gate=hard_gate,
        )
        return {
            "accepted": gate.get("accepted") is True,
            "assemblyPath": str(output),
            "evidencePath": gate.get("evidencePath"),
            "message": gate.get("message"),
            "cadActionEvidencePaths": [str(result_path)],
            "validationProfile": gate.get("validationProfile"),
            "assemblyStatus": gate.get("assemblyStatus"),
            "collisionStatus": gate.get("collisionStatus"),
            "validationEvidenceKind": gate.get("validationEvidenceKind"),
        }

    return run
