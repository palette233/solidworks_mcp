"""Read-only completion audit for the six-role station-closure Goal.

The audit deliberately does not run SolidWorks or reinterpret a failed CAD
result.  It binds the catalog/gap baseline, the ordered closure program and the
three current acceptance chains, then reports exactly which evidence is still
missing.  This keeps ``ready_not_started`` and historical evidence from being
mistaken for completion of the current Goal.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from time import perf_counter
from typing import Any

from .staged_chain_execution_batch import (
    build_staged_chain_execution_batch_status,
)


EXPECTED_PHASES = {
    "saved_output_readonly_postchecks": 15,
    "fresh_nonprototype_cad_validations": 2,
    "scanner_current_context_chains": 6,
    "new_six_role_cumulative_chain": 3,
}
EXPECTED_INTENTS = {
    "normal": {
        "sourceChainId": "station-aa00-six-role-current-v1",
        "stageOrder": [
            "s01-transport",
            "s02-scanner",
            "s03-calibration",
            "s04-cleaning",
            "s05-cup",
        ],
    },
    "reordered": {
        "sourceChainId": "station-aa00-six-role-reordered-current-v1",
        "stageOrder": [
            "s03-calibration",
            "s01-transport",
            "s04-cleaning",
            "s05-cup",
            "s02-scanner",
        ],
    },
    "positionVariant": {
        "sourceChainId": "station-aa00-six-role-plus10mm-current-v2",
        "stageOrder": [
            "s01-transport",
            "s02-scanner",
            "s03-calibration",
            "s04-cleaning",
            "s05-cup",
        ],
    },
}
EXPECTED_STAGE_ROLES = {
    "s01-transport": "Transport",
    "s02-scanner": "Scanner",
    "s03-calibration": "Calibration",
    "s04-cleaning": "CleaningWeighing",
    "s05-cup": "WasteCup",
}
PROTOTYPE_PROXY_ROLES = {"Scanner", "CleaningWeighing", "WasteCup"}


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _scoped(workspace: Path, path: Path) -> Path:
    resolved = path.resolve() if path.is_absolute() else (workspace / path).resolve()
    resolved.relative_to(workspace)
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    return resolved


def _relative(workspace: Path, path: Path) -> str:
    return path.resolve().relative_to(workspace).as_posix()


def _entry(
    check_id: str,
    passed: bool,
    summary: str,
    *,
    evidence: list[str] | None = None,
    missing: list[str] | None = None,
    failed: bool = False,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "checkId": check_id,
        "status": "passed" if passed else ("failed" if failed else "incomplete"),
        "summary": summary,
        "evidence": evidence or [],
        "missingEvidence": missing or [],
        "details": details or {},
    }


def _hash_binding_matches(workspace: Path, binding: dict[str, Any]) -> bool:
    path = _scoped(workspace, Path(str(binding.get("path") or "")))
    return _sha256(path) == binding.get("sha256")


def _find_chain(
    chain_sources: list[dict[str, Any]], source_chain_id: str
) -> dict[str, Any] | None:
    return next(
        (
            row
            for row in chain_sources
            if row.get("sourceChainId") == source_chain_id
        ),
        None,
    )


def _stage_rows(attempt: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("stageId")): row
        for row in attempt.get("stages") or []
        if row.get("stageId")
    }


def _positive(value: Any) -> bool:
    return isinstance(value, (int, float)) and float(value) > 0.0


def build_six_role_goal_acceptance_audit(
    workspace: Path,
    coverage_path: Path,
    gap_queue_path: Path,
    closure_program_status_path: Path,
    acceptance_batch_report_path: Path,
    failure_plan_path: Path,
) -> dict[str, Any]:
    """Build a strict, read-only completion audit for the active Goal."""

    clock = perf_counter()
    workspace = workspace.resolve()
    paths = {
        "coverage": _scoped(workspace, coverage_path),
        "gapQueue": _scoped(workspace, gap_queue_path),
        "closureProgram": _scoped(workspace, closure_program_status_path),
        "acceptanceBatch": _scoped(workspace, acceptance_batch_report_path),
        "failurePlan": _scoped(workspace, failure_plan_path),
    }
    coverage = _read(paths["coverage"])
    gap = _read(paths["gapQueue"])
    closure = _read(paths["closureProgram"])
    batch = _read(paths["acceptanceBatch"])
    failure_plan = _read(paths["failurePlan"])
    checks: list[dict[str, Any]] = []

    coverage_summary = coverage.get("summary") or {}
    coverage_ok = (
        coverage.get("schemaVersion") == "six-role-station-coverage/v1"
        and coverage_summary.get("exactPairCount") == 68
        and len(coverage.get("pairs") or []) == 68
        and sum((coverage_summary.get("roleCounts") or {}).values()) == 17
        and coverage_summary.get("crossProjectPairCount") == 51
    )
    checks.append(
        _entry(
            "coverage_catalog_integrity",
            coverage_ok,
            "六类、四基座的68个精确配对目录完整。",
            evidence=[_relative(workspace, paths["coverage"])],
            missing=[] if coverage_ok else ["有效的68项六类工位覆盖目录"],
            failed=not coverage_ok,
            details={
                "exactPairCount": coverage_summary.get("exactPairCount"),
                "configuredCount": coverage_summary.get(
                    "configuredStationRulePairCount"
                ),
                "strictValidatedCount": coverage_summary.get(
                    "validatedStationRulePairCount"
                ),
                "crossProjectPairCount": coverage_summary.get(
                    "crossProjectPairCount"
                ),
            },
        )
    )

    gap_sources = gap.get("sourceFiles") or []
    coverage_binding = next(
        (
            item
            for item in gap_sources
            if Path(str(item.get("path") or "")).name == paths["coverage"].name
        ),
        None,
    )
    gap_summary = gap.get("summary") or {}
    gap_ok = (
        gap.get("schemaVersion") == "station-gap-batch-preparation/v1"
        and coverage_binding is not None
        and _hash_binding_matches(workspace, coverage_binding)
        and gap_summary.get("pendingPairCount") == len(gap.get("queue") or [])
        and sum((gap_summary.get("workClassCounts") or {}).values())
        == gap_summary.get("pendingPairCount")
    )
    checks.append(
        _entry(
            "gap_report_binds_current_coverage",
            gap_ok,
            "缺口报告与当前覆盖目录摘要绑定且工作分类守恒。",
            evidence=[_relative(workspace, paths["gapQueue"])],
            missing=[] if gap_ok else ["与当前覆盖摘要一致的缺口队列"],
            failed=not gap_ok,
            details={
                "pendingPairCount": gap_summary.get("pendingPairCount"),
                "workClassCounts": gap_summary.get("workClassCounts"),
                "pairClassCounts": gap_summary.get("pairClassCounts"),
            },
        )
    )

    phase_by_id = {
        str(row.get("phaseId")): row for row in closure.get("phases") or []
    }
    phase_details: dict[str, Any] = {}
    incomplete_phases: list[str] = []
    phase_shape_ok = set(phase_by_id) == set(EXPECTED_PHASES)
    for phase_id, expected_total in EXPECTED_PHASES.items():
        row = phase_by_id.get(phase_id) or {}
        complete = (
            row.get("totalCount") == expected_total
            and row.get("completedCount") == expected_total
            and row.get("status") == "complete"
        )
        phase_details[phase_id] = {
            "expectedTotal": expected_total,
            "totalCount": row.get("totalCount"),
            "completedCount": row.get("completedCount"),
            "status": row.get("status"),
            "strictPassedCount": row.get("strictPassedCount"),
            "deferredCount": row.get("deferredCount"),
            "complete": complete,
        }
        if not complete:
            incomplete_phases.append(phase_id)
    closure_complete = (
        phase_shape_ok
        and not incomplete_phases
        and closure.get("status") == "complete"
        and closure.get("nextAction") is None
    )
    checks.append(
        _entry(
            "ordered_closure_program_complete",
            closure_complete,
            "15项历史后检工作均已处理（严格通过或以缺失源引用明确延期），随后2项新CAD、6条扫描链和3条六类验收链依次完成。",
            evidence=[_relative(workspace, paths["closureProgram"])],
            missing=[f"完成阶段：{value}" for value in incomplete_phases],
            failed=not phase_shape_ok,
            details=phase_details,
        )
    )

    batch_shape_ok = (
        batch.get("schemaVersion")
        == "staged-chain-registry-recompilation-batch/v1"
        and batch.get("chainCount") == 3
        and batch.get("readyCount") == 3
        and batch.get("cadStarted") is False
        and len(batch.get("chains") or []) == 3
    )
    batch_errors: list[str] = []
    chain_sources = batch.get("chains") or []
    for row in chain_sources:
        try:
            for path_key, hash_key in (
                ("sourceRequestPath", "sourceRequestSha256"),
                ("generatedRequestPath", "generatedRequestSha256"),
                ("compilationPath", "compilationSha256"),
            ):
                bound_path = _scoped(workspace, Path(str(row.get(path_key) or "")))
                if _sha256(bound_path) != row.get(hash_key):
                    batch_errors.append(f"{path_key}摘要不匹配：{bound_path}")
            if row.get("status") != "ready_not_started":
                batch_errors.append(f"链不是编译就绪状态：{row.get('generatedChainId')}")
            if row.get("targetStationPreflightPassed") is not True:
                batch_errors.append(f"工位预检未通过：{row.get('generatedChainId')}")
            if row.get("cadStarted") is not False:
                batch_errors.append(f"编译批次错误宣称已启动CAD：{row.get('generatedChainId')}")
        except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
            batch_errors.append(str(exc))
    batch_ok = batch_shape_ok and not batch_errors
    checks.append(
        _entry(
            "acceptance_batch_integrity",
            batch_ok,
            "正常、变序和位置参数变化三条当前规则链均有不可变编译证据。",
            evidence=[_relative(workspace, paths["acceptanceBatch"])],
            missing=batch_errors,
            failed=not batch_ok,
            details={
                "chainCount": batch.get("chainCount"),
                "readyCount": batch.get("readyCount"),
                "compileDurationSeconds": batch.get("durationSeconds"),
            },
        )
    )

    intent_details: dict[str, Any] = {}
    intent_errors: list[str] = []
    role_scope_ok = True
    for intent, expected in EXPECTED_INTENTS.items():
        row = _find_chain(chain_sources, expected["sourceChainId"])
        if row is None:
            intent_errors.append(f"缺少{intent}链")
            continue
        request_path = _scoped(workspace, Path(row["sourceRequestPath"]))
        request = _read(request_path)
        steps = request.get("steps") or []
        order = [str(step.get("stageId")) for step in steps]
        roles = [str(step.get("moduleRole")) for step in steps]
        explicit_scope = {
            str(step.get("moduleRole"))
            for step in steps
            if step.get("allowPrototypeEstimate") is True
        }
        projects = {
            str((step.get("moduleSelection") or {}).get("projectId"))
            for step in steps
        }
        projects.add(str((request.get("baseSelection") or {}).get("projectId")))
        current_ok = (
            order == expected["stageOrder"]
            and request.get("allowPrototypeEstimate") is None
            and explicit_scope == PROTOTYPE_PROXY_ROLES
            and roles == [EXPECTED_STAGE_ROLES[stage_id] for stage_id in order]
            and projects == {"project01", "project03", "project05"}
            and (request.get("baseSelection") or {}).get("moduleToken") == "AA00"
            and all(
                (step.get("moduleSelection") or {}).get("confirmed") is True
                for step in steps
            )
        )
        role_scope_ok = role_scope_ok and current_ok
        if not current_ok:
            intent_errors.append(f"{intent}链顺序、角色、项目或代理授权不符合验收定义")
        intent_details[intent] = {
            "sourceRequestPath": _relative(workspace, request_path),
            "stageOrder": order,
            "roles": roles,
            "projects": sorted(projects),
            "prototypeProxyScopeRoles": sorted(explicit_scope),
            "passed": current_ok,
        }
    checks.append(
        _entry(
            "three_chain_intents_and_scoped_authority",
            role_scope_ok and len(intent_details) == 3,
            "三条链覆盖正常顺序、依赖合法变序和位置变化，原型代理授权仅限工艺后检阶段。",
            evidence=[item["sourceRequestPath"] for item in intent_details.values()],
            missing=intent_errors,
            failed=bool(intent_errors),
            details=intent_details,
        )
    )

    nonprototype_errors: list[str] = []
    station_plans: dict[tuple[str, str], dict[str, Any]] = {}
    planning_durations: list[float] = []
    for row in chain_sources:
        intent_id = str(row.get("sourceChainId"))
        compilation_path = _scoped(workspace, Path(row["compilationPath"]))
        compilation = _read(compilation_path)
        chain_path = _scoped(workspace, Path(str(compilation.get("chainPath") or "")))
        chain = _read(chain_path)
        output_root = compilation_path.parent
        for stage in chain.get("stages") or []:
            stage_id = str(stage.get("stageId"))
            plan_path = output_root / "station-preparation" / stage_id / "station-plan.json"
            if not plan_path.is_file():
                nonprototype_errors.append(f"缺少工位计划：{intent_id}/{stage_id}")
                continue
            plan = _read(plan_path)
            station_plans[(intent_id, stage_id)] = plan
            if plan.get("sourceWorldPoseCopied") is not False:
                nonprototype_errors.append(f"来源世界位姿未明确禁用：{intent_id}/{stage_id}")
            timing = plan.get("timing") or {}
            if _positive(timing.get("durationSeconds")):
                planning_durations.append(float(timing["durationSeconds"]))
            else:
                nonprototype_errors.append(f"缺少规划耗时：{intent_id}/{stage_id}")
    nonprototype_ok = not nonprototype_errors and len(station_plans) == 15
    checks.append(
        _entry(
            "nonprototype_planning_and_timing",
            nonprototype_ok,
            "15个阶段均明确禁用来源世界位姿复制并记录规划耗时。",
            evidence=[_relative(workspace, paths["acceptanceBatch"])],
            missing=nonprototype_errors,
            failed=bool(nonprototype_errors),
            details={
                "stagePlanCount": len(station_plans),
                "planningDurationSeconds": sum(planning_durations),
            },
        )
    )

    normal_id = EXPECTED_INTENTS["normal"]["sourceChainId"]
    variant_id = EXPECTED_INTENTS["positionVariant"]["sourceChainId"]
    normal_position = (
        station_plans.get((normal_id, "s04-cleaning"), {}).get(
            "effectivePositionParametersMeters"
        )
        or {}
    )
    variant_position = (
        station_plans.get((variant_id, "s04-cleaning"), {}).get(
            "effectivePositionParametersMeters"
        )
        or {}
    )
    position_delta = {
        key: (
            float(variant_position[key]) - float(normal_position[key])
            if key in normal_position and key in variant_position
            else None
        )
        for key in ("longitudinal", "lateral", "supportGap")
    }
    position_ok = (
        position_delta["longitudinal"] is not None
        and abs(position_delta["longitudinal"] - 0.01) <= 1e-9
        and abs(position_delta["lateral"] or 0.0) <= 1e-9
        and abs(position_delta["supportGap"] or 0.0) <= 1e-9
        and station_plans.get((variant_id, "s04-cleaning"), {}).get(
            "explicitPositionOverride"
        )
        is True
    )
    checks.append(
        _entry(
            "position_variant_is_exactly_plus_10mm",
            position_ok,
            "位置参数变化链仅将GN00纵向工位增加10 mm。",
            missing=[] if position_ok else ["可认证的GN00纵向+10 mm参数差异"],
            failed=not position_ok,
            details={
                "normalMeters": normal_position,
                "variantMeters": variant_position,
                "deltaMeters": position_delta,
            },
        )
    )

    runtime = build_staged_chain_execution_batch_status(
        workspace, paths["acceptanceBatch"]
    )
    chains_complete = (
        runtime.get("status") == "complete"
        and runtime.get("completedChainCount") == 3
        and all(
            row.get("runtimeState") == "completed_target_station_validated"
            for row in runtime.get("chains") or []
        )
    )
    checks.append(
        _entry(
            "three_acceptance_chains_completed",
            chains_complete,
            "三条六类链均完成真实CAD、逐阶段检查点和当前工位后检。",
            evidence=[
                row["latestAttemptPath"]
                for row in runtime.get("chains") or []
                if row.get("latestAttemptPath")
            ],
            missing=(
                []
                if chains_complete
                else [
                    f"完成链：{row['chainId']}（当前{row['runtimeState']}）"
                    for row in runtime.get("chains") or []
                    if row.get("runtimeState")
                    != "completed_target_station_validated"
                ]
            ),
            details={
                "completedChainCount": runtime.get("completedChainCount"),
                "runtimeStateCounts": runtime.get("runtimeStateCounts"),
            },
        )
    )

    first_chain = (runtime.get("chains") or [{}])[0]
    first_root = workspace / str(first_chain.get("outputRoot") or "")
    attempt_paths = sorted((first_root / "run-attempts").glob("attempt-*.json"))
    attempts = [_read(path) for path in attempt_paths]
    injected_index = next(
        (
            index
            for index, attempt in enumerate(attempts)
            if attempt.get("injectedFailureBeforeStage") == "s02-scanner"
            and attempt.get("success") is False
        ),
        None,
    )
    recovery_ok = False
    recovery_details: dict[str, Any] = {"attemptCount": len(attempts)}
    if injected_index is not None:
        injected = attempts[injected_index]
        injected_stages = _stage_rows(injected)
        later_success = next(
            (
                attempt
                for attempt in attempts[injected_index + 1 :]
                if attempt.get("success") is True
                and attempt.get("targetStationValidated") is True
            ),
            None,
        )
        later_stages = _stage_rows(later_success or {})
        injected_transport = injected_stages.get("s01-transport") or {}
        recovered_transport = later_stages.get("s01-transport") or {}
        recovery_ok = (
            injected_stages.get("s02-scanner", {}).get("status") == "failed"
            and injected_transport.get("status")
            in {"succeeded", "reused_committed_checkpoint"}
            and recovered_transport.get("status") == "reused_committed_checkpoint"
            and injected_transport.get("jobId")
            == recovered_transport.get("jobId")
        )
        recovery_details.update(
            {
                "injectedAttempt": injected_index + 1,
                "recoveredByLaterSuccess": later_success is not None,
                "transportJobIdBeforeFailure": injected_transport.get("jobId"),
                "transportJobIdAfterResume": recovered_transport.get("jobId"),
                "transportStatusAfterResume": recovered_transport.get("status"),
            }
        )
    checks.append(
        _entry(
            "single_failure_resume_without_duplicate_insert",
            recovery_ok,
            "s02-scanner前单次故障后由resume恢复，已提交传输检查点未重复插入。",
            evidence=[_relative(workspace, path) for path in attempt_paths],
            missing=[] if recovery_ok else ["一次故障注入及随后成功resume的运行证据"],
            details={
                **recovery_details,
                "failurePlan": _relative(workspace, paths["failurePlan"]),
                "plannedFailureChainId": (
                    failure_plan.get("nextAction") or {}
                ).get("chainId"),
            },
        )
    )

    compile_timing_ok = _positive(batch.get("durationSeconds")) and all(
        _positive(row.get("durationSeconds")) for row in chain_sources
    )
    checks.append(
        _entry(
            "compilation_timing_recorded",
            compile_timing_ok,
            "三条链的批量和单链编译耗时已记录。",
            missing=[] if compile_timing_ok else ["完整的单链和批量编译耗时"],
            failed=not compile_timing_ok,
            details={
                "batchDurationSeconds": batch.get("durationSeconds"),
                "chainDurationsSeconds": [
                    row.get("durationSeconds") for row in chain_sources
                ],
            },
        )
    )

    stage_evidence_errors: list[str] = []
    cad_seconds = 0.0
    reopen_seconds = 0.0
    postcheck_seconds = 0.0
    final_assemblies: list[str] = []
    for row in runtime.get("chains") or []:
        if row.get("runtimeState") != "completed_target_station_validated":
            stage_evidence_errors.append(f"链未完成，无法审计阶段证据：{row.get('chainId')}")
            continue
        output_root = workspace / row["outputRoot"]
        chain = _read(output_root / "chain.json")
        for stage in chain.get("stages") or []:
            stage_id = str(stage.get("stageId"))
            closure_path = output_root / stage_id / "stage-closure.json"
            station_path = output_root / stage_id / "station-postcheck.json"
            if not closure_path.is_file() or not station_path.is_file():
                stage_evidence_errors.append(
                    f"缺少阶段闭环或工位后检：{row.get('chainId')}/{stage_id}"
                )
                continue
            stage_closure = _read(closure_path)
            station = _read(station_path)
            if stage_closure.get("status") != "passed":
                stage_evidence_errors.append(
                    f"阶段闭环未通过：{row.get('chainId')}/{stage_id}"
                )
            if not _positive(stage_closure.get("executionDurationSeconds")):
                stage_evidence_errors.append(
                    f"缺少CAD执行耗时：{row.get('chainId')}/{stage_id}"
                )
            else:
                cad_seconds += float(stage_closure["executionDurationSeconds"])
            final_path = Path(str(stage_closure.get("finalAssemblyPath") or ""))
            if not final_path.is_file() or _sha256(final_path) != stage_closure.get(
                "finalAssemblySha256"
            ):
                stage_evidence_errors.append(
                    f"最终装配体摘要不匹配：{row.get('chainId')}/{stage_id}"
                )
            if stage_id == (chain.get("stages") or [])[-1].get("stageId"):
                final_assemblies.append(str(final_path))
            if station.get("targetStationValidated") is not True:
                stage_evidence_errors.append(
                    f"目标工位后检未通过：{row.get('chainId')}/{stage_id}"
                )
            reopened_path = Path(str(station.get("savedStatePath") or ""))
            postcheck_path = Path(str(station.get("postcheckPath") or ""))
            if not reopened_path.is_file() or _sha256(reopened_path) != station.get(
                "savedStateSha256"
            ):
                stage_evidence_errors.append(
                    f"保存重开证据缺失或摘要错误：{row.get('chainId')}/{stage_id}"
                )
                continue
            reopened = _read(reopened_path)
            if reopened.get("success") is not True or not _positive(
                reopened.get("durationSeconds")
            ):
                stage_evidence_errors.append(
                    f"保存重开未通过或缺耗时：{row.get('chainId')}/{stage_id}"
                )
            else:
                reopen_seconds += float(reopened["durationSeconds"])
            if not postcheck_path.is_file() or _sha256(postcheck_path) != station.get(
                "postcheckSha256", _sha256(postcheck_path) if postcheck_path.is_file() else ""
            ):
                stage_evidence_errors.append(
                    f"工位后检文件缺失或摘要错误：{row.get('chainId')}/{stage_id}"
                )
                continue
            postcheck = _read(postcheck_path)
            post_timing = postcheck.get("timing") or {}
            if postcheck.get("targetStationValidated") is not True or not _positive(
                post_timing.get("durationSeconds")
            ):
                stage_evidence_errors.append(
                    f"工位后检未通过或缺耗时：{row.get('chainId')}/{stage_id}"
                )
            else:
                postcheck_seconds += float(post_timing["durationSeconds"])
        if (chain.get("stages") or []) and row.get("runtimeState") == "completed_target_station_validated":
            final_stage = str((chain.get("stages") or [])[-1].get("stageId"))
            final_station_path = output_root / final_stage / "station-postcheck.json"
            if final_station_path.is_file():
                station = _read(final_station_path)
                reopened_path = Path(str(station.get("savedStatePath") or ""))
                if reopened_path.is_file():
                    reopened = _read(reopened_path)
                    components = (reopened.get("observed") or {}).get("components") or []
                    fixed = [item for item in components if item.get("isFixed") is True]
                    if len(components) != 6 or len(fixed) != 1:
                        stage_evidence_errors.append(
                            f"最终装配体不是6对象且仅基座固定：{row.get('chainId')}"
                        )
    stage_evidence_ok = chains_complete and not stage_evidence_errors
    checks.append(
        _entry(
            "cad_save_reopen_postcheck_and_final_assemblies",
            stage_evidence_ok,
            "每阶段真实CAD、保存重开和工位后检均通过，最终三套装配体各含6对象且仅基座固定。",
            evidence=final_assemblies,
            missing=stage_evidence_errors,
            details={
                "cadExecutionSeconds": cad_seconds,
                "saveReopenSeconds": reopen_seconds,
                "stationPostcheckSeconds": postcheck_seconds,
                "finalAssemblies": final_assemblies,
            },
        )
    )

    passed_count = sum(check["status"] == "passed" for check in checks)
    failed_count = sum(check["status"] == "failed" for check in checks)
    incomplete_count = len(checks) - passed_count - failed_count
    goal_complete = passed_count == len(checks)
    return {
        "schemaVersion": "six-role-goal-acceptance-audit/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "durationSeconds": perf_counter() - clock,
        "status": "complete" if goal_complete else "incomplete",
        "goalComplete": goal_complete,
        "summary": {
            "checkCount": len(checks),
            "passedCount": passed_count,
            "incompleteCount": incomplete_count,
            "failedCount": failed_count,
            "strictValidatedPairCount": coverage_summary.get(
                "validatedStationRulePairCount"
            ),
            "pendingPairCount": gap_summary.get("pendingPairCount"),
            "completedClosurePhaseCount": sum(
                item["complete"] for item in phase_details.values()
            ),
            "completedAcceptanceChainCount": runtime.get("completedChainCount"),
        },
        "checks": checks,
        "sourceEvidence": {
            key: {"path": _relative(workspace, path), "sha256": _sha256(path)}
            for key, path in paths.items()
        },
        "acceptanceBoundary": {
            "collisionOrBrepRequired": False,
            "actualFasteningRequired": False,
            "productionReleaseRequired": False,
            "dynamicProcessRequired": False,
            "statement": (
                "Completion requires current CAD/save-reopen/station evidence; "
                "compile-ready or historical evidence alone is insufficient."
            ),
        },
    }
