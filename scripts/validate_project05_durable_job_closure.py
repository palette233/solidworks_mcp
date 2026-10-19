from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


WORKSPACE = Path(__file__).resolve().parents[1]
BACKEND_SRC = WORKSPACE / "apps" / "demo-backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.ordered_assembly_planner import preview_ordered_assembly
from demo_backend.semantic_assembly_jobs import (
    AssemblyJobExecutor,
    AssemblyJobError,
    DurableAssemblyJobStore,
    validated_artifact_step_runner,
)


REQUIREMENT = (
    "项目05：先添加D000，再添加K000，然后添加F000，接着添加M000，"
    "再添加G000，然后添加N000，接着添加P000，最后添加B000。"
)
CLOSURE_PATH = (
    WORKSPACE
    / "demo"
    / "semantic_ports"
    / "project05_ordered_jobs"
    / "latest_ordered_closure.json"
)
OUTPUT_ROOT = (
    WORKSPACE
    / "demo"
    / "semantic_ports"
    / "project05_ordered_jobs"
    / "functional_closure"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_closure() -> dict[str, Any]:
    payload = json.loads(CLOSURE_PATH.read_text(encoding="utf-8"))
    if payload.get("success") is not True:
        raise AssemblyJobError("项目05有序装配闭包未通过。")
    return payload


def event_types(store: DurableAssemblyJobStore, job_id: str) -> list[str]:
    path = store.root / job_id / "events.jsonl"
    return [
        json.loads(line)["eventType"]
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> int:
    closure = load_closure()
    plan = preview_ordered_assembly("project05", REQUIREMENT)["plan"]
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    root = OUTPUT_ROOT / run_id
    root.mkdir(parents=True, exist_ok=True)
    validated_runner = validated_artifact_step_runner(closure, WORKSPACE)

    success_store = DurableAssemblyJobStore(root / "success")
    success_job = success_store.create(
        plan,
        execution_mode="validated_artifact_replay",
        idempotency_key=f"project05-real-success-{run_id}",
    )
    success = AssemblyJobExecutor(success_store, validated_runner).run(
        success_job["jobId"]
    )

    pause_store = DurableAssemblyJobStore(root / "pause-resume")
    pause_job = pause_store.create(
        plan,
        execution_mode="validated_artifact_replay",
        idempotency_key=f"project05-real-pause-{run_id}",
    )
    paused_once = False

    def pausing_runner(job: dict[str, Any], step: dict[str, Any], previous: Path | None):
        nonlocal paused_once
        result = validated_runner(job, step, previous)
        if not paused_once:
            paused_once = True
            pause_store.request_pause(job["jobId"])
        return result

    paused = AssemblyJobExecutor(pause_store, pausing_runner).run(pause_job["jobId"])
    pause_store.prepare_resume(pause_job["jobId"])
    resumed = AssemblyJobExecutor(pause_store, validated_runner).run(
        pause_job["jobId"]
    )

    rollback_store = DurableAssemblyJobStore(root / "failure-resume")
    rollback_job = rollback_store.create(
        plan,
        execution_mode="validated_artifact_replay",
        idempotency_key=f"project05-real-rollback-{run_id}",
    )

    def failing_runner(job: dict[str, Any], step: dict[str, Any], previous: Path | None):
        if step["moduleToken"] == "K000":
            raise AssemblyJobError("受控门禁失败：用于验证回滚到D000检查点。")
        return validated_runner(job, step, previous)

    failed = AssemblyJobExecutor(rollback_store, failing_runner).run(
        rollback_job["jobId"]
    )
    rollback_store.prepare_resume(rollback_job["jobId"])
    recovered = AssemblyJobExecutor(rollback_store, validated_runner).run(
        rollback_job["jobId"]
    )

    expected_tokens = ["D000", "K000", "F000", "M000", "G000", "N000", "P000", "B000"]
    checks = {
        "fullChainSucceeded": success["status"] == "succeeded",
        "fullChainTokensMatch": [row["moduleToken"] for row in success["steps"]]
        == expected_tokens,
        "fullChainFinalArtifactExists": Path(
            success["lastCommittedCheckpoint"]["assemblyPath"]
        ).is_file(),
        "fullChainEvidenceManifestExists": (
            success_store.root / success_job["jobId"] / "evidence-manifest.json"
        ).is_file(),
        "pauseReached": paused["status"] == "paused",
        "pauseCheckpointIsD000": paused["lastCommittedCheckpoint"]["moduleToken"]
        == "D000",
        "pauseResumeSucceeded": resumed["status"] == "succeeded",
        "controlledFailureReached": failed["status"] == "failed",
        "rollbackCheckpointIsD000": (
            failed.get("rollback") or {}
        ).get("checkpoint", {}).get("moduleToken")
        == "D000",
        "failureResumeSucceeded": recovered["status"] == "succeeded",
        "failedStepRetriedOnce": recovered["steps"][1]["attemptCount"] == 2,
    }
    report = {
        "schemaVersion": "project05-durable-job-functional-closure/v1",
        "runId": run_id,
        "generatedAt": utc_now(),
        "projectId": "project05",
        "executionMode": "validated_artifact_replay",
        "realCadRerunPerformed": False,
        "sourceClosurePath": str(CLOSURE_PATH),
        "sourceArtifactsArePreviouslyCadValidated": True,
        "requirement": REQUIREMENT,
        "checks": checks,
        "success": all(checks.values()),
        "scenarios": {
            "fullChain": {
                "jobId": success_job["jobId"],
                "status": success["status"],
                "events": event_types(success_store, success_job["jobId"]),
                "jobPath": str(success_store.root / success_job["jobId"] / "job.json"),
            },
            "pauseResume": {
                "jobId": pause_job["jobId"],
                "pausedStatus": paused["status"],
                "finalStatus": resumed["status"],
                "events": event_types(pause_store, pause_job["jobId"]),
                "jobPath": str(pause_store.root / pause_job["jobId"] / "job.json"),
            },
            "failureRollbackResume": {
                "jobId": rollback_job["jobId"],
                "failedStatus": failed["status"],
                "rollback": failed.get("rollback"),
                "finalStatus": recovered["status"],
                "events": event_types(rollback_store, rollback_job["jobId"]),
                "jobPath": str(rollback_store.root / rollback_job["jobId"] / "job.json"),
            },
        },
        "boundary": (
            "本报告验证自然语言计划绑定、持久化任务、检查点、暂停恢复和失败回滚；"
            "它复用此前真实SolidWorks闭环产物，不代表本次重新驱动SolidWorks。"
        ),
    }
    output = root / "project05_durable_job_functional_closure.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    latest = OUTPUT_ROOT / "latest.json"
    latest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"success": report["success"], "output": str(output)}, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
