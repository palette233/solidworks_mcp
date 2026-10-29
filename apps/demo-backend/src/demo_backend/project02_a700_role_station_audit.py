"""Audit the Project02 A700 native role station for an N000 substitution.

The report is deliberately review-only.  It proves the bounded station region
and whether the N000 footprint can geometrically fit, but it does not invent a
mechanical endpoint bundle when the A700/A600 native mounting interface has not
yet been captured.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from .mechanical_interface_contracts import MechanicalInterfaceContractError
from .parameterized_datum_placement import load_parameterized_datum_placement_catalog


SCHEMA = "project02-a700-native-role-station-audit/v1"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _dot(left: list[float], right: list[float]) -> float:
    return sum(float(a) * float(b) for a, b in zip(left, right, strict=True))


def _subtract(left: list[float], right: list[float]) -> list[float]:
    return [float(a) - float(b) for a, b in zip(left, right, strict=True)]


def _project_bbox(
    bbox: list[float], origin: list[float], x_axis: list[float], y_axis: list[float]
) -> dict[str, float]:
    if len(bbox) != 6:
        raise MechanicalInterfaceContractError("A700 world bounding box is malformed")
    values = []
    for x in (bbox[0], bbox[3]):
        for y in (bbox[1], bbox[4]):
            for z in (bbox[2], bbox[5]):
                offset = _subtract([x, y, z], origin)
                values.append((_dot(offset, x_axis), _dot(offset, y_axis)))
    return {
        "minX": min(row[0] for row in values),
        "maxX": max(row[0] for row in values),
        "minY": min(row[1] for row in values),
        "maxY": max(row[1] for row in values),
    }


def build_project02_a700_role_station_audit(workspace: Path) -> dict[str, Any]:
    workspace = workspace.resolve()
    frame_path = workspace / "demo/layout_previews/project02_a600_installation_frame.json"
    surface_path = workspace / "demo/layout_previews/project02_a600_installation_surface.json"
    geometry_path = workspace / "demo/FL9A24D062A000_8components_real_geometry.json"
    for path in (frame_path, surface_path, geometry_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    frame = _read(frame_path)
    surface = _read(surface_path)
    geometry = _read(geometry_path)
    if frame.get("status") != "PASS_A600_INSTALLATION_FRAME":
        raise MechanicalInterfaceContractError("A600 installation frame is not valid")
    a700_rows = [
        row
        for row in geometry.get("components") or []
        if "A700" in str(row.get("componentName") or "")
    ]
    if len(a700_rows) != 1:
        raise MechanicalInterfaceContractError("A700 native component does not resolve uniquely")
    axes = frame["axesWorld"]
    station = _project_bbox(
        list(a700_rows[0]["boundingBoxWorld"]),
        list(frame["originWorldMeters"]),
        list(axes["xIntoMachine"]),
        list(axes["yTransportLateral"]),
    )

    catalog = load_parameterized_datum_placement_catalog(workspace)
    slot_rows = [
        row
        for row in catalog.get("contracts") or []
        if row.get("side") == "base_slot"
        and row.get("moduleDefinitionId") == "project02::A600"
        and "CleaningWeighing" in (row.get("acceptedModuleRoles") or [])
    ]
    if len(slot_rows) != 1:
        raise MechanicalInterfaceContractError("A600 cleaning role slot does not resolve uniquely")
    profile = (
        (slot_rows[0].get("geometrySignature") or {})
        .get("finiteSupportProfilesByModuleDefinitionId", {})
        .get("project05::N000")
    )
    if not profile:
        raise MechanicalInterfaceContractError("N000 footprint profile is missing")
    offsets = profile["movingFootprintOffsetsFromDatum"]
    footprint_size = {
        "x": float(offsets["maxLongitudinal"]) - float(offsets["minLongitudinal"]),
        "y": float(offsets["maxLateral"]) - float(offsets["minLateral"]),
    }
    station_size = {
        "x": station["maxX"] - station["minX"],
        "y": station["maxY"] - station["minY"],
    }
    fits = footprint_size["x"] <= station_size["x"] and footprint_size["y"] <= station_size["y"]
    target_datum_interval = {
        "minX": station["minX"] - float(offsets["minLongitudinal"]),
        "maxX": station["maxX"] - float(offsets["maxLongitudinal"]),
        "minY": station["minY"] - float(offsets["minLateral"]),
        "maxY": station["maxY"] - float(offsets["maxLateral"]),
    }
    transport = surface["transportSupportRegion"]
    overlap = not (
        station["maxX"] <= transport["minX"]
        or station["minX"] >= transport["maxX"]
        or station["maxY"] <= transport["minY"]
        or station["minY"] >= transport["maxY"]
    )
    core = {
        "schemaVersion": SCHEMA,
        "status": "blocked_before_cad_missing_role_station_endpoint_bundle",
        "classification": "REVIEW_REQUIRED",
        "nativeModuleDefinitionId": "project02::A700",
        "replacementModuleDefinitionId": "project05::N000",
        "targetBaseDefinitionId": "project02::A600",
        "coordinateFrame": "A600_INSTALLATION_FRAME",
        "nativeRoleStationBoundsMeters": station,
        "nativeRoleStationSizeMeters": station_size,
        "replacementFootprintSizeMeters": footprint_size,
        "replacementEnvelopeFitsRoleStation": fits,
        "allowedReplacementDatumIntervalMeters": target_datum_interval,
        "nativeStationOverlapsTransportSupportAabb": overlap,
        "cadLaunchAllowed": False,
        "blockers": [
            {
                "code": "A700_A600_NATIVE_ENDPOINT_BUNDLE_NOT_CAPTURED",
                "detail": (
                    "A700's bounded role-station envelope is measurable, but its A600 support/"
                    "direction/location endpoint bundle has not been registered. Envelope fit alone "
                    "cannot authorize a replacement mate graph."
                ),
            },
            {
                "code": "ROLE_STATION_TRANSPORT_BOUNDARY_REQUIRES_EXACT_FOOTPRINT_PLACEMENT",
                "detail": (
                    "The A700 role-station AABB touches the transport support region in plan view; "
                    "a replacement must use the bounded datum interval and pass an explicit "
                    "transport-occupancy gate before CAD release."
                ),
            },
        ],
        "forbiddenFallback": {
            "longitudinalMeters": 0.465,
            "lateralMeters": 0.7125,
            "reason": "previous recipe placed N000 directly over the A800 transport region",
        },
        "nextAction": (
            "capture A700/A600 native support and location endpoints, map the N000 port to that "
            "role station, then validate one datum inside the reported interval from a nonprototype pose"
        ),
        "evidencePaths": [str(frame_path), str(surface_path), str(geometry_path)],
        "claimBoundary": (
            "This report proves a prototype-derived role-station envelope and footprint fit only. "
            "It does not claim mechanical interface compatibility, fastening, collision/B-rep or production release."
        ),
    }
    if not all(math.isfinite(value) for value in (*station.values(), *footprint_size.values())):
        raise MechanicalInterfaceContractError("role-station audit produced non-finite geometry")
    return {**core, "auditDigest": _digest(core)}
