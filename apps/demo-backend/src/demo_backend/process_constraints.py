from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Literal

# Maintenance rule: every process-constraint change must update
# docs/layout_constraints_and_solver_principles-CN.md and its change log.


ModuleType = Literal[
    "gantry",
    "dispenser",
    "transport",
    "return_transport",
    "glue_supply",
    "scanner",
    "ccd",
    "calibration",
    "cleaning",
    "weighing",
    "carrier",
    "functional",
]

PreferredSide = Literal["auto", "low", "high"]


class ProcessConstraintConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class SemanticPoint:
    u: float
    v: float


@dataclass(frozen=True)
class SemanticRegion:
    min_u: float
    min_v: float
    max_u: float
    max_v: float


@dataclass(frozen=True)
class ModuleSemantic:
    component_name: str
    module_type: ModuleType
    points: dict[str, SemanticPoint] = field(default_factory=dict)
    regions: dict[str, SemanticRegion] = field(default_factory=dict)
    preferred_side: PreferredSide = "auto"
    allowed_rotation_quarters: tuple[int, ...] = (0, 1, 2, 3)
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {
            "moduleType": self.module_type,
            "points": {name: {"u": item.u, "v": item.v} for name, item in self.points.items()},
            "regions": {
                name: {
                    "minU": item.min_u,
                    "minV": item.min_v,
                    "maxU": item.max_u,
                    "maxV": item.max_v,
                }
                for name, item in self.regions.items()
            },
            "preferredSide": self.preferred_side,
            "allowedRotationDegrees": [item * 90 for item in self.allowed_rotation_quarters],
            "parameters": self.parameters,
        }


_MODULE_TYPES: set[str] = {
    "gantry",
    "dispenser",
    "transport",
    "return_transport",
    "glue_supply",
    "scanner",
    "ccd",
    "calibration",
    "cleaning",
    "weighing",
    "carrier",
    "functional",
}


def normalize_module_semantics(
    component_names: list[str],
    requested: dict[str, dict[str, Any]],
) -> dict[str, ModuleSemantic]:
    canonical = {name.lower(): name for name in component_names}
    result: dict[str, ModuleSemantic] = {}
    for requested_name, raw in requested.items():
        component_name = canonical.get(str(requested_name).strip().lower())
        if not component_name:
            raise ProcessConstraintConfigurationError(
                f"Semantic module '{requested_name}' was not found in the geometry capture."
            )
        if not isinstance(raw, dict):
            raise ProcessConstraintConfigurationError(
                f"Semantic module '{component_name}' must be a JSON object."
            )
        module_type = str(raw.get("moduleType") or raw.get("module_type") or "").strip().lower()
        if module_type not in _MODULE_TYPES:
            raise ProcessConstraintConfigurationError(
                f"Semantic module '{component_name}' has unsupported moduleType '{module_type}'."
            )
        points = _read_points(component_name, raw.get("points") or {})
        regions = _read_regions(component_name, raw.get("regions") or {})
        preferred_side = str(raw.get("preferredSide") or raw.get("preferred_side") or "auto").lower()
        if preferred_side not in {"auto", "low", "high"}:
            raise ProcessConstraintConfigurationError(
                f"Semantic module '{component_name}' preferredSide must be auto, low, or high."
            )
        allowed = raw.get("allowedRotationDegrees", raw.get("allowed_rotation_degrees", [0, 90, 180, 270]))
        if not isinstance(allowed, list) or not allowed:
            raise ProcessConstraintConfigurationError(
                f"Semantic module '{component_name}' allowedRotationDegrees must be a non-empty array."
            )
        quarters: list[int] = []
        for value in allowed:
            degrees = float(value)
            nearest = round(degrees / 90.0)
            if not math.isclose(degrees, nearest * 90.0, abs_tol=1e-9):
                raise ProcessConstraintConfigurationError(
                    f"Semantic module '{component_name}' rotation {degrees} is not a multiple of 90 degrees."
                )
            quarter = nearest % 4
            if quarter not in quarters:
                quarters.append(quarter)
        parameters = raw.get("parameters") or {}
        if not isinstance(parameters, dict):
            raise ProcessConstraintConfigurationError(
                f"Semantic module '{component_name}' parameters must be a JSON object."
            )
        if module_type == "scanner" and preferred_side == "auto":
            barcode_side = str(parameters.get("barcodeSide") or "").lower()
            if barcode_side in {"low", "high"}:
                preferred_side = barcode_side
        result[component_name] = ModuleSemantic(
            component_name=component_name,
            module_type=module_type,  # type: ignore[arg-type]
            points=points,
            regions=regions,
            preferred_side=preferred_side,  # type: ignore[arg-type]
            allowed_rotation_quarters=tuple(quarters),
            parameters=dict(parameters),
        )
    return result


def role_overrides_from_semantics(semantics: dict[str, ModuleSemantic]) -> dict[str, str]:
    role_by_type = {
        "gantry": "gantry",
        "transport": "transport",
        "return_transport": "transport",
        "glue_supply": "glue",
    }
    return {
        name: role_by_type.get(item.module_type, "functional")
        for name, item in semantics.items()
    }


