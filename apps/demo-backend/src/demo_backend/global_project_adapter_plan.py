"""Bind a global semantic assembly graph to an existing project CAD runner.

This module deliberately stops before SolidWorks.  It resolves the project,
checks the engineering order, locates a verified base checkpoint and emits the
durable-job steps that an existing project-specific runner can consume.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from .global_assembly_context import validate_global_assembly_context
from .global_module_catalog import validate_global_module_catalog
from .project_assembly_profile import load_project_assembly_profile
from .semantic_assembly_jobs import AssemblyJobError, DurableAssemblyJobStore


GLOBAL_PROJECT_ADAPTER_PLAN_SCHEMA = "global-project-adapter-plan/v1"

MATE_DRIVEN_PORT_ASSEMBLY = "mate_driven_port_assembly"
PROTOTYPE_POSE_DEPENDENCY = "prototype_pose_dependency"
ASSEMBLY_MODES = {MATE_DRIVEN_PORT_ASSEMBLY, PROTOTYPE_POSE_DEPENDENCY}


class GlobalProjectAdapterPlanError(ValueError):
    pass


RUNNER_REGISTRY = {
    "project01": "project01_semantic_assembly_cad_runner.project01_live_cad_step_runner",
    "project02": "semantic_assembly_cad_runner.live_cad_step_runner",
    "project03": "project03_semantic_assembly_cad_runner.project03_live_cad_step_runner",
    "project05": "project05_semantic_assembly_cad_runner.project05_live_cad_step_runner",
}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GlobalProjectAdapterPlanError(f"无法读取项目闭环证据：{path}: {exc}") from exc
    if not isinstance(value, dict):
        raise GlobalProjectAdapterPlanError(f"项目闭环证据根节点必须为对象：{path}")
    return value


def _definition_map(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item["moduleDefinitionId"]): item
        for item in catalog.get("moduleDefinitions") or []
    }


def _connection_template_map(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item["globalTemplateId"]): item
        for item in catalog.get("connectionTemplates") or []
        if item.get("globalTemplateId")
    }


def _normalize_assembly_mode(value: str | None) -> str:
    mode = str(value or MATE_DRIVEN_PORT_ASSEMBLY).strip().lower()
    if mode not in ASSEMBLY_MODES:
        raise GlobalProjectAdapterPlanError(
            f"不支持的装配定位模式：{value}。允许值：{sorted(ASSEMBLY_MODES)}"
        )
    return mode


def _audit_pose_dependencies(
    catalog: dict[str, Any], context: dict[str, Any], assembly_mode: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Classify whether every driving connection can locate its target by mates.

    The catalog already records the mechanical conclusion in ``constraintEffect``.
    This audit turns that information into an execution boundary: source-pose or
    case-anchor fallbacks must never be entered silently.
    """

    templates = _connection_template_map(catalog)
    rows: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    for connection in context.get("connections") or []:
        connection_id = str(connection.get("connectionId") or "")
        template_id = str(connection.get("globalTemplateId") or "")
        template = templates.get(template_id)
        if template is None:
            row = {
                "connectionId": connection_id,
                "globalTemplateId": template_id,
                "status": "template_missing",
                "fullyLocatesAddedComponent": None,
                "remainingDof": "unknown",
                "residualDofPolicy": "unknown",
                "prototypePoseRequired": False,
            }
            rows.append(row)
            if assembly_mode == MATE_DRIVEN_PORT_ASSEMBLY:
                blockers.append(
                    {
                        "code": "POSE_AUDIT_TEMPLATE_MISSING",
                        "connectionId": connection_id,
                        "detail": f"连接{connection_id}找不到关系模板，无法证明配合可独立定位。",
                    }
                )
            continue

        effect = template.get("constraintEffect") or {}
        fully_locates = effect.get("fullyLocatesAddedComponent")
        residual_policy = str(effect.get("residualDofPolicy") or "").strip()
        remaining_dof = str(effect.get("remainingDof") or "").strip()
        normalized_policy = residual_policy.lower()
        prototype_required = fully_locates is False or any(
            marker in normalized_policy
            for marker in ("source_pose", "case_anchor", "prototype_pose")
        )
        if prototype_required:
            status = "prototype_pose_required"
        elif fully_locates is True:
            status = "mate_driven_ready"
        else:
            status = "port_completeness_unverified"
        row = {
            "connectionId": connection_id,
            "globalTemplateId": template_id,
            "status": status,
            "fullyLocatesAddedComponent": fully_locates,
            "remainingDof": remaining_dof or None,
            "residualDofPolicy": residual_policy or None,
            "prototypePoseRequired": prototype_required,
        }
        rows.append(row)
        if assembly_mode != MATE_DRIVEN_PORT_ASSEMBLY:
            continue
        if prototype_required:
            blockers.append(
                {
                    "code": "PROTOTYPE_POSE_DEPENDENCY_NOT_ALLOWED",
                    "connectionId": connection_id,
                    "detail": (
                        f"连接{connection_id}的配合束不能独立封闭刚体自由度；"
                        f"剩余自由度：{remaining_dof or '未明确'}；"
                        f"当前策略：{residual_policy or '原型/案例位姿锚点'}。"
                    ),
                    "remainingDof": remaining_dof or None,
                }
            )
        elif fully_locates is not True:
            blockers.append(
                {
                    "code": "PORT_COMPLETENESS_UNVERIFIED",
                    "connectionId": connection_id,
                    "detail": (
                        f"连接{connection_id}尚未证明语义端口能够独立定位新增模组；"
                        "请补齐机械基准或完成非原型初始位姿验证。"
                    ),
                }
            )

    dependent = [row for row in rows if row["prototypePoseRequired"]]
    ready = [row for row in rows if row["status"] == "mate_driven_ready"]
    return {
        "assemblyMode": assembly_mode,
        "connectionCount": len(rows),
        "mateDrivenReadyCount": len(ready),
        "prototypePoseRequiredCount": len(dependent),
        "portable": assembly_mode == MATE_DRIVEN_PORT_ASSEMBLY and len(blockers) == 0,
        "connections": rows,
        "statement": (
            "仅允许语义端口和配合图独立驱动定位；原型顶层位姿与固定目标组件均不可隐式补足自由度。"
            if assembly_mode == MATE_DRIVEN_PORT_ASSEMBLY
            else "显式启用原型位姿依赖兜底；结果仅用于粗复原、调试和端口标定，不证明可移植装配。"
        ),
    }, blockers


