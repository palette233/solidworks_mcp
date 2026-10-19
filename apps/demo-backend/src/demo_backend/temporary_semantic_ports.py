"""Context-local semantic ports created from user-selected SolidWorks faces."""

from __future__ import annotations

import hashlib
import json
import math
import re
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .face_endpoint_catalog import append_face_endpoint


TEMPORARY_PORT_SCHEMA = "temporary-semantic-port-registry/v1"
TEMPORARY_CONNECTION_PREVIEW_SCHEMA = "temporary-connection-preview/v1"
_LOCK = threading.RLock()


class TemporarySemanticPortError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")[:32] or "port"


def registry_path(context_path: Path) -> Path:
    return context_path.with_suffix(".temporary-ports.json")


def endpoint_catalog_path(context_path: Path) -> Path:
    return context_path.with_suffix(".temporary-face-catalog.json")


def _new_registry(context: dict[str, Any]) -> dict[str, Any]:
    timestamp = _now()
    return {
        "schemaVersion": TEMPORARY_PORT_SCHEMA,
        "contextId": context["contextId"],
        "ports": [],
        "createdAt": timestamp,
        "updatedAt": timestamp,
    }


def _new_endpoint_catalog(context: dict[str, Any], source_path: str | None) -> dict[str, Any]:
    return {
        "SchemaVersion": "solidworks-face-endpoint-catalog/v1",
        "SourceAssemblyPath": source_path,
        "CatalogMode": "context_selected_faces",
        "EndpointCount": 0,
        "Endpoints": [],
        "ContextId": context["contextId"],
    }


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TemporarySemanticPortError(f"无法读取临时端口文件：{path}: {exc}") from exc
    if not isinstance(value, dict):
        raise TemporarySemanticPortError(f"临时端口文件根节点必须为对象：{path}")
    return value


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def reset_temporary_ports(context_path: Path, context: dict[str, Any]) -> None:
    with _LOCK:
        _write(registry_path(context_path), _new_registry(context))
        _write(endpoint_catalog_path(context_path), _new_endpoint_catalog(context, None))


def load_temporary_ports(context_path: Path, context: dict[str, Any]) -> dict[str, Any]:
    path = registry_path(context_path)
    registry = _read(path) if path.is_file() else _new_registry(context)
    if registry.get("schemaVersion") != TEMPORARY_PORT_SCHEMA:
        raise TemporarySemanticPortError("不支持的临时语义端口版本。")
    if registry.get("contextId") != context.get("contextId"):
        raise TemporarySemanticPortError("临时端口与装配上下文编号不一致。")
    if not isinstance(registry.get("ports"), list):
        raise TemporarySemanticPortError("临时端口文件缺少ports数组。")
    return registry


def parse_captured_endpoint(tool_result: dict[str, Any]) -> dict[str, Any]:
    if str(tool_result.get("status") or "") != "ok":
        raise TemporarySemanticPortError(
            str(tool_result.get("message") or "SolidWorks选面捕获未成功。")
        )
    rows = tool_result.get("toolResults") or tool_result.get("tool_results") or []
    for row in rows:
        texts = row.get("text") or []
        if isinstance(texts, str):
            texts = [texts]
        for text in texts:
            try:
                value = json.loads(text)
            except (TypeError, json.JSONDecodeError):
                continue
            if isinstance(value, dict) and value.get("EndpointId") and value.get("Endpoint"):
                return value
    raise TemporarySemanticPortError("SolidWorks结果中没有可登记的面端点JSON。")


def parse_active_assembly_path(tool_result: dict[str, Any]) -> str:
    """Read the assembly identity captured immediately before the selected face."""

    if str(tool_result.get("status") or "") != "ok":
        raise TemporarySemanticPortError("无法确认当前活动SolidWorks装配体。")
    for row in tool_result.get("toolResults") or tool_result.get("tool_results") or []:
        texts = row.get("text") or []
        if isinstance(texts, str):
            texts = [texts]
        for text in texts:
            try:
                value = json.loads(text)
            except (TypeError, json.JSONDecodeError):
                continue
            if (
                isinstance(value, dict)
                and int(value.get("Type") or value.get("type") or 0) == 2
                and str(value.get("Path") or value.get("path") or "").strip()
            ):
                return str(value.get("Path") or value.get("path")).strip()
    raise TemporarySemanticPortError("选面前无法取得活动装配体路径。")


