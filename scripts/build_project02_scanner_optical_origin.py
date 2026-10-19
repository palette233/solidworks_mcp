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
    capture_entry_from_probe,
    evidence_readiness,
    infer_optical_axis_from_symmetric_faces,
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
DEFAULT_CANDIDATES = ROOT / "demo" / "layout_previews" / "project02_scanner_face_candidates.json"
DEFAULT_REVIEW = ROOT / "demo" / "layout_previews" / "project02_scanner_optical_face_review.json"
DEFAULT_EVIDENCE = ROOT / "demo" / "layout_previews" / "project02_scanner_barcode_points.json"
MODULE_NAME = "FL9A24D062A180.001-1"
LEFT_FACE_INDEX = 766
RIGHT_FACE_INDEX = 765


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Rebase the Project02 SR-X100 symmetric-window optical-axis inference "
            "from a lightweight review assembly into the prototype A180 module frame."
        )
    )
    parser.add_argument("--assembly", type=Path, default=DEFAULT_ASSEMBLY)
    parser.add_argument("--geometry", type=Path, default=DEFAULT_GEOMETRY)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--exe", type=Path, default=DEFAULT_EXE)
    parser.add_argument("--proxy", action="store_true")
    args = parser.parse_args()

    geometry = _load_json(args.geometry)
    candidates = _load_json(args.candidates)
    review = _load_json(args.review)
    evidence = _load_json(args.evidence)
    source_module = next(
        item for item in geometry.get("components") or []
        if item.get("componentName") == MODULE_NAME
    )
    source_transform = source_module["sourceTransform"]
    by_index = {
        int(item["source"]["Index"]): item["source"]
        for item in candidates.get("candidates") or []
    }
    left = by_index[LEFT_FACE_INDEX]
    right = by_index[RIGHT_FACE_INDEX]
    inferred = infer_optical_axis_from_symmetric_faces(left, right)
    review_world_point = [
        (left["WorldCenter"][index] + right["WorldCenter"][index]) / 2.0
        for index in range(3)
    ]
    review_world_direction = inferred["localOpticalAxisLine"]

    with McpClient(
        args.exe.resolve(),
        client_name="Project02ScannerOpticalOrigin",
        request_timeout=90.0,
        framing="lsp",
        direct_stdio=not args.proxy,
    ) as client:
        client.call_tool(
            "activate_document_by_title", {"title": args.assembly.stem}
        )
        poses = client.call_tool("list_component_poses", {"topLevelOnly": True})
    review_pose = next(
        item for item in poses
        if _value(item, "Name", "name") == MODULE_NAME
    )
    review_transform = _value(review_pose, "Transform", "transform")
    rebased = rebase_world_geometry_between_component_transforms(
        review_world_point,
        review_world_direction,
        review_transform,
        source_transform,
    )
    probe = {
        "Success": True,
        "LeafComponentFullName": (
            "FL9A24D062A180.001-1/248004电气-sr-x100-0801A-1"
        ),
        "WorldCenter": rebased["worldPoint"],
        "WorldNormal": rebased["worldDirection"],
        "LocalCenter": inferred["localCenterMeters"],
        "LocalNormal": inferred["localOpticalAxisLine"],
        "Area": (float(left["Area"]) + float(right["Area"])) / 2.0,
    }
    entry = capture_entry_from_probe(geometry, "scanner", probe)
    entry.update(
        {
            "measurementStatus": "cad-inferred-symmetric-windows",
            "directCentralLensFaceMeasured": False,
            "readyForCoarseLayout": True,
            "inferenceMethod": inferred["method"],
            "opticalAxisSignResolved": False,
            "symmetricFaceIndices": [LEFT_FACE_INDEX, RIGHT_FACE_INDEX],
            "anchorSeparationMeters": inferred["anchorSeparationMeters"],
            "transformAudit": {
                "reviewAssembly": str(args.assembly.resolve()),
                "reviewModuleTransform": review_transform,
                "prototypeModuleTransform": source_transform,
                "reviewWorldOpticalOriginMeters": review_world_point,
                "prototypeWorldOpticalOriginMeters": rebased["worldPoint"],
                "componentLocalOpticalOriginMeters": rebased[
                    "componentLocalPoint"
                ],
            },
        }
    )

    evidence.setdefault("entries", {})["scanner"] = entry
    evidence["updatedAt"] = datetime.now(timezone.utc).isoformat()
    evidence["status"] = "SCANNER_CAD_INFERRED_AWAITING_BARCODE"
    evidence["readiness"] = evidence_readiness(evidence)
    review["moduleCoordinateConversion"] = {
        "status": "READY_FOR_COARSE_LAYOUT",
        "moduleLocalPointMeters": entry["moduleLocalPointMeters"],
        "heightAboveModuleBottomMeters": entry[
            "heightAboveModuleBottomMeters"
        ],
        "normalInLayoutFrame": entry["normalInLayoutFrame"],
        "prototypeWorldOpticalOriginMeters": rebased["worldPoint"],
        "measurementStatus": entry["measurementStatus"],
        "transformAudit": entry["transformAudit"],
    }
    _write_json(args.evidence, evidence)
    _write_json(args.review, review)
    print(
        json.dumps(
            {
                "status": evidence["status"],
                "moduleLocalPointMeters": entry["moduleLocalPointMeters"],
                "heightAboveModuleBottomMeters": entry[
                    "heightAboveModuleBottomMeters"
                ],
                "normalInLayoutFrame": entry["normalInLayoutFrame"],
                "prototypeWorldOpticalOriginMeters": rebased["worldPoint"],
                "readiness": evidence["readiness"],
                "evidencePath": str(args.evidence.resolve()),
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


def _value(item: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in item:
            return item[name]
    return None


if __name__ == "__main__":
    raise SystemExit(main())