def _project_aliases(definition: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for alias in definition.get("projectAliases") or []:
        project_id = str(alias.get("projectId") or "").strip().lower()
        if project_id:
            result[project_id] = alias
    return result


def _resolve_project(
    definitions: dict[str, dict[str, Any]], context: dict[str, Any]
) -> tuple[str | None, list[dict[str, Any]]]:
    scopes: list[set[str]] = []
    blockers: list[dict[str, Any]] = []
    for instance in context.get("instances") or []:
        definition_id = str(instance.get("moduleDefinitionId") or "")
        definition = definitions.get(definition_id)
        if definition is None:
            blockers.append(
                {
                    "code": "MODULE_DEFINITION_NOT_FOUND",
                    "detail": definition_id,
                }
            )
            continue
        projects = set(_project_aliases(definition))
        if not projects:
            blockers.append(
                {
                    "code": "MODULE_PROJECT_ALIAS_MISSING",
                    "detail": definition_id,
                }
            )
        else:
            scopes.append(projects)
    common = set.intersection(*scopes) if scopes else set()
    if len(common) != 1:
        blockers.append(
            {
                "code": "PROJECT_SCOPE_NOT_UNIQUE",
                "detail": "上下文中的模组不能唯一归属同一个项目。",
                "candidateProjects": sorted(common),
            }
        )
        return None, blockers
    return next(iter(common)), blockers


def _instance_tokens(
    definitions: dict[str, dict[str, Any]],
    context: dict[str, Any],
    project_id: str,
) -> tuple[list[str], dict[str, str], list[dict[str, Any]]]:
    tokens: list[str] = []
    by_instance: dict[str, str] = {}
    blockers: list[dict[str, Any]] = []
    for instance in context.get("instances") or []:
        instance_id = str(instance.get("instanceId") or "")
        definition = definitions.get(str(instance.get("moduleDefinitionId") or "")) or {}
        alias = _project_aliases(definition).get(project_id)
        token = str((alias or {}).get("moduleToken") or "").upper()
        if not token:
            blockers.append(
                {
                    "code": "PROJECT_MODULE_TOKEN_MISSING",
                    "detail": instance_id,
                }
            )
            continue
        tokens.append(token)
        by_instance[instance_id] = token
    return tokens, by_instance, blockers


def _expanded_sequence(
    profile: dict[str, Any], definitions: dict[str, dict[str, Any]], project_id: str
) -> list[str]:
    definitions_by_token: dict[str, dict[str, Any]] = {}
    for definition in definitions.values():
        alias = _project_aliases(definition).get(project_id)
        if alias:
            definitions_by_token[str(alias.get("moduleToken") or "").upper()] = definition
    result: list[str] = []
    for token in profile["validatedSequence"]:
        module = profile["modules"][token]
        definition = definitions_by_token.get(token) or {}
        # Multiple component names represent one composite module group.  A
        # repeated instance count is expanded only for one-source definitions
        # such as Project02 T401-1/T401-2.
        count = 1
        if len(definition.get("componentNames") or []) <= 1:
            count = max(1, int(module.get("instanceCount", 1)))
        result.extend([token] * count)
    return result


def _sequence_assessment(actual: list[str], expected: list[str]) -> dict[str, Any]:
    mismatch = next(
        (
            index
            for index, token in enumerate(actual)
            if index >= len(expected) or token != expected[index]
        ),
        None,
    )
    if mismatch is None and len(actual) <= len(expected):
        kind = "exact" if len(actual) == len(expected) else "validated_prefix"
        return {
            "status": "accepted",
            "kind": kind,
            "actual": actual,
            "expected": expected,
            "nextExpectedTokens": expected[len(actual) :],
            "firstMismatchIndex": None,
            "missingPredecessors": [],
        }
    mismatch = mismatch if mismatch is not None else len(expected)
    offending = actual[mismatch] if mismatch < len(actual) else None
    missing: list[str] = []
    if offending in expected[mismatch:]:
        missing = expected[mismatch : expected.index(offending, mismatch)]
    return {
        "status": "blocked",
        "kind": "sequence_mismatch",
        "actual": actual,
        "expected": expected,
        "nextExpectedTokens": [],
        "firstMismatchIndex": mismatch,
        "offendingToken": offending,
        "missingPredecessors": missing,
    }


def _resolve_seed_checkpoint(
    workspace: Path, profile: dict[str, Any]
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    relative = str((profile.get("artifacts") or {}).get("orderedClosure") or "")
    closure_path = (workspace / relative).resolve()
    if not closure_path.is_file():
        return None, [
            {
                "code": "ORDERED_CLOSURE_MISSING",
                "detail": str(closure_path),
            }
        ]
    closure = _read_json(closure_path)
    base_token = str(profile["baseModule"])
    base = next(
        (row for row in closure.get("steps") or [] if row.get("moduleToken") == base_token),
        None,
    )
    if base is None:
        return None, [
            {
                "code": "BASE_CHECKPOINT_NOT_RECORDED",
                "detail": f"{closure_path} / {base_token}",
            }
        ]
    assembly = Path(str(base.get("assemblyPath") or "")).resolve()
    evidence = Path(str(base.get("evidencePath") or "")).resolve()
    missing = [str(path) for path in (assembly, evidence) if not path.is_file()]
    if missing:
        return None, [
            {
                "code": "BASE_CHECKPOINT_FILE_MISSING",
                "detail": "；".join(missing),
            }
        ]
    return {
        "stepId": f"seed-{base_token.lower()}",
        "moduleToken": base_token,
        "assemblyPath": str(assembly),
        "evidencePath": str(evidence),
        "closurePath": str(closure_path),
        "verification": "existing_ordered_closure",
    }, []


def _runner_grouped_tokens(workspace: Path, profile: dict[str, Any]) -> set[str]:
    """Read runner evidence for one CAD step that inserts several instances.

    Project02 represents two T401 semantic instances but its validated CAD
    runner intentionally inserts both actions in one durable T401 step.  The
    full-machine closure is the authority for that grouping.
    """

    relative = str((profile.get("artifacts") or {}).get("fullMachineClosure") or "")
    path = (workspace / relative).resolve()
    if not path.is_file():
        return set()
    closure = _read_json(path)
    return {
        str(row.get("moduleToken") or "").upper()
        for row in closure.get("steps") or []
        if len(row.get("instanceTokens") or []) > 1
    }


def compile_global_project_adapter_plan(
    workspace: Path,
    catalog: dict[str, Any],
    context: dict[str, Any],
    execution_manifest: dict[str, Any],
    *,
    assembly_mode: str = MATE_DRIVEN_PORT_ASSEMBLY,
    profile_loader: Callable[[str], dict[str, Any]] = load_project_assembly_profile,
) -> dict[str, Any]:
    """Create a fail-closed project runner plan without starting CAD."""

    validate_global_module_catalog(catalog)
    validate_global_assembly_context(context)
    assembly_mode = _normalize_assembly_mode(assembly_mode)
    workspace = workspace.resolve()
    definitions = _definition_map(catalog)
    pose_dependency_audit, pose_blockers = _audit_pose_dependencies(
        catalog, context, assembly_mode
    )
    project_id, blockers = _resolve_project(definitions, context)
    blockers.extend(pose_blockers)
    if not project_id:
        return _blocked_plan(
            context,
            execution_manifest,
            blockers,
            assembly_mode=assembly_mode,
            pose_dependency_audit=pose_dependency_audit,
        )

    actual, tokens_by_instance, token_blockers = _instance_tokens(
        definitions, context, project_id
    )
    blockers.extend(token_blockers)
    profile = profile_loader(project_id)
    expected = _expanded_sequence(profile, definitions, project_id)
    sequence = _sequence_assessment(actual, expected)
    if sequence["status"] != "accepted":
        blockers.append(
            {
                "code": "SEQUENCE_NOT_VALIDATED_PREFIX",
                "detail": "全局上下文未遵循项目已验证机械装配顺序。",
                "missingPredecessors": sequence["missingPredecessors"],
                "firstMismatchIndex": sequence["firstMismatchIndex"],
            }
        )
    if execution_manifest.get("status") != "ready_for_project_adapter":
        blockers.append(
            {
                "code": "GLOBAL_EXECUTION_MANIFEST_BLOCKED",
                "detail": "全局语义连接清单尚未全部就绪。",
            }
        )
    runner_id = RUNNER_REGISTRY.get(project_id)
    if not runner_id:
        blockers.append(
            {
                "code": "PROJECT_RUNNER_NOT_REGISTERED",
                "detail": project_id,
            }
        )
    seed, seed_blockers = _resolve_seed_checkpoint(workspace, profile)
    blockers.extend(seed_blockers)
    grouped_tokens = _runner_grouped_tokens(workspace, profile)

    manifest_by_target = {
        str(step.get("targetInstanceId") or ""): step
        for step in execution_manifest.get("steps") or []
    }
    job_steps: list[dict[str, Any]] = []
    for instance_index, instance in enumerate((context.get("instances") or [])[1:], start=1):
        instance_id = str(instance["instanceId"])
        token = tokens_by_instance.get(instance_id)
        manifest_step = manifest_by_target.get(instance_id)
        if manifest_step is None:
            blockers.append(
                {
                    "code": "INSTANCE_MANIFEST_STEP_MISSING",
                    "detail": instance_id,
                }
            )
            continue
        if token in grouped_tokens and job_steps and job_steps[-1]["moduleToken"] == token:
            job_steps[-1]["targetInstanceIds"].append(instance_id)
            job_steps[-1]["connectionIds"].append(manifest_step.get("connectionId"))
            job_steps[-1]["semanticConnectionRequests"].append(
                manifest_step.get("semanticConnectionRequest")
            )
            job_steps[-1]["groupedInstanceCount"] += 1
            continue
        step_number = len(job_steps) + 1
        job_steps.append(
            {
                "stepId": f"step-{step_number:02d}-{str(token).lower()}",
                "moduleToken": token,
                "targetInstanceId": instance_id,
                "targetInstanceIds": [instance_id],
                "connectionId": manifest_step.get("connectionId"),
                "connectionIds": [manifest_step.get("connectionId")],
                "sourceCheckpointPolicy": (
                    "verified_external_seed" if step_number == 1 else "previous_committed_step"
                ),
                "expectedSourceModuleTokens": actual[:instance_index],
                "semanticConnectionRequest": manifest_step.get("semanticConnectionRequest"),
                "semanticConnectionRequests": [
                    manifest_step.get("semanticConnectionRequest")
                ],
                "groupedInstanceCount": 1,
                "runnerId": runner_id,
                "commitPolicy": "save_reopen_then_commit",
            }
        )

    safe = not blockers and bool(job_steps) and seed is not None
    return {
        "schemaVersion": GLOBAL_PROJECT_ADAPTER_PLAN_SCHEMA,
        "contextId": context["contextId"],
        "contextRevision": int(context.get("revision") or 0),
        "contextDigest": context["contextDigest"],
        "catalogDigest": catalog["catalogDigest"],
        "projectId": project_id,
        "assemblyMode": assembly_mode,
        "prototypePoseDependency": assembly_mode == PROTOTYPE_POSE_DEPENDENCY,
        "portable": pose_dependency_audit["portable"],
        "poseDependencyAudit": pose_dependency_audit,
        "projectProfilePath": profile.get("profilePath"),
        "projectProfileDigest": profile.get("profileDigest"),
        "status": "ready_for_durable_job" if safe else "blocked",
        "safeToCreateDurableJob": safe,
        "sequenceAssessment": sequence,
        "runnerBinding": {
            "runnerId": runner_id,
            "groupedInstanceTokens": sorted(grouped_tokens),
            "solidWorksStarted": False,
        },
        "seedCheckpoint": seed,
        "stepCount": len(job_steps),
        "steps": job_steps,
        "blockers": blockers,
        "executionBoundary": {
            "solidWorksExecuted": False,
            "collisionGateExecuted": False,
            "collisionPolicy": "deferred_by_user_scope",
            "statement": "本计划只绑定顺序、累计检查点和既有CAD runner；不会启动SolidWorks。",
        },
    }


def _blocked_plan(
    context: dict[str, Any],
    manifest: dict[str, Any],
    blockers: list[dict[str, Any]],
    *,
    assembly_mode: str = MATE_DRIVEN_PORT_ASSEMBLY,
    pose_dependency_audit: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schemaVersion": GLOBAL_PROJECT_ADAPTER_PLAN_SCHEMA,
        "contextId": context["contextId"],
        "contextRevision": int(context.get("revision") or 0),
        "contextDigest": context["contextDigest"],
        "catalogDigest": context["catalogDigest"],
        "projectId": None,
        "assemblyMode": assembly_mode,
        "prototypePoseDependency": assembly_mode == PROTOTYPE_POSE_DEPENDENCY,
        "portable": False,
        "poseDependencyAudit": pose_dependency_audit,
        "status": "blocked",
        "safeToCreateDurableJob": False,
        "sequenceAssessment": None,
        "runnerBinding": None,
        "seedCheckpoint": None,
        "stepCount": 0,
        "steps": [],
        "blockers": blockers,
        "executionBoundary": {
            "solidWorksExecuted": False,
            "collisionGateExecuted": False,
            "collisionPolicy": "deferred_by_user_scope",
        },
    }


def create_seeded_durable_job(
    store: DurableAssemblyJobStore,
    plan: dict[str, Any],
    *,
    execution_mode: str = "live_cad",
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Create and seed a durable job only from a fully accepted adapter plan."""

    if plan.get("safeToCreateDurableJob") is not True:
        raise AssemblyJobError("项目适配计划未通过硬前置检查，禁止创建执行任务。")
    seed = plan.get("seedCheckpoint") or {}
    job = store.create(
        plan,
        execution_mode=execution_mode,
        idempotency_key=idempotency_key,
    )
    if not job.get("lastCommittedCheckpoint"):
        job = store.seed_verified_checkpoint(
            str(job["jobId"]),
            step_id=str(seed["stepId"]),
            module_token=str(seed["moduleToken"]),
            assembly_path=Path(str(seed["assemblyPath"])),
            evidence_path=Path(str(seed["evidencePath"])),
        )
    return job


def build_checkpoint_continuation_plan(
    full_plan: dict[str, Any],
    seed_job: dict[str, Any],
    *,
    step_limit: int,
) -> dict[str, Any]:
    """Create a contiguous suffix plan from one succeeded durable checkpoint."""

    if full_plan.get("safeToCreateDurableJob") is not True:
        raise AssemblyJobError("当前完整项目适配计划未通过，禁止从检查点续跑。")
    if seed_job.get("status") != "succeeded":
        raise AssemblyJobError("只有已成功提交的任务才能作为续跑检查点。")
    source_plan = seed_job.get("plan") or {}
    for key in ("contextId", "contextDigest", "projectId"):
        if source_plan.get(key) != full_plan.get(key):
            raise AssemblyJobError(f"续跑任务的{key}与当前项目适配计划不一致。")
    checkpoint = seed_job.get("lastCommittedCheckpoint") or {}
    checkpoint_step_id = str(checkpoint.get("stepId") or "")
    checkpoint_module = str(checkpoint.get("moduleToken") or "")
    full_steps = list(full_plan.get("steps") or [])
    checkpoint_index = next(
        (
            index
            for index, step in enumerate(full_steps)
            if str(step.get("stepId") or "") == checkpoint_step_id
            and str(step.get("moduleToken") or "") == checkpoint_module
        ),
        None,
    )
    if checkpoint_index is None:
        raise AssemblyJobError("续跑检查点不属于当前完整计划。")
    source_steps = list(seed_job.get("steps") or [])
    if not source_steps or any(step.get("status") != "succeeded" for step in source_steps):
        raise AssemblyJobError("续跑来源任务仍有未成功步骤。")
    if str(source_steps[-1].get("stepId") or "") != checkpoint_step_id:
        raise AssemblyJobError("续跑任务最后成功步骤与最后检查点不一致。")
    assembly_path = Path(str(checkpoint.get("assemblyPath") or "")).resolve()
    evidence_path = Path(str(checkpoint.get("evidencePath") or "")).resolve()
    if not assembly_path.is_file() or not evidence_path.is_file():
        raise AssemblyJobError("续跑检查点装配体或证据文件不存在。")
    start_index = checkpoint_index + 1
    if start_index >= len(full_steps):
        raise AssemblyJobError("该检查点已经是完整计划最后一步，没有可续跑步骤。")
    if step_limit < 1 or start_index + step_limit > len(full_steps):
        raise AssemblyJobError("续跑步骤数超过当前检查点后的剩余计划。")
    selected_steps = [dict(step) for step in full_steps[start_index : start_index + step_limit]]
    selected_steps[0]["sourceCheckpointPolicy"] = "verified_external_seed"
    continuation_seed = {
        **checkpoint,
        "assemblyPath": str(assembly_path),
        "evidencePath": str(evidence_path),
        "verification": "succeeded_durable_job_checkpoint",
        "sourceJobId": str(seed_job.get("jobId") or ""),
    }
    return {
        **full_plan,
        "seedCheckpoint": continuation_seed,
        "steps": selected_steps,
        "stepCount": len(selected_steps),
        "executionScope": {
            "kind": "validated_continuation",
            "requestedStepCount": len(selected_steps),
            "fullStepCount": len(full_steps),
            "startStepIndex": start_index,
            "moduleTokens": [str(step["moduleToken"]) for step in selected_steps],
            "seedJobId": str(seed_job.get("jobId") or ""),
            "seedStepId": checkpoint_step_id,
        },
    }


def build_direct_edit_checkpoint_continuation_plan(
    full_plan: dict[str, Any],
    seed_job: dict[str, Any],
    direct_edit: dict[str, Any],
    *,
    step_limit: int,
) -> dict[str, Any]:
    """Continue a project plan from an attested post-job direct mate edit."""

    if direct_edit.get("status") != "succeeded":
        raise AssemblyJobError("直接配合实体检查点尚未成功。")
    if str(direct_edit.get("sourceJobId") or "") != str(seed_job.get("jobId") or ""):
        raise AssemblyJobError("直接配合实体检查点与来源任务不匹配。")
    assembly_path = Path(str(direct_edit.get("assemblyPath") or "")).resolve()
    evidence_path = Path(str(direct_edit.get("executionEvidencePath") or "")).resolve()
    if not assembly_path.is_file() or not evidence_path.is_file():
        raise AssemblyJobError("直接配合实体检查点装配体或执行证据不存在。")
    import hashlib

    def digest(path: Path) -> str:
        value = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                value.update(chunk)
        return value.hexdigest()

    if digest(assembly_path) != str(direct_edit.get("assemblySha256") or ""):
        raise AssemblyJobError("直接配合实体检查点装配体哈希不匹配。")
    if digest(evidence_path) != str(direct_edit.get("executionEvidenceSha256") or ""):
        raise AssemblyJobError("直接配合实体检查点执行证据哈希不匹配。")

    source_checkpoint = dict(seed_job.get("lastCommittedCheckpoint") or {})
    if not source_checkpoint:
        raise AssemblyJobError("来源任务没有最后成功检查点。")
    derived_job = dict(seed_job)
    derived_job["lastCommittedCheckpoint"] = {
        **source_checkpoint,
        "assemblyPath": str(assembly_path),
        "evidencePath": str(evidence_path),
        "validationEvidenceKind": "direct_mate_edit_save_reopen",
        "sourceEditId": direct_edit.get("editId"),
    }
    plan = build_checkpoint_continuation_plan(
        full_plan,
        derived_job,
        step_limit=step_limit,
    )
    plan["seedCheckpoint"] = {
        **plan["seedCheckpoint"],
        "verification": "attested_direct_mate_edit_checkpoint",
        "sourceEditId": direct_edit.get("editId"),
        "assemblySha256": direct_edit.get("assemblySha256"),
        "executionEvidenceSha256": direct_edit.get("executionEvidenceSha256"),
    }
    plan["executionScope"] = {
        **plan["executionScope"],
        "kind": "validated_direct_edit_continuation",
        "seedEditId": direct_edit.get("editId"),
    }
    return plan
