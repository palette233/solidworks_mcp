from __future__ import annotations

import argparse
import json
import math
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
    apply_evidence_to_request,
    capture_entry_from_probe,
    evidence_readiness,
    rebase_world_geometry_between_component_transforms,
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
DEFAULT_ASSEMBLY = ROOT / "demo" / "FL9A24D062A000_8modules_clean_solved_v1.SLDASM"
DEFAULT_GEOMETRY = ROOT / "demo" / "FL9A24D062A000_8components_real_geometry.json"
DEFAULT_EVIDENCE = ROOT / "demo" / "layout_previews" / "project02_scanner_barcode_points.json"
DEFAULT_REVIEW = ROOT / "demo" / "layout_previews" / "project02_barcode_face_review.json"
DEFAULT_REQUEST = ROOT / "demo" / "FL9A24D062A000_real_process_request.json"
A800_NAME = "FL9A24D062A800.001-1"
BARCODE_COMPONENT = (
    "FL9A24D062A800.001-1/056-19475000-00_ASM_165_ASM-8/模拟二维码-1"
)
BARCODE_FACE_INDEX = 4


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Capture the Project02 carrier-8 simulated QR-code face, rebase it from "
            "the review assembly to the prototype A800 frame and update optical evidence."
        )
    )
    parser.add_argument("--assembly", type=Path, default=DEFAULT_ASSEMBLY)
    parser.add_argument("--geometry", type=Path, default=DEFAULT_GEOMETRY)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--request", type=Path, default=DEFAULT_REQUEST)
    parser.add_argument("--exe", type=Path, default=DEFAULT_EXE)
    parser.add_argument("--proxy", action="store_true")
    parser.add_argument("--no-apply", action="store_true")
    args = parser.parse_args()

    geometry = _load_json(args.geometry)
    evidence = _load_json(args.evidence)
    request = _load_json(args.request)
    source_module = next(
        item for item in geometry.get("components") or []
        if item.get("componentName") == A800_NAME
    )
    source_transform = source_module["sourceTransform"]

    with McpClient(
        args.exe.resolve(),
        client_name="Project02BarcodePoint",
        request_timeout=120.0,
        framing="lsp",
        direct_stdio=not args.proxy,
    ) as client:
        client.call_tool(
            "activate_document_by_title", {"title": args.assembly.stem}
        )
        poses = client.call_tool("list_component_poses", {"topLevelOnly": True})
        face_geometry = client.call_tool(
            "list_face_geometry",
            {"componentName": BARCODE_COMPONENT, "planarOnly": True},
        )
        selection = client.call_tool(
            "select_face_geometry",
            {
                "faceIndex": BARCODE_FACE_INDEX,
                "componentName": BARCODE_COMPONENT,
            },
        )
        record = client.call_tool(
            "record_face_mapping",
            {"faceName": "A800条码面", "componentName": A800_NAME},
        )
    review_pose = next(
        item for item in poses if _value(item, "Name", "name") == A800_NAME
    )
    review_transform = _value(review_pose, "Transform", "transform")
    face = next(
        item for item in _value(face_geometry, "Faces", "faces")
        if int(_value(item, "Index", "index")) == BARCODE_FACE_INDEX
    )
    rebased = rebase_world_geometry_between_component_transforms(
        _value(face, "WorldCenter", "worldCenter"),
        _value(face, "WorldNormal", "worldNormal"),
        review_transform,
        source_transform,
    )
    probe = {
        "Success": True,
        "LeafComponentFullName": BARCODE_COMPONENT,
        "WorldCenter": rebased["worldPoint"],
        "WorldNormal": rebased["worldDirection"],
        "LocalCenter": _value(face, "LocalCenter", "localCenter"),
        "LocalNormal": _value(face, "LocalNormal", "localNormal"),
        "Area": _value(face, "Area", "area"),
        "PersistentReferenceBase64": _value(
            face, "PersistentReferenceBase64", "persistentReferenceBase64"
        ),
        "MappingPath": _value(record, "MappingPath", "mappingPath"),
    }
    entry = capture_entry_from_probe(geometry, "barcode", probe)
    entry.update(
        {
            "measurementStatus": "direct-face-measured",
            "carrierInstance": "056-19475000-00_ASM_165_ASM-8",
            "leafPart": "模拟二维码.SLDPRT",
            "faceIndex": BARCODE_FACE_INDEX,
            "faceDimensionsMeters": [0.010, 0.010],
            "selectionRationale": (
                "Five simulated-QR carrier instances exist. Carrier-8 is the only "
                "instance near the prototype scanner projection and is the carrier "
                "shown at the scan/buffer side of the A800 transport."
            ),
            "recordResult": record,
            "transformAudit": {
                "reviewAssembly": str(args.assembly.resolve()),
                "reviewModuleTransform": review_transform,
                "prototypeModuleTransform": source_transform,
                "reviewWorldBarcodeCenterMeters": _value(
                    face, "WorldCenter", "worldCenter"
                ),
                "prototypeWorldBarcodeCenterMeters": rebased["worldPoint"],
                "componentLocalBarcodeCenterMeters": rebased[
                    "componentLocalPoint"
                ],
            },
        }
    )
    scanner = (evidence.get("entries") or {}).get("scanner")
    if not isinstance(scanner, dict):
        raise SystemExit(
            "Scanner optical-origin evidence is missing; run "
            "build_project02_scanner_optical_origin.py first."
        )
    scanner_world = scanner["worldCenterMeters"]
    vector = [
        rebased["worldPoint"][index] - scanner_world[index]
        for index in range(3)
    ]
    distance = math.sqrt(sum(value * value for value in vector))
    direction = [value / distance for value in vector]
    relationship = {
        "prototypeScannerToBarcodeVectorMeters": vector,
        "prototypeScannerToBarcodeDistanceMeters": distance,
        "prototypeScannerToBarcodeUnitDirection": direction,
        "workingDistanceInConfiguredRange": 0.05 <= distance <= 0.35,
        "interpretation": (
            "The vector connects the inferred scanner optical center to the direct "
            "QR face center in the prototype pose. It is evidence for coarse layout, "
            "not confirmation of the scanner stage's final dynamic scan position."
        ),
    }
    entry["scannerRelationship"] = relationship
    evidence.setdefault("entries", {})["barcode"] = entry
    evidence["updatedAt"] = datetime.now(timezone.utc).isoformat()
    evidence["status"] = "OPTICAL_POINTS_READY_ENGINEERING_CONFIRMATION_PENDING"
    evidence["readiness"] = evidence_readiness(evidence)
    _write_json(args.evidence, evidence)

    applied = False
    if not args.no_apply:
        request = apply_evidence_to_request(
            request,
            evidence,
            evidence_path=_portable_path(args.evidence),
        )
        scanner_parameters = request["moduleSemantics"][
            "FL9A24D062A180.001-1"
        ].setdefault("parameters", {})
        scanner_parameters[
            "prototypeScannerToBarcodeDistanceMeters"
        ] = distance
        scanner_parameters[
            "prototypeScannerToBarcodeUnitDirection"
        ] = direction
        scanner_parameters[
            "opticalPointPairEvidenceStatus"
        ] = "CAD points ready; dynamic scan position and vendor range unconfirmed"
        _write_json(args.request, request)
        applied = True

    review = {
        "schemaVersion": "project02-barcode-face-review/v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "status": evidence["status"],
        "module": "A800",
        "leafPart": "模拟二维码.SLDPRT",
        "discoveredInstanceCount": 5,
        "selectedCarrierInstance": "056-19475000-00_ASM_165_ASM-8",
        "selectedFaceIndex": BARCODE_FACE_INDEX,
        "selection": selection,
        "selectionRationale": entry["selectionRationale"],
        "prototypePoint": {
            "worldCenterMeters": entry["worldCenterMeters"],
            "moduleLocalPointMeters": entry["moduleLocalPointMeters"],
            "heightAboveModuleBottomMeters": entry[
                "heightAboveModuleBottomMeters"
            ],
        },
        "scannerRelationship": relationship,
        "screenshot": (
            "demo/screenshots/project02_barcode/"
            "project02-a800-carrier-8-qr-face-4-selected.png"
        ),
        "remainingEngineeringConfirmations": [
            "Confirm the scanner stage position used during barcode capture.",
            "Confirm the SR-X100 configured working-distance range.",
            "Confirm that carrier-8 is the buffer-position carrier in the production sequence.",
        ],
    }
    _write_json(args.review, review)
    print(
        json.dumps(
            {
                "status": evidence["status"],
                "requestApplied": applied,
                "barcodeModuleLocalPointMeters": entry[
                    "moduleLocalPointMeters"
                ],
                "barcodeHeightMeters": entry[
                    "heightAboveModuleBottomMeters"
                ],
                "scannerToBarcodeDistanceMeters": distance,
                "workingDistanceInConfiguredRange": relationship[
                    "workingDistanceInConfiguredRange"
                ],
                "readiness": evidence["readiness"],
                "evidencePath": str(args.evidence.resolve()),
                "reviewPath": str(args.review.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.resolve().read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise SystemExit(f"Expected JSON object: {path}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    resolved = path.resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


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