def compile_process_constraints(
    component_names: list[str],
    semantics: dict[str, ModuleSemantic],
    roles: dict[str, str],
    gantry_name: str,
    long_axis: str,
    requested: tuple[dict[str, Any], ...],
    auto_generate: bool,
    default_clearance: float,
) -> list[dict[str, Any]]:
    constraints = [
        _normalize_explicit_constraint(component_names, item, index)
        for index, item in enumerate(requested)
    ]
    if not auto_generate or not semantics:
        return constraints

    by_type: dict[str, list[ModuleSemantic]] = {}
    for item in semantics.values():
        by_type.setdefault(item.module_type, []).append(item)

    transports = by_type.get("transport", [])
    gantry = semantics.get(gantry_name)
    if gantry is None:
        gantry = ModuleSemantic(gantry_name, "gantry")

    work_points: list[tuple[ModuleSemantic, str]] = []
    for transport in transports:
        for point_name in transport.points:
            lowered = point_name.lower()
            if lowered.startswith("workposition") or lowered.startswith("fiducial"):
                work_points.append((transport, point_name))

    reach_regions = _reach_regions(gantry)
    for transport, point_name in work_points:
        for region_name in reach_regions:
            constraints.append(
                _point_in_region(
                    f"auto-work-reach-{transport.component_name}-{point_name}-{region_name}",
                    transport.component_name,
                    point_name,
                    gantry_name,
                    region_name,
                    "Dispensing work point must be inside the configured valve reach region.",
                )
            )

    for scanner in by_type.get("scanner", []):
        transport = _single_target_with_point(transports, "barcode", scanner.component_name, "scanner")
        _require_point(scanner, "scanOrigin")
        maximum = _positive_parameter(scanner, "maxWorkingDistanceMeters")
        minimum = float(scanner.parameters.get("minWorkingDistanceMeters") or 0.0)
        if minimum < 0 or minimum > maximum:
            raise ProcessConstraintConfigurationError(
                f"Scanner '{scanner.component_name}' minWorkingDistanceMeters must be non-negative and not exceed maxWorkingDistanceMeters."
            )
        barcode_side = str(scanner.parameters.get("barcodeSide") or "").lower()
        if barcode_side not in {"low", "high"}:
            raise ProcessConstraintConfigurationError(
                f"Scanner '{scanner.component_name}' requires parameters.barcodeSide = low or high."
            )
        constraints.extend(
            [
                _point_distance(
                    f"auto-scanner-distance-{scanner.component_name}",
                    scanner.component_name,
                    "scanOrigin",
                    transport.component_name,
                    "barcode",
                    maximum,
                    "Scanner origin must be within configured working distance of the barcode.",
                    minimum,
                    semantic_point_height_meters(scanner, "scanOrigin"),
                    semantic_point_height_meters(transport, "barcode"),
                ),
                {
                    "id": f"auto-scanner-side-{scanner.component_name}",
                    "type": "sameSide",
                    "component": scanner.component_name,
                    "referenceComponent": transport.component_name,
                    "axis": "short",
                    "side": barcode_side,
                    "hard": True,
                    "message": "Scanner must stay on the configured barcode side of transport.",
                },
                _line_of_sight(
                    f"auto-scanner-los-{scanner.component_name}",
                    scanner.component_name,
                    "scanOrigin",
                    transport.component_name,
                    "barcode",
                    "Scanner-to-barcode line of sight must remain clear.",
                    semantic_point_height_meters(scanner, "scanOrigin"),
                    semantic_point_height_meters(transport, "barcode"),
                ),
            ]
        )
        optical_axis = scanner.parameters.get("opticalAxisDirectionLocal")
        direction: tuple[float, float, float] | None = None
        maximum_deviation: float | None = None
        if optical_axis is not None:
            if not isinstance(optical_axis, (list, tuple)) or len(optical_axis) != 3:
                raise ProcessConstraintConfigurationError(
                    f"Scanner '{scanner.component_name}' parameters.opticalAxisDirectionLocal "
                    "must contain [u, v, height]."
                )
            direction = tuple(float(value) for value in optical_axis)
            if not all(math.isfinite(value) for value in direction) or math.isclose(
                math.sqrt(sum(value * value for value in direction)), 0.0, abs_tol=1e-12
            ):
                raise ProcessConstraintConfigurationError(
                    f"Scanner '{scanner.component_name}' optical axis must be a finite non-zero vector."
                )
            maximum_deviation = float(
                scanner.parameters.get("maxOpticalAxisDeviationDegrees") or 0.0
            )
            if not 0.0 < maximum_deviation <= 180.0:
                raise ProcessConstraintConfigurationError(
                    f"Scanner '{scanner.component_name}' requires parameters."
                    "maxOpticalAxisDeviationDegrees in (0, 180]."
                )
            source_height = semantic_point_height_meters(scanner, "scanOrigin")
            target_height = semantic_point_height_meters(transport, "barcode")
            if source_height is None or target_height is None:
                raise ProcessConstraintConfigurationError(
                    f"Scanner '{scanner.component_name}' directed optical-axis constraint "
                    "requires scanOrigin and barcode heights."
                )
            constraints.append(
                {
                    "id": f"auto-scanner-directed-axis-{scanner.component_name}",
                    "type": "directedPointing",
                    "sourceComponent": scanner.component_name,
                    "sourcePoint": "scanOrigin",
                    "targetComponent": transport.component_name,
                    "targetPoint": "barcode",
                    "expectedDirectionLocal": list(direction),
                    "maxDeviationDegrees": maximum_deviation,
                    "sourceHeightMeters": source_height,
                    "targetHeightMeters": target_height,
                    "hard": True,
                    "message": (
                        "Scanner optical axis must point from the scan origin toward the "
                        "carrier barcode within the configured angular tolerance."
                    ),
                }
            )

        dynamic_scan_points = transport.parameters.get(
            "dynamicScanWindowPointNames", []
        )
        if dynamic_scan_points:
            if not transport.parameters.get(
                "dynamicScanWindowAcceptedForCoarseLayout", False
            ):
                raise ProcessConstraintConfigurationError(
                    f"Transport '{transport.component_name}' dynamic scan window points "
                    "require parameters.dynamicScanWindowAcceptedForCoarseLayout=true."
                )
            if not isinstance(dynamic_scan_points, list) or not all(
                isinstance(value, str) and value.strip()
                for value in dynamic_scan_points
            ):
                raise ProcessConstraintConfigurationError(
                    f"Transport '{transport.component_name}' parameters."
                    "dynamicScanWindowPointNames must be an array of point names."
                )
            source_height = semantic_point_height_meters(scanner, "scanOrigin")
            target_height = semantic_point_height_meters(transport, "barcode")
            for raw_point_name in dynamic_scan_points:
                point_name = raw_point_name.strip()
                _require_point(transport, point_name)
                constraints.extend(
                    [
                        _point_distance(
                            f"auto-scanner-dynamic-distance-{scanner.component_name}-{point_name}",
                            scanner.component_name,
                            "scanOrigin",
                            transport.component_name,
                            point_name,
                            maximum,
                            "Every endpoint of the coarse carrier stop window must remain within scanner working distance.",
                            minimum,
                            source_height,
                            target_height,
                        ),
                        _line_of_sight(
                            f"auto-scanner-dynamic-los-{scanner.component_name}-{point_name}",
                            scanner.component_name,
                            "scanOrigin",
                            transport.component_name,
                            point_name,
                            "Every endpoint of the coarse carrier stop window must remain visible to the scanner.",
                            source_height,
                            target_height,
                        ),
                    ]
                )
                if direction is not None and maximum_deviation is not None:
                    if source_height is None or target_height is None:
                        raise ProcessConstraintConfigurationError(
                            f"Scanner '{scanner.component_name}' dynamic directed-axis "
                            "constraints require scanOrigin and barcode heights."
                        )
                    constraints.append(
                        {
                            "id": (
                                f"auto-scanner-dynamic-directed-axis-"
                                f"{scanner.component_name}-{point_name}"
                            ),
                            "type": "directedPointing",
                            "sourceComponent": scanner.component_name,
                            "sourcePoint": "scanOrigin",
                            "targetComponent": transport.component_name,
                            "targetPoint": point_name,
                            "expectedDirectionLocal": list(direction),
                            "maxDeviationDegrees": maximum_deviation,
                            "sourceHeightMeters": source_height,
                            "targetHeightMeters": target_height,
                            "hard": True,
                            "message": (
                                "Scanner optical axis must cover every endpoint of the "
                                "coarse carrier stop window."
                            ),
                        }
                    )

    for ccd in by_type.get("ccd", []):
        _require_point(ccd, "cameraOrigin")
        if not work_points:
            raise ProcessConstraintConfigurationError(
                f"CCD '{ccd.component_name}' requires at least one transport point named workPosition* or fiducial*."
            )
        has_fov = "fieldOfView" in ccd.regions
        moving_axis_coverage = bool(ccd.parameters.get("movingAxisCoverage", False))
        maximum = float(ccd.parameters.get("maxWorkingDistanceMeters") or 0.0)
        if not has_fov and maximum <= 0:
            raise ProcessConstraintConfigurationError(
                f"CCD '{ccd.component_name}' requires region fieldOfView or positive "
                "parameters.maxWorkingDistanceMeters."
            )
        minimum = float(ccd.parameters.get("minWorkingDistanceMeters") or 0.0)
        if minimum < 0 or (maximum > 0 and minimum > maximum):
            raise ProcessConstraintConfigurationError(
                f"CCD '{ccd.component_name}' minWorkingDistanceMeters must be non-negative and not exceed maxWorkingDistanceMeters."
            )
        for transport, point_name in work_points:
            if maximum > 0:
                constraints.append(
                    _point_distance(
                        f"auto-ccd-distance-{ccd.component_name}-{transport.component_name}-{point_name}",
                        ccd.component_name,
                        "cameraOrigin",
                        transport.component_name,
                        point_name,
                        maximum,
                        "CCD origin must be within configured working distance of each work point.",
                        minimum,
                    )
                )
            if has_fov:
                constraints.append(
                    _point_in_region(
                        f"auto-ccd-fov-{ccd.component_name}-{transport.component_name}-{point_name}",
                        transport.component_name,
                        point_name,
                        ccd.component_name,
                        "fieldOfView",
                        "Each work point must be inside the configured CCD field of view.",
                    )
                )
            if not moving_axis_coverage:
                constraints.append(
                    _line_of_sight(
                            f"auto-ccd-los-{ccd.component_name}-{transport.component_name}-{point_name}",
                            ccd.component_name,
                            "cameraOrigin",
                            transport.component_name,
                            point_name,
                            "CCD-to-work-point line of sight must remain clear.",
                    )
                )

    for module_type in ("calibration", "cleaning", "weighing"):
        for service in by_type.get(module_type, []):
            _require_point(service, "servicePoint")
            if not reach_regions:
                raise ProcessConstraintConfigurationError(
                    f"{module_type.title()} module '{service.component_name}' requires gantry region "
                    "dualValveReach or both leftValveReach/rightValveReach."
                )
            for region_name in reach_regions:
                constraints.append(
                    _point_in_region(
                        f"auto-{module_type}-reach-{service.component_name}-{region_name}",
                        service.component_name,
                        "servicePoint",
                        gantry_name,
                        region_name,
                        f"{module_type.title()} service point must be inside valve reach.",
                    )
                )
            # A valve-reachable point is necessary but not sufficient for a
            # service module.  Calibration in particular also needs an open,
            # purpose-built station rather than any narrow gap inside the
            # gantry reach.  Projects can name that station on the gantry with
            # parameters.serviceRegion; the same mechanism is reusable for
            # cleaning and weighing stations.
            service_region = str(service.parameters.get("serviceRegion") or "").strip()
            if service_region:
                if service_region not in gantry.regions:
                    raise ProcessConstraintConfigurationError(
                        f"{module_type.title()} module '{service.component_name}' serviceRegion "
                        f"'{service_region}' is not defined on gantry '{gantry_name}'."
                    )
                constraints.append(
                    _point_in_region(
                        f"auto-{module_type}-service-zone-{service.component_name}-{service_region}",
                        service.component_name,
                        "servicePoint",
                        gantry_name,
                        service_region,
                        f"{module_type.title()} service point must be inside its dedicated service zone.",
                    )
                )

    for cleaning in by_type.get("cleaning", []):
        isolation = float(cleaning.parameters.get("isolationClearanceMeters") or default_clearance)
        isolation_mode = str(cleaning.parameters.get("isolationMode") or "moduleBounds")
        if isolation < 0:
            raise ProcessConstraintConfigurationError(
                f"Cleaning module '{cleaning.component_name}' isolationClearanceMeters must be non-negative."
            )
        for other in by_type.get("ccd", []) + by_type.get("weighing", []):
            if isolation_mode == "servicePoints":
                target_point = "cameraOrigin" if other.module_type == "ccd" else "servicePoint"
                _require_point(other, target_point)
                constraints.append(
                    _point_distance(
                        f"auto-cleaning-isolation-{cleaning.component_name}-{other.component_name}",
                        cleaning.component_name,
                        "servicePoint",
                        other.component_name,
                        target_point,
                        1.0e9,
                        "Cleaning service point must be isolated from the CCD/weighing service point.",
                        isolation,
                    )
                )
            elif isolation_mode == "moduleBounds":
                constraints.append(
                    {
                        "id": f"auto-cleaning-isolation-{cleaning.component_name}-{other.component_name}",
                        "type": "moduleClearance",
                        "firstComponent": cleaning.component_name,
                        "secondComponent": other.component_name,
                        "minDistanceMeters": isolation,
                        "hard": True,
                        "message": "Cleaning must be isolated from CCD and weighing modules.",
                    }
                )
            else:
                raise ProcessConstraintConfigurationError(
                    f"Cleaning module '{cleaning.component_name}' isolationMode must be moduleBounds or servicePoints."
                )

    return _deduplicate_constraints(constraints)


