"""Project03 live-CAD action adapter for evidence-backed ordered prefixes.

Each added token has its own effective mate graph.  A token becomes API-visible
only after an uninterrupted real-CAD job and release closure succeed; adding a
specification here alone is not a release decision.
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


def project03_live_cad_step_runner(
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
    script = workspace / "scripts" / "run_context_incremental_insert.py"
    evidence_root = workspace / "demo" / "semantic_ports"
    base = evidence_root / "project03_AE00_first_increment_v1/step00_AA00_AF00_context.SLDASM"
    specs = {
        "AE00": {
            "graph": evidence_root / "project03_AE00_first_increment_v1/assembly_plan_effective.json",
            "target": "FL9A24D063AE00",
            "output": "step01_AA00_AF00_AE00_increment.SLDASM",
            "requiresPrevious": False,
        },
        "AD00": {
            "graph": evidence_root / "project03_AD00_second_increment_v1/assembly_plan_effective.json",
            "target": "FL9A24D063AD00",
            "output": "step02_AA00_AF00_AE00_AD00_increment.SLDASM",
            "requiresPrevious": True,
        },
        "AI00": {
            "graph": evidence_root / "project03_AI00_third_increment_v1/assembly_plan_effective.json",
            "target": "FL9A24D063AI00",
            "output": "step03_AA00_AF00_AE00_AD00_AI00_increment.SLDASM",
            "requiresPrevious": True,
        },
        "AG00": {
            "graph": evidence_root / "project03_AG00_fourth_increment_anchored_v1/assembly_plan_effective.json",
            "target": "FL9A24D063AG00",
            "output": "step04_AA00_AF00_AE00_AD00_AI00_AG00_increment.SLDASM",
            "requiresPrevious": True,
        },
        "AH00": {
            "graph": evidence_root / "project03_AH00_fifth_increment_v1/assembly_plan_effective.json",
            "target": "FL9A24D063AH00",
            "output": "step05_AA00_AF00_AE00_AD00_AI00_AG00_AH00_increment.SLDASM",
            "requiresPrevious": True,
        },
        "AJ00": {
            "graph": evidence_root / "project03_AJ00_sixth_increment_v1/assembly_plan_effective.json",
            "target": "FL9A24D063AJ00",
            "output": "step06_AA00_AF00_AE00_AD00_AI00_AG00_AH00_AJ00_increment.SLDASM",
            "requiresPrevious": True,
        },
        "AB00": {
            "graph": evidence_root / "project03_AB00_final_stage_action1_v1/assembly_plan_effective.json",
            "target": "FL9A24D063AB00",
            "output": "step07a_AA00_AF00_AE00_AD00_AI00_AG00_AH00_AJ00_AB00_increment.SLDASM",
            "requiresPrevious": True,
            "secondGraph": evidence_root / "project03_full_hybrid_static_v1/assembly_plan_effective.json",
            "secondTarget": "FL9A24D063AC00_STATIC_SNAPSHOT",
            "secondOutput": "step07b_project03_full_10_object_hybrid_static.SLDASM",
        },
    }
    extra_graphs = [
        Path(str(spec["secondGraph"]))
        for spec in specs.values()
        if spec.get("secondGraph") is not None
    ]
    for required in (
        script,
        executable,
        base,
        *(spec["graph"] for spec in specs.values()),
        *extra_graphs,
    ):
        if not required.is_file():
            raise AssemblyJobError(f"项目03现场CAD执行依赖不存在：{required}")

    def run(
        job: dict[str, Any], step: dict[str, Any], previous: Path | None
    ) -> dict[str, Any]:
        token = str(step.get("moduleToken") or "")
        spec = specs.get(token)
        if spec is None:
            raise AssemblyJobError(
                f"项目03现场适配器当前只实现AE00/AD00/AI00/AG00/AH00/AJ00/AB00，{token}尚未发布。"
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
        action_evidence: list[Path] = []

        def execute_action(
            action_source: Path,
            graph: Path,
            target: str,
            output_name: str,
        ) -> Path:
            action_output = working / output_name
            result_path = action_output.with_suffix(".context-insert.result.json")
            command = [
                sys.executable,
                str(script),
                "--source",
                str(action_source),
                "--effective",
                str(graph),
                "--output",
                str(action_output),
                "--target",
                target,
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
                or not action_output.is_file()
                or not result_path.is_file()
            ):
                raise AssemblyJobError(
                    f"{token}项目03现场CAD动作失败；returnCode="
                    f"{int(getattr(completed, 'returncode', 1))}; "
                    f"stderr={str(getattr(completed, 'stderr', ''))[-1000:]}"
                )
            result = json.loads(result_path.read_text(encoding="utf-8"))
            if result.get("success") is not True:
                raise AssemblyJobError(
                    f"{token}未通过配合创建、保存重开和约束状态验证。"
                )
            action_evidence.append(result_path)
            return action_output

        output = execute_action(
            source,
            Path(str(spec["graph"])),
            str(spec["target"]),
            str(spec["output"]),
        )
        if spec.get("secondGraph") is not None:
            output = execute_action(
                output,
                Path(str(spec["secondGraph"])),
                str(spec["secondTarget"]),
                str(spec["secondOutput"]),
            )
        gate = validate_cad_step(
            job=job,
            step=step,
            output=output,
            previous=previous,
            cad_action_evidence_paths=[str(path) for path in action_evidence],
            hard_gate=hard_gate,
        )
        return {
            "accepted": gate.get("accepted") is True,
            "assemblyPath": str(output),
            "evidencePath": gate.get("evidencePath"),
            "message": gate.get("message"),
            "cadActionEvidencePaths": [str(path) for path in action_evidence],
            "validationProfile": gate.get("validationProfile"),
            "assemblyStatus": gate.get("assemblyStatus"),
            "collisionStatus": gate.get("collisionStatus"),
            "validationEvidenceKind": gate.get("validationEvidenceKind"),
        }

    return run
