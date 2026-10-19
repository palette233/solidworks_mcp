"""Build a compact, user-facing summary for one durable CAD manifest job."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from .assembly_user_failure import build_assembly_user_failure


SCHEMA = "global-manifest-job-user-summary/v1"


class GlobalManifestJobUserSummaryError(ValueError):
    pass


def _elapsed_seconds(started_at: Any, completed_at: Any) -> float | None:
    if not started_at or not completed_at:
        return None
    try:
        started = datetime.fromisoformat(str(started_at).replace("Z", "+00:00"))
        completed = datetime.fromisoformat(
            str(completed_at).replace("Z", "+00:00")
        )
    except ValueError:
        return None
    return round((completed - started).total_seconds(), 6)


def build_global_manifest_job_user_summary(
    job: dict[str, Any],
    *,
    cad_results_by_step: dict[str, dict[str, Any]],
    preflight: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Condense command, semantic relation, CAD and timing evidence."""

    if job.get("schemaVersion") != "ordered-assembly-job/v2":
        raise GlobalManifestJobUserSummaryError("不支持的持久装配作业版本。")
    plan = job.get("plan") or {}
    audit = (plan.get("commandAudit") or {}).get("payload") or {}
    commands = audit.get("commands") or []
    if not commands:
        raise GlobalManifestJobUserSummaryError("作业缺少自然语言命令审计。")

    instances: dict[str, dict[str, Any]] = {}
    connections: dict[str, dict[str, Any]] = {}
    for command in commands:
        for instance in command.get("moduleInstances") or []:
            instances[str(instance.get("instanceId") or "")] = deepcopy(instance)
        for connection in command.get("connections") or []:
            connections[str(connection.get("connectionId") or "")] = deepcopy(
                connection
            )

    step_rows = []
    all_cad_checks_passed = True
    for step in job.get("steps") or []:
        step_id = str(step.get("stepId") or "")
        result = cad_results_by_step.get(step_id) or {}
        tool = result.get("toolResult") or {}
        requested = int(tool.get("RequestedMateCount") or 0)
        created = int(tool.get("CreatedMateCount") or 0)
        cad_passed = bool(
            step.get("status") == "succeeded"
            and result.get("success") is True
            and tool.get("Success") is True
            and requested > 0
            and created == requested
            and tool.get("TargetConstraintStateAccepted") is True
            and tool.get("MateSolveClean") is True
            and tool.get("Reopened") is True
            and tool.get("ReopenedMateParametersMatch") is True
        )
        all_cad_checks_passed = all_cad_checks_passed and cad_passed
        checkpoint = step.get("checkpoint") or {}
        step_rows.append(
            {
                "stepId": step_id,
                "moduleToken": step.get("moduleToken"),
                "operation": step.get("operation"),
                "status": step.get("status"),
                "requestedMateCount": requested,
                "createdMateCount": created,
                "targetFullyConstrained": tool.get("TargetFullyConstrained"),
                "targetConstraintStateAccepted": tool.get(
                    "TargetConstraintStateAccepted"
                ),
                "mateSolveClean": tool.get("MateSolveClean"),
                "saveCloseReopenPassed": bool(
                    tool.get("Reopened") is True
                    and tool.get("ReopenedMateParametersMatch") is True
                ),
                "cadPassed": cad_passed,
                "assemblyPath": checkpoint.get("assemblyPath"),
                "stepDurationSeconds": (
                    (step.get("attempts") or [{}])[-1].get("durationSeconds")
                ),
                "cadAdapterDurationSeconds": result.get("durationSeconds"),
                "baseWrapperCacheStatus": (
                    (checkpoint.get("timingBreakdown") or {}).get(
                        "baseWrapperCacheStatus"
                    )
                ),
                "estimatedPreparationSecondsAvoided": (
                    (checkpoint.get("timingBreakdown") or {}).get(
                        "estimatedPreparationSecondsAvoided"
                    )
                ),
            }
        )

    release = plan.get("relationReleaseBinding") or {}
    compile_timing = (preflight or {}).get("naturalLanguageCompilation") or {}
    overall_passed = bool(
        job.get("status") == "succeeded"
        and job.get("assemblyStatus") == "assembled"
        and step_rows
        and all_cad_checks_passed
    )
    summary_blockers: list[Any] = []
    summary_blockers.extend(plan.get("blockers") or [])
    summary_blockers.extend(audit.get("blockers") or [])
    failed_step = next(
        (row for row in job.get("steps") or [] if row.get("status") == "failed"),
        None,
    )
    if failed_step is not None:
        summary_blockers.extend(failed_step.get("blockers") or [])
    raw_error = str(
        job.get("error") or (failed_step or {}).get("error") or ""
    ).strip()
    user_failure = (
        None
        if overall_passed
        else build_assembly_user_failure(
            blockers=summary_blockers,
            status="cad_execution_failed",
            raw_error=raw_error,
            stage="cad_execution",
        )
    )
    return {
        "schemaVersion": SCHEMA,
        "status": "passed" if overall_passed else "not_passed",
        "jobId": job.get("jobId"),
        "contextId": plan.get("contextId"),
        "naturalLanguageCommands": [
            str(row.get("requirement") or "") for row in commands
        ],
        "moduleInstances": sorted(
            instances.values(), key=lambda row: str(row.get("instanceId") or "")
        ),
        "connections": [
            {
                "connectionId": row.get("connectionId"),
                "globalTemplateId": row.get("globalTemplateId"),
                "purpose": row.get("purpose"),
                "sourceInstanceId": row.get("instanceAId"),
                "sourcePortId": (row.get("portA") or {}).get("globalPortId"),
                "targetInstanceId": row.get("instanceBId"),
                "targetPortId": (row.get("portB") or {}).get("globalPortId"),
                "expectedResidualDof": row.get(
                    "singleTemplateExpectedResidualDof"
                ),
                "cadPacketId": row.get("cadPacketId"),
            }
            for row in sorted(
                connections.values(),
                key=lambda item: str(item.get("connectionId") or ""),
            )
        ],
        "releaseBinding": {
            "releaseId": release.get("releaseId"),
            "catalogDigest": release.get("catalogDigest"),
            "authorizedDrivingTemplateIds": deepcopy(
                release.get("authorizedDrivingTemplateIds") or []
            ),
        },
        "cadSteps": step_rows,
        "resultAssemblyPath": (
            (job.get("lastCommittedCheckpoint") or {}).get("assemblyPath")
            or (step_rows[-1].get("assemblyPath") if step_rows else None)
        ),
        "timingSeconds": {
            "naturalLanguageCompilation": compile_timing.get("totalSeconds"),
            "jobExecution": job.get("executionDurationSeconds")
            or _elapsed_seconds(job.get("startedAt"), job.get("completedAt")),
        },
        "collisionStatus": job.get("collisionStatus") or "not_evaluated",
        "userFailureExplanation": user_failure,
        "claims": {
            "naturalLanguageMapped": audit.get("mappedCommandCount")
            == audit.get("commandCount"),
            "releasedTemplateAuthorized": (
                (plan.get("releaseAuthority") or {}).get("status") == "verified"
            ),
            "cadLifecyclePassed": all_cad_checks_passed,
            "collisionOrBrepPassed": False,
        },
    }


