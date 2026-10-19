from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .semantic_port_catalog import (
    SemanticPortCatalogError,
    build_semantic_assembly_plan,
    build_semantic_connection_patch,
    select_semantic_port,
    validate_semantic_port_catalog,
)
from .semantic_assembly_intent import (
    SemanticAssemblyIntentError,
    parse_project02_semantic_assembly_intent,
    resolve_semantic_assembly_intent,
)


DEFAULT_DIR = Path("demo/semantic_ports/project02_A500_full_installation_v2")
DEFAULT_SEMANTIC_CATALOG = DEFAULT_DIR / "semantic_port_catalog.json"
DEFAULT_ENDPOINT_CATALOG = DEFAULT_DIR / "face_endpoint_catalog.json"
DEFAULT_SOURCE_GRAPH = DEFAULT_DIR / "base_A600_A700_graph.json"
DEFAULT_REQUEST = DEFAULT_DIR / "assembly_plan_request.json"
DEFAULT_CLOSURE_SUMMARY = (
    DEFAULT_DIR
    / "context_insert_v7_auto_closure"
    / "context_incremental_release_closure.json"
)
DEFAULT_NATURAL_LANGUAGE_REQUIREMENT = (
    "在项目02中，以A600和A700作为固定上下文，新增A500。"
    "A500保持刚性，A700保持柔性。将A500安装到A600，"
    "并验证A500与A700保持50 mm间距，不要将该间距作为驱动配合。"
    "另存为独立装配体。"
)


class SemanticPortWorkbenchError(ValueError):
    pass


def _workspace_file(workspace: Path, value: str | None, default: Path) -> Path:
    root = workspace.resolve()
    candidate = Path(value) if value else default
    resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise SemanticPortWorkbenchError("Semantic-port JSON files must remain inside the workspace.") from exc
    if not resolved.is_file():
        raise SemanticPortWorkbenchError(f"Semantic-port JSON file was not found: {resolved}")
    return resolved


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SemanticPortWorkbenchError(f"Could not read JSON '{path}': {exc}") from exc
    if not isinstance(value, dict):
        raise SemanticPortWorkbenchError(f"JSON root must be an object: {path}")
    return value


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _endpoint_map(endpoint_catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("EndpointId") or ""): item
        for item in endpoint_catalog.get("Endpoints") or []
    }


def _port_view(port: dict[str, Any], endpoint_catalog: dict[str, Any]) -> dict[str, Any]:
    by_id = _endpoint_map(endpoint_catalog)
    bindings = []
    for binding in port.get("endpointBindings") or []:
        endpoint_id = str(binding.get("endpointId") or "")
        entry = by_id.get(endpoint_id) or {}
        endpoint = entry.get("Endpoint") or {}
        bindings.append(
            {
                "role": binding.get("role"),
                "endpointId": endpoint_id,
                "geometryClass": entry.get("GeometryClass"),
                "leafHierarchyPath": endpoint.get("RelativeLeafHierarchyPath"),
                "faceIndex": endpoint.get("FaceIndexInBody"),
                "faceAreaSquareMeters": endpoint.get("FaceArea"),
                "faceCenterLocal": endpoint.get("FaceCenterLocal"),
                "faceNormalLocal": endpoint.get("FaceNormalLocal"),
                "recoveryConfidence": entry.get("RecoveryConfidence"),
            }
        )
    return {
        "portId": port.get("portId"),
        "displayName": port.get("displayName"),
        "description": port.get("description"),
        "moduleToken": port.get("moduleToken"),
        "moduleHierarchyPath": port.get("moduleHierarchyPath"),
        "category": port.get("category"),
        "interfaceType": port.get("interfaceType"),
        "status": port.get("status"),
        "evidence": port.get("evidence"),
        "endpointBindings": bindings,
    }


