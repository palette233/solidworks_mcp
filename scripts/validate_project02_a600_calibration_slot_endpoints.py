#!/usr/bin/env python3
"""Recover every selected A600 calibration-slot endpoint in SolidWorks."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from capture_assembly_entity_annotations import McpClient


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXE = (
    ROOT
    / "vendor/solidworks-mcp/app/SolidWorksMcpApp/bin/Release/net8.0-windows/"
    "win-x64/SolidWorksMcpApp.exe"
)
DEFAULT_DIRECTORY = (
    ROOT
    / "demo/cross_project_substitution/alternate-slot-discovery-v1/"
    "project02_A600_calibration_slot_acquisition"
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Recover the three selected A600 candidate-slot faces."
    )
    parser.add_argument("--exe", type=Path, default=DEFAULT_EXE)
    parser.add_argument(
        "--catalog",
        type=Path,
        default=DEFAULT_DIRECTORY / "a600-native-service-leaf-face-catalog-v1.json",
    )
    parser.add_argument(
        "--selection",
        type=Path,
        default=DEFAULT_DIRECTORY / "candidate_selection.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_DIRECTORY / "endpoint_recovery_evidence.json",
    )
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument(
        "--replace-output",
        action="store_true",
        help="Replace an earlier evidence file after the candidate selection digest changes.",
    )
    args = parser.parse_args()

    output = args.output.resolve()
    if output.exists() and not args.replace_output:
        raise FileExistsError(f"Refusing to overwrite recovery evidence: {output}")
    selection = _read(args.selection.resolve())
    selected = selection["selectedCandidate"]
    endpoint_ids = [
        *selected["supportPlaneEndpointIds"],
        *selected["locatingEndpointIds"],
    ]
    started = time.perf_counter()
    results = []
    with McpClient(
        args.exe.resolve(),
        client_name="ValidateProject02A600CalibrationSlotEndpoints",
        request_timeout=args.timeout,
        framing="newline",
        direct_stdio=True,
    ) as client:
        tools = {tool.get("name") for tool in client.list_tools()}
        if "select_face_endpoint_from_catalog" not in tools:
            raise RuntimeError(
                "Published MCP build is missing select_face_endpoint_from_catalog"
            )
        for endpoint_id in endpoint_ids:
            endpoint_started = time.perf_counter()
            result = client.call_tool(
                "SelectFaceEndpointFromCatalog",
                {
                    "catalogPath": str(args.catalog.resolve()),
                    "endpointId": endpoint_id,
                    "zoomToSelection": False,
                },
            )
            results.append(
                {
                    "endpointId": endpoint_id,
                    "success": bool(result.get("Success", result.get("success", False))),
                    "resolutionStrategy": result.get(
                        "ResolutionStrategy", result.get("resolutionStrategy")
                    ),
                    "moduleHierarchyPath": result.get(
                        "ModuleHierarchyPath", result.get("moduleHierarchyPath")
                    ),
                    "leafHierarchyPath": result.get(
                        "LeafHierarchyPath", result.get("leafHierarchyPath")
                    ),
                    "durationSeconds": round(time.perf_counter() - endpoint_started, 6),
                    "message": result.get("Message", result.get("message")),
                }
            )

    core = {
        "schemaVersion": "cross-project-slot-endpoint-recovery/v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "selectionDigest": selection["selectionDigest"],
        "catalogPath": str(args.catalog.resolve()),
        "endpointCount": len(endpoint_ids),
        "recoveredCount": sum(row["success"] for row in results),
        "allRecovered": all(row["success"] for row in results),
        "durationSeconds": round(time.perf_counter() - started, 6),
        "results": results,
        "scope": "read-only endpoint recovery; no mate creation or assembly save",
    }
    evidence = {**core, "evidenceDigest": _digest(core)}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0 if evidence["allRecovered"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
