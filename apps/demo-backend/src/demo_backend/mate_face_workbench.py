from __future__ import annotations

import json
import hashlib
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .face_endpoint_catalog import (
    FaceEndpointCatalogError,
    list_face_candidates,
    validate_mate_endpoint_pair,
)
from .mate_graph_edit import MateGraphEditError, compile_mate_graph_patch


DEFAULT_CATALOG_RELATIVE = Path(
    "demo/mate_graph_edit/face_catalog/project02_A500_A700_seed_plus_A720009_leaf_v1.json"
)
DEFAULT_SOURCE_GRAPH_RELATIVE = Path("demo/layout_previews/project02_module_mate_graph_v3.json")

MATE_TYPES: dict[int, tuple[str, str]] = {
    0: ("重合", "swMateCOINCIDENT"),
    2: ("垂直", "swMatePERPENDICULAR"),
    3: ("平行", "swMatePARALLEL"),
    5: ("距离", "swMateDISTANCE"),
    6: ("角度", "swMateANGLE"),
}


class MateFaceWorkbenchError(ValueError):
    pass


def _workspace_json(workspace: Path, value: str | None, default: Path) -> Path:
    root = workspace.resolve()
    path = Path(value) if value else default
    resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise MateFaceWorkbenchError("Workbench JSON paths must remain inside the workspace.") from exc
    if not resolved.is_file():
        raise MateFaceWorkbenchError(f"Workbench JSON file was not found: {resolved}")
    return resolved


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MateFaceWorkbenchError(f"Could not read JSON '{path}': {exc}") from exc
    if not isinstance(value, dict):
        raise MateFaceWorkbenchError(f"JSON root must be an object: {path}")
    return value


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _application_digest(
    source_graph: dict[str, Any],
    catalog: dict[str, Any],
    patch: dict[str, Any],
) -> str:
    return _canonical_digest(
        {
            "sourceGraphSha256": _canonical_digest(source_graph),
            "catalogSha256": _canonical_digest(catalog),
            "patch": patch,
        }
    )


