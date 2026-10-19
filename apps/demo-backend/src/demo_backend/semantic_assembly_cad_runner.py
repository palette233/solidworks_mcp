"""Serial live-CAD step runner for durable semantic assembly jobs.

The runner supports two deliberately separate acceptance profiles:

``demo``
    A real mate operation, save and reopen check is enough to commit an
    *assembly* checkpoint.  Collision is explicitly recorded as not evaluated.

``engineering``
    The same CAD evidence must additionally pass the supplied collision gate.

Keeping these profiles separate prevents a several-minute B-rep audit from
blocking the natural-language assembly demo while preserving the stricter
engineering path as an explicit opt-in operation.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

from .semantic_assembly_jobs import AssemblyJobError, DurableAssemblyJobStore, StepRunner


CommandRunner = Callable[[list[str], float], Any]
HardGate = Callable[[dict[str, Any], dict[str, Any], Path, Path | None], dict[str, Any]]


def validate_cad_step(
    *,
    job: dict[str, Any],
    step: dict[str, Any],
    output: Path,
    previous: Path | None,
    cad_action_evidence_paths: list[str],
    hard_gate: HardGate,
) -> dict[str, Any]:
    """Apply the job's explicit validation profile to one saved CAD step."""

    profile = str(
        job.get("validationProfile")
        or (job.get("plan") or {}).get("validationProfile")
        or "engineering"
    )
    if profile == "demo":
        if not cad_action_evidence_paths:
            raise AssemblyJobError("演示装配检查点缺少CAD保存重开证据。")
        return {
            "accepted": True,
            "evidencePath": cad_action_evidence_paths[-1],
            "message": "装配、保存和重开已通过；碰撞尚未评估。",
            "validationProfile": "demo",
            "assemblyStatus": "assembled",
            "collisionStatus": "not_evaluated",
            "validationEvidenceKind": "cad_save_reopen",
        }
    if profile != "engineering":
        raise AssemblyJobError(f"未知验证档位：{profile}")
    gate = hard_gate(job, step, output, previous)
    return {
        **gate,
        "validationProfile": "engineering",
        "assemblyStatus": "assembled" if gate.get("accepted") is True else "rejected",
        "collisionStatus": "passed" if gate.get("accepted") is True else "rejected",
        "validationEvidenceKind": "collision_hard_gate",
    }


def default_command_runner(command: list[str], timeout_seconds: float) -> Any:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_live_cad_step_specs(
    closure: dict[str, Any],
    *,
    required_tokens: set[str] | None = None,
) -> tuple[Path, dict[str, list[dict[str, str]]]]:
    steps = closure.get("steps") or []
    base = next((row for row in steps if row.get("moduleToken") == "A600"), None)
    if not base:
        raise AssemblyJobError("CAD执行目录缺少A600基座检查点。")
    base_path = Path(str(base.get("assemblyPath") or "")).resolve()
    if not base_path.is_file():
        raise AssemblyJobError(f"A600基座装配体不存在：{base_path}")

    specs: dict[str, list[dict[str, str]]] = {}
    for row in steps:
        token = str(row.get("moduleToken") or "")
        if token == "A600":
            continue
        if required_tokens is not None and token not in required_tokens:
            continue
        if token == "A100":
            directory = Path(str(row.get("assemblyPath") or "")).resolve().parent
            insertion_evidence = directory / (
                "step06_A600_A800_A180_A700_A300_A500_A100_V1.context-insert.result.json"
            )
            replacement = directory / "A100_WITH_A150_SLOT0_RIGID_V5_CLEAN.SLDASM"
            replacement_health_path = replacement.with_suffix(".replacement-result.json")
            prototype_health_path = (
                directory / "FL9A24D062A100.001.prototype-health-diagnostics.json"
            )
            evidence = _load(insertion_evidence) if insertion_evidence.is_file() else {}
            replacement_health = (
                _load(replacement_health_path) if replacement_health_path.is_file() else {}
            )
            graph_path = Path(str(evidence.get("effectiveGraphPath") or "")).resolve()
            target = str(evidence.get("targetModuleToken") or "")
            clean_replacement = (
                replacement_health.get("success") is True
                and replacement_health.get("finalOpenNeedsRegen") is False
                and (
                    replacement_health.get("finalRebuildState") or {}
                ).get("NeedsRebuild") is False
            )
            if (
                not graph_path.is_file()
                or not target
                or not replacement.is_file()
                or not prototype_health_path.is_file()
                or not clean_replacement
            ):
                raise AssemblyJobError(
                    "A100缺少插入有效图，或静态刚性替换体未通过无NeedsRegen重开门禁。"
                )
            specs[token] = [
                {
                    "actionKind": "context_incremental",
                    "effectiveGraphPath": str(graph_path),
                    "targetModuleToken": target,
                    "sourceEvidencePath": str(insertion_evidence),
                },
                {
                    "actionKind": "replace_top_level_and_set_rigid",
                    "componentSelector": "A100",
                    "replacementFilePath": str(replacement),
                    "sourceEvidencePath": str(replacement_health_path),
                    "baselineHealthPath": str(prototype_health_path),
                },
            ]
            continue
        evidence_values = row.get("evidencePaths") or [row.get("evidencePath")]
        actions = []
        for value in evidence_values:
            evidence_path = Path(str(value or "")).resolve()
            if not evidence_path.is_file():
                raise AssemblyJobError(f"{token}缺少CAD增量证据：{evidence_path}")
            evidence = _load(evidence_path)
            graph_path = Path(str(evidence.get("effectiveGraphPath") or "")).resolve()
            target = str(evidence.get("targetModuleToken") or "")
            if not graph_path.is_file() or not target:
                raise AssemblyJobError(f"{token}的CAD增量证据缺少有效图或目标实例。")
            actions.append(
                {
                    "actionKind": "context_incremental",
                    "effectiveGraphPath": str(graph_path),
                    "targetModuleToken": target,
                    "sourceEvidencePath": str(evidence_path),
                }
            )
        specs[token] = actions
    return base_path, specs


