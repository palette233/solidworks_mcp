#!/usr/bin/env python3
"""Build a leaf-level, static AC00 snapshot graph from a prototype subtree capture.

This graph is deliberately a geometry-preserving fallback.  It inserts every
leaf part as a fixed top-level component at the world Transform2 captured from
the Project03 prototype.  It does not preserve the original AC00 hierarchy,
internal mates, or motion semantics, so downstream reports must not describe
the result as a kinematic reconstruction.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "editable-module-mate-graph/v1"
SNAPSHOT_SCHEMA_VERSION = "project03-ac00-flat-static-snapshot/v1"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.resolve().read_text(encoding="utf-8-sig"))


def _components(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("components") or payload.get("Components")
    if rows is None:
        tool = payload.get("toolResult") or payload.get("ToolResult") or {}
        rows = tool.get("components") or tool.get("Components")
    if not isinstance(rows, list):
        raise ValueError("Subtree capture does not contain a component list.")
    return rows


def _value(row: dict[str, Any], name: str, default: Any = None) -> Any:
    return row.get(name, row.get(name[0].upper() + name[1:], default))


def _validate_transform(value: Any, label: str) -> list[float]:
    if not isinstance(value, list) or len(value) != 16:
        raise ValueError(f"{label} must contain one 16-value Transform2 array.")
    return [float(item) for item in value]


def build(capture: dict[str, Any], capture_path: Path | None = None) -> dict[str, Any]:
    leaves = [
        row
        for row in _components(capture)
        if str(_value(row, "path", "")).lower().endswith(".sldprt")
    ]
    if not leaves:
        raise ValueError("No SLDPRT leaf instances were found in the capture.")

    modules: list[dict[str, Any]] = []
    fixed_tokens: list[str] = []
    manifest: list[dict[str, Any]] = []
    for index, row in enumerate(leaves, start=1):
        path = Path(str(_value(row, "path", "")))
        if not path.is_file():
            raise FileNotFoundError(path)
        transform = _validate_transform(
            _value(row, "transform"), f"leaf[{index}].transform"
        )
        relative = str(
            _value(row, "relativeHierarchyPath", _value(row, "hierarchyPath", ""))
        )
        if not relative:
            raise ValueError(f"leaf[{index}] has no hierarchy identity.")
        token = f"AC00_SNAPSHOT_LEAF_{index:03d}"
        hierarchy = f"{token}::{relative}"
        fixed_tokens.append(token)
        modules.append(
            {
                "ModuleToken": token,
                "Name": str(_value(row, "name", path.stem)),
                "Path": str(path.resolve()),
                "HierarchyPath": hierarchy,
                "SourceTransform": transform,
                "IsSuppressed": False,
                "SuppressionState": 3,
                "SuppressionStateName": "swComponentFullyResolved",
                "VisibilityState": 1,
                "ReferencedConfiguration": _value(row, "referencedConfiguration"),
                "SolvingState": 0,
                "SolvingStateName": "swComponentRigidSolving",
            }
        )
        manifest.append(
            {
                "moduleToken": token,
                "sourceRelativeHierarchyPath": relative,
                "sourceLeafPath": str(path.resolve()),
                "expectedWorldTransform": transform,
            }
        )

    source_assembly = str(
        capture.get("sourceAssemblyPath")
        or capture.get("SourceAssemblyPath")
        or (capture.get("toolResult") or capture.get("ToolResult") or {}).get(
            "SourceAssemblyPath", ""
        )
    )
    capture_sha = None
    if capture_path is not None:
        capture_sha = hashlib.sha256(capture_path.resolve().read_bytes()).hexdigest()
    return {
        "SchemaVersion": SCHEMA_VERSION,
        "SourceAssemblyPath": source_assembly,
        "ModuleCount": len(modules),
        "InterModuleMateCount": 0,
        "Modules": modules,
        "Mates": [],
        "MateBundleCount": 0,
        "MateBundles": [],
        "SavedJsonPath": None,
        "EditPolicy": {
            "baseModuleToken": fixed_tokens[0],
            "initialPlacementMode": "source_pose",
            "sourceGraphImmutable": True,
            "fixedModuleTokens": fixed_tokens,
            "caseAnchoredModuleTokens": [],
            "targetLeafPoseAnchors": [],
        },
        "StaticSnapshotAudit": {
            "schemaVersion": SNAPSHOT_SCHEMA_VERSION,
            "purpose": "Preserve AC00 prototype-context leaf geometry and world poses.",
            "sourceCapturePath": str(capture_path.resolve()) if capture_path else None,
            "sourceCaptureSha256": capture_sha,
            "leafInstanceCount": len(modules),
            "allLeafPathsExist": True,
            "hierarchyPreserved": False,
            "internalMatesPreserved": False,
            "motionSemanticsPreserved": False,
            "productionReady": False,
            "allowedClaim": "static full-geometry reconstruction only",
            "leafManifest": manifest,
        },
    }


def write(path: Path, value: dict[str, Any]) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    capture_path = args.capture.resolve()
    graph = build(load(capture_path), capture_path)
    write(args.output, graph)
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "leafInstanceCount": graph["ModuleCount"],
                "mateCount": graph["InterModuleMateCount"],
                "motionSemanticsPreserved": False,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