def _write_json_exclusive(path: Path, value: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _workspace_application_output(workspace: Path, value: str) -> Path:
    workspace = workspace.resolve()
    allowed_root = (workspace / "demo" / "mate_graph_edit" / "ui_runs").resolve()
    candidate = Path(value)
    resolved = candidate.resolve() if candidate.is_absolute() else (workspace / candidate).resolve()
    try:
        resolved.relative_to(allowed_root)
    except ValueError as exc:
        raise MateFaceWorkbenchError(
            "Output assembly must remain inside demo/mate_graph_edit/ui_runs."
        ) from exc
    if resolved.suffix.lower() != ".sldasm":
        raise MateFaceWorkbenchError("Output assembly must use the .SLDASM extension.")
    return resolved


def _endpoint_view(entry: dict[str, Any]) -> dict[str, Any]:
    endpoint = entry.get("Endpoint") or {}
    return {
        "endpointId": entry.get("EndpointId"),
        "moduleToken": endpoint.get("ModuleToken"),
        "moduleHierarchyPath": endpoint.get("ModuleHierarchyPath"),
        "leafHierarchyPath": endpoint.get("LeafHierarchyPath"),
        "relativeLeafHierarchyPath": endpoint.get("RelativeLeafHierarchyPath"),
        "leafComponentName": endpoint.get("LeafComponentName"),
        "geometryClass": entry.get("GeometryClass"),
        "bodyIndex": endpoint.get("BodyIndex"),
        "faceIndex": endpoint.get("FaceIndexInBody"),
        "faceAreaSquareMeters": endpoint.get("FaceArea"),
        "faceCenterLocal": endpoint.get("FaceCenterLocal"),
        "faceCenterWorld": endpoint.get("FaceCenterWorld"),
        "faceNormalLocal": endpoint.get("FaceNormalLocal"),
        "faceNormalWorld": endpoint.get("FaceNormalWorld"),
        "recoveryConfidence": entry.get("RecoveryConfidence"),
    }


def load_face_endpoint_workbench(
    workspace: Path,
    catalog_path: str | None = None,
) -> dict[str, Any]:
    path = _workspace_json(workspace, catalog_path, DEFAULT_CATALOG_RELATIVE)
    catalog = _read_json(path)
    try:
        entries = list_face_candidates(catalog, geometry_class=None)
    except FaceEndpointCatalogError as exc:
        raise MateFaceWorkbenchError(str(exc)) from exc
    endpoints = [_endpoint_view(entry) for entry in entries]
    modules = sorted({str(item["moduleToken"]) for item in endpoints if item.get("moduleToken")})
    leaves = sorted(
        {
            str(item["relativeLeafHierarchyPath"])
            for item in endpoints
            if item.get("relativeLeafHierarchyPath")
        }
    )
    return {
        "success": True,
        "catalogPath": str(path),
        "catalogMode": catalog.get("CatalogMode"),
        "sourceAssemblyPath": catalog.get("SourceAssemblyPath"),
        "endpointCount": len(endpoints),
        "modules": modules,
        "leaves": leaves,
        "mergedLeafSelectors": catalog.get("MergedLeafSelectors") or [],
        "endpoints": endpoints,
        "message": f"Loaded {len(endpoints)} reusable face endpoints without starting a new CAD scan.",
    }


def build_face_mate_patch_preview(
    workspace: Path,
    payload: dict[str, Any],
) -> dict[str, Any]:
    catalog_path = _workspace_json(
        workspace,
        str(payload.get("catalogPath") or "") or None,
        DEFAULT_CATALOG_RELATIVE,
    )
    source_graph_path = _workspace_json(
        workspace,
        str(payload.get("sourceGraphPath") or "") or None,
        DEFAULT_SOURCE_GRAPH_RELATIVE,
    )
    catalog = _read_json(catalog_path)
    source_graph = _read_json(source_graph_path)
    endpoint_ids = [str(payload.get("faceAEndpointId") or ""), str(payload.get("faceBEndpointId") or "")]
    mate_type = int(payload.get("mateType", -1))
    if mate_type not in MATE_TYPES:
        raise MateFaceWorkbenchError(f"Workbench mate type {mate_type} is not supported.")
    try:
        selected = validate_mate_endpoint_pair(catalog, endpoint_ids, mate_type)
    except FaceEndpointCatalogError as exc:
        raise MateFaceWorkbenchError(str(exc)) from exc
    endpoints = [item.get("Endpoint") or {} for item in selected]
    module_tokens = list(dict.fromkeys(str(item.get("ModuleToken") or "") for item in endpoints))
    label, type_name = MATE_TYPES[mate_type]
    distance = None
    angle = None
    if mate_type == 5:
        distance = float(payload.get("distanceMeters", 0.0))
        if not math.isfinite(distance) or distance < 0:
            raise MateFaceWorkbenchError("Distance must be a finite non-negative value in metres.")
    if mate_type == 6:
        angle_degrees = float(payload.get("angleDegrees", 0.0))
        if not math.isfinite(angle_degrees):
            raise MateFaceWorkbenchError("Angle must be finite.")
        angle = math.radians(angle_degrees)
    mate_name = str(payload.get("mateName") or f"界面新增{label}1").strip()
    if not mate_name:
        raise MateFaceWorkbenchError("Mate name must not be empty.")
    patch = {
        "schemaVersion": "mate-graph-patch/v1",
        "includeModuleTokens": module_tokens,
        "baseModuleToken": module_tokens[0],
        "initialPlacementMode": "source_pose",
        "operations": [
            {
                "operation": "addMate",
                "endpointIds": endpoint_ids,
                "mate": {
                    "MateName": mate_name,
                    "MateType": mate_type,
                    "MateTypeName": type_name,
                    "Alignment": int(payload.get("alignment", 0)),
                    "AlignmentName": "swMateAlignALIGNED"
                    if int(payload.get("alignment", 0)) == 0
                    else "swMateAlignANTI_ALIGNED",
                    "Distance": distance,
                    "Angle": angle,
                },
            }
        ],
    }
    try:
        effective = compile_mate_graph_patch(source_graph, patch, catalog)
    except MateGraphEditError as exc:
        raise MateFaceWorkbenchError(str(exc)) from exc
    return {
        "success": True,
        "compatible": True,
        "message": f"两个平面端点可用于{label}配合；当前仅生成预览，不修改SolidWorks。",
        "catalogPath": str(catalog_path),
        "sourceGraphPath": str(source_graph_path),
        "selectedEndpoints": [_endpoint_view(item) for item in selected],
        "patch": patch,
        "previewDigest": _application_digest(source_graph, catalog, patch),
        "suggestedOutputAssemblyPath": str(
            workspace.resolve()
            / "demo"
            / "mate_graph_edit"
            / "ui_runs"
            / (
                "project02_A500_A700_ui_"
                + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                + ".SLDASM"
            )
        ),
        "effectiveSummary": {
            "moduleCount": effective.get("ModuleCount"),
            "mateCount": effective.get("InterModuleMateCount"),
            "operationCount": (effective.get("PatchAudit") or {}).get("operationCount"),
            "warnings": (effective.get("PatchAudit") or {}).get("warnings") or [],
        },
    }


def prepare_face_mate_patch_application(
    workspace: Path,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if payload.get("confirmed") is not True:
        raise MateFaceWorkbenchError(
            "Explicit confirmation is required before creating a SolidWorks assembly."
        )
    preview = build_face_mate_patch_preview(workspace, payload)
    supplied_digest = str(payload.get("previewDigest") or "").strip()
    if not supplied_digest or supplied_digest != preview["previewDigest"]:
        raise MateFaceWorkbenchError(
            "Patch preview has changed or is stale; generate a new preview before applying it."
        )

    output_value = str(payload.get("outputAssemblyPath") or "").strip()
    if not output_value:
        raise MateFaceWorkbenchError("A new output assembly path is required.")
    output_path = _workspace_application_output(workspace, output_value)
    patch_path = output_path.with_suffix(".patch.json")
    effective_path = output_path.with_suffix(".effective.json")
    result_path = output_path.with_suffix(".result.json")
    existing = [path for path in (output_path, patch_path, effective_path, result_path) if path.exists()]
    if existing:
        raise MateFaceWorkbenchError(
            "Refusing to overwrite existing output: " + ", ".join(str(path) for path in existing)
        )

    catalog = _read_json(Path(preview["catalogPath"]))
    source_graph = _read_json(Path(preview["sourceGraphPath"]))
    try:
        effective = compile_mate_graph_patch(source_graph, preview["patch"], catalog)
    except MateGraphEditError as exc:
        raise MateFaceWorkbenchError(str(exc)) from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_exclusive(patch_path, preview["patch"])
    _write_json_exclusive(effective_path, effective)
    return {
        "preview": preview,
        "outputAssemblyPath": str(output_path),
        "patchPath": str(patch_path),
        "effectiveGraphPath": str(effective_path),
        "resultPath": str(result_path),
        "preparedAtUtc": datetime.now(timezone.utc).isoformat(),
    }


def finalize_face_mate_patch_application(
    prepared: dict[str, Any],
    operation: dict[str, Any],
) -> dict[str, Any]:
    tool_payload: dict[str, Any] = {}
    tool_results = operation.get("toolResults") or []
    if tool_results:
        texts = tool_results[-1].get("text") or []
        if texts:
            try:
                decoded = json.loads(texts[-1])
                if isinstance(decoded, dict):
                    tool_payload = decoded
            except json.JSONDecodeError:
                tool_payload = {}

    output_path = Path(prepared["outputAssemblyPath"])
    tool_success = bool(tool_payload.get("Success", tool_payload.get("success", False)))
    success = operation.get("status") == "ok" and tool_success and output_path.is_file()
    record = {
        "schemaVersion": "mate-face-workbench-application-result/v1",
        "success": success,
        "preparedAtUtc": prepared["preparedAtUtc"],
        "finishedAtUtc": datetime.now(timezone.utc).isoformat(),
        "previewDigest": prepared["preview"]["previewDigest"],
        "artifacts": {
            "outputAssemblyPath": prepared["outputAssemblyPath"],
            "patchPath": prepared["patchPath"],
            "effectiveGraphPath": prepared["effectiveGraphPath"],
            "resultPath": prepared["resultPath"],
        },
        "operation": operation,
        "solidWorksResult": tool_payload,
    }
    _write_json_exclusive(Path(prepared["resultPath"]), record)
    requested = tool_payload.get("RequestedActiveMateCount", tool_payload.get("requestedActiveMateCount"))
    created = tool_payload.get("CreatedMateCount", tool_payload.get("createdMateCount"))
    reopened = tool_payload.get("ReopenedMateCount", tool_payload.get("reopenedMateCount"))
    parameters_match = tool_payload.get(
        "ReopenedMateParametersMatch",
        tool_payload.get("reopenedMateParametersMatch"),
    )
    creation_errors_clear = tool_payload.get(
        "MateCreationErrorsClear",
        tool_payload.get("mateCreationErrorsClear"),
    )
    components_not_overconstrained = tool_payload.get(
        "ReopenedComponentsNotOverConstrained",
        tool_payload.get("reopenedComponentsNotOverConstrained"),
    )
    component_semantics_match = tool_payload.get(
        "ReopenedComponentSemanticsMatch",
        tool_payload.get("reopenedComponentSemanticsMatch"),
    )
    return {
        "status": "ok" if success else "error",
        "success": success,
        "message": (
            "Patch已应用到新装配体，并完成保存、关闭、重开和配合参数复核。"
            if success
            else operation.get("message") or "SolidWorks重建未通过。"
        ),
        "previewDigest": prepared["preview"]["previewDigest"],
        "artifacts": record["artifacts"],
        "rebuildSummary": {
            "requestedMateCount": requested,
            "createdMateCount": created,
            "reopenedMateCount": reopened,
            "parametersMatch": parameters_match,
            "mateCreationErrorsClear": creation_errors_clear,
            "componentsNotOverConstrained": components_not_overconstrained,
            "componentSemanticsMatch": component_semantics_match,
        },
        "solidWorksResult": tool_payload,
    }