def evaluate_process_constraints(
    constraints: list[dict[str, Any]],
    semantics: dict[str, ModuleSemantic],
    footprints: dict[str, Any],
    placements: list[Any],
    roles: dict[str, str],
    long_axis: str,
) -> dict[str, Any]:
    by_name = {item.component_name: item for item in placements}
    diagnostics: list[dict[str, Any]] = []
    for constraint in constraints:
        kind = constraint["type"]
        if kind == "pointDistance":
            first = _world_point(constraint["sourceComponent"], constraint["sourcePoint"], semantics, by_name)
            second = _world_point(constraint["targetComponent"], constraint["targetPoint"], semantics, by_name)
            planar_distance = math.dist(first, second)
            source_height, target_height = _constraint_endpoint_heights(
                constraint,
                semantics,
            )
            vertical_distance = (
                abs(target_height - source_height)
                if source_height is not None and target_height is not None
                else None
            )
            distance = (
                math.hypot(planar_distance, vertical_distance)
                if vertical_distance is not None
                else planar_distance
            )
            minimum = float(constraint.get("minDistanceMeters") or 0.0)
            maximum = float(constraint["maxDistanceMeters"])
            success = minimum - 1e-9 <= distance <= maximum + 1e-9
            measured = {
                "distanceMeters": distance,
                "planarDistanceMeters": planar_distance,
                "verticalDistanceMeters": vertical_distance,
                "sourceHeightMeters": source_height,
                "targetHeightMeters": target_height,
                "heightAware": vertical_distance is not None,
                "minDistanceMeters": minimum,
                "maxDistanceMeters": maximum,
            }
        elif kind == "pointInRegion":
            point = _world_point(constraint["pointComponent"], constraint["point"], semantics, by_name)
            region = _world_region(constraint["regionComponent"], constraint["region"], semantics, by_name)
            success = _contains_point(region, point)
            measured = {"point": list(point), "region": list(region)}
        elif kind == "sameSide":
            component = by_name[constraint["component"]]
            reference = by_name[constraint["referenceComponent"]]
            axis = long_axis if constraint.get("axis") == "long" else _other_axis(long_axis)
            delta = _axis_center(component.bounds, axis) - _axis_center(reference.bounds, axis)
            side = constraint["side"]
            success = delta <= 1e-9 if side == "low" else delta >= -1e-9
            measured = {"axis": axis, "side": side, "signedCenterDeltaMeters": delta}
        elif kind == "moduleClearance":
            first = by_name[constraint["firstComponent"]]
            second = by_name[constraint["secondComponent"]]
            distance = _rectangle_distance(first.bounds, second.bounds)
            minimum = float(constraint["minDistanceMeters"])
            success = distance + 1e-9 >= minimum
            measured = {"distanceMeters": distance, "minDistanceMeters": minimum}
        elif kind == "relativeAnchorWindow":
            component = by_name[constraint["component"]]
            reference = by_name[constraint["referenceComponent"]]
            delta_u = component.anchor_u - reference.anchor_u
            delta_v = component.anchor_v - reference.anchor_v
            minimum_u = float(constraint["minDeltaU"])
            maximum_u = float(constraint["maxDeltaU"])
            minimum_v = float(constraint["minDeltaV"])
            maximum_v = float(constraint["maxDeltaV"])
            success = (
                minimum_u - 1e-9 <= delta_u <= maximum_u + 1e-9
                and minimum_v - 1e-9 <= delta_v <= maximum_v + 1e-9
            )
            measured = {
                "deltaU": delta_u,
                "deltaV": delta_v,
                "minDeltaU": minimum_u,
                "maxDeltaU": maximum_u,
                "minDeltaV": minimum_v,
                "maxDeltaV": maximum_v,
            }
        elif kind == "relativeAnchorExclusionWindow":
            component = by_name[constraint["component"]]
            reference = by_name[constraint["referenceComponent"]]
            delta_u = component.anchor_u - reference.anchor_u
            delta_v = component.anchor_v - reference.anchor_v
            minimum_u = float(constraint["minDeltaU"])
            maximum_u = float(constraint["maxDeltaU"])
            minimum_v = float(constraint["minDeltaV"])
            maximum_v = float(constraint["maxDeltaV"])
            inside_failed_window = (
                minimum_u - 1e-9 <= delta_u <= maximum_u + 1e-9
                and minimum_v - 1e-9 <= delta_v <= maximum_v + 1e-9
            )
            success = not inside_failed_window
            measured = {
                "deltaU": delta_u,
                "deltaV": delta_v,
                "excludedMinDeltaU": minimum_u,
                "excludedMaxDeltaU": maximum_u,
                "excludedMinDeltaV": minimum_v,
                "excludedMaxDeltaV": maximum_v,
                "insideExcludedWindow": inside_failed_window,
            }
        elif kind == "lineOfSight":
            first = _world_point(constraint["sourceComponent"], constraint["sourcePoint"], semantics, by_name)
            second = _world_point(constraint["targetComponent"], constraint["targetPoint"], semantics, by_name)
            source_height, target_height = _constraint_endpoint_heights(
                constraint,
                semantics,
            )
            requested_blockers = constraint.get("blockerComponents")
            if requested_blockers:
                blockers = [by_name[name] for name in requested_blockers]
            else:
                excluded = {constraint["sourceComponent"], constraint["targetComponent"]}
                blockers = [
                    item for item in placements
                    if item.component_name not in excluded and roles.get(item.component_name) != "gantry"
                    and not bool(
                        semantics.get(item.component_name)
                        and semantics[item.component_name].parameters.get("lineOfSightTransparent", False)
                    )
                ]
            blocked_by = [
                item.component_name
                for item in blockers
                if any(
                    _line_of_sight_envelope_blocks(
                        first,
                        second,
                        envelope,
                        source_height,
                        target_height,
                    )
                    for envelope in _line_of_sight_blocking_envelopes(
                        item,
                        semantics.get(item.component_name),
                    )
                )
            ]
            success = not blocked_by
            measured = {
                "source": list(first),
                "target": list(second),
                "blockedBy": blocked_by,
                "sourceHeightMeters": source_height,
                "targetHeightMeters": target_height,
                "heightAware": source_height is not None,
            }
        elif kind == "directedPointing":
            first = _world_point(
                constraint["sourceComponent"], constraint["sourcePoint"], semantics, by_name
            )
            second = _world_point(
                constraint["targetComponent"], constraint["targetPoint"], semantics, by_name
            )
            source_height, target_height = _constraint_endpoint_heights(
                constraint,
                semantics,
            )
            if source_height is None or target_height is None:
                raise ProcessConstraintConfigurationError(
                    f"Directed-pointing constraint '{constraint['id']}' requires endpoint heights."
                )
            actual = (
                second[0] - first[0],
                second[1] - first[1],
                target_height - source_height,
            )
            expected_raw = constraint["expectedDirectionLocal"]
            source_placement = by_name[constraint["sourceComponent"]]
            expected_uv = _rotate(
                float(expected_raw[0]),
                float(expected_raw[1]),
                source_placement.rotation_quarters,
            )
            expected = (expected_uv[0], expected_uv[1], float(expected_raw[2]))
            actual_unit = _unit_vector3(actual, constraint["id"], "actual source-to-target")
            expected_unit = _unit_vector3(expected, constraint["id"], "expected optical-axis")
            dot = max(-1.0, min(1.0, sum(a * b for a, b in zip(actual_unit, expected_unit))))
            deviation = math.degrees(math.acos(dot))
            maximum_deviation = float(constraint["maxDeviationDegrees"])
            success = deviation <= maximum_deviation + 1e-9
            measured = {
                "source": [first[0], first[1], source_height],
                "target": [second[0], second[1], target_height],
                "actualDirection": list(actual_unit),
                "expectedDirection": list(expected_unit),
                "deviationDegrees": deviation,
                "maxDeviationDegrees": maximum_deviation,
            }
        else:
            raise ProcessConstraintConfigurationError(f"Unsupported process constraint type '{kind}'.")

        hard = bool(constraint.get("hard", True))
        diagnostics.append(
            {
                "id": constraint["id"],
                "type": kind,
                "hard": hard,
                "success": success,
                "message": constraint.get("message") or ("ok" if success else "constraint failed"),
                "measured": measured,
            }
        )

    hard_failures = [item for item in diagnostics if item["hard"] and not item["success"]]
    soft_failures = [item for item in diagnostics if not item["hard"] and not item["success"]]
    return {
        "success": not hard_failures,
        "hardFeasible": not hard_failures,
        "constraintCount": len(diagnostics),
        "passedCount": sum(bool(item["success"]) for item in diagnostics),
        "hardFailureCount": len(hard_failures),
        "softFailureCount": len(soft_failures),
        "diagnostics": diagnostics,
    }