def live_cad_step_runner(
    *,
    store: DurableAssemblyJobStore,
    closure: dict[str, Any],
    workspace: Path,
    executable: Path,
    hard_gate: HardGate,
    timeout_seconds: float = 1800.0,
    command_runner: CommandRunner = default_command_runner,
    required_tokens: set[str] | None = None,
) -> StepRunner:
    """Build a runner that saves independent outputs and requires a hard gate."""
    base_path, specs = build_live_cad_step_specs(
        closure,
        required_tokens=required_tokens,
    )
    script = (workspace / "scripts/run_context_incremental_insert.py").resolve()
    replacement_script = (
        workspace / "scripts/replace_top_level_component_and_set_rigid.py"
    ).resolve()
    executable = executable.resolve()
    for required in (script, executable):
        if not required.is_file():
            raise AssemblyJobError(f"CAD执行依赖不存在：{required}")
    if any(
        action.get("actionKind") == "replace_top_level_and_set_rigid"
        for actions in specs.values()
        for action in actions
    ) and not replacement_script.is_file():
        raise AssemblyJobError(f"CAD执行依赖不存在：{replacement_script}")

    def run(
        job: dict[str, Any], step: dict[str, Any], previous: Path | None
    ) -> dict[str, Any]:
        token = str(step["moduleToken"])
        actions = specs.get(token)
        if not actions:
            raise AssemblyJobError(f"没有登记{token}的现场CAD动作。")
        working = store.root / str(job["jobId"]) / "cad-working"
        working.mkdir(parents=True, exist_ok=True)
        source = previous.resolve() if previous else base_path
        action_evidence: list[str] = []
        for index, action in enumerate(actions, start=1):
            suffix = f"attempt{step['attemptCount']}-action{index}"
            output = (working / f"{step['stepId']}-{suffix}.SLDASM").resolve()
            result_path = output.with_suffix(".context-insert.result.json")
            if action.get("actionKind") == "replace_top_level_and_set_rigid":
                command = [
                    sys.executable,
                    str(replacement_script),
                    "--source",
                    str(source),
                    "--output",
                    str(output),
                    "--component",
                    action["componentSelector"],
                    "--replacement",
                    action["replacementFilePath"],
                    "--result",
                    str(result_path),
                    "--baseline-health",
                    action["baselineHealthPath"],
                    "--exe",
                    str(executable),
                    "--timeout",
                    str(timeout_seconds),
                ]
            else:
                command = [
                    sys.executable,
                    str(script),
                    "--source",
                    str(source),
                    "--effective",
                    action["effectiveGraphPath"],
                    "--output",
                    str(output),
                    "--target",
                    action["targetModuleToken"],
                    "--result",
                    str(result_path),
                    "--exe",
                    str(executable),
                    "--timeout",
                    str(timeout_seconds),
                    "--direct-stdio",
                ]
            completed = command_runner(command, timeout_seconds + 60.0)
            return_code = int(getattr(completed, "returncode", 1))
            if return_code != 0 or not output.is_file() or not result_path.is_file():
                raise AssemblyJobError(
                    f"{token} CAD动作{index}失败；returnCode={return_code}; "
                    f"stderr={str(getattr(completed, 'stderr', ''))[-1000:]}"
                )
            result = _load(result_path)
            if result.get("success") is not True:
                raise AssemblyJobError(f"{token} CAD动作{index}未通过保存重开验证。")
            source = output
            action_evidence.append(str(result_path))

        gate = validate_cad_step(
            job=job,
            step=step,
            output=source,
            previous=previous,
            cad_action_evidence_paths=action_evidence,
            hard_gate=hard_gate,
        )
        return {
            "accepted": gate.get("accepted") is True,
            "assemblyPath": str(source),
            "evidencePath": gate.get("evidencePath"),
            "message": gate.get("message"),
            "cadActionEvidencePaths": action_evidence,
            "validationProfile": gate.get("validationProfile"),
            "assemblyStatus": gate.get("assemblyStatus"),
            "collisionStatus": gate.get("collisionStatus"),
            "validationEvidenceKind": gate.get("validationEvidenceKind"),
        }

    return run
