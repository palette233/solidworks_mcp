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
    rank_optical_face_candidates,
    world_point_from_request,
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
DEFAULT_REQUEST = ROOT / "demo" / "FL9A24D062A000_real_process_request.json"
DEFAULT_OUTPUT = (
    ROOT / "demo" / "layout_previews" / "project02_scanner_face_candidates.json"
)
DEFAULT_SCREENSHOT_DIR = ROOT / "demo" / "screenshots" / "project02_scanner_faces"
DEFAULT_LEAF_COMPONENT = "sr-x100-0801A-1"
REVIEWED_OPTICAL_LOCAL_DIRECTION = [0.0, 1.0, 0.0]
REVIEWED_OPTICAL_LOCAL_SIDE_DIRECTION = [0.0, -1.0, 0.0]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Enumerate and rank Project02 SR-X100 planar faces, select the leading "
            "candidates in SolidWorks, and export zoomed review screenshots."
        )
    )
    parser.add_argument("--geometry", type=Path, default=DEFAULT_GEOMETRY)
    parser.add_argument("--request", type=Path, default=DEFAULT_REQUEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--screenshot-dir", type=Path, default=DEFAULT_SCREENSHOT_DIR)
    parser.add_argument("--leaf-component", default=DEFAULT_LEAF_COMPONENT)
    parser.add_argument("--document-title", default="FL9A24D062A000.001")
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--screenshots", type=int, default=3)
    parser.add_argument(
        "--review-ranks",
        default="",
        help="Comma-separated candidate ranks to screenshot instead of the leading N.",
    )
    parser.add_argument("--exe", type=Path, default=DEFAULT_EXE)
    parser.add_argument("--proxy", action="store_true")
    parser.add_argument(
        "--reuse-ranking",
        action="store_true",
        help="Reuse candidates already stored in --output and only regenerate screenshots.",
    )
    args = parser.parse_args()

    geometry_path = args.geometry.resolve()
    request_path = args.request.resolve()
    output_path = args.output.resolve()
    screenshot_dir = args.screenshot_dir.resolve()
    exe_path = args.exe.resolve()
    for label, path in (
        ("geometry capture", geometry_path),
        ("process request", request_path),
        ("MCP executable", exe_path),
    ):
        if not path.is_file():
            raise SystemExit(f"Missing {label}: {path}")

    geometry = _load_json(geometry_path)
    request = _load_json(request_path)
    target_world = world_point_from_request(
        geometry,
        request,
        "FL9A24D062A800.001-1",
        "barcode",
        "barcodeHeightMeters",
    )
    scanner_parameters = (
        request["moduleSemantics"]["FL9A24D062A180.001-1"].get("parameters") or {}
    )
    min_distance = float(scanner_parameters.get("minWorkingDistanceMeters", 0.07))
    max_distance = float(scanner_parameters.get("maxWorkingDistanceMeters", 1.0))

    screenshot_dir.mkdir(parents=True, exist_ok=True)
    cached_result = (
        _load_json(output_path)
        if args.reuse_ranking and output_path.is_file()
        else None
    )
    with McpClient(
        exe_path,
        client_name="Project02ScannerFaceCandidates",
        request_timeout=120.0,
        framing="lsp",
        direct_stdio=not args.proxy,
    ) as client:
        client.call_tool(
            "activate_document_by_title", {"title": args.document_title}
        )
        active_document = client.call_tool("get_active_document", {})
        if cached_result is not None:
            resolved_component = str(
                cached_result.get("leafComponent") or args.leaf_component
            )
            ranked = list(cached_result.get("candidates") or [])
            face_geometry = {
                "ReferencedDocumentPath": cached_result.get("referencedDocumentPath"),
                "FaceCount": (cached_result.get("faceCounts") or {}).get("all"),
                "PlanarFaceCount": (cached_result.get("faceCounts") or {}).get("planar"),
            }
        else:
            face_geometry = client.call_tool(
                "list_face_geometry",
                {"componentName": args.leaf_component, "planarOnly": True},
            )
            resolved_component = str(
                _value(face_geometry, "ComponentName", "componentName")
                or args.leaf_component
            )
            faces = _value(face_geometry, "Faces", "faces") or []
            ranked = rank_optical_face_candidates(
                faces,
                target_world,
                min_working_distance_meters=min_distance,
                max_working_distance_meters=max_distance,
                expected_local_direction=REVIEWED_OPTICAL_LOCAL_DIRECTION,
                expected_local_side_direction=REVIEWED_OPTICAL_LOCAL_SIDE_DIRECTION,
            )
        if not ranked:
            raise SystemExit("No planar SR-X100 face candidates were returned.")

        review_rows: list[dict[str, Any]] = []
        requested_ranks = {
            int(value.strip())
            for value in args.review_ranks.split(",")
            if value.strip()
        }
        review_candidates = (
            [item for item in ranked if int(item["rank"]) in requested_ranks]
            if requested_ranks
            else ranked[: max(0, min(args.screenshots, len(ranked)))]
        )
        for candidate in review_candidates:
            source = candidate["source"]
            face_index = int(_value(source, "Index", "index"))
            selection = client.call_tool(
                "select_face_geometry",
                {
                    "faceIndex": face_index,
                    "componentName": resolved_component,
                },
            )
            zoom = client.call_tool("zoom_to_selection", {})
            screenshot_path = screenshot_dir / f"rank-{candidate['rank']:02d}-face-{face_index}.png"
            screenshot = client.call_tool(
                "export_current_view_png",
                {
                    "outputPath": str(screenshot_path),
                    "width": 1600,
                    "height": 1000,
                    "includeBase64Data": False,
                    "fitToView": False,
                },
            )
            probe = client.call_tool(
                "get_selected_face_mapping_probe",
                {
                    "faceName": f"A180扫描出光面候选{candidate['rank']}",
                    "componentName": "FL9A24D062A180.001-1",
                },
            )
            review_rows.append(
                {
                    "rank": candidate["rank"],
                    "faceIndex": face_index,
                    "selection": selection,
                    "zoom": zoom,
                    "screenshot": screenshot,
                    "screenshotPath": _portable_path(screenshot_path),
                    "probe": probe,
                }
            )

    result = {
        "schemaVersion": "project02-scanner-face-candidates/v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "activeDocument": active_document,
        "leafComponentSelector": args.leaf_component,
        "leafComponent": resolved_component,
        "referencedDocumentPath": _value(
            face_geometry, "ReferencedDocumentPath", "referencedDocumentPath"
        ),
        "prototypeBarcodeProxyWorldMeters": target_world,
        "workingDistanceMeters": {"minimum": min_distance, "maximum": max_distance},
        "faceCounts": {
            "all": _value(face_geometry, "FaceCount", "faceCount"),
            "planar": _value(face_geometry, "PlanarFaceCount", "planarFaceCount"),
        },
        "rankingMethod": (
            "Planar face normal alignment toward the provisional A800 barcode point, "
            "working-distance feasibility and optical-window area prior, augmented by "
            "the CAD-probed SR-X100 optical side (outward local +Y / SolidWorks Bottom view)."
        ),
        "reviewedOpticalLocalDirection": REVIEWED_OPTICAL_LOCAL_DIRECTION,
        "reviewedOpticalLocalSideDirection": REVIEWED_OPTICAL_LOCAL_SIDE_DIRECTION,
        "semanticCaveat": (
            "Geometry scoring produces candidates, not proof that a casing face is an optical window. "
            "Review screenshots before recording a persistent semantic mapping."
        ),
        "candidates": ranked[: max(1, args.top)],
        "visualReviewArtifacts": review_rows,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": "CANDIDATES_READY",
                "outputPath": str(output_path),
                "faceCounts": result["faceCounts"],
                "topCandidates": [
                    {
                        "rank": item["rank"],
                        "faceIndex": _value(item["source"], "Index", "index"),
                        "score": round(item["score"], 3),
                        "alignment": round(item["normalAlignment"], 4),
                        "distanceMeters": round(item["distanceToTargetMeters"], 4),
                        "areaSquareMeters": item["areaSquareMeters"],
                    }
                    for item in ranked[: max(1, args.top)]
                ],
                "screenshots": [row["screenshotPath"] for row in review_rows],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise SystemExit(f"Expected JSON object: {path}")
    return value


def _value(item: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in item:
            return item[name]
    return None


def _portable_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
