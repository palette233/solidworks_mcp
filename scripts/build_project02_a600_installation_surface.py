from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CAPTURE = ROOT / "demo/layout_previews/project02_a600_installation_geometry_capture.json"
DEFAULT_FRAME = ROOT / "demo/layout_previews/project02_a600_installation_frame.json"
DEFAULT_GRAPH = ROOT / "demo/layout_previews/project02_module_mate_graph_v2.json"
DEFAULT_OUTPUT = ROOT / "demo/layout_previews/project02_a600_installation_surface.json"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a coarse A600 upper installation surface and structural keepouts."
    )
    parser.add_argument("--capture", type=Path, default=DEFAULT_CAPTURE)
    parser.add_argument("--frame", type=Path, default=DEFAULT_FRAME)
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--edge-margin", type=float, default=0.03)
    parser.add_argument("--obstacle-height", type=float, default=0.03)
    parser.add_argument("--grid", type=float, default=0.025)
    args = parser.parse_args()

    capture = _load(args.capture)
    frame = _load(args.frame)
    graph = _load(args.graph)
    origin, axes = _frame(frame)

    a600_pose = capture["a600Pose"]
    a600_world_box = _numbers(a600_pose, "BoundingBoxWorld", 6)
    enclosure_bounds = _project_box(a600_world_box, origin, axes)
    # The operation face is X=0 by construction. Small handles/panels may extend
    # toward the operator, but upper process modules must remain inside the cabinet.
    platform_bounds = {
        "minX": max(0.0, enclosure_bounds[0]),
        "minY": enclosure_bounds[1],
        "maxX": enclosure_bounds[3],
        "maxY": enclosure_bounds[4],
        "z": 0.0,
    }
    safe_bounds = _inset(platform_bounds, args.edge_margin)

    contact = _unique_mate(graph, "重合35")
    width = _unique_mate(graph, "宽度9")
    support_endpoint = _one_endpoint(contact, "A600")
    support_center = _world_to_frame(
        _numbers(support_endpoint, "FaceCenterWorld", 3), origin, axes
    )
    face_box = _numbers(support_endpoint, "FaceBoxLocal", 6)
    nonzero_spans = sorted(
        value
        for value in (
            abs(face_box[3] - face_box[0]),
            abs(face_box[4] - face_box[1]),
            abs(face_box[5] - face_box[2]),
        )
        if value > 1e-6
    )
    if len(nonzero_spans) != 2:
        raise SystemExit(f"A600 support face does not expose two planar spans: {nonzero_spans}")
    width_centers = [
        _numbers(item, "FaceCenterWorld", 3)
        for item in width.get("Endpoints", [])
        if item.get("ModuleToken") == "A600"
    ]
    if len(width_centers) != 2:
        raise SystemExit("宽度9 does not expose two A600 reference faces")
    width_separation = _distance(width_centers[0], width_centers[1])
    lateral_span = max(nonzero_spans)
    depth_span = min(nonzero_spans)
    transport_support = {
        "minX": support_center[0] - depth_span / 2,
        "minY": support_center[1] - lateral_span / 2,
        "maxX": support_center[0] + depth_span / 2,
        "maxY": support_center[1] + lateral_span / 2,
        "z": support_center[2],
        "faceAreaSquareMeters": float(support_endpoint.get("FaceArea") or 0.0),
        "sourceMate": "重合35",
        "widthReferenceMate": "宽度9",
        "widthReferenceSeparationMeters": width_separation,
    }

    capture_envelopes = capture["a600LeafBodyEnvelopes"]
    body_boxes: list[dict[str, Any]] = []
    conditional_boxes: list[dict[str, Any]] = []
    platform_area = _area(platform_bounds)
    for item in capture_envelopes.get("Bodies", []):
        box = _project_box(_numbers(item, "BoundingBoxWorld", 6), origin, axes)
        clipped = _clip_plan(box, safe_bounds)
        if clipped is None or box[5] <= args.obstacle_height:
            continue
        entry = {
            "component": (item.get("Component") or {}).get("Name"),
            "hierarchyPath": (item.get("Component") or {}).get("HierarchyPath"),
            "bodyIndex": item.get("BodyIndex"),
            "bounds": clipped,
            "heightRangeMeters": [box[2], box[5]],
        }
        overlap_ratio = _box_area(clipped) / max(platform_area, 1e-9)
        # One non-convex upper-frame solid spans almost the complete deck. Its AABB
        # cannot be treated as a solid obstacle; route it to structural/portal review.
        if overlap_ratio >= 0.35:
            entry["reason"] = "non-convex structural body has an oversized planar AABB"
            entry["planOverlapRatio"] = overlap_ratio
            conditional_boxes.append(entry)
        else:
            body_boxes.append(entry)

    merged_keepouts, grid_summary = _raster_keepouts(
        safe_bounds, body_boxes, args.grid
    )
    failed_count = int(capture_envelopes.get("FailedBodyCount") or 0)
    captured_count = int(capture_envelopes.get("BodyCount") or 0)
    total_count = captured_count + failed_count
    coverage_ratio = captured_count / total_count if total_count else 0.0
    checks = [
        _check("installation-frame-valid", frame.get("success") is True),
        _check("a600-world-envelope-valid", _area(platform_bounds) > 1.0),
        _check("support-face-inside-platform", _contains(platform_bounds, transport_support)),
        _check("mate-width-consistent-with-support-span", abs(width_separation - lateral_span) <= 0.1),
        _check("leaf-envelope-coverage-at-least-99-percent", coverage_ratio >= 0.99),
        _check("coarse-keepouts-generated", len(merged_keepouts) > 0),
    ]
    success = all(item["passed"] for item in checks)
    result = {
        "schemaVersion": "project02-a600-installation-surface/v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "success": success,
        "status": (
            "PASS_COARSE_A600_INSTALLATION_SURFACE_WITH_CONDITIONAL_STRUCTURE"
            if success
            else "FAIL_A600_INSTALLATION_SURFACE"
        ),
        "moduleCode": "A600",
        "frameName": frame.get("frameName"),
        "sourceCapture": str(args.capture.resolve()),
        "sourceFrame": str(args.frame.resolve()),
        "sourceMateGraph": str(args.graph.resolve()),
        "coordinateConvention": {
            "x": "operation face into machine",
            "y": "transport lateral direction",
            "z": "up from transport support plane",
        },
        "enclosureBoundsFrameMeters": enclosure_bounds,
        "installationPlatform": {
            "boundary": platform_bounds,
            "safeBoundary": safe_bounds,
            "edgeMarginMeters": args.edge_margin,
            "interpretation": "coarse upper installation platform; excludes operation-side protrusions",
        },
        "transportSupportRegion": transport_support,
        "hardKeepoutRegions": merged_keepouts,
        "hardKeepoutSourceBodyCount": len(body_boxes),
        "conditionalStructuralBodies": conditional_boxes,
        "gridSummary": grid_summary,
        "captureCoverage": {
            "capturedBodyCount": captured_count,
            "failedBodyCount": failed_count,
            "coverageRatio": coverage_ratio,
            "coverageComplete": bool(capture_envelopes.get("CoverageComplete")),
            "failures": capture_envelopes.get("Failures", []),
        },
        "usableForCoarseLayout": success,
        "authoritativeForFinalCollision": False,
        "collisionPolicy": {
            "ordinaryModules": "footprint must stay inside safeBoundary and outside hardKeepoutRegions",
            "transportModule": "A800 uses transportSupportRegion and its direct mate interface; nominal mounting contact is allowed",
            "conditionalStructure": "oversized non-convex A600 bodies require portal evidence or conditional B-Rep after visual approval",
            "missingBodies": "failed body boxes remain an explicit final-validation blocker",
        },
        "checks": checks,
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": result["status"],
                "output": str(output),
                "hardKeepoutRegionCount": len(merged_keepouts),
                "conditionalStructuralBodyCount": len(conditional_boxes),
                "captureCoverageRatio": coverage_ratio,
            },
            ensure_ascii=False,
        )
    )
    return 0 if success else 2