def load_semantic_port_workbench(
    workspace: Path,
    semantic_catalog_path: str | None = None,
    endpoint_catalog_path: str | None = None,
    source_graph_path: str | None = None,
    request_path: str | None = None,
) -> dict[str, Any]:
    semantic_path = _workspace_file(workspace, semantic_catalog_path, DEFAULT_SEMANTIC_CATALOG)
    endpoint_path = _workspace_file(workspace, endpoint_catalog_path, DEFAULT_ENDPOINT_CATALOG)
    graph_path = _workspace_file(workspace, source_graph_path, DEFAULT_SOURCE_GRAPH)
    demo_request_path = _workspace_file(workspace, request_path, DEFAULT_REQUEST)
    semantic_catalog = _read_json(semantic_path)
    endpoint_catalog = _read_json(endpoint_path)
    validation = validate_semantic_port_catalog(semantic_catalog, endpoint_catalog)
    closure_path = (workspace.resolve() / DEFAULT_CLOSURE_SUMMARY).resolve()
    latest_closure = _read_json(closure_path) if closure_path.is_file() else None
    return {
        "success": True,
        "projectId": semantic_catalog.get("projectId"),
        "semanticCatalogPath": str(semantic_path),
        "endpointCatalogPath": str(endpoint_path),
        "sourceGraphPath": str(graph_path),
        "demoRequestPath": str(demo_request_path),
        "ports": [_port_view(item, endpoint_catalog) for item in semantic_catalog.get("ports") or []],
        "connectionTemplates": semantic_catalog.get("connectionTemplates") or [],
        "demoRequest": _read_json(demo_request_path),
        "defaultNaturalLanguageRequirement": DEFAULT_NATURAL_LANGUAGE_REQUIREMENT,
        "latestClosurePath": str(closure_path) if latest_closure is not None else None,
        "latestClosure": latest_closure,
        "validation": validation,
        "message": "语义端口目录已加载；端口通过EndpointId绑定到现有面注册表。",
    }


def preview_semantic_assembly_intent(
    workspace: Path, payload: dict[str, Any]
) -> dict[str, Any]:
    """Parse natural language, ground it to ports, and compile a read-only preview."""

    semantic_path = _workspace_file(
        workspace,
        str(payload.get("semanticCatalogPath") or "") or None,
        DEFAULT_SEMANTIC_CATALOG,
    )
    endpoint_path = _workspace_file(
        workspace,
        str(payload.get("endpointCatalogPath") or "") or None,
        DEFAULT_ENDPOINT_CATALOG,
    )
    graph_path = _workspace_file(
        workspace,
        str(payload.get("sourceGraphPath") or "") or None,
        DEFAULT_SOURCE_GRAPH,
    )
    request_path = _workspace_file(
        workspace,
        str(payload.get("planTemplatePath") or "") or None,
        DEFAULT_REQUEST,
    )
    semantic_catalog = _read_json(semantic_path)
    endpoint_catalog = _read_json(endpoint_path)
    source_graph = _read_json(graph_path)
    plan_template = _read_json(request_path)
    try:
        validate_semantic_port_catalog(semantic_catalog, endpoint_catalog)
        intent = parse_project02_semantic_assembly_intent(
            str(payload.get("requirement") or "")
        )
        resolution = resolve_semantic_assembly_intent(
            intent, semantic_catalog, source_graph, plan_template
        )
    except (SemanticPortCatalogError, SemanticAssemblyIntentError) as exc:
        raise SemanticPortWorkbenchError(str(exc)) from exc

    compiled_preview = preview_semantic_connection(
        workspace,
        {
            "semanticCatalogPath": str(semantic_path),
            "endpointCatalogPath": str(endpoint_path),
            "sourceGraphPath": str(graph_path),
            "connectionRequest": resolution["assemblyPlan"],
        },
    )
    compiled_preview.update(
        {
            "message": (
                "自然语言需求已解析、完成语义端口选择并通过配合图预检；"
                "当前尚未修改SolidWorks。"
            ),
            "requirement": str(payload.get("requirement") or ""),
            "parsedIntent": intent,
            "intentResolution": resolution,
            "planTemplatePath": str(request_path),
        }
    )
    return compiled_preview