def render_global_manifest_job_user_summary_markdown(
    summary: dict[str, Any],
) -> str:
    if summary.get("schemaVersion") != SCHEMA:
        raise GlobalManifestJobUserSummaryError("不支持的用户摘要版本。")
    lines = [
        f"# 装配任务摘要：{summary.get('contextId')}",
        "",
        f"- 结果：`{summary.get('status')}`",
        f"- 作业：`{summary.get('jobId')}`",
        f"- 发布：`{(summary.get('releaseBinding') or {}).get('releaseId')}`",
        f"- 输出装配体：`{summary.get('resultAssemblyPath')}`",
        f"- 碰撞/B-rep：`{summary.get('collisionStatus')}`",
        "",
        "## 自然语言命令",
        "",
    ]
    lines.extend(
        f"{index}. {command}"
        for index, command in enumerate(
            summary.get("naturalLanguageCommands") or [], start=1
        )
    )
    lines.extend(["", "## 语义连接", ""])
    for row in summary.get("connections") or []:
        lines.extend(
            [
                f"- 模板：`{row.get('globalTemplateId')}`",
                f"  - 源端口：`{row.get('sourcePortId')}`",
                f"  - 目标端口：`{row.get('targetPortId')}`",
                f"  - 预期剩余自由度：`{row.get('expectedResidualDof')}`",
            ]
        )
    lines.extend(["", "## CAD结果", ""])
    for row in summary.get("cadSteps") or []:
        lines.append(
            "- "
            f"{row.get('moduleToken')}: {row.get('createdMateCount')}/"
            f"{row.get('requestedMateCount')}配合，"
            f"完全约束={row.get('targetFullyConstrained')}，"
            f"保存重开={row.get('saveCloseReopenPassed')}，"
            f"耗时={row.get('stepDurationSeconds')} s"
        )
    failure = summary.get("userFailureExplanation")
    if failure:
        lines.extend(
            [
                "",
                "## 未通过原因",
                "",
                f"- 原因码：`{failure.get('reasonCode')}`",
                f"- 说明：{failure.get('summary')}",
                f"- 原因：{failure.get('explanation')}",
                "- 建议：",
            ]
        )
        lines.extend(
            f"  - {action}" for action in failure.get("suggestedActions") or []
        )
    lines.extend(
        [
            "",
            "> 本摘要不包含实体干涉或B-rep通过声明；"
            "`not_evaluated`表示尚未执行该项工程验证。",
            "",
        ]
    )
    return "\n".join(lines)


