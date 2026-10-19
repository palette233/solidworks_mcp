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
DEFAULT_OUTPUT = (
    ROOT / "demo" / "layout_previews" / "project02_a600_operation_face.json"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture the currently selected Project02 A600 operation face."
    )
    parser.add_argument("--component", default="FL9A24D062A600.001-1")
    parser.add_argument("--face-name", default="操作面")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--exe", type=Path, default=DEFAULT_EXE)
    parser.add_argument(
        "--proxy",
        action="store_true",
        help="Use the long-lived SolidWorks MCP Hub instead of a dedicated direct-stdio session.",
    )
    parser.add_argument(
        "--probe-only",
        action="store_true",
        help="Validate and report the current selection without writing face_mappings.json.",
    )
    parser.add_argument(
        "--include-pose",
        action="store_true",
        help="Also enumerate top-level poses. This is intentionally opt-in for large assemblies.",
    )
    args = parser.parse_args()
    exe = args.exe.resolve()
    if not exe.is_file():
        raise SystemExit(f"SolidWorksMcpApp executable does not exist: {exe}")

    with McpClient(
        exe,
        client_name="Project02A600OperationFaceCapture",
        request_timeout=60.0,
        framing="lsp",
        direct_stdio=not args.proxy,
    ) as client:
        probe = client.call_tool(
            "get_selected_face_mapping_probe",
            {"faceName": args.face_name, "componentName": args.component},
        )
        _validate_probe(probe, args.component)
        # Keep operation-face capture deliberately light: the Project02 assembly is
        # large, and enumerating all component poses can take long enough to mask a
        # successful attachment/record as an MCP timeout.
        a600_pose: dict[str, Any] | None = None
        if args.include_pose:
            poses = client.call_tool("list_component_poses", {"topLevelOnly": True})
            a600_pose = _find_component_pose(poses, args.component)
        record: dict[str, Any] | None = None
        if not args.probe_only:
            record = client.call_tool(
                "record_face_mapping",
                {"faceName": args.face_name, "componentName": args.component},
            )
            if not _value(record, "Success", "success"):
                raise SystemExit(
                    f"Face mapping write failed: {json.dumps(record, ensure_ascii=False)}"
                )
            probe = client.call_tool(
                "get_selected_face_mapping_probe",
                {"faceName": args.face_name, "componentName": args.component},
            )
            _validate_probe(probe, args.component)

    result = {
        "schemaVersion": "project02-a600-operation-face/v1",
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        "projectId": "project02",
        "moduleCode": "A600",
        "componentName": args.component,
        "faceMappingName": args.face_name,
        "engineerConfirmed": not args.probe_only,
        "engineeringMeaning": (
            "The plane people face while operating the machine. Service modules are "
            "preferentially placed near this plane; if usable space is insufficient, "
            "they move to the opposite side."
        ),
        "probeOnly": args.probe_only,
        "recordResult": record,
        "selectedFaceProbe": probe,
        "a600TopLevelPose": a600_pose,
        "interpretationLimits": [
            "The selected plane is confirmed as the operation face.",
            "Its world normal is not yet a low/high solver-side label.",
            "The A600 local station frame and vendor A600-A800 XYZ dimensions remain separate inputs.",
        ],
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"savedPath={output}")
    return 0


def _validate_probe(probe: dict[str, Any], component_name: str) -> None:
    if not _value(probe, "Success", "success"):
        raise SystemExit(
            "The current SolidWorks selection is not a readable face: "
            + json.dumps(probe, ensure_ascii=False)
        )
    leaf_path = str(
        _value(probe, "LeafComponentFullName", "leafComponentFullName") or ""
    )
    if "A600" not in leaf_path.upper():
        raise SystemExit(
            f"Selected face is not under A600 '{component_name}': leaf={leaf_path}"
        )
    normal = _value(probe, "WorldNormal", "worldNormal")
    if not isinstance(normal, list) or len(normal) != 3:
        raise SystemExit("Selected A600 face is not planar or has no world normal.")


def _find_component_pose(raw: Any, component_name: str) -> dict[str, Any]:
    if not isinstance(raw, list):
        raise SystemExit("list_component_poses did not return an array.")
    matches = [
        item
        for item in raw
        if str(_value(item, "Name", "name") or "").lower()
        == component_name.lower()
    ]
    if len(matches) != 1:
        names = [str(_value(item, "Name", "name") or "") for item in raw]
        raise SystemExit(
            f"Expected one top-level A600 component '{component_name}', found {len(matches)}. "
            f"Top-level names: {names}"
        )
    pose = matches[0]
    bounds = _value(pose, "BoundingBoxWorld", "boundingBoxWorld")
    if not isinstance(bounds, list) or len(bounds) != 6:
        raise SystemExit("A600 top-level pose has no six-value world bounding box.")
    return pose


def _value(item: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in item:
            return item[name]
    return None


if __name__ == "__main__":
    raise SystemExit(main())
