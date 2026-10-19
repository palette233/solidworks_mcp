from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.global_cad_driving_evidence import (  # noqa: E402
    assess_driving_insert_evidence,
)


JOB_ID = "project03-job-cea5e3c2ac90"
JOB_ROOT = ROOT / "demo/global_assembly_contexts/manifest_jobs" / JOB_ID
CONTEXT_ROOT = ROOT / (
    "demo/global_assembly_contexts/project03-aa00-ae00-ad00-v12-driving-v1"
)
RELEASE_ID = "relation-v12-project03-ae00-ad00-driving-20261011"


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON根节点必须是对象：{path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    job = _read(JOB_ROOT / "job.json")
    compile_report = _read(CONTEXT_ROOT / "report.json")
    command_audit = _read(CONTEXT_ROOT / "command-audit-summary.json")
    steps = job.get("steps") or []
    if len(steps) != 2:
        raise ValueError("Project03 v12必须正好包含两个累计CAD包。")
    step_rows = []
    assessments = []
    for step in steps:
        checkpoint = step.get("checkpoint") or {}
        evidence_path = Path(str(checkpoint.get("evidencePath") or ""))
        run_dir = evidence_path.parent
        cad_result_path = run_dir / "cad-result.json"
        envelope_path = run_dir / "execution-envelope.json"
        cad_result = _read(cad_result_path)
        envelope = _read(envelope_path)
        assessment = assess_driving_insert_evidence(
            cad_result,
            expected_mate_count=3,
        )
        assessments.append(assessment)
        step_rows.append(
            {
                "stepId": step["stepId"],
                "moduleToken": step["moduleToken"],
                "status": step["status"],
                "attemptDurationSeconds": (step.get("attempts") or [{}])[-1].get(
                    "durationSeconds"
                ),
                "cadDurationSeconds": cad_result.get("durationSeconds"),
                "phaseDurationsSeconds": (cad_result.get("toolResult") or {}).get(
                    "PhaseDurationsSeconds"
                ),
                "inputAssemblyPath": checkpoint.get("inputAssemblyPath"),
                "assemblyPath": checkpoint.get("assemblyPath"),
                "releaseAuthorityStatus": (
                    envelope.get("releaseAuthority") or {}
                ).get("status"),
                "cadAssessment": assessment,
                "cadResultPath": str(cad_result_path),
                "executionEnvelopePath": str(envelope_path),
            }
        )
    first_output = str((steps[0].get("checkpoint") or {}).get("assemblyPath") or "")
    second_input = str((steps[1].get("checkpoint") or {}).get("inputAssemblyPath") or "")
    final_path = Path(
        str((steps[1].get("checkpoint") or {}).get("assemblyPath") or "")
    )
    checks = {
        "compileReady": (
            compile_report.get("status") == "ready_for_generic_cad_executor"
            and compile_report.get("cadPacketCount") == 2
        ),
        "commandAuditComplete": (
            command_audit.get("mappedCommandCount")
            == command_audit.get("commandCount")
        ),
        "jobSucceeded": (
            job.get("status") == "succeeded"
            and job.get("assemblyStatus") == "assembled"
        ),
        "releaseBound": (
            ((job.get("plan") or {}).get("relationReleaseBinding") or {}).get(
                "releaseId"
            )
            == RELEASE_ID
        ),
        "twoPacketsCommitted": all(
            row.get("status") == "succeeded" and row.get("checkpoint")
            for row in steps
        ),
        "packet2ConsumesPacket1Checkpoint": (
            first_output != "" and second_input == first_output
        ),
        "bothCheckpointCadRunsPassed": all(
            row.get("checkpointPassed") is True for row in assessments
        ),
        "finalAssemblySaved": final_path.is_file(),
    }
    report = {
        "schemaVersion": "project03-ae00-ad00-durable-closure/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if all(checks.values()) else "blocked",
        "jobId": JOB_ID,
        "releaseId": RELEASE_ID,
        "checks": checks,
        "naturalLanguageCommands": compile_report.get("naturalLanguageCommands"),
        "steps": step_rows,
        "totalExecutionDurationSeconds": job.get("executionDurationSeconds"),
        "finalAssemblyPath": str(final_path),
        "finalAssemblySha256": _sha256(final_path) if final_path.is_file() else None,
        "collisionStatus": "not_evaluated",
        "statement": (
            "AE00与AD00均由项目无关持久执行器独立插入；第二包严格消费第一包"
            "检查点，两包均通过非锚点、完全约束及保存重开门禁。"
        ),
    }
    output = CONTEXT_ROOT / "durable-executor-closure.json"
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