def register_captured_face(
    context_path: Path,
    context: dict[str, Any],
    captured_entry: dict[str, Any],
    *,
    instance_id: str,
    module_token: str,
    display_name: str,
    interface_type: str,
    role: str = "primary",
    aliases: list[str] | None = None,
    source_assembly_path: str | None = None,
) -> dict[str, Any]:
    instances = {
        str(row.get("instanceId") or ""): row for row in context.get("instances") or []
    }
    instance = instances.get(instance_id)
    if instance is None:
        raise TemporarySemanticPortError(f"上下文中不存在模组实例：{instance_id}")
    endpoint = captured_entry.get("Endpoint") or {}
    captured_token = str(endpoint.get("ModuleToken") or "")
    if not captured_token or captured_token.casefold() != module_token.casefold():
        raise TemporarySemanticPortError(
            f"选中面的所属模组{captured_token!r}与声明的{module_token!r}不一致。"
        )
    if str(captured_entry.get("GeometryClass") or "").casefold() != "plane":
        raise TemporarySemanticPortError("当前人工兜底阶段只接受平面端点。")
    display_name = str(display_name or "").strip()
    interface_type = str(interface_type or "").strip()
    role = str(role or "primary").strip()
    if not display_name or not interface_type or not role:
        raise TemporarySemanticPortError("显示名称、接口类型和端点角色不能为空。")
    endpoint_id = str(captured_entry.get("EndpointId") or "").strip()
    if not endpoint_id:
        raise TemporarySemanticPortError("选面结果缺少EndpointId。")
    identity = {
        "contextId": context["contextId"],
        "instanceId": instance_id,
        "endpointId": endpoint_id,
        "interfaceType": interface_type,
        "role": role,
    }
    port_id = (
        f"temp:{context['contextId']}:{_slug(display_name)}:{_digest(identity)[:12]}"
    )
    normalized_aliases = list(
        dict.fromkeys(
            [
                display_name,
                port_id,
                *(str(value).strip() for value in aliases or [] if str(value).strip()),
            ]
        )
    )
    port = {
        "portId": port_id,
        "displayName": display_name,
        "aliases": normalized_aliases,
        "moduleInstanceId": instance_id,
        "moduleDefinitionId": instance.get("moduleDefinitionId"),
        "moduleToken": module_token,
        "moduleHierarchyPath": endpoint.get("ModuleHierarchyPath"),
        "category": "mechanical",
        "interfaceType": interface_type,
        "status": "user_selected_provisional",
        "endpointBindings": [{"role": role, "endpointId": endpoint_id}],
        "provenance": {
            "kind": "solidworks_user_selected_face",
            "sourceAssemblyPath": source_assembly_path,
            "capturedAtContextRevision": int(context.get("revision") or 0),
            "capturedAt": _now(),
        },
    }
    registry_file = registry_path(context_path)
    catalog_file = endpoint_catalog_path(context_path)
    with _LOCK:
        registry = load_temporary_ports(context_path, context)
        existing = next(
            (row for row in registry["ports"] if row.get("portId") == port_id), None
        )
        if existing is None:
            registry["ports"].append(port)
        elif existing != port:
            # Captured timestamps are provenance, not identity. Reuse the first
            # registration instead of producing duplicate endpoint aliases.
            port = existing

        if catalog_file.is_file():
            catalog = _read(catalog_file)
        else:
            catalog = _new_endpoint_catalog(
                context, source_assembly_path
            )
        catalog_source = str(catalog.get("SourceAssemblyPath") or "").strip()
        if source_assembly_path and catalog_source and Path(source_assembly_path).resolve() != Path(
            catalog_source
        ).resolve():
            raise TemporarySemanticPortError(
                "当前临时面目录已经绑定另一装配体；请新建上下文或重新捕获。"
            )
        if source_assembly_path and not catalog_source:
            catalog["SourceAssemblyPath"] = source_assembly_path
        if not any(
            row.get("EndpointId") == endpoint_id for row in catalog.get("Endpoints") or []
        ):
            catalog = append_face_endpoint(catalog, captured_entry)
        registry["updatedAt"] = _now()
        _write(registry_file, registry)
        _write(catalog_file, catalog)
    return {
        "success": True,
        "contextId": context["contextId"],
        "port": deepcopy(port),
        "registryPath": str(registry_file),
        "endpointCatalogPath": str(catalog_file),
        "cadModified": False,
    }