def _read_points(component_name: str, raw: Any) -> dict[str, SemanticPoint]:
    if not isinstance(raw, dict):
        raise ProcessConstraintConfigurationError(f"Semantic module '{component_name}' points must be an object.")
    result: dict[str, SemanticPoint] = {}
    for name, value in raw.items():
        if isinstance(value, dict):
            u, v = value.get("u"), value.get("v")
        elif isinstance(value, list) and len(value) >= 2:
            u, v = value[:2]
        else:
            raise ProcessConstraintConfigurationError(
                f"Point '{component_name}.{name}' must be {{u,v}} or [u,v]."
            )
        result[str(name)] = SemanticPoint(float(u), float(v))
    return result


def _read_regions(component_name: str, raw: Any) -> dict[str, SemanticRegion]:
    if not isinstance(raw, dict):
        raise ProcessConstraintConfigurationError(f"Semantic module '{component_name}' regions must be an object.")
    result: dict[str, SemanticRegion] = {}
    for name, value in raw.items():
        if not isinstance(value, dict):
            raise ProcessConstraintConfigurationError(f"Region '{component_name}.{name}' must be an object.")
        region = SemanticRegion(
            float(value["minU"]),
            float(value["minV"]),
            float(value["maxU"]),
            float(value["maxV"]),
        )
        if region.min_u > region.max_u or region.min_v > region.max_v:
            raise ProcessConstraintConfigurationError(f"Region '{component_name}.{name}' has inverted bounds.")
        result[str(name)] = region
    return result


