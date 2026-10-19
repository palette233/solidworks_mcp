"""Bind one successful Demo checkpoint to an editable mate-graph patch.

This is deliberately a planning and evidence layer.  Exporting the graph is
read-only, compiling a patch does not start SolidWorks, and executing the
resulting graph remains an explicit later operation.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .mate_graph_edit import MateGraphEditError, compile_mate_graph_patch
from .mate_dof_analysis import MateDofAnalysisError, analyze_target_mate_dof
from .mate_transaction_preflight import (
    MateTransactionPreflightError,
    preflight_direct_mate_transaction,
)
from .component_state_policy import evaluate_component_state_policy


EXPORT_SPEC_SCHEMA = "checkpoint-mate-graph-export/v1"
GRAPH_BINDING_SCHEMA = "checkpoint-mate-graph-binding/v1"
COMPILED_PREVIEW_SCHEMA = "checkpoint-temporary-mate-preview/v1"


class CheckpointMateGraphAdapterError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _json_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CheckpointMateGraphAdapterError(f"无法读取JSON：{path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CheckpointMateGraphAdapterError(f"JSON根节点必须是对象：{path}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def _same_path(first: str | Path, second: str | Path) -> bool:
    return str(Path(first).resolve()).casefold() == str(Path(second).resolve()).casefold()


def _project_tokens(
    catalog: dict[str, Any], context: dict[str, Any], project_id: str
) -> tuple[list[str], dict[str, str], dict[str, str]]:
    definitions = {
        str(row.get("moduleDefinitionId") or ""): row
        for row in catalog.get("moduleDefinitions") or []
    }
    tokens: list[str] = []
    by_instance: dict[str, str] = {}
    project_by_instance: dict[str, str] = {}
    for instance in context.get("instances") or []:
        definition = definitions.get(str(instance.get("moduleDefinitionId") or ""))
        if definition is None:
            raise CheckpointMateGraphAdapterError(
                f"目录中找不到模组定义：{instance.get('moduleDefinitionId')}"
            )
        aliases = [
            alias
            for alias in definition.get("projectAliases") or []
            if str(alias.get("projectId") or "").strip()
            and str(alias.get("moduleToken") or "").strip()
        ]
        if project_id.casefold() == "project-global":
            # A generic manifest can contain modules from several projects.
            # The concrete CAD definition normally has one traceable source
            # alias.  Never guess when a merged definition is ambiguous.
            unique_aliases = {
                (
                    str(alias.get("projectId") or "").strip().lower(),
                    str(alias.get("moduleToken") or "").strip().upper(),
                ): alias
                for alias in aliases
            }
            matches = list(unique_aliases.values())
        else:
            matches = [
                alias
                for alias in aliases
                if str(alias.get("projectId") or "").casefold()
                == project_id.casefold()
            ]
        if len(matches) != 1 or not str(matches[0].get("moduleToken") or "").strip():
            scope = "跨项目来源" if project_id.casefold() == "project-global" else project_id
            raise CheckpointMateGraphAdapterError(
                f"实例{instance.get('instanceId')}没有唯一的{scope}模组编号。"
            )
        token = str(matches[0]["moduleToken"]).strip().upper()
        instance_id = str(instance["instanceId"])
        if token in tokens:
            if project_id.casefold() == "project-global":
                raise CheckpointMateGraphAdapterError(
                    f"检查点包含重复模组编号{token}；当前只读导出工具无法按项目区分同名模组。"
                )
        else:
            tokens.append(token)
        by_instance[instance_id] = token
        project_by_instance[instance_id] = str(matches[0]["projectId"]).strip().lower()
    return tokens, by_instance, project_by_instance


def build_checkpoint_graph_export_spec(
    workspace: Path,
    context_path: Path,
    context: dict[str, Any],
    catalog: dict[str, Any],
    conversation: dict[str, Any],
    *,
    expected_demo_job_id: str | None = None,
) -> dict[str, Any]:
    """Create a deterministic, fail-closed read-only export specification."""

    latest = conversation.get("latestSuccessfulDemo")
    if not isinstance(latest, dict):
        raise CheckpointMateGraphAdapterError("当前上下文没有成功的Demo检查点。")
    job_id = str(latest.get("jobId") or "")
    if expected_demo_job_id and job_id != expected_demo_job_id:
        raise CheckpointMateGraphAdapterError(
            f"最近成功检查点已从{expected_demo_job_id}变化为{job_id}。"
        )
    revision = int(context.get("revision") or 0)
    if int(latest.get("contextRevision") or -1) != revision:
        raise CheckpointMateGraphAdapterError(
            "最近成功Demo检查点不是当前图修订，请先执行或恢复当前修订。"
        )
    if str(latest.get("contextDigest") or "") != str(context.get("contextDigest") or ""):
        raise CheckpointMateGraphAdapterError("Demo检查点绑定的上下文摘要已过期。")
    project_id = str(latest.get("projectId") or "").strip().lower()
    if not project_id:
        raise CheckpointMateGraphAdapterError("成功检查点缺少projectId绑定。")
    assembly_path = Path(str(latest.get("assemblyPath") or "")).resolve()
    if not assembly_path.is_file():
        raise CheckpointMateGraphAdapterError(f"Demo装配体不存在：{assembly_path}")
    tokens, by_instance, project_by_instance = _project_tokens(
        catalog, context, project_id
    )
    assembly_sha = _file_digest(assembly_path)
    output_dir = context_path.parent / "checkpoint-graphs" / context["contextId"]
    graph_path = output_dir / f"{job_id}-{assembly_sha[:12]}.mate-graph.json"
    binding_path = graph_path.with_suffix(".binding.json")
    stat = assembly_path.stat()
    spec = {
        "schemaVersion": EXPORT_SPEC_SCHEMA,
        "status": "ready",
        "contextId": context["contextId"],
        "contextRevision": revision,
        "contextDigest": context["contextDigest"],
        "demoJobId": job_id,
        "projectId": project_id,
        "checkpointAssembly": {
            "path": str(assembly_path),
            "sha256": assembly_sha,
            "sizeBytes": stat.st_size,
            "lastWriteTimeNs": stat.st_mtime_ns,
        },
        "moduleTokens": tokens,
        "moduleTokenByInstanceId": by_instance,
        "sourceProjectByInstanceId": project_by_instance,
        "outputGraphPath": str(graph_path),
        "bindingPath": str(binding_path),
        "toolCall": {
            "tool": "export_module_mate_graph",
            "arguments": {
                "sourceAssemblyPath": str(assembly_path),
                "moduleTokens": tokens,
                "outputPath": str(graph_path),
                "saveJson": True,
            },
        },
        "executionBoundary": {
            "operation": "read_only_graph_export",
            "solidWorksAssemblyModified": False,
        },
        "createdAt": _now(),
    }
    spec["specDigest"] = _json_digest(
        {key: value for key, value in spec.items() if key != "createdAt"}
    )
    return spec


def finalize_checkpoint_graph_export(
    spec: dict[str, Any], tool_status: str
) -> dict[str, Any]:
    """Validate the written graph and create its immutable checkpoint binding."""

    if spec.get("schemaVersion") != EXPORT_SPEC_SCHEMA:
        raise CheckpointMateGraphAdapterError("不支持的检查点配合图导出规格。")
    if tool_status != "ok":
        raise CheckpointMateGraphAdapterError(
            f"SolidWorks只读配合图导出未成功：{tool_status}"
        )
    assembly_path = Path(str((spec.get("checkpointAssembly") or {}).get("path") or ""))
    expected_assembly_sha = str(
        (spec.get("checkpointAssembly") or {}).get("sha256") or ""
    )
    if not assembly_path.is_file() or _file_digest(assembly_path) != expected_assembly_sha:
        raise CheckpointMateGraphAdapterError("导出期间Demo检查点装配体发生变化。")
    graph_path = Path(str(spec.get("outputGraphPath") or ""))
    if not graph_path.is_file():
        raise CheckpointMateGraphAdapterError(f"配合图文件不存在：{graph_path}")
    graph = _read_json(graph_path)
    if not _same_path(str(graph.get("SourceAssemblyPath") or ""), assembly_path):
        raise CheckpointMateGraphAdapterError("配合图的源装配体不是已绑定Demo检查点。")
    modules = graph.get("Modules")
    mates = graph.get("Mates")
    if not isinstance(modules, list) or not isinstance(mates, list):
        raise CheckpointMateGraphAdapterError("导出配合图缺少Modules或Mates数组。")
    exported_tokens = {
        str(row.get("ModuleToken") or "").upper() for row in modules
    }
    missing = sorted(set(spec.get("moduleTokens") or []) - exported_tokens)
    if missing:
        raise CheckpointMateGraphAdapterError(
            "配合图未覆盖请求的模组：" + "、".join(missing)
        )
    binding = {
        "schemaVersion": GRAPH_BINDING_SCHEMA,
        "contextId": spec["contextId"],
        "contextRevision": spec["contextRevision"],
        "contextDigest": spec["contextDigest"],
        "demoJobId": spec["demoJobId"],
        "projectId": spec["projectId"],
        "checkpointAssembly": copy.deepcopy(spec["checkpointAssembly"]),
        "mateGraph": {
            "path": str(graph_path.resolve()),
            "sha256": _file_digest(graph_path),
            "schemaVersion": graph.get("SchemaVersion"),
            "moduleCount": len(modules),
            "mateCount": len(mates),
        },
        "moduleTokenByInstanceId": copy.deepcopy(spec["moduleTokenByInstanceId"]),
        "sourceProjectByInstanceId": copy.deepcopy(
            spec.get("sourceProjectByInstanceId") or {}
        ),
        "exportSpecDigest": spec["specDigest"],
        "createdAt": _now(),
    }
    binding["bindingDigest"] = _json_digest(binding)
    binding_path = Path(str(spec["bindingPath"]))
    _write_json(binding_path, binding)
    return {
        "success": True,
        "status": "bound",
        "binding": binding,
        "bindingPath": str(binding_path),
        "sourceAssemblyModified": False,
    }


_MATE_TYPE_NAMES = {
    0: "swMateCOINCIDENT",
    2: "swMatePERPENDICULAR",
    3: "swMatePARALLEL",
    5: "swMateDISTANCE",
    6: "swMateANGLE",
}


_MATE_ALIGNMENT_NAMES = {
    0: "swMateAlignALIGNED",
    1: "swMateAlignANTI_ALIGNED",
    2: "swMateAlignCLOSEST",
}


def _selected_face_alignment(
    mate_type: int,
    endpoint_ids: list[str],
    endpoint_catalog: dict[str, Any],
    draft: dict[str, Any],
) -> tuple[int, str, dict[str, Any]]:
    """Keep a selected planar pair in its observed normal relationship.

    A coincident mate with the wrong aligned/anti-aligned flag can satisfy the
    same infinite plane after flipping and translating an otherwise under-
    constrained module.  The selected faces already carry assembly-context
    normals, so use those normals instead of silently defaulting to ALIGNED.
    """

    fallback = int(draft.get("alignment") or 0)
    fallback_name = _MATE_ALIGNMENT_NAMES.get(fallback, "swMateAlignALIGNED")
    evidence: dict[str, Any] = {
        "method": "draft_fallback",
        "normalDot": None,
        "reason": "mate type is not coincident or world normals are unavailable",
    }
    if mate_type != 0 or len(endpoint_ids) != 2:
        return fallback, fallback_name, evidence
    entries = {
        str(row.get("EndpointId") or ""): row
        for row in endpoint_catalog.get("Endpoints") or []
    }
    try:
        normals = [
            [float(value) for value in entries[endpoint_id]["Endpoint"]["FaceNormalWorld"]]
            for endpoint_id in endpoint_ids
        ]
    except (KeyError, TypeError, ValueError):
        return fallback, fallback_name, evidence
    if any(len(normal) != 3 for normal in normals):
        return fallback, fallback_name, evidence
    lengths = [math.sqrt(sum(value * value for value in normal)) for normal in normals]
    if min(lengths) <= 1e-12:
        return fallback, fallback_name, evidence
    dot = sum(first * second for first, second in zip(*normals)) / (
        lengths[0] * lengths[1]
    )
    if abs(abs(dot) - 1.0) > 1e-4:
        raise CheckpointMateGraphAdapterError(
            f"重合配合要求两选择面平行，当前法向点积为{dot:.9f}。"
        )
    alignment = 1 if dot < 0 else 0
    return alignment, _MATE_ALIGNMENT_NAMES[alignment], {
        "method": "selected_face_world_normals",
        "normalDot": dot,
        "reason": "preserve the selected faces' observed normal relationship",
    }


def _verify_binding(binding: dict[str, Any]) -> tuple[Path, Path, dict[str, Any]]:
    if binding.get("schemaVersion") != GRAPH_BINDING_SCHEMA:
        raise CheckpointMateGraphAdapterError("不支持的检查点配合图绑定。")
    expected_digest = str(binding.get("bindingDigest") or "")
    digest_source = {key: value for key, value in binding.items() if key != "bindingDigest"}
    if expected_digest != _json_digest(digest_source):
        raise CheckpointMateGraphAdapterError("检查点配合图绑定摘要不匹配。")
    assembly_path = Path(
        str((binding.get("checkpointAssembly") or {}).get("path") or "")
    )
    graph_path = Path(str((binding.get("mateGraph") or {}).get("path") or ""))
    if not assembly_path.is_file() or _file_digest(assembly_path) != str(
        (binding.get("checkpointAssembly") or {}).get("sha256") or ""
    ):
        raise CheckpointMateGraphAdapterError("绑定的Demo检查点已变化。")
    if not graph_path.is_file() or _file_digest(graph_path) != str(
        (binding.get("mateGraph") or {}).get("sha256") or ""
    ):
        raise CheckpointMateGraphAdapterError("绑定的配合图已变化。")
    return assembly_path, graph_path, _read_json(graph_path)


def load_checkpoint_graph_binding(spec: dict[str, Any]) -> dict[str, Any]:
    """Load a cached binding only when it still describes this exact spec."""

    binding_path = Path(str(spec.get("bindingPath") or ""))
    if not binding_path.is_file():
        raise CheckpointMateGraphAdapterError("当前检查点尚未导出并绑定配合图。")
    binding = _read_json(binding_path)
    _verify_binding(binding)
    expected = {
        "contextId": spec.get("contextId"),
        "contextRevision": spec.get("contextRevision"),
        "contextDigest": spec.get("contextDigest"),
        "demoJobId": spec.get("demoJobId"),
        "projectId": spec.get("projectId"),
        "exportSpecDigest": spec.get("specDigest"),
    }
    mismatched = [key for key, value in expected.items() if binding.get(key) != value]
    if mismatched:
        raise CheckpointMateGraphAdapterError(
            "缓存配合图绑定已过期：" + "、".join(mismatched)
        )
    return binding


def compile_temporary_connection_for_checkpoint(
    context: dict[str, Any],
    binding: dict[str, Any],
    temporary_preview: dict[str, Any],
    endpoint_catalog: dict[str, Any],
    *,
    target_module_token: str,
    output_dir: Path | None = None,
    target_leaf_pose_anchors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compile all existing target mates plus one selected-face mate.

    The effective graph is intentionally target-local so it is suitable for the
    existing assembly-context remate executor.  No CAD operation occurs here.
    """

    assembly_path, graph_path, source_graph = _verify_binding(binding)
    if temporary_preview.get("status") != "ready":
        raise CheckpointMateGraphAdapterError("临时配合草案尚未就绪。")
    if temporary_preview.get("contextId") != context.get("contextId"):
        raise CheckpointMateGraphAdapterError("临时配合草案属于其他上下文。")
    if int(temporary_preview.get("contextRevision") or -1) != int(
        context.get("revision") or 0
    ):
        raise CheckpointMateGraphAdapterError("临时配合草案的上下文修订已过期。")
    if str(temporary_preview.get("contextDigest") or "") != str(
        context.get("contextDigest") or ""
    ):
        raise CheckpointMateGraphAdapterError("临时配合草案的上下文摘要已过期。")
    for field in ("contextId", "contextRevision", "contextDigest"):
        if binding.get(field) != context.get(
            {"contextId": "contextId", "contextRevision": "revision", "contextDigest": "contextDigest"}[field]
        ):
            raise CheckpointMateGraphAdapterError("检查点绑定不是当前上下文修订。")
    preview_digest = str(temporary_preview.get("previewDigest") or "")
    preview_source = {
        key: value for key, value in temporary_preview.items() if key != "previewDigest"
    }
    if preview_digest != _json_digest(preview_source):
        raise CheckpointMateGraphAdapterError("临时配合草案摘要不匹配。")
    if endpoint_catalog.get("SchemaVersion") != "solidworks-face-endpoint-catalog/v1":
        raise CheckpointMateGraphAdapterError("临时面目录版本不受支持。")
    catalog_source = str(endpoint_catalog.get("SourceAssemblyPath") or "").strip()
    if catalog_source and not _same_path(catalog_source, assembly_path):
        raise CheckpointMateGraphAdapterError("临时面目录来自其他装配体。")

    target = str(target_module_token or "").strip().upper()
    selected_ports = temporary_preview.get("selectedPorts") or []
    selected_tokens = [str(row.get("moduleToken") or "").upper() for row in selected_ports]
    if target not in selected_tokens:
        raise CheckpointMateGraphAdapterError("目标重配模组必须是两个已选面之一。")
    if len(selected_tokens) != 2 or len(set(selected_tokens)) != 2:
        raise CheckpointMateGraphAdapterError("临时配合必须连接两个不同模组。")
    module_by_token = {
        str(row.get("ModuleToken") or "").upper(): row
        for row in source_graph.get("Modules") or []
    }
    if target not in module_by_token:
        raise CheckpointMateGraphAdapterError(f"检查点配合图中没有目标模组{target}。")
    missing_selected = [token for token in selected_tokens if token not in module_by_token]
    if missing_selected:
        raise CheckpointMateGraphAdapterError(
            "检查点配合图缺少选面模组：" + "、".join(missing_selected)
        )
    incident = [
        copy.deepcopy(mate)
        for mate in source_graph.get("Mates") or []
        if target in {
            str(value).upper() for value in mate.get("ModuleTokens") or []
        }
    ]
    involved = {target, *selected_tokens}
    for mate in incident:
        involved.update(str(value).upper() for value in mate.get("ModuleTokens") or [])
    subset = copy.deepcopy(source_graph)
    subset["Modules"] = [
        copy.deepcopy(row)
        for row in source_graph.get("Modules") or []
        if str(row.get("ModuleToken") or "").upper() in involved
    ]
    subset["Mates"] = incident
    subset["ModuleCount"] = len(subset["Modules"])
    subset["InterModuleMateCount"] = len(incident)

    draft = temporary_preview.get("mateDraft") or {}
    mate_type = int(draft.get("mateType"))
    if mate_type not in _MATE_TYPE_NAMES:
        raise CheckpointMateGraphAdapterError(f"暂不支持配合类型{mate_type}。")
    other = next(token for token in selected_tokens if token != target)
    mate_name = f"NL_{target}_{other}_{preview_digest[:10]}"
    endpoint_ids = [str(value) for value in temporary_preview.get("endpointIds") or []]
    alignment, alignment_name, alignment_evidence = _selected_face_alignment(
        mate_type, endpoint_ids, endpoint_catalog, draft
    )
    mate: dict[str, Any] = {
        "MateName": mate_name,
        "MateType": mate_type,
        "MateTypeName": _MATE_TYPE_NAMES[mate_type],
        "Alignment": alignment,
        "AlignmentName": alignment_name,
        "Distance": None,
        "Angle": None,
        "IsSuppressed": False,
    }
    if mate_type == 5:
        distance = draft.get("distanceMeters")
        if distance is None or not math.isfinite(float(distance)) or float(distance) < 0:
            raise CheckpointMateGraphAdapterError("距离配合缺少有效距离。")
        mate["Distance"] = float(distance)
    if mate_type == 6:
        degrees = draft.get("angleDegrees")
        if degrees is None or not math.isfinite(float(degrees)):
            raise CheckpointMateGraphAdapterError("角度配合缺少有效角度。")
        mate["Angle"] = math.radians(float(degrees))
    base = "A600" if "A600" in involved and target != "A600" else other
    uses_checkpoint_pose_anchor = len(incident) == 0
    patch = {
        "schemaVersion": "mate-graph-patch/v1",
        "baseModuleToken": base,
        "initialPlacementMode": "source_pose",
        "fixedContextModuleTokens": sorted(involved - {target}),
        "caseAnchoredModuleTokens": [target] if uses_checkpoint_pose_anchor else [],
        # Direct context editing preserves existing source mates.  PatchAudit tells
        # the CAD executor that only the newly added mate must be created.
        "sourceMateNamesToSuppress": [],
        "targetLeafPoseAnchors": copy.deepcopy(target_leaf_pose_anchors or []),
        "operations": [
            {
                "operation": "addMate",
                "mate": mate,
                "endpointIds": endpoint_ids,
            }
        ],
    }
    try:
        effective = compile_mate_graph_patch(subset, patch, endpoint_catalog)
    except MateGraphEditError as exc:
        raise CheckpointMateGraphAdapterError(str(exc)) from exc
    try:
        dof_analysis = analyze_target_mate_dof(effective, target)
    except MateDofAnalysisError as exc:
        raise CheckpointMateGraphAdapterError(str(exc)) from exc
    try:
        transaction_preflight = preflight_direct_mate_transaction(effective, target)
    except MateTransactionPreflightError as exc:
        raise CheckpointMateGraphAdapterError(str(exc)) from exc
    state_policy = evaluate_component_state_policy(
        effective,
        target,
        execution_mode="direct_existing_component_mate_edit",
    )
    if state_policy.get("status") != "ready":
        raise CheckpointMateGraphAdapterError(
            "刚柔性执行策略未就绪：" + str(state_policy.get("reason") or "unknown")
        )
    if any(
        target
        not in {str(value).upper() for value in mate_row.get("ModuleTokens") or []}
        for mate_row in effective.get("Mates") or []
    ):
        raise CheckpointMateGraphAdapterError(
            "生成的目标局部图含有不关联目标模组的配合，拒绝交给重配执行器。"
        )
    next_tool = "remate_component_in_assembly_context_from_mate_graph"
    status = "ready_for_explicit_direct_mate_edit_confirmation"
    result = {
        "schemaVersion": COMPILED_PREVIEW_SCHEMA,
        "status": status,
        "contextId": context["contextId"],
        "contextRevision": context["revision"],
        "contextDigest": context["contextDigest"],
        "demoJobId": binding["demoJobId"],
        "checkpointAssemblyPath": str(assembly_path),
        "checkpointAssemblySha256": binding["checkpointAssembly"]["sha256"],
        "sourceMateGraphPath": str(graph_path),
        "sourceMateGraphSha256": binding["mateGraph"]["sha256"],
        "targetModuleToken": target,
        "preservedExistingMateNames": [
            str(row.get("MateName") or "") for row in incident
        ],
        "newMateName": mate_name,
        "constraintSafety": {
            "sourceDrivingMateCount": len(incident),
            "usesCheckpointPoseAnchor": uses_checkpoint_pose_anchor,
            "executionStrategy": "direct_existing_component_mate_edit",
            "claimBoundary": (
                "在当前Demo检查点的已有组件上新增面配合；其余自由度仍由当前位姿与既有配合保持，"
                "这不是厂商安装基准，也不证明跨项目通用定位。"
                if uses_checkpoint_pose_anchor
                else "目标既有驱动配合原位保留；仅创建新增配合，并在CAD执行时验证不过约束。"
            ),
            "selectedFaceAlignment": alignment_evidence,
            "targetLeafPoseAnchorCount": len(target_leaf_pose_anchors or []),
            "rigidBodyDofAnalysis": dof_analysis,
            "directMateTransactionPreflight": transaction_preflight,
            "componentStatePolicy": state_policy,
        },
        "patch": patch,
        "effectiveGraph": effective,
        "executionBoundary": {
            "solidWorksModified": False,
            "nextTool": next_tool,
            "requiresExplicitConfirmation": True,
        },
        "createdAt": _now(),
    }
    result["compiledPreviewDigest"] = _json_digest(result)
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        prefix = f"{binding['demoJobId']}-{target.lower()}-{preview_digest[:10]}"
        patch_path = output_dir / f"{prefix}.patch.json"
        graph_output_path = output_dir / f"{prefix}.effective-graph.json"
        preview_path = output_dir / f"{prefix}.compiled-preview.json"
        _write_json(patch_path, patch)
        _write_json(graph_output_path, effective)
        persisted = copy.deepcopy(result)
        persisted["artifacts"] = {
            "patchPath": str(patch_path),
            "effectiveGraphPath": str(graph_output_path),
            "compiledPreviewPath": str(preview_path),
        }
        _write_json(preview_path, persisted)
        result = persisted
    return result
