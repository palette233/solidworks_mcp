"""Audit Project05 leaf occupancy captures and produce a resumable work packet."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REQUIRED_CAPTURE_CODES = ("A000", "E000", "D000", "K000", "B000", "Z000", "F000", "G000", "M000", "N000", "P000")


def _capture_path(workspace: Path, code: str) -> Path:
    return workspace / "demo/layout_previews" / f"project05_{code.lower()}_world_leaf_envelopes.json"


def build_project05_structural_capture_plan(
    workspace: Path, readiness: dict[str, Any]
) -> dict[str, Any]:
    modules = {str(item.get("cadId") or ""): item for item in readiness.get("modules") or []}
    rows = []
    for code in REQUIRED_CAPTURE_CODES:
        path = _capture_path(workspace, code)
        complete = False
        body_count = 0
        error = None
        if path.is_file():
            try:
                payload = json.loads(path.read_text(encoding="utf-8-sig"))
                complete = payload.get("coverageComplete") is True
                body_count = int(payload.get("bodyCount") or len(payload.get("bodies") or []))
            except (OSError, ValueError, TypeError) as exc:
                error = str(exc)
        cad_id = next((key for key in modules if code in key), None)
        module = modules.get(cad_id or "", {})
        rows.append({
            "moduleToken": code,
            "cadId": cad_id,
            "expectedAssemblyFileName": module.get("expectedFileName"),
            "resolvedCadPath": module.get("resolvedCadPath"),
            "worldCapturePath": str(path),
            "captureComplete": complete,
            "bodyCount": body_count,
            "captureError": error,
            "resumeAction": None if complete else "capture standalone @root leaf bodies and map by the active Project05 top-level pose",
        })
    pending = [item["moduleToken"] for item in rows if not item["captureComplete"]]
    return {
        "schemaVersion": "project05-structural-capture-plan/v1",
        "projectId": "project05",
        "status": "PROJECT05_STRUCTURAL_OCCUPANCY_COMPLETE" if not pending else "PROJECT05_STRUCTURAL_OCCUPANCY_CAPTURE_BLOCKED",
        "requiredModuleCount": len(rows),
        "completeCaptureCount": len(rows) - len(pending),
        "pendingCaptureCount": len(pending),
        "pendingCaptureCodes": pending,
        "captures": rows,
        "resumeOrder": [code for code in ("A000", "E000", "D000", "B000", "Z000") if code in pending],
        "retryPrerequisites": [
            "start from a clean responsive SolidWorks/MCP session",
            "verify MCP initialize returns before opening any Project05 module",
            "capture one module at a time and persist progress after each @root result",
            "rebuild project05_module_occupancy.json after every successful capture",
        ],
        "releaseGate": {
            "coarseTop3SolveAllowed": not pending,
            "reason": "strict multi-AABB separation cannot be certified while required structural modules still use broad top-level placeholders",
        },
    }