def _mentioned_ports(registry: dict[str, Any], requirement: str) -> list[dict[str, Any]]:
    text = str(requirement or "").casefold()
    rows = []
    for port in registry.get("ports") or []:
        terms = [port.get("portId"), port.get("displayName"), *(port.get("aliases") or [])]
        best = max(
            (len(str(term)) for term in terms if str(term).casefold() in text),
            default=0,
        )
        if best:
            rows.append((best, str(port["portId"]), port))
    rows.sort(key=lambda item: (-item[0], item[1]))
    return [row[2] for row in rows]


def preview_temporary_connection(
    context_path: Path,
    context: dict[str, Any],
    requirement: str,
    *,
    port_ids: list[str] | None = None,
) -> dict[str, Any]:
    registry = load_temporary_ports(context_path, context)
    by_id = {str(row["portId"]): row for row in registry.get("ports") or []}
    if port_ids:
        selected = [by_id.get(str(value)) for value in port_ids]
        if any(value is None for value in selected):
            raise TemporarySemanticPortError("显式端口编号中包含未知临时端口。")
        selected = [value for value in selected if value is not None]
    else:
        selected = _mentioned_ports(registry, requirement)
    blockers: list[dict[str, str]] = []
    if len(selected) != 2:
        blockers.append(
            {
                "code": "TWO_TEMPORARY_PORTS_REQUIRED",
                "detail": f"自然语言解析到{len(selected)}个临时端口，必须明确引用两个。",
            }
        )
    elif selected[0].get("moduleInstanceId") == selected[1].get("moduleInstanceId"):
        blockers.append(
            {
                "code": "DISTINCT_MODULE_INSTANCES_REQUIRED",
                "detail": "配合必须连接两个不同的模组实例。",
            }
        )
    text = str(requirement or "")
    mate_type = None
    mate_label = None
    distance_meters = None
    angle_degrees = None
    if "重合" in text or "贴合" in text:
        mate_type, mate_label = 0, "重合"
    elif "平行" in text:
        mate_type, mate_label = 3, "平行"
    elif "垂直" in text:
        mate_type, mate_label = 2, "垂直"
    elif "距离" in text or "间距" in text:
        match = re.search(r"(-?\d+(?:\.\d+)?)\s*(mm|毫米|m|米)", text, re.I)
        if match:
            value = float(match.group(1))
            distance_meters = value / 1000.0 if match.group(2).casefold() in {"mm", "毫米"} else value
        if distance_meters is None or not math.isfinite(distance_meters) or distance_meters < 0:
            blockers.append(
                {"code": "DISTANCE_VALUE_REQUIRED", "detail": "距离配合需要非负的mm或m数值。"}
            )
        mate_type, mate_label = 5, "距离"
    elif "角度" in text:
        match = re.search(r"(-?\d+(?:\.\d+)?)\s*(?:°|度)", text)
        if match:
            angle_degrees = float(match.group(1))
        if angle_degrees is None or not math.isfinite(angle_degrees):
            blockers.append(
                {"code": "ANGLE_VALUE_REQUIRED", "detail": "角度配合需要以度为单位的数值。"}
            )
        mate_type, mate_label = 6, "角度"
    else:
        blockers.append(
            {
                "code": "BASIC_MATE_TYPE_REQUIRED",
                "detail": "请明确重合、平行、垂直、距离或角度配合。",
            }
        )
    endpoint_ids = [
        str((port.get("endpointBindings") or [{}])[0].get("endpointId") or "")
        for port in selected[:2]
    ]
    payload = {
        "schemaVersion": TEMPORARY_CONNECTION_PREVIEW_SCHEMA,
        "contextId": context["contextId"],
        "contextRevision": int(context.get("revision") or 0),
        "contextDigest": context.get("contextDigest"),
        "requirement": requirement,
        "status": "ready" if not blockers else "blocked",
        "selectedPorts": deepcopy(selected[:2]),
        "endpointIds": endpoint_ids,
        "mateDraft": {
            "mateType": mate_type,
            "mateLabel": mate_label,
            "distanceMeters": distance_meters,
            "angleDegrees": angle_degrees,
            "alignment": 0,
        },
        "blockers": blockers,
        "endpointCatalogPath": str(endpoint_catalog_path(context_path)),
        "executionBoundary": {
            "solidWorksModified": False,
            "readyForCurrentCheckpointGraphAdapter": not blockers,
            "statement": "本阶段只完成用户选面到基础配合草案；执行前仍需导出/绑定当前Demo检查点的配合图。",
        },
    }
    payload["previewDigest"] = _digest(payload)
    return payload