def write_global_manifest_job_user_summary(
    job: dict[str, Any], directory: Path
) -> dict[str, Any]:
    """Write compact evidence without changing the durable job outcome."""

    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    preflight_path = directory / "preflight.json"
    preflight = None
    if preflight_path.is_file():
        try:
            preflight = json.loads(preflight_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            preflight = None

    cad_results: dict[str, dict[str, Any]] = {}
    for step in job.get("steps") or []:
        for value in (step.get("checkpoint") or {}).get(
            "cadActionEvidencePaths"
        ) or []:
            path = Path(str(value))
            if path.name != "cad-result.json" or not path.is_file():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict):
                cad_results[str(step.get("stepId") or "")] = payload
            break

    try:
        summary = build_global_manifest_job_user_summary(
            job,
            cad_results_by_step=cad_results,
            preflight=preflight,
        )
    except GlobalManifestJobUserSummaryError as exc:
        summary = {
            "schemaVersion": SCHEMA,
            "status": "unavailable",
            "jobId": job.get("jobId"),
            "contextId": (job.get("plan") or {}).get("contextId"),
            "naturalLanguageCommands": [],
            "moduleInstances": [],
            "connections": [],
            "releaseBinding": {},
            "cadSteps": [],
            "resultAssemblyPath": None,
            "timingSeconds": {},
            "collisionStatus": job.get("collisionStatus") or "not_evaluated",
            "userFailureExplanation": build_assembly_user_failure(
                status="failed",
                raw_error=str(exc),
                stage="summary_generation",
            ),
            "claims": {
                "naturalLanguageMapped": False,
                "releasedTemplateAuthorized": False,
                "cadLifecyclePassed": False,
                "collisionOrBrepPassed": False,
            },
            "blockers": [str(exc)],
        }

    json_path = directory / "user-summary.json"
    markdown_path = directory / "user-summary.md"
    json_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(
        render_global_manifest_job_user_summary_markdown(summary),
        encoding="utf-8",
    )
    return {
        "status": summary.get("status"),
        "jsonPath": str(json_path),
        "markdownPath": str(markdown_path),
    }
