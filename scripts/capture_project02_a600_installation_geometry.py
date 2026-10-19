from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from capture_assembly_entity_annotations import McpClient


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXE = (
    ROOT
    / "vendor"
    / "solidworks-mcp"
    / "app"
    / "SolidWorksMcpApp"
    / "bin"
    / "Release"
    / "net8.0-windows"
    / "win-x64"
    / "SolidWorksMcpApp.exe"
)
DEFAULT_OUTPUT = ROOT / "demo/layout_previews/project02_a600_installation_geometry_capture.json"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read Project02 A600/A800 top-level poses and A600 leaf-body envelopes."
    )
    parser.add_argument("--exe", type=Path, default=DEFAULT_EXE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--a600", default="FL9A24D062A600.001-1")
    parser.add_argument("--a800", default="FL9A24D062A800.001-1")
    parser.add_argument("--timeout", type=float, default=900.0)
    args = parser.parse_args()

    exe = args.exe.resolve()
    if not exe.is_file():
        raise SystemExit(f"SolidWorksMcpApp executable does not exist: {exe}")

    with McpClient(
        exe,
        client_name="Project02A600InstallationGeometryCapture",
        request_timeout=args.timeout,
        framing="lsp",
        direct_stdio=True,
    ) as client:
        poses = client.call_tool("list_component_poses", {"topLevelOnly": True})
        a600_pose = _one_pose(poses, args.a600)
        a800_pose = _one_pose(poses, args.a800)
        a600_leaf_envelopes = client.call_tool(
            "capture_leaf_body_envelopes", {"hierarchyPath": args.a600}
        )

    result = {
        "schemaVersion": "project02-a600-installation-geometry-capture/v1",
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        "success": True,
        "readOnly": True,
        "a600Pose": a600_pose,
        "a800Pose": a800_pose,
        "a600LeafBodyEnvelopes": a600_leaf_envelopes,
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "PASS_A600_GEOMETRY_CAPTURE",
                "output": str(output),
                "leafComponentCount": _pick(a600_leaf_envelopes, "LeafComponentCount"),
                "bodyCount": _pick(a600_leaf_envelopes, "BodyCount"),
            },
            ensure_ascii=False,
        )
    )
    return 0


def _one_pose(raw: Any, name: str) -> dict[str, Any]:
    if not isinstance(raw, list):
        raise SystemExit("list_component_poses did not return an array")
    matches = [item for item in raw if str(_pick(item, "Name", "")).lower() == name.lower()]
    if len(matches) != 1:
        raise SystemExit(f"Expected exactly one top-level component {name}; found {len(matches)}")
    pose = matches[0]
    if len(_pick(pose, "BoundingBoxWorld", []) or []) != 6:
        raise SystemExit(f"Top-level component {name} has no six-value world bounding box")
    if len(_pick(pose, "Transform", []) or []) < 12:
        raise SystemExit(f"Top-level component {name} has no usable world transform")
    return pose


def _pick(item: dict[str, Any], name: str, default: Any = None) -> Any:
    return item.get(name, item.get(name[0].lower() + name[1:], default))


if __name__ == "__main__":
    raise SystemExit(main())
