"""Plan a read-only station inspection for an already published CAD output.

This bridge deliberately does not recreate mates or insert components.  It binds an
existing successful non-prototype CAD result to the existing bounded read-only
verifier, so older pair releases can receive current target-station evidence without
silently rerunning the assembly operation.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


SCHEMA = "saved-output-station-inspection-request/v1"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_digest(payload: dict) -> str:
    unsigned = dict(payload)
    unsigned.pop("requestDigest", None)
    return hashlib.sha256(
        json.dumps(
            unsigned,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _resolve(workspace: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (workspace / path).resolve()


def _reference_resolution(request: dict) -> tuple[list[dict], list[Path]]:
    """Authenticate optional immutable files used only for transient path lookup."""

    resolution = request.get("referenceResolution")
    if resolution is None:
        return [], []
    if resolution.get("policy") != "transient-exact-file-parent-search/v1":
        raise ValueError("Unsupported saved-output reference-resolution policy")
    mappings = resolution.get("mappings") or []
    if not mappings:
        raise ValueError("Reference resolution requires at least one exact mapping")
    authenticated: list[dict] = []
    folders: list[Path] = []
    saved_names: set[str] = set()
    for row in mappings:
        saved_path = str(row.get("savedPath") or "")
        resolved_path = Path(str(row.get("resolvedPath") or "")).resolve()
        expected_sha = str(row.get("sha256") or "")
        if not saved_path or not resolved_path.is_file():
            raise ValueError("Reference-resolution mapping is incomplete")
        if Path(saved_path).name.casefold() != resolved_path.name.casefold():
            raise ValueError("Resolved reference filename differs from the saved reference")
        saved_name = Path(saved_path).name.casefold()
        if saved_name in saved_names:
            raise ValueError("Duplicate saved reference in resolution mapping")
        saved_names.add(saved_name)
        actual_sha = _sha256(resolved_path)
        if actual_sha != expected_sha:
            raise ValueError("Resolved reference is missing or changed")
        authenticated.append(
            {
                "savedPath": saved_path,
                "resolvedPath": str(resolved_path),
                "sha256": actual_sha,
            }
        )
        if all(str(folder).casefold() != str(resolved_path.parent).casefold() for folder in folders):
            folders.append(resolved_path.parent)
    return authenticated, folders


def _saved_output_station_inspection_binding(
    workspace: Path, request_path: Path, *, require_new_evidence: bool
) -> dict:
    """Authenticate one inspection request and its immutable CAD inputs.

    Planning requires the output paths to be absent.  Downstream station-candidate
    derivation deliberately reuses the same authenticated request *after* the
    read-only state exists, so it uses this helper with ``require_new_evidence``
    disabled.  Keeping both paths behind the same checks prevents the postcheck
    bridge from accepting a different CAD result, graph or assembly.
    """

    workspace = workspace.resolve()
    request_path = request_path.resolve()
    request = _read(request_path)
    if request.get("schemaVersion") != SCHEMA:
        raise ValueError("Unsupported saved-output inspection request schema")
    if request.get("requestDigest") != _canonical_digest(request):
        raise ValueError("Saved-output inspection request digest mismatch")

    cad_binding = request.get("cadResult") or {}
    cad_path = _resolve(workspace, str(cad_binding.get("path") or ""))
    if not cad_path.is_file() or _sha256(cad_path) != cad_binding.get("sha256"):
        raise ValueError("Bound CAD result is missing or changed")
    cad = _read(cad_path)
    tool = cad.get("toolResult") or {}
    required_flags = (
        "Success",
        "Reopened",
        "ReopenedMateParametersMatch",
        "MateSolveClean",
        "TargetFullyConstrained",
        "IndependentComponentInserted",
    )
    if cad.get("success") is not True or any(tool.get(key) is not True for key in required_flags):
        raise ValueError("Bound CAD result is not a successful non-prototype closure")
    if tool.get("TargetCaseAnchored") not in (False, 0, None):
        raise ValueError("A case-anchored CAD result is not eligible for this inspection")
    if int(tool.get("AppliedTargetLeafPoseAnchorCount") or 0) != 0:
        raise ValueError("A leaf-anchored CAD result is not eligible for this inspection")

    assembly_path = Path(str(cad.get("outputAssemblyPath") or "")).resolve()
    expected_assembly_sha = request.get("outputAssemblySha256")
    if (
        not assembly_path.is_file()
        or _sha256(assembly_path) != cad.get("outputAssemblySha256")
        or _sha256(assembly_path) != expected_assembly_sha
    ):
        raise ValueError("Bound output assembly is missing or changed")

    graph_path = Path(str(cad.get("executionEffectiveGraphPath") or "")).resolve()
    if (
        not graph_path.is_file()
        or _sha256(graph_path) != cad.get("executionEffectiveGraphSha256")
    ):
        raise ValueError("Bound effective mate graph is missing or changed")
    graph = _read(graph_path)
    modules = graph.get("Modules") or []
    expected_count = request.get("expectedTopLevelComponentCount")
    if not isinstance(expected_count, int) or expected_count < 2:
        raise ValueError("Expected top-level component count must be at least two")
    if len(modules) != expected_count:
        raise ValueError("Expected component count differs from the effective graph")

    base_token = request.get("baseToken")
    target_token = request.get("targetToken")
    if tool.get("TargetModuleToken") != target_token:
        raise ValueError("Requested target differs from the CAD result")
    if sum(row.get("ModuleToken") == base_token for row in modules) != 1:
        raise ValueError("Requested base is not unique in the effective graph")
    if sum(row.get("ModuleToken") == target_token for row in modules) != 1:
        raise ValueError("Requested target is not unique in the effective graph")

    output_state_path = _resolve(workspace, str(request.get("outputStatePath") or ""))
    process_report_path = _resolve(
        workspace, str(request.get("processReportPath") or "")
    )
    if require_new_evidence and (
        output_state_path.exists() or process_report_path.exists()
    ):
        raise FileExistsError("Saved-output inspection evidence already exists")
    if output_state_path.parent != process_report_path.parent:
        raise ValueError("State and process evidence must share one immutable directory")

    source_binding = request.get("sourceCheckpoint")
    source_path = None
    if source_binding:
        source_path = _resolve(workspace, str(source_binding.get("path") or ""))
        if not source_path.is_file() or _sha256(source_path) != source_binding.get("sha256"):
            raise ValueError("Bound source checkpoint is missing or changed")

    command = [
        "python",
        "scripts/verify_datum_chain_live_state.py",
        "--cad-result",
        str(cad_path),
        "--report",
        str(output_state_path),
        "--count",
        str(expected_count),
        "--base",
        str(base_token),
    ]
    if source_path:
        command.extend(["--source", str(source_path)])
    reference_mappings, reference_folders = _reference_resolution(request)
    for folder in reference_folders:
        command.extend(["--reference-search-folder", str(folder)])
    return {
        "schemaVersion": "saved-output-station-inspection-plan/v1",
        "requestPath": str(request_path),
        "requestDigest": request["requestDigest"],
        "cadResultPath": str(cad_path),
        "cadResultSha256": _sha256(cad_path),
        "outputAssemblyPath": str(assembly_path),
        "outputAssemblySha256": expected_assembly_sha,
        "effectiveGraphPath": str(graph_path),
        "effectiveGraphSha256": _sha256(graph_path),
        "baseToken": base_token,
        "targetToken": target_token,
        "expectedTopLevelComponentCount": expected_count,
        "outputStatePath": str(output_state_path),
        "processReportPath": str(process_report_path),
        "sourceCheckpointPath": str(source_path) if source_path else None,
        "referenceResolutionMappings": reference_mappings,
        "referenceSearchFolders": [str(folder) for folder in reference_folders],
        "command": command,
        "readOnly": True,
        "cadStarted": False,
        "requiresCleanSolidWorksSession": True,
        "recreatesMatesOrComponents": False,
        "claimBoundary": request.get("claimBoundary"),
    }


def build_saved_output_station_inspection_plan(
    workspace: Path, request_path: Path
) -> dict:
    """Authenticate a historical CAD output and derive one bounded read-only action."""

    return _saved_output_station_inspection_binding(
        workspace, request_path, require_new_evidence=True
    )


def authenticate_saved_output_station_inspection_binding(
    workspace: Path, request_path: Path
) -> dict:
    """Re-authenticate a completed read-only inspection without planning a rerun."""

    return _saved_output_station_inspection_binding(
        workspace, request_path, require_new_evidence=False
    )