def preview_semantic_connection(workspace: Path, payload: dict[str, Any]) -> dict[str, Any]:
    semantic_path = _workspace_file(
        workspace,
        str(payload.get("semanticCatalogPath") or "") or None,
        DEFAULT_SEMANTIC_CATALOG,
    )
    endpoint_path = _workspace_file(
        workspace,
        str(payload.get("endpointCatalogPath") or "") or None,
        DEFAULT_ENDPOINT_CATALOG,
    )
    graph_path = _workspace_file(
        workspace,
        str(payload.get("sourceGraphPath") or "") or None,
        DEFAULT_SOURCE_GRAPH,
    )
    semantic_catalog = _read_json(semantic_path)
    endpoint_catalog = _read_json(endpoint_path)
    source_graph = _read_json(graph_path)
    request = payload.get("connectionRequest")
    if not isinstance(request, dict):
        raise SemanticPortWorkbenchError("connectionRequest must be an object.")
    execution_mode = str(payload.get("executionMode") or "context_incremental")
    if execution_mode not in {"blank_rebuild", "context_incremental"}:
        raise SemanticPortWorkbenchError(
            "executionMode must be blank_rebuild or context_incremental."
        )
    try:
        if request.get("schemaVersion") == "semantic-assembly-plan/v1":
            compiled = build_semantic_assembly_plan(
                source_graph, semantic_catalog, endpoint_catalog, request
            )
            port_ids = list(
                dict.fromkeys(
                    str(connection.get(field) or "")
                    for connection in request.get("connections") or []
                    for field in ("portAId", "portBId")
                )
            )
            selected_ports = [
                select_semantic_port(semantic_catalog, port_id) for port_id in port_ids
            ]
        else:
            compiled = build_semantic_connection_patch(
                source_graph, semantic_catalog, endpoint_catalog, request
            )
            selected_ports = [
                select_semantic_port(
                    semantic_catalog, str(request.get("portAId") or "")
                ),
                select_semantic_port(
                    semantic_catalog, str(request.get("portBId") or "")
                ),
            ]
    except SemanticPortCatalogError as exc:
        raise SemanticPortWorkbenchError(str(exc)) from exc
    preview_payload = {
        "sourceGraphSha256": _digest(source_graph),
        "semanticCatalogSha256": _digest(semantic_catalog),
        "endpointCatalogSha256": _digest(endpoint_catalog),
        "connectionRequest": request,
        "executionMode": execution_mode,
    }
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return {
        "success": True,
        "message": "语义端口连接预检通过；当前尚未修改SolidWorks。",
        "semanticCatalogPath": str(semantic_path),
        "endpointCatalogPath": str(endpoint_path),
        "sourceGraphPath": str(graph_path),
        "connectionRequest": request,
        "selectedPorts": [
            _port_view(port, endpoint_catalog) for port in selected_ports
        ],
        "patch": compiled["patch"],
        "effectiveSummary": compiled["summary"],
        "previewDigest": _digest(preview_payload),
        "suggestedOutputAssemblyPath": str(
            workspace.resolve()
            / "demo"
            / "semantic_ports"
            / "ui_runs"
            / f"project02_semantic_assembly_{timestamp}.SLDASM"
        ),
        "executionBoundary": {
            "mode": execution_mode,
            "modifiesPrototype": False,
            "preservesExistingParentContext": execution_mode == "context_incremental",
            "fullyLocatesAddedComponent": bool(
                compiled["summary"].get("cadVerifiedFullyConstrained")
                or (compiled["summary"].get("constraintEffect") or {}).get(
                    "fullyLocatesAddedComponent"
                ) is True
            ),
            "validationRelationCount": int(
                compiled["summary"].get("validationRelationCount") or 0
            ),
        },
    }


def _output_path(workspace: Path, value: str) -> Path:
    root = workspace.resolve()
    allowed = (root / "demo" / "semantic_ports" / "ui_runs").resolve()
    candidate = Path(value)
    resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    try:
        resolved.relative_to(allowed)
    except ValueError as exc:
        raise SemanticPortWorkbenchError(
            "Output assembly must remain inside demo/semantic_ports/ui_runs."
        ) from exc
    if resolved.suffix.lower() != ".sldasm":
        raise SemanticPortWorkbenchError("Output assembly must use the .SLDASM extension.")
    return resolved


