"""Compile ordered natural-language module requests into a durable CAD job.

This is deliberately project-sequence independent: the global module catalog,
semantic-port compatibility and the resulting connection graph decide whether
each turn is valid.  No SolidWorks process is started by this compiler.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

from .assembly_conversation import bind_job
from .global_assembly_workbench import (
    apply_command_sequence,
    compile_cad_transaction_manifest,
    compile_transaction_dag,
    context_path,
    create_context,
    load_context,
    load_global_catalog,
    load_released_relation_catalog,
)
from .global_cad_manifest_orchestrator import (
    build_manifest_job_plan,
    manifest_job_status_view,
    write_manifest_job_artifacts,
)
from .semantic_assembly_jobs import DurableAssemblyJobStore
from .evidence_backed_long_chain import (
    order_requirements_by_released_installation_dependencies,
)
from .global_relation_catalog_release import load_relation_catalog_release
from .global_interface_contract_planner import (
    assess_global_assembly_context_interfaces,
)


SCHEMA = "global-natural-language-manifest-compilation/v1"


class GlobalNaturalLanguageManifestError(ValueError):
    pass


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def compile_natural_language_manifest_job(
    workspace: Path,
    payload: dict[str, Any],
    *,
    store: DurableAssemblyJobStore | None = None,
) -> dict[str, Any]:
    workspace = workspace.resolve()
    context_id = str(payload.get("contextId") or "").strip()
    requirements = payload.get("requirements")
    if not context_id:
        raise GlobalNaturalLanguageManifestError("contextId不能为空。")
    if not isinstance(requirements, list) or not 2 <= len(requirements) <= 20:
        raise GlobalNaturalLanguageManifestError("requirements必须包含2至20条自然语言命令。")
    normalized = [str(item or "").strip() for item in requirements]
    if any(not item for item in normalized):
        raise GlobalNaturalLanguageManifestError("自然语言命令不能为空。")

    compile_started = perf_counter()
    phases: dict[str, float] = {}
    phase_started = perf_counter()
    catalog_path = str(payload.get("catalogPath") or "").strip() or None
    release_manifest_path = (
        str(payload.get("releaseManifestPath") or "").strip() or None
    )
    if catalog_path and release_manifest_path:
        raise GlobalNaturalLanguageManifestError(
            "catalogPath与releaseManifestPath不能同时指定。"
        )
    selections = payload.get("confirmedModuleSelections")
    confirmed_selections: list[dict[str, Any]] | None = None
    if selections is not None:
        if not isinstance(selections, list) or len(selections) != len(normalized):
            raise GlobalNaturalLanguageManifestError(
                "confirmedModuleSelections必须与requirements逐项对应且长度相同。"
            )
        confirmed_selections = []
        for index, selection in enumerate(selections, start=1):
            if not isinstance(selection, dict) or selection.get("confirmed") is not True:
                raise GlobalNaturalLanguageManifestError(
                    f"第{index}项模组选定必须由调用方显式confirmed=true。"
                )
            definition_id = selection.get("moduleDefinitionId")
            if not isinstance(definition_id, str) or not definition_id.strip():
                raise GlobalNaturalLanguageManifestError(
                    f"第{index}项模组选定缺少moduleDefinitionId。"
                )
            confirmed_selections.append(
                {"inputOrder": index, "moduleDefinitionId": definition_id.strip(), "confirmed": True}
            )
        selected_catalog = (
            load_released_relation_catalog(workspace, release_manifest_path)[0]
            if release_manifest_path
            else load_global_catalog(workspace, catalog_path)
        )
        known_definitions = {
            row["moduleDefinitionId"] for row in selected_catalog.get("moduleDefinitions") or []
        }
        for selection in confirmed_selections:
            if selection["moduleDefinitionId"] not in known_definitions:
                raise GlobalNaturalLanguageManifestError(
                    f"第{selection['inputOrder']}项moduleDefinitionId不存在于当前绑定目录。"
                )
    original_confirmed_selections = confirmed_selections
    created = create_context(
        workspace,
        {
            "contextId": context_id,
            "displayName": payload.get("displayName") or f"自然语言清单任务：{context_id}",
            "catalogPath": catalog_path,
            "releaseManifestPath": release_manifest_path,
            "overwrite": bool(payload.get("overwrite")),
        },
    )
    phases["createContext"] = round(perf_counter() - phase_started, 6)
    dependency_ordering = None
    original_requirements = list(normalized)
    if bool(payload.get("autoOrderByReleasedDependencies")):
        if not release_manifest_path:
            raise GlobalNaturalLanguageManifestError(
                "自动依赖排序必须绑定不可变关系发布。"
            )
        phase_started = perf_counter()
        manifest_file = Path(release_manifest_path)
        if not manifest_file.is_absolute():
            manifest_file = (workspace / manifest_file).resolve()
        try:
            manifest_file.relative_to(workspace)
        except ValueError as exc:
            raise GlobalNaturalLanguageManifestError(
                "关系发布清单必须位于当前工作区。"
            ) from exc
        released_catalog, released_manifest = load_relation_catalog_release(
            manifest_file,
            workspace_root=workspace,
        )
        dependency_ordering = (
            order_requirements_by_released_installation_dependencies(
                released_catalog,
                released_manifest,
                normalized,
            )
        )
        phases["orderByReleasedDependencies"] = round(
            perf_counter() - phase_started, 6
        )
        if dependency_ordering.get("status") != "ready":
            report = {
                "schemaVersion": SCHEMA,
                "success": False,
                "status": "blocked_before_manifest",
                "contextId": context_id,
                "requirements": original_requirements,
                "confirmedModuleSelections": original_confirmed_selections,
                "dependencyOrdering": dependency_ordering,
                "releaseManifestPath": release_manifest_path,
                "cadStarted": False,
                "collisionStatus": "not_evaluated",
                "generatedAt": datetime.now(timezone.utc).isoformat(),
                "timingSeconds": {
                    "phasesSeconds": phases,
                    "totalSeconds": round(perf_counter() - compile_started, 6),
                },
            }
            context_file = context_path(workspace, context_id)
            report_path = context_file.with_suffix(
                ".natural-language-compilation.json"
            )
            _write(report_path, report)
            return {**report, "reportPath": str(report_path)}
        normalized = list(dependency_ordering["orderedRequirements"])
        if confirmed_selections is not None:
            ordered_selections = []
            for step in dependency_ordering["steps"]:
                selection = confirmed_selections[step["inputOrder"] - 1]
                if step["moduleDefinitionId"] != selection["moduleDefinitionId"]:
                    raise GlobalNaturalLanguageManifestError(
                        "自动依赖排序的识别结果与已确认模组不同；不能替换工程师选择。"
                    )
                ordered_selections.append(selection)
            confirmed_selections = ordered_selections
    phase_started = perf_counter()
    sequence = apply_command_sequence(
        workspace,
        context_id,
        {
            "catalogPath": catalog_path,
            "confirmed": True,
            "commands": [
                {
                    "requirement": item,
                    **(
                        {
                            "moduleDefinitionId": confirmed_selections[index]["moduleDefinitionId"],
                            "confirmed": True,
                        }
                        if confirmed_selections is not None else {}
                    ),
                }
                for index, item in enumerate(normalized)
            ],
            "relationExecutionMode": payload.get("relationExecutionMode"),
        },
    )
    phases["applyNaturalLanguageCommands"] = round(
        perf_counter() - phase_started, 6
    )
    context_file = context_path(workspace, context_id)
    report_path = context_file.with_suffix(".natural-language-compilation.json")
    if sequence.get("success") is not True:
        report = {
            "schemaVersion": SCHEMA,
            "success": False,
            "status": "blocked_before_manifest",
            "contextId": context_id,
            "requirements": normalized,
            "confirmedModuleSelections": confirmed_selections,
            "relationExecutionMode": str(
                payload.get("relationExecutionMode") or "direct_installation"
            ),
            "releaseManifestPath": release_manifest_path,
            "sequence": sequence,
            "cadStarted": False,
            "collisionStatus": "not_evaluated",
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "timingSeconds": {
                "phasesSeconds": phases,
                "totalSeconds": round(perf_counter() - compile_started, 6),
            },
        }
        _write(report_path, report)
        return {**report, "reportPath": str(report_path)}

    phase_started = perf_counter()
    mechanical_interface_preflight = assess_global_assembly_context_interfaces(
        workspace,
        load_context(workspace, context_id),
        relation_execution_mode=payload.get("relationExecutionMode"),
    )
    phases["mechanicalInterfacePreflight"] = round(
        perf_counter() - phase_started, 6
    )
    if (
        bool(payload.get("enforceMechanicalInterfaceContracts"))
        and mechanical_interface_preflight.get("status") != "ready"
    ):
        report = {
            "schemaVersion": SCHEMA,
            "success": False,
            "status": "blocked_by_mechanical_interface_contracts",
            "contextId": context_id,
            "requirements": normalized,
            "confirmedModuleSelections": confirmed_selections,
            "relationExecutionMode": str(
                payload.get("relationExecutionMode") or "direct_installation"
            ),
            "releaseManifestPath": release_manifest_path,
            "sequence": sequence,
            "mechanicalInterfacePreflight": mechanical_interface_preflight,
            "cadStarted": False,
            "jobCreated": False,
            "collisionStatus": "not_evaluated",
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "timingSeconds": {
                "phasesSeconds": phases,
                "totalSeconds": round(perf_counter() - compile_started, 6),
            },
        }
        _write(report_path, report)
        return {**report, "reportPath": str(report_path)}

    positioning_standard_id = str(
        payload.get("positioningStandardId") or ""
    ).strip() or None
    phase_started = perf_counter()
    dag = compile_transaction_dag(workspace, context_id)
    phases["compileTransactionDag"] = round(perf_counter() - phase_started, 6)
    dag_path = context_file.with_suffix(".transaction-dag.json")
    _write(dag_path, dag)
    phase_started = perf_counter()
    manifest = compile_cad_transaction_manifest(
        workspace,
        context_id,
        positioning_standard_id=positioning_standard_id,
        driving_strategy_selections=payload.get("drivingStrategySelections"),
    )
    phases["compileCadManifest"] = round(perf_counter() - phase_started, 6)
    manifest_path = context_file.with_suffix(".cad-transaction-manifest.json")
    _write(manifest_path, manifest)
    if manifest.get("status") != "ready_for_generic_executor_implementation":
        report = {
            "schemaVersion": SCHEMA,
            "success": False,
            "status": "blocked_before_job_creation",
            "contextId": context_id,
            "requirements": normalized,
            "confirmedModuleSelections": confirmed_selections,
            "contextPath": str(context_file),
            "releaseManifestPath": release_manifest_path,
            "manifestPath": str(manifest_path),
            "manifestStatus": manifest.get("status"),
            "positioningStandardId": positioning_standard_id,
            "positioningStandard": manifest.get("positioningStandard"),
            "drivingStrategySelections": manifest.get("drivingStrategySelections"),
            "mechanicalInterfacePreflight": mechanical_interface_preflight,
            "blockers": manifest.get("blockers") or [],
            "cadStarted": False,
            "jobCreated": False,
            "collisionStatus": "not_evaluated",
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "timingSeconds": {
                "phasesSeconds": phases,
                "totalSeconds": round(perf_counter() - compile_started, 6),
            },
        }
        _write(report_path, report)
        return {**report, "reportPath": str(report_path)}

    phase_started = perf_counter()
    plan = build_manifest_job_plan(
        workspace,
        manifest_path,
        start_order=int(payload.get("startOrder") or 1),
        packet_limit=payload.get("packetLimit"),
    )
    phases["buildDurableJobPlan"] = round(perf_counter() - phase_started, 6)
    store = store or DurableAssemblyJobStore(
        workspace / "demo" / "global_assembly_contexts" / "manifest_jobs"
    )
    phase_started = perf_counter()
    job = store.create(
        plan,
        execution_mode="generic_cad_manifest",
        idempotency_key=payload.get("idempotencyKey"),
    )
    phases["createDurableJob"] = round(perf_counter() - phase_started, 6)
    phase_started = perf_counter()
    bind_job(context_file, load_context(workspace, context_id), job)
    phases["bindJobToConversation"] = round(
        perf_counter() - phase_started, 6
    )
    total_seconds = round(perf_counter() - compile_started, 6)
    preflight = {
        "schemaVersion": "global-manifest-job-preflight/v1",
        "naturalLanguageCompilation": {
            "totalSeconds": total_seconds,
            "phasesSeconds": phases,
            "confirmedModuleSelections": confirmed_selections,
        },
    }
    _write(store._dir(job["jobId"]) / "preflight.json", preflight)
    write_manifest_job_artifacts(store, job["jobId"])
    report = {
        "schemaVersion": SCHEMA,
        "success": True,
        "status": "job_created_not_started",
        "contextId": context_id,
        "requirements": normalized,
        "confirmedModuleSelections": confirmed_selections,
        "originalConfirmedModuleSelections": original_confirmed_selections,
        "relationExecutionMode": str(
            payload.get("relationExecutionMode") or "direct_installation"
        ),
        "originalRequirements": original_requirements,
        "dependencyOrdering": dependency_ordering,
        "turnCount": sequence.get("turnCount"),
        "contextPath": str(context_file),
        "releaseManifestPath": release_manifest_path,
        "manifestPath": str(manifest_path),
        "manifestStatus": manifest.get("status"),
        "positioningStandardId": positioning_standard_id,
        "positioningStandard": manifest.get("positioningStandard"),
        "drivingStrategySelections": manifest.get("drivingStrategySelections"),
        "mechanicalInterfacePreflight": mechanical_interface_preflight,
        "packetCount": manifest.get("packetCount"),
        "jobId": job["jobId"],
        "cadStarted": False,
        "collisionStatus": "not_evaluated",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "timingSeconds": {
            "phasesSeconds": phases,
            "totalSeconds": total_seconds,
        },
    }
    _write(report_path, report)
    return {
        **report,
        "reportPath": str(report_path),
        "job": manifest_job_status_view(store, job["jobId"]),
    }
