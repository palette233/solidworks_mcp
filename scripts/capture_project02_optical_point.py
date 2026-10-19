from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from capture_assembly_entity_annotations import McpClient


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.project02_optical_points import (  # noqa: E402
    TARGETS,
    Project02OpticalPointError,
    apply_evidence_to_request,
    capture_entry_from_probe,
    evidence_readiness,
)


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
DEFAULT_GEOMETRY = ROOT / "demo" / "FL9A24D062A000_8components_real_geometry.json"
DEFAULT_EVIDENCE = (
    ROOT / "demo" / "layout_previews" / "project02_scanner_barcode_points.json"
)
DEFAULT_REQUEST = ROOT / "demo" / "FL9A24D062A000_real_process_request.json"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Capture one selected Project02 optical face and convert its center into "
            "the owning module's layout-local point."
        )
    )
    parser.add_argument("--target", choices=sorted(TARGETS), required=True)
    parser.add_argument("--geometry", type=Path, default=DEFAULT_GEOMETRY)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--request", type=Path, default=DEFAULT_REQUEST)
    parser.add_argument("--exe", type=Path, default=DEFAULT_EXE)
    parser.add_argument(
        "--proxy",
        action="store_true",
        help="Use the long-lived MCP hub. Prefer this only when it is known to own the visible SolidWorks session.",
    )
    parser.add_argument(
        "--probe-only",
        action="store_true",
        help="Validate the selected face without persisting a face mapping or evidence file.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="After both targets exist, replace provisional request points with captured values.",
    )
    parser.add_argument(
        "--allow-non-sr-x100-face",
        action="store_true",
        help="Allow a scanner selection outside the identified SR-X100 leaf part (not recommended).",
    )
    args = parser.parse_args()

    geometry_path = args.geometry.resolve()
    evidence_path = args.evidence.resolve()
    request_path = args.request.resolve()
    exe_path = args.exe.resolve()
    for label, path in (("geometry capture", geometry_path), ("MCP executable", exe_path)):
        if not path.is_file():
            raise SystemExit(f"Missing {label}: {path}")

    geometry = _load_json(geometry_path)
    spec = TARGETS[args.target]
    with McpClient(
        exe_path,
        client_name=f"Project02OpticalPoint-{args.target}",
        request_timeout=60.0,
        framing="lsp",
        direct_stdio=not args.proxy,
    ) as client:
        probe = client.call_tool(
            "get_selected_face_mapping_probe",
            {
                "faceName": spec["mappingName"],
                "componentName": spec["componentName"],
            },
        )
        entry = capture_entry_from_probe(
            geometry,
            args.target,
            probe,
            require_leaf_hint=not args.allow_non_sr_x100_face,
        )
        record: dict[str, Any] | None = None
        if not args.probe_only:
            record = client.call_tool(
                "record_face_mapping",
                {
                    "faceName": spec["mappingName"],
                    "componentName": spec["componentName"],
                },
            )
            if not _value(record, "Success", "success"):
                raise Project02OpticalPointError(
                    "Persistent face mapping failed: "
                    + json.dumps(record, ensure_ascii=False)
                )
            probe = client.call_tool(
                "get_selected_face_mapping_probe",
                {
                    "faceName": spec["mappingName"],
                    "componentName": spec["componentName"],
                },
            )
            entry = capture_entry_from_probe(
                geometry,
                args.target,
                probe,
                require_leaf_hint=not args.allow_non_sr_x100_face,
            )
            entry["recordResult"] = record

    result = _load_or_create_evidence(evidence_path, geometry_path)
    if args.probe_only:
        print(json.dumps({"probeOnly": True, "entry": entry}, ensure_ascii=False, indent=2))
        return 0

    result.setdefault("entries", {})[args.target] = entry
    result["updatedAt"] = datetime.now(timezone.utc).isoformat()
    result["readiness"] = evidence_readiness(result)
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    applied = False
    if args.apply:
        if not result["readiness"]["pointCaptureComplete"]:
            missing = ", ".join(result["readiness"]["missingTargets"])
            raise SystemExit(
                f"Evidence was saved, but request was not updated; first capture: {missing}"
            )
        if not request_path.is_file():
            raise SystemExit(f"Missing request JSON: {request_path}")
        request = _load_json(request_path)
        request = apply_evidence_to_request(
            request,
            result,
            evidence_path=_portable_path(evidence_path),
        )
        request_path.write_text(
            json.dumps(request, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        applied = True

    print(
        json.dumps(
            {
                "status": "CAPTURED",
                "target": args.target,
                "evidencePath": str(evidence_path),
                "requestApplied": applied,
                "readiness": result["readiness"],
                "moduleLocalPointMeters": entry["moduleLocalPointMeters"],
                "normalInLayoutFrame": entry["normalInLayoutFrame"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise SystemExit(f"Expected JSON object: {path}")
    return data


def _load_or_create_evidence(path: Path, geometry_path: Path) -> dict[str, Any]:
    if path.is_file():
        result = _load_json(path)
        result.setdefault("entries", {})
        return result
    return {
        "schemaVersion": "project02-scanner-barcode-points/v1",
        "projectId": "project02",
        "geometryCapturePath": _portable_path(geometry_path),
        "captureMethod": (
            "Engineer selects a planar CAD face; MCP records a persistent face mapping, "
            "world center/normal and a module-bottom-frame local point."
        ),
        "entries": {},
    }


def _portable_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def _value(item: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in item:
            return item[name]
    return None


if __name__ == "__main__":
    raise SystemExit(main())