def _write_exclusive(path: Path, value: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def prepare_semantic_connection_application(
    workspace: Path, payload: dict[str, Any]
) -> dict[str, Any]:
    if payload.get("confirmed") is not True:
        raise SemanticPortWorkbenchError("Explicit confirmation is required before CAD execution.")
    preview = preview_semantic_connection(workspace, payload)
    if str(payload.get("previewDigest") or "") != preview["previewDigest"]:
        raise SemanticPortWorkbenchError(
            "Semantic connection preview is stale; generate a new preview before applying."
        )
    output = _output_path(workspace, str(payload.get("outputAssemblyPath") or ""))
    request_path = output.with_suffix(".connection-request.json")
    patch_path = output.with_suffix(".patch.json")
    effective_path = output.with_suffix(".effective.json")
    result_path = output.with_suffix(".result.json")
    collisions = [
        path
        for path in (output, request_path, patch_path, effective_path, result_path)
        if path.exists()
    ]
    if collisions:
        raise SemanticPortWorkbenchError(
            "Refusing to overwrite existing output: " + ", ".join(str(item) for item in collisions)
        )
    semantic_catalog = _read_json(Path(preview["semanticCatalogPath"]))
    endpoint_catalog = _read_json(Path(preview["endpointCatalogPath"]))
    source_graph = _read_json(Path(preview["sourceGraphPath"]))
    request = preview["connectionRequest"]
    if request.get("schemaVersion") == "semantic-assembly-plan/v1":
        compiled = build_semantic_assembly_plan(
            source_graph, semantic_catalog, endpoint_catalog, request
        )
    else:
        compiled = build_semantic_connection_patch(
            source_graph, semantic_catalog, endpoint_catalog, request
        )
    execution_mode = str(payload.get("executionMode") or preview["executionBoundary"]["mode"])
    effective_graph = compiled["effectiveGraph"]
    source_assembly_path = str(
        effective_graph.get("SourceAssemblyPath")
        or effective_graph.get("sourceAssemblyPath")
        or source_graph.get("SourceAssemblyPath")
        or source_graph.get("sourceAssemblyPath")
        or ""
    )
    source_tokens = {
        str(item.get("ModuleToken") or item.get("moduleToken") or "")
        for item in (source_graph.get("Modules") or source_graph.get("modules") or [])
    }
    added_tokens = [
        str(item.get("ModuleToken") or item.get("moduleToken") or "")
        for item in (effective_graph.get("Modules") or effective_graph.get("modules") or [])
        if str(item.get("ModuleToken") or item.get("moduleToken") or "") not in source_tokens
    ]
    target_module_token = added_tokens[0] if len(added_tokens) == 1 else ""
    if execution_mode == "context_incremental":
        if not source_assembly_path:
            raise SemanticPortWorkbenchError(
                "context_incremental requires SourceAssemblyPath in the source/effective graph."
            )
        if not target_module_token:
            raise SemanticPortWorkbenchError(
                "context_incremental requires exactly one added component token."
            )
    output.parent.mkdir(parents=True, exist_ok=True)
    _write_exclusive(request_path, preview["connectionRequest"])
    _write_exclusive(patch_path, compiled["patch"])
    _write_exclusive(effective_path, compiled["effectiveGraph"])
    return {
        "preparedAtUtc": datetime.now(timezone.utc).isoformat(),
        "preview": preview,
        "outputAssemblyPath": str(output),
        "requestPath": str(request_path),
        "patchPath": str(patch_path),
        "effectiveGraphPath": str(effective_path),
        "resultPath": str(result_path),
        "executionMode": execution_mode,
        "sourceAssemblyPath": source_assembly_path,
        "targetModuleToken": target_module_token,
    }


def finalize_semantic_connection_application(
    prepared: dict[str, Any], operation: dict[str, Any]
) -> dict[str, Any]:
    tool_payload: dict[str, Any] = {}
    results = operation.get("toolResults") or []
    if results:
        texts = results[-1].get("text") or []
        if texts:
            try:
                candidate = json.loads(texts[-1])
                if isinstance(candidate, dict):
                    tool_payload = candidate
            except json.JSONDecodeError:
                pass
    tool_success = bool(tool_payload.get("Success", tool_payload.get("success", False)))
    validation_results = tool_payload.get(
        "ValidationResults", tool_payload.get("validationResults", [])
    ) or []
    validation_passed = sum(
        1 for item in validation_results if item.get("Passed", item.get("passed")) is True
    )
    validation_summary = {
        "relationCount": len(validation_results),
        "passedCount": validation_passed,
        "allPassed": len(validation_results) == validation_passed,
        "results": validation_results,
    }
    output_exists = Path(prepared["outputAssemblyPath"]).is_file()
    success = operation.get("status") == "ok" and tool_success and output_exists
    record = {
        "schemaVersion": "semantic-port-application-result/v1",
        "success": success,
        "preparedAtUtc": prepared["preparedAtUtc"],
        "finishedAtUtc": datetime.now(timezone.utc).isoformat(),
        "executionMode": prepared["executionMode"],
        "artifacts": {
            key: prepared[key]
            for key in (
                "outputAssemblyPath",
                "requestPath",
                "patchPath",
                "effectiveGraphPath",
                "resultPath",
            )
        },
        "operation": operation,
        "solidWorksResult": tool_payload,
        "validationSummary": validation_summary,
        "releaseGate": {
            "status": "PENDING_EXACT_INTERFERENCE",
            "releaseAllowed": False,
            "message": "CAD重建与工艺尺寸复核完成后，仍须通过独立实体干涉门禁。",
        },
    }
    _write_exclusive(Path(prepared["resultPath"]), record)
    return {
        "status": "ok" if success else "error",
        "success": success,
        "message": (
            "新增组件节点和语义端口连接已生成独立装配体，并完成保存重开复核。"
            if success
            else operation.get("message") or "语义端口CAD执行未通过。"
        ),
        "executionMode": record["executionMode"],
        "artifacts": record["artifacts"],
        "solidWorksResult": tool_payload,
        "validationSummary": validation_summary,
        "releaseGate": record["releaseGate"],
    }