def _normalize_explicit_constraint(component_names: list[str], raw: dict[str, Any], index: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ProcessConstraintConfigurationError(f"Process constraint #{index + 1} must be a JSON object.")
    item = dict(raw)
    item["id"] = str(item.get("id") or f"constraint-{index + 1}")
    item["type"] = str(item.get("type") or "")
    allowed = {
        "pointDistance",
        "pointInRegion",
        "sameSide",
        "moduleClearance",
        "relativeAnchorWindow",
        "relativeAnchorExclusionWindow",
        "lineOfSight",
        "directedPointing",
    }
    if item["type"] not in allowed:
        raise ProcessConstraintConfigurationError(
            f"Process constraint '{item['id']}' has unsupported type '{item['type']}'."
        )
    canonical = {name.lower(): name for name in component_names}
    component_keys = {
        "sourceComponent",
        "targetComponent",
        "pointComponent",
        "regionComponent",
        "component",
        "referenceComponent",
        "firstComponent",
        "secondComponent",
    }
    for key in component_keys:
        if key not in item:
            continue
        resolved = canonical.get(str(item[key]).strip().lower())
        if not resolved:
            raise ProcessConstraintConfigurationError(
                f"Process constraint '{item['id']}' references unknown component '{item[key]}'."
            )
        item[key] = resolved
    if "blockerComponents" in item:
        item["blockerComponents"] = [
            canonical.get(str(name).strip().lower()) or _unknown_component(item["id"], name)
            for name in item["blockerComponents"]
        ]
    item["hard"] = bool(item.get("hard", True))
    required_by_type = {
        "pointDistance": ("sourceComponent", "sourcePoint", "targetComponent", "targetPoint", "maxDistanceMeters"),
        "pointInRegion": ("pointComponent", "point", "regionComponent", "region"),
        "sameSide": ("component", "referenceComponent", "axis", "side"),
        "moduleClearance": ("firstComponent", "secondComponent", "minDistanceMeters"),
        "relativeAnchorWindow": (
            "component",
            "referenceComponent",
            "minDeltaU",
            "maxDeltaU",
            "minDeltaV",
            "maxDeltaV",
        ),
        "relativeAnchorExclusionWindow": (
            "component",
            "referenceComponent",
            "minDeltaU",
            "maxDeltaU",
            "minDeltaV",
            "maxDeltaV",
        ),
        "lineOfSight": ("sourceComponent", "sourcePoint", "targetComponent", "targetPoint"),
        "directedPointing": (
            "sourceComponent",
            "sourcePoint",
            "targetComponent",
            "targetPoint",
            "expectedDirectionLocal",
            "maxDeviationDegrees",
        ),
    }
    missing = [key for key in required_by_type[item["type"]] if key not in item]
    if missing:
        raise ProcessConstraintConfigurationError(
            f"Process constraint '{item['id']}' is missing required fields: {', '.join(missing)}."
        )
    if item["type"] == "pointDistance":
        minimum = float(item.get("minDistanceMeters") or 0.0)
        maximum = float(item["maxDistanceMeters"])
        if minimum < 0 or maximum <= 0 or minimum > maximum:
            raise ProcessConstraintConfigurationError(
                f"Process constraint '{item['id']}' has invalid point distance limits."
            )
    elif item["type"] == "sameSide":
        if item["axis"] not in {"short", "long"} or item["side"] not in {"low", "high"}:
            raise ProcessConstraintConfigurationError(
                f"Process constraint '{item['id']}' sameSide axis must be short/long and side low/high."
            )
    elif item["type"] == "moduleClearance" and float(item["minDistanceMeters"]) < 0:
        raise ProcessConstraintConfigurationError(
            f"Process constraint '{item['id']}' minDistanceMeters must be non-negative."
        )
    elif item["type"] in {"relativeAnchorWindow", "relativeAnchorExclusionWindow"}:
        values = {
            key: float(item[key])
            for key in ("minDeltaU", "maxDeltaU", "minDeltaV", "maxDeltaV")
        }
        if not all(math.isfinite(value) for value in values.values()):
            raise ProcessConstraintConfigurationError(
                f"Process constraint '{item['id']}' relative-anchor limits must be finite."
            )
        if values["minDeltaU"] > values["maxDeltaU"] or values["minDeltaV"] > values["maxDeltaV"]:
            raise ProcessConstraintConfigurationError(
                f"Process constraint '{item['id']}' has inverted relative-anchor limits."
            )
    elif item["type"] == "directedPointing":
        direction = item["expectedDirectionLocal"]
        if not isinstance(direction, (list, tuple)) or len(direction) != 3:
            raise ProcessConstraintConfigurationError(
                f"Process constraint '{item['id']}' expectedDirectionLocal must contain three values."
            )
        values = tuple(float(value) for value in direction)
        if not all(math.isfinite(value) for value in values) or math.isclose(
            math.sqrt(sum(value * value for value in values)), 0.0, abs_tol=1e-12
        ):
            raise ProcessConstraintConfigurationError(
                f"Process constraint '{item['id']}' expectedDirectionLocal must be finite and non-zero."
            )
        maximum_deviation = float(item["maxDeviationDegrees"])
        if not 0.0 < maximum_deviation <= 180.0:
            raise ProcessConstraintConfigurationError(
                f"Process constraint '{item['id']}' maxDeviationDegrees must be in (0, 180]."
            )
    return item


def _unknown_component(constraint_id: str, name: Any) -> str:
    raise ProcessConstraintConfigurationError(
        f"Process constraint '{constraint_id}' references unknown blocker component '{name}'."
    )


def _reach_regions(gantry: ModuleSemantic) -> list[str]:
    if "dualValveReach" in gantry.regions:
        return ["dualValveReach"]
    if "leftValveReach" in gantry.regions and "rightValveReach" in gantry.regions:
        return ["leftValveReach", "rightValveReach"]
    return []


def _single_target_with_point(
    candidates: list[ModuleSemantic],
    point_name: str,
    source_name: str,
    source_type: str,
) -> ModuleSemantic:
    matches = [item for item in candidates if point_name in item.points]
    if len(matches) != 1:
        raise ProcessConstraintConfigurationError(
            f"{source_type.title()} '{source_name}' requires exactly one transport with point '{point_name}'; "
            f"found {len(matches)}. Use explicit processConstraints for multi-transport layouts."
        )
    return matches[0]


def _require_point(module: ModuleSemantic, point_name: str) -> None:
    if point_name not in module.points:
        raise ProcessConstraintConfigurationError(
            f"{module.module_type.title()} module '{module.component_name}' requires point '{point_name}'."
        )


def _positive_parameter(module: ModuleSemantic, name: str) -> float:
    value = float(module.parameters.get(name) or 0.0)
    if value <= 0:
        raise ProcessConstraintConfigurationError(
            f"{module.module_type.title()} module '{module.component_name}' requires positive parameters.{name}."
        )
    return value


def _point_distance(
    constraint_id: str,
    source_component: str,
    source_point: str,
    target_component: str,
    target_point: str,
    maximum: float,
    message: str,
    minimum: float = 0.0,
    source_height_meters: float | None = None,
    target_height_meters: float | None = None,
) -> dict[str, Any]:
    result = {
        "id": constraint_id,
        "type": "pointDistance",
        "sourceComponent": source_component,
        "sourcePoint": source_point,
        "targetComponent": target_component,
        "targetPoint": target_point,
        "minDistanceMeters": minimum,
        "maxDistanceMeters": maximum,
        "hard": True,
        "message": message,
    }
    if source_height_meters is not None or target_height_meters is not None:
        if source_height_meters is None or target_height_meters is None:
            raise ProcessConstraintConfigurationError(
                f"Point-distance constraint '{constraint_id}' requires both endpoint heights."
            )
        result["sourceHeightMeters"] = float(source_height_meters)
        result["targetHeightMeters"] = float(target_height_meters)
    return result


def _point_in_region(
    constraint_id: str,
    point_component: str,
    point: str,
    region_component: str,
    region: str,
    message: str,
) -> dict[str, Any]:
    return {
        "id": constraint_id,
        "type": "pointInRegion",
        "pointComponent": point_component,
        "point": point,
        "regionComponent": region_component,
        "region": region,
        "hard": True,
        "message": message,
    }


def _line_of_sight(
    constraint_id: str,
    source_component: str,
    source_point: str,
    target_component: str,
    target_point: str,
    message: str,
    source_height_meters: float | None = None,
    target_height_meters: float | None = None,
) -> dict[str, Any]:
    result = {
        "id": constraint_id,
        "type": "lineOfSight",
        "sourceComponent": source_component,
        "sourcePoint": source_point,
        "targetComponent": target_component,
        "targetPoint": target_point,
        "hard": True,
        "message": message,
    }
    if source_height_meters is not None or target_height_meters is not None:
        if source_height_meters is None or target_height_meters is None:
            raise ProcessConstraintConfigurationError(
                f"Line-of-sight constraint '{constraint_id}' requires both endpoint heights."
            )
        result["sourceHeightMeters"] = float(source_height_meters)
        result["targetHeightMeters"] = float(target_height_meters)
    return result


def _world_point(
    component_name: str,
    point_name: str,
    semantics: dict[str, ModuleSemantic],
    placements: dict[str, Any],
) -> tuple[float, float]:
    semantic = semantics.get(component_name)
    if semantic is None or point_name not in semantic.points:
        raise ProcessConstraintConfigurationError(
            f"Process constraint requires undefined point '{component_name}.{point_name}'."
        )
    placement = placements[component_name]
    point = semantic.points[point_name]
    u, v = _rotate(point.u, point.v, placement.rotation_quarters)
    return placement.anchor_u + u, placement.anchor_v + v


def semantic_point_height_meters(
    semantic: ModuleSemantic | None,
    point_name: str,
) -> float | None:
    """Return a process point height in the common installation frame.

    Point-specific heights are stored relative to the module bottom.  Replay
    already uses ``installationNormalOffsetMeters`` to place that bottom above
    the common base, so process distance and line-of-sight checks must add the
    same offset.  If a point height is unknown, the 2-D compatibility behavior
    is retained rather than inventing a value.
    """

    if semantic is None:
        return None
    key = f"{point_name}HeightMeters"
    if key not in semantic.parameters:
        return None
    local_height = float(semantic.parameters[key])
    installation_offset = float(
        semantic.parameters.get("installationNormalOffsetMeters") or 0.0
    )
    if not math.isfinite(local_height) or not math.isfinite(installation_offset):
        raise ProcessConstraintConfigurationError(
            f"Process point '{semantic.component_name}.{point_name}' height and "
            "installationNormalOffsetMeters must be finite."
        )
    return installation_offset + local_height


def _constraint_endpoint_heights(
    constraint: dict[str, Any],
    semantics: dict[str, ModuleSemantic],
) -> tuple[float | None, float | None]:
    source_height = constraint.get("sourceHeightMeters")
    target_height = constraint.get("targetHeightMeters")
    if source_height is None and target_height is None:
        source_height = semantic_point_height_meters(
            semantics.get(str(constraint["sourceComponent"])),
            str(constraint["sourcePoint"]),
        )
        target_height = semantic_point_height_meters(
            semantics.get(str(constraint["targetComponent"])),
            str(constraint["targetPoint"]),
        )
        if source_height is None or target_height is None:
            return None, None
    elif (source_height is None) != (target_height is None):
        raise ProcessConstraintConfigurationError(
            f"Process constraint '{constraint['id']}' must define both "
            "sourceHeightMeters and targetHeightMeters, or neither."
        )
    source_height = float(source_height)
    target_height = float(target_height)
    if not math.isfinite(source_height) or not math.isfinite(target_height):
        raise ProcessConstraintConfigurationError(
            f"Process constraint '{constraint['id']}' heights must be finite."
        )
    return source_height, target_height


def _world_region(
    component_name: str,
    region_name: str,
    semantics: dict[str, ModuleSemantic],
    placements: dict[str, Any],
) -> tuple[float, float, float, float]:
    semantic = semantics.get(component_name)
    if semantic is None or region_name not in semantic.regions:
        raise ProcessConstraintConfigurationError(
            f"Process constraint requires undefined region '{component_name}.{region_name}'."
        )
    placement = placements[component_name]
    region = semantic.regions[region_name]
    corners = [
        _rotate(u, v, placement.rotation_quarters)
        for u in (region.min_u, region.max_u)
        for v in (region.min_v, region.max_v)
    ]
    return (
        placement.anchor_u + min(item[0] for item in corners),
        placement.anchor_v + min(item[1] for item in corners),
        placement.anchor_u + max(item[0] for item in corners),
        placement.anchor_v + max(item[1] for item in corners),
    )


def _line_of_sight_blocking_envelopes(
    placement: Any,
    semantic: ModuleSemantic | None,
) -> list[dict[str, Any]]:
    parameters = semantic.parameters if semantic else {}
    raw_boxes = parameters.get("occupancyBoxesLocal")
    if not parameters.get("useOccupancyBoxesForLineOfSight", False) or not isinstance(raw_boxes, list):
        return [{"bounds": placement.bounds, "heightRangeMeters": None}]
    envelopes: list[dict[str, Any]] = []
    for raw in raw_boxes:
        local = raw.get("bounds") if isinstance(raw, dict) else None
        if not isinstance(local, (list, tuple)) or len(local) != 4:
            raise ProcessConstraintConfigurationError(
                f"Component '{placement.component_name}' occupancyBoxesLocal must define four-value bounds."
            )
        corners = [
            _rotate(float(u), float(v), placement.rotation_quarters)
            for u in (local[0], local[2])
            for v in (local[1], local[3])
        ]
        height = raw.get("heightRangeMeters") if isinstance(raw, dict) else None
        height_range = None
        if height is not None:
            if not isinstance(height, (list, tuple)) or len(height) != 2:
                raise ProcessConstraintConfigurationError(
                    f"Component '{placement.component_name}' occupancyBoxesLocal heightRangeMeters "
                    "must contain two values."
                )
            height_range = (float(height[0]), float(height[1]))
            if (
                not all(math.isfinite(value) for value in height_range)
                or height_range[0] > height_range[1]
            ):
                raise ProcessConstraintConfigurationError(
                    f"Component '{placement.component_name}' occupancyBoxesLocal has an invalid "
                    "heightRangeMeters."
                )
        envelopes.append(
            {
                "bounds": (
                placement.anchor_u + min(point[0] for point in corners),
                placement.anchor_v + min(point[1] for point in corners),
                placement.anchor_u + max(point[0] for point in corners),
                placement.anchor_v + max(point[1] for point in corners),
                ),
                "heightRangeMeters": height_range,
            }
        )
    return envelopes or [{"bounds": placement.bounds, "heightRangeMeters": None}]


def _line_of_sight_blocking_bounds(
    placement: Any,
    semantic: ModuleSemantic | None,
) -> list[tuple[float, float, float, float]]:
    """Compatibility projection used by older diagnostics and tests."""
    return [
        envelope["bounds"]
        for envelope in _line_of_sight_blocking_envelopes(placement, semantic)
    ]


def _line_of_sight_envelope_blocks(
    start: tuple[float, float],
    end: tuple[float, float],
    envelope: dict[str, Any],
    source_height: float | None,
    target_height: float | None,
) -> bool:
    interval = _segment_bounds_parameter_interval(start, end, envelope["bounds"])
    if interval is None:
        return False
    height_range = envelope.get("heightRangeMeters")
    if source_height is None or target_height is None or height_range is None:
        return True
    first_height = source_height + (target_height - source_height) * interval[0]
    second_height = source_height + (target_height - source_height) * interval[1]
    beam_min, beam_max = sorted((first_height, second_height))
    return not (
        beam_max < height_range[0] - 1e-9
        or beam_min > height_range[1] + 1e-9
    )


def _rotate(u: float, v: float, quarters: int) -> tuple[float, float]:
    radians = math.radians((quarters % 4) * 90.0)
    cosine, sine = math.cos(radians), math.sin(radians)
    return cosine * u - sine * v, sine * u + cosine * v


def _unit_vector3(
    vector: tuple[float, float, float],
    constraint_id: str,
    label: str,
) -> tuple[float, float, float]:
    magnitude = math.sqrt(sum(value * value for value in vector))
    if not math.isfinite(magnitude) or magnitude <= 1e-12:
        raise ProcessConstraintConfigurationError(
            f"Directed-pointing constraint '{constraint_id}' has a zero or invalid {label} vector."
        )
    return tuple(value / magnitude for value in vector)


def _rectangle_distance(first: tuple[float, float, float, float], second: tuple[float, float, float, float]) -> float:
    delta_u = max(first[0] - second[2], second[0] - first[2], 0.0)
    delta_v = max(first[1] - second[3], second[1] - first[3], 0.0)
    return math.hypot(delta_u, delta_v)


def _segment_intersects_bounds(
    start: tuple[float, float],
    end: tuple[float, float],
    bounds: tuple[float, float, float, float],
) -> bool:
    return _segment_bounds_parameter_interval(start, end, bounds) is not None


def _segment_bounds_parameter_interval(
    start: tuple[float, float],
    end: tuple[float, float],
    bounds: tuple[float, float, float, float],
) -> tuple[float, float] | None:
    delta_u, delta_v = end[0] - start[0], end[1] - start[1]
    lower, upper = 0.0, 1.0
    for origin, delta, minimum, maximum in (
        (start[0], delta_u, bounds[0], bounds[2]),
        (start[1], delta_v, bounds[1], bounds[3]),
    ):
        if abs(delta) < 1e-12:
            if origin < minimum or origin > maximum:
                return None
            continue
        first = (minimum - origin) / delta
        second = (maximum - origin) / delta
        entry, exit_ = min(first, second), max(first, second)
        lower, upper = max(lower, entry), min(upper, exit_)
        if lower > upper:
            return None
    lower, upper = max(lower, 0.0), min(upper, 1.0)
    return (lower, upper) if lower <= upper else None


def _contains_point(bounds: tuple[float, float, float, float], point: tuple[float, float]) -> bool:
    return bounds[0] - 1e-9 <= point[0] <= bounds[2] + 1e-9 and bounds[1] - 1e-9 <= point[1] <= bounds[3] + 1e-9


def _axis_center(bounds: tuple[float, float, float, float], axis: str) -> float:
    return (bounds[0] + bounds[2]) / 2.0 if axis == "u" else (bounds[1] + bounds[3]) / 2.0


def _other_axis(axis: str) -> str:
    return "v" if axis == "u" else "u"


def _deduplicate_constraints(constraints: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in constraints:
        constraint_id = str(item["id"])
        if constraint_id in seen:
            raise ProcessConstraintConfigurationError(f"Duplicate process constraint id '{constraint_id}'.")
        seen.add(constraint_id)
        result.append(item)
    return result
