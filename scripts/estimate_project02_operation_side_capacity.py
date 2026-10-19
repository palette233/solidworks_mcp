from __future__ import annotations

import argparse
import itertools
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REQUEST = ROOT / "demo" / "FL9A24D062A000_real_process_request.json"
DEFAULT_OUTPUT = (
    ROOT / "demo" / "layout_previews" / "project02_operation_side_capacity.json"
)


def _resolve(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _dot(first: list[float], second: list[float]) -> float:
    return sum(float(a) * float(b) for a, b in zip(first, second))


def _sub(first: list[float], second: list[float]) -> list[float]:
    return [float(a) - float(b) for a, b in zip(first, second)]


def _project_world_box(
    box: list[float],
    origin: list[float],
    axes: tuple[list[float], list[float], list[float]],
) -> dict[str, float]:
    points = []
    for world in itertools.product(
        (float(box[0]), float(box[3])),
        (float(box[1]), float(box[4])),
        (float(box[2]), float(box[5])),
    ):
        delta = _sub(list(world), origin)
        points.append(tuple(_dot(delta, axis) for axis in axes))
    return {
        "minX": min(point[0] for point in points),
        "minY": min(point[1] for point in points),
        "minZ": min(point[2] for point in points),
        "maxX": max(point[0] for point in points),
        "maxY": max(point[1] for point in points),
        "maxZ": max(point[2] for point in points),
    }


def _intersection(
    first: dict[str, float], second: dict[str, float]
) -> dict[str, float] | None:
    result = {
        "minX": max(float(first["minX"]), float(second["minX"])),
        "minY": max(float(first["minY"]), float(second["minY"])),
        "maxX": min(float(first["maxX"]), float(second["maxX"])),
        "maxY": min(float(first["maxY"]), float(second["maxY"])),
    }
    return (
        result
        if result["maxX"] > result["minX"] and result["maxY"] > result["minY"]
        else None
    )


def _union_area(rectangles: list[dict[str, float]]) -> float:
    xs = sorted(
        {
            float(value)
            for rectangle in rectangles
            for value in (rectangle["minX"], rectangle["maxX"])
        }
    )
    area = 0.0
    for low, high in zip(xs, xs[1:]):
        if high <= low:
            continue
        intervals = sorted(
            (
                float(rectangle["minY"]),
                float(rectangle["maxY"]),
            )
            for rectangle in rectangles
            if float(rectangle["minX"]) < high
            and float(rectangle["maxX"]) > low
        )
        covered = 0.0
        if intervals:
            start, end = intervals[0]
            for next_start, next_end in intervals[1:]:
                if next_start <= end:
                    end = max(end, next_end)
                else:
                    covered += end - start
                    start, end = next_start, next_end
            covered += end - start
        area += (high - low) * covered
    return area


def _component_code(name: str) -> str:
    for code in ("A500", "A700", "A300"):
        if code in name.upper():
            return code
    return ""


def estimate(request_path: Path) -> dict[str, Any]:
    request = json.loads(request_path.read_text(encoding="utf-8"))
    policy = request["assemblySequencePolicy"]
    geometry_path = _resolve(request["geometryCapturePath"])
    frame_path = _resolve(policy["installationFrame"]["evidencePath"])
    surface_path = _resolve(policy["installationGeometry"]["evidencePath"])
    geometry = json.loads(geometry_path.read_text(encoding="utf-8"))
    frame = json.loads(frame_path.read_text(encoding="utf-8"))
    surface = json.loads(surface_path.read_text(encoding="utf-8"))

    safe = surface["installationPlatform"]["safeBoundary"]
    transport = surface["transportSupportRegion"]
    front_band = {
        "minX": float(safe["minX"]),
        "minY": float(safe["minY"]),
        "maxX": float(transport["minX"]),
        "maxY": float(safe["maxY"]),
    }
    clipped_keepouts = [
        clipped
        for raw in surface.get("hardKeepoutRegions") or []
        if (clipped := _intersection(front_band, raw)) is not None
    ]
    gross_area = (front_band["maxX"] - front_band["minX"]) * (
        front_band["maxY"] - front_band["minY"]
    )
    keepout_area = _union_area(clipped_keepouts)

    origin = [float(value) for value in frame["originWorldMeters"]]
    axes_world = frame["axesWorld"]
    axes = (
        [float(value) for value in axes_world["xIntoMachine"]],
        [float(value) for value in axes_world["yTransportLateral"]],
        [float(value) for value in axes_world["zUp"]],
    )
    service_bounds: dict[str, dict[str, float]] = {}
    for component in geometry.get("components") or []:
        code = _component_code(str(component.get("componentName") or ""))
        box = component.get("boundingBoxWorld")
        if code and isinstance(box, list) and len(box) == 6:
            service_bounds[code] = _project_world_box(box, origin, axes)
    if set(service_bounds) != {"A500", "A700", "A300"}:
        raise RuntimeError(
            "Project02 service-module world boxes are incomplete: "
            + ", ".join(sorted(service_bounds))
        )
    cluster = {
        "minX": min(item["minX"] for item in service_bounds.values()),
        "minY": min(item["minY"] for item in service_bounds.values()),
        "minZ": min(item["minZ"] for item in service_bounds.values()),
        "maxX": max(item["maxX"] for item in service_bounds.values()),
        "maxY": max(item["maxY"] for item in service_bounds.values()),
        "maxZ": max(item["maxZ"] for item in service_bounds.values()),
    }

    base_frame = geometry["baseFrame"]
    operation_outward = [float(value) for value in axes_world["operationOutward"]]
    u_dot = _dot(operation_outward, base_frame["uAxis"])
    v_dot = _dot(operation_outward, base_frame["vAxis"])
    if max(abs(u_dot), abs(v_dot)) < 0.9:
        raise RuntimeError("A600 operation direction is not aligned with the Layout2D axes.")
    if abs(v_dot) >= abs(u_dot):
        legacy_axis = "v"
        legacy_side = "high" if v_dot > 0 else "low"
    else:
        legacy_axis = "u"
        legacy_side = "high" if u_dot > 0 else "low"

    gross_depth = front_band["maxX"] - front_band["minX"]
    required_depth = cluster["maxX"] - float(safe["minX"])
    prototype_near_front = all(
        item["minX"] >= float(safe["minX"]) - 0.04
        and item["minX"] < float(transport["minX"])
        for item in service_bounds.values()
    )
    return {
        "schemaVersion": "project02-operation-side-capacity/v1",
        "success": True,
        "status": "PASS_COARSE_NONCONVEX_OPERATION_SIDE_ESTIMATE",
        "projectId": "project02",
        "operationFaceSide": "front",
        "legacySolverMapping": {
            "axis": legacy_axis,
            "side": legacy_side,
            "operationOutwardDotU": u_dot,
            "operationOutwardDotV": v_dot,
        },
        "operationSideGrossBand": {
            **front_band,
            "grossDepthMeters": gross_depth,
            "grossWidthMeters": front_band["maxY"] - front_band["minY"],
            "grossAreaSquareMeters": gross_area,
            "a600KeepoutAreaSquareMeters": keepout_area,
            "remainingAreaBeforeAnchoredModuleOccupancySquareMeters": max(
                0.0, gross_area - keepout_area
            ),
        },
        "prototypeServiceCluster": {
            "moduleCodes": ["A500", "A700", "A300"],
            "moduleBoundsFrameMeters": service_bounds,
            "unionBoundsFrameMeters": cluster,
            "requiredDepthFromSafeFrontMeters": required_depth,
            "requiredLateralSpanMeters": cluster["maxY"] - cluster["minY"],
            "allModulesStartNearOperationFace": prototype_near_front,
        },
        "capacityDecision": {
            "simpleRectangularBandFits": required_depth <= gross_depth + 1e-9,
            "prototypeDemonstratesNonConvexFit": prototype_near_front,
            "estimatedSelectedSide": "front" if prototype_near_front else "back",
            "decisionMethod": "prototype-observed-nonconvex-fit",
            "confidence": "medium",
            "reason": (
                "The service cluster is deeper than the unobstructed front rectangular band, "
                "but the prototype places A500/A700/A300 from the operation face into gaps around "
                "the transport and portal structures. A scalar width/depth test is therefore not "
                "a valid rejection rule for Project02."
            ),
        },
        "maintenanceEstimate": {
            "staticModuleClearanceMeters": float(request["minimumClearanceMeters"]),
            "a500ProtectedAccessStripDepthMeters": 0.1,
            "source": "existing provisional A500 protectedSpaceBoxesLocal",
            "authoritativeForFinalMaintenance": False,
        },
        "usableForCoarseLayout": prototype_near_front,
        "authoritativeForFinalMaintenance": False,
        "remainingConfirmation": (
            "Confirm tool withdrawal, consumable replacement and operator hand-access envelopes; "
            "then replace the prototype-observed fit with explicit 3-D service-space envelopes."
        ),
        "sources": {
            "request": str(request_path),
            "geometry": str(geometry_path),
            "installationFrame": str(frame_path),
            "installationSurface": str(surface_path),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", default=str(DEFAULT_REQUEST))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    request_path = _resolve(args.request).resolve()
    output_path = _resolve(args.output).resolve()
    result = estimate(request_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if args.apply:
        request = json.loads(request_path.read_text(encoding="utf-8"))
        policy = request["assemblySequencePolicy"]
        policy["operationFace"]["legacySolverSide"] = result[
            "legacySolverMapping"
        ]["side"]
        policy["operationSideCapacity"] = {
            "confirmed": False,
            "estimateAcceptedForCoarseLayout": True,
            "evidencePath": str(output_path.relative_to(ROOT)).replace("\\", "/"),
            "estimatedSelectedSide": result["capacityDecision"][
                "estimatedSelectedSide"
            ],
            "legacySolverSide": result["legacySolverMapping"]["side"],
            "confidence": result["capacityDecision"]["confidence"],
        }
        request_path.write_text(
            json.dumps(request, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