def _raster_keepouts(
    boundary: dict[str, float],
    boxes: list[dict[str, Any]],
    cell: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    nx = max(1, math.ceil((boundary["maxX"] - boundary["minX"]) / cell))
    ny = max(1, math.ceil((boundary["maxY"] - boundary["minY"]) / cell))
    occupied: set[tuple[int, int]] = set()
    for ix in range(nx):
        x0 = boundary["minX"] + ix * cell
        x1 = min(boundary["maxX"], x0 + cell)
        for iy in range(ny):
            y0 = boundary["minY"] + iy * cell
            y1 = min(boundary["maxY"], y0 + cell)
            if any(_overlap([x0, y0, x1, y1], item["bounds"]) for item in boxes):
                occupied.add((ix, iy))

    runs: list[tuple[int, int, int]] = []
    for iy in range(ny):
        ix = 0
        while ix < nx:
            if (ix, iy) not in occupied:
                ix += 1
                continue
            start = ix
            while ix + 1 < nx and (ix + 1, iy) in occupied:
                ix += 1
            runs.append((iy, start, ix))
            ix += 1

    rectangles: list[dict[str, Any]] = []
    active: dict[tuple[int, int], tuple[int, int]] = {}
    for iy in range(ny):
        row_runs = {(start, end) for row, start, end in runs if row == iy}
        next_active: dict[tuple[int, int], tuple[int, int]] = {}
        for key in row_runs:
            if key in active:
                next_active[key] = (active[key][0], iy)
            else:
                next_active[key] = (iy, iy)
        for key, (start_row, end_row) in active.items():
            if key not in row_runs:
                rectangles.append(_grid_rect(boundary, cell, key, start_row, end_row))
        active = next_active
    for key, (start_row, end_row) in active.items():
        rectangles.append(_grid_rect(boundary, cell, key, start_row, end_row))

    return rectangles, {
        "cellSizeMeters": cell,
        "columnCount": nx,
        "rowCount": ny,
        "occupiedCellCount": len(occupied),
        "freeCellCount": nx * ny - len(occupied),
        "occupiedRatio": len(occupied) / (nx * ny),
    }


def _grid_rect(
    boundary: dict[str, float],
    cell: float,
    x_run: tuple[int, int],
    start_row: int,
    end_row: int,
) -> dict[str, Any]:
    return {
        "minX": boundary["minX"] + x_run[0] * cell,
        "minY": boundary["minY"] + start_row * cell,
        "maxX": min(boundary["maxX"], boundary["minX"] + (x_run[1] + 1) * cell),
        "maxY": min(boundary["maxY"], boundary["minY"] + (end_row + 1) * cell),
        "source": "rasterizedA600LeafBodyAabb",
    }


def _frame(frame: dict[str, Any]) -> tuple[list[float], list[list[float]]]:
    axes = frame["axesWorld"]
    return (
        [float(value) for value in frame["originWorldMeters"]],
        [
            [float(value) for value in axes["xIntoMachine"]],
            [float(value) for value in axes["yTransportLateral"]],
            [float(value) for value in axes["zUp"]],
        ],
    )


def _project_box(box: list[float], origin: list[float], axes: list[list[float]]) -> list[float]:
    points = [
        _world_to_frame([x, y, z], origin, axes)
        for x in (box[0], box[3])
        for y in (box[1], box[4])
        for z in (box[2], box[5])
    ]
    return [
        min(point[0] for point in points),
        min(point[1] for point in points),
        min(point[2] for point in points),
        max(point[0] for point in points),
        max(point[1] for point in points),
        max(point[2] for point in points),
    ]


def _world_to_frame(point: list[float], origin: list[float], axes: list[list[float]]) -> list[float]:
    delta = [point[index] - origin[index] for index in range(3)]
    return [sum(delta[index] * axis[index] for index in range(3)) for axis in axes]


def _inset(bounds: dict[str, float], margin: float) -> dict[str, float]:
    result = {
        "minX": bounds["minX"] + margin,
        "minY": bounds["minY"] + margin,
        "maxX": bounds["maxX"] - margin,
        "maxY": bounds["maxY"] - margin,
        "z": bounds["z"],
    }
    if result["minX"] >= result["maxX"] or result["minY"] >= result["maxY"]:
        raise SystemExit("A600 edge margin consumes the complete installation platform")
    return result


def _clip_plan(box: list[float], bounds: dict[str, float]) -> list[float] | None:
    clipped = [
        max(box[0], bounds["minX"]),
        max(box[1], bounds["minY"]),
        min(box[3], bounds["maxX"]),
        min(box[4], bounds["maxY"]),
    ]
    return clipped if clipped[0] < clipped[2] and clipped[1] < clipped[3] else None


def _overlap(first: list[float], second: list[float]) -> bool:
    return not (
        first[2] <= second[0]
        or second[2] <= first[0]
        or first[3] <= second[1]
        or second[3] <= first[1]
    )


def _contains(outer: dict[str, float], inner: dict[str, float]) -> bool:
    return (
        outer["minX"] <= inner["minX"] <= inner["maxX"] <= outer["maxX"]
        and outer["minY"] <= inner["minY"] <= inner["maxY"] <= outer["maxY"]
    )


def _area(bounds: dict[str, float]) -> float:
    return max(0.0, bounds["maxX"] - bounds["minX"]) * max(
        0.0, bounds["maxY"] - bounds["minY"]
    )


def _box_area(bounds: list[float]) -> float:
    return max(0.0, bounds[2] - bounds[0]) * max(0.0, bounds[3] - bounds[1])


def _unique_mate(graph: dict[str, Any], name: str) -> dict[str, Any]:
    matches = [
        item
        for item in graph.get("Mates", [])
        if item.get("MateName") == name and set(item.get("ModuleTokens", [])) == {"A600", "A800"}
    ]
    if len(matches) != 1:
        raise SystemExit(f"Expected one A600-A800 mate {name}; found {len(matches)}")
    return matches[0]


def _one_endpoint(mate: dict[str, Any], token: str) -> dict[str, Any]:
    matches = [item for item in mate.get("Endpoints", []) if item.get("ModuleToken") == token]
    if len(matches) != 1:
        raise SystemExit(f"Expected one {token} endpoint for {mate.get('MateName')}")
    return matches[0]


def _numbers(item: dict[str, Any], name: str, length: int) -> list[float]:
    value = item.get(name, item.get(name[0].lower() + name[1:]))
    if not isinstance(value, list) or len(value) != length:
        raise SystemExit(f"Missing {length}-value {name}")
    return [float(number) for number in value]


def _distance(first: list[float], second: list[float]) -> float:
    return math.sqrt(sum((first[index] - second[index]) ** 2 for index in range(3)))


def _check(name: str, passed: bool) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed)}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.resolve().read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
