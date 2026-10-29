"""Read-only cup-mouth geometry, separate from mounting and CAD authorization.

A mouth is witnessed by a planar annulus and two full coaxial cylindrical
surfaces on one leaf/body. A module or leaf bounding-box center is not a mouth.
The explicitly supplied opening direction is a Demo semantic estimate; the
analytic faces establish its center/radius, not its manufacturing suitability.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from time import perf_counter

from .wastecup_target_station import _apply, _dot, _inverse, _transform, _vector


def _unit(value):
    value = _vector(value, 3)
    length = math.sqrt(_dot(value, value))
    if length < 1e-12:
        raise ValueError("Opening direction must be nonzero")
    return [x / length for x in value]


def _positive(value, label):
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be positive and finite")
    return float(value)


def _subtract(a, b):
    return [x-y for x, y in zip(a, b, strict=True)]


def _axis_point_at_plane(origin, axis, point, normal):
    denominator = _dot(axis, normal)
    if abs(denominator) < 1-1e-7:
        raise ValueError("Cup rim must be perpendicular to its axis")
    distance = _dot(_subtract(point, origin), normal) / denominator
    return [x+distance*y for x, y in zip(origin, axis, strict=True)]


def _full_cylinder(endpoint, tolerance):
    """Area and all extents must agree with a complete analytic cylinder."""
    axis = _unit(endpoint["CylinderAxisLocal"])
    origin = _vector(endpoint["CylinderOriginLocal"], 3)
    radius = _positive(endpoint["CylinderRadius"], "Cylinder radius")
    height = _positive(endpoint["FaceArea"], "Cylinder area") / (2*math.pi*radius)
    box = _vector(endpoint["FaceBoxLocal"], 6)
    center = [(box[i]+box[i+3])/2 for i in range(3)]
    delta = _subtract(center, origin)
    if math.dist(delta, [_dot(delta, axis)*x for x in axis]) > tolerance:
        raise ValueError("Cylinder bounds are not centered on its analytic axis")
    for i in range(3):
        extent = height*abs(axis[i]) + 2*radius*math.sqrt(max(0, 1-axis[i]**2))
        if abs(box[i+3]-box[i]-extent) > tolerance:
            raise ValueError("Partial/trimmed cylinder cannot certify a complete cup opening")
    return axis, origin, radius, height, center


def _mouth(plane, inner, outer, *, module, module_definition_id, up, tolerance):
    p, a, b = (row["Endpoint"] for row in (plane, inner, outer))
    identity = (p["RelativeLeafHierarchyPath"], p["BodyIndex"])
    if any((e["RelativeLeafHierarchyPath"], e["BodyIndex"]) != identity for e in (a, b)):
        raise ValueError("Rim and cylinders must be on the same leaf and body")
    for row in (plane, inner, outer):
        if not row.get("EndpointId") or not row["Endpoint"].get("SourceAssemblyPersistentReferenceBase64"):
            raise ValueError("Cup faces require stable endpoint identity")
    axis, origin, radius, height, middle = _full_cylinder(a, tolerance)
    other_axis, other_origin, outside, other_height, other_middle = _full_cylinder(b, tolerance)
    if not outside > radius:
        raise ValueError("Cup inner radius must be smaller than outer radius")
    if abs(_dot(axis, other_axis)) < 1-1e-7:
        raise ValueError("Cup cylinders are not coaxial")
    shift = _subtract(other_origin, origin)
    if math.dist(shift, [_dot(shift, axis)*x for x in axis]) > tolerance:
        raise ValueError("Cup cylinders have different axis lines")
    normal = _unit(p["FaceNormalLocal"])
    center = _axis_point_at_plane(origin, axis, _vector(p["FaceCenterLocal"], 3), normal)
    for midpoint, h in ((middle, height), (other_middle, other_height)):
        if abs(abs(_dot(_subtract(center, midpoint), axis))-h/2) > tolerance:
            raise ValueError("Rim plane does not terminate both cylindrical surfaces")
    expected_area = math.pi*(outside**2-radius**2)
    if abs(_positive(p["FaceArea"], "Rim area")-expected_area) > max(1e-10, expected_area*1e-5):
        raise ValueError("Planar face is not a complete annular rim")
    bounds = _vector(p["FaceBoxLocal"], 6)
    for i in range(3):
        span = outside*math.sqrt(max(0, 1-normal[i]**2))
        if max(abs(bounds[i]-(center[i]-span)), abs(bounds[i+3]-(center[i]+span))) > tolerance:
            raise ValueError("Rim bounds disagree with the analytic concentric annulus")
    world_axis = _unit(a["CylinderAxisWorld"])
    world_normal = _unit(p["FaceNormalWorld"])
    world_center = _axis_point_at_plane(_vector(a["CylinderOriginWorld"], 3), world_axis,
                                      _vector(p["FaceCenterWorld"], 3), world_normal)
    if abs(_dot(world_normal, up)) < 1-1e-6:
        raise ValueError("Rim is not aligned with the explicit Demo opening direction")
    outward = [x*(1 if _dot(world_normal, up) > 0 else -1) for x in world_normal]
    # A second annulus on a closed bottom must not be selected as the opening.
    local_outward = [x*(1 if _dot(world_normal, up) > 0 else -1) for x in normal]
    if any(_dot(_subtract(center, mid), local_outward) <= 0 for mid in (middle, other_middle)):
        raise ValueError("Annulus is the opposite end, not the requested opening side")
    root = _transform(module["SourceTransform"])
    point_id = "cup-mouth:" + hashlib.sha256((module_definition_id+"|"+identity[0]+"|"+
                p["SourceAssemblyPersistentReferenceBase64"]).encode()).hexdigest()[:20]
    return {
        "pointId": point_id, "moduleDefinitionId": module_definition_id,
        "moduleToken": module["ModuleToken"], "leafPath": identity[0], "bodyIndex": identity[1],
        "centerLeafLocalMeters": center, "centerModuleLocalMeters": _inverse(world_center, root),
        "centerSourceAssemblyWorldMeters": world_center,
        "openingNormalModuleLocal": [_dot(outward, root[i:i+3]) for i in (0, 3, 6)],
        "openingNormalSourceAssemblyWorld": outward, "openingRadiusMeters": radius,
        "outerRimRadiusMeters": outside,
        "rimEndpointId": plane["EndpointId"], "innerCylinderEndpointId": inner["EndpointId"],
        "outerCylinderEndpointId": outer["EndpointId"],
        "stableFaceReferences": [r["Endpoint"]["SourceAssemblyPersistentReferenceBase64"] for r in (plane, inner, outer)],
        "internalGeometryRigid": module.get("SolvingState") == 0,
        "method": "analytic_coaxial_full_cylinders_and_planar_annulus_intersection",
        "semanticAuthority": "explicit_opening_direction_demo_estimate",
        "engineeringConfirmed": False, "demoOnly": True,
    }


def extract_cup_mouth_points(catalog, *, module_definition_id, opening_direction_world,
                            geometry_tolerance_meters=1e-6):
    """Discover bounded leaf candidates. Missing/ambiguous geometry never passes."""
    tolerance = _positive(geometry_tolerance_meters, "Geometry tolerance")
    up = _unit(opening_direction_world)
    if len(catalog.get("Modules", [])) != 1 or not catalog.get("SourceAssemblyPath"):
        raise ValueError("Expected one-module leaf catalog with a source coordinate frame")
    module = catalog["Modules"][0]
    if module.get("IsSuppressed") is True:
        raise ValueError("Suppressed module cannot provide a cup functional point")
    _transform(module["SourceTransform"])
    rows = catalog.get("Endpoints", [])
    if any(r.get("Endpoint", {}).get("ModuleToken") != module["ModuleToken"] for r in rows):
        raise ValueError("Catalog endpoint module identity differs")
    planes = [r for r in rows if r.get("Endpoint", {}).get("SurfaceType") == "Plane"]
    cylinders = [r for r in rows if r.get("Endpoint", {}).get("SurfaceType") == "Cylinder"]
    result, rejected = [], []
    for plane in planes:
        for inner in cylinders:
            for outer in cylinders:
                if inner is outer:
                    continue
                try:
                    point = _mouth(plane, inner, outer, module=module, module_definition_id=module_definition_id,
                                   up=up, tolerance=tolerance)
                    result.append(point)
                except (ValueError, KeyError, TypeError) as exc:
                    rejected.append(str(exc))
    # One physical mouth per leaf/body. Never rank ambiguity by area or array order.
    identities = [(p["leafPath"], p["bodyIndex"]) for p in result]
    if len(identities) != len(set(identities)):
        raise ValueError("Ambiguous cup-mouth geometry on one leaf/body")
    return {
        "schemaVersion": "cup-function-points/v1", "moduleDefinitionId": module_definition_id,
        "sourceAssemblyPath": catalog["SourceAssemblyPath"], "modulePath": module.get("Path"),
        "moduleSourceTransformForMeasurementOnly": module["SourceTransform"], "points": result,
        "status": "geometry_candidates_measured" if result else "cup_geometry_missing",
        "rejectionReasons": sorted(set(rejected)), "newCadExecuted": False,
        "capturedPoseUsedForMeasurementOnly": True, "prototypePoseExecutionAuthorized": False,
        "cadLaunchAllowed": False, "collisionOrBrep": "not_evaluated", "actualFastening": "not_verified",
    }


def compare_cup_mouth_to_native_stations(*, source_points, native_points, mapping,
                                        observed_source_transform, observed_base_transform,
                                        native_base_transform, plane_tolerance_meters,
                                        angular_tolerance_degrees, radial_margin_meters=0):
    """Check whether native discharge points fall inside the observed cup mouths.

Transforms are measurement inputs, never output placement commands. Explicit
one-to-one mapping avoids swapping two cups by a nearest-neighbour heuristic.
"""
    plane_tol = _positive(plane_tolerance_meters, "Plane tolerance")
    angle_tol = _positive(angular_tolerance_degrees, "Angular tolerance")
    if angle_tol >= 90:
        raise ValueError("Angular tolerance must be less than 90 degrees")
    if type(radial_margin_meters) not in (int, float) or not math.isfinite(radial_margin_meters) or radial_margin_meters < 0:
        raise ValueError("Radial margin must be finite and non-negative")
    source_pose, base_pose, native_base = map(_transform, (observed_source_transform, observed_base_transform, native_base_transform))
    source = {p["pointId"]: p for p in source_points}
    native = {p["pointId"]: p for p in native_points}
    if not source or len(source) != len(source_points) or len(native) != len(native_points):
        raise ValueError("Cup point identities must be nonempty and unique")
    if (not isinstance(mapping, dict) or set(mapping) != set(source) or set(mapping.values()) != set(native)
            or len(mapping.values()) != len(set(mapping.values()))):
        raise ValueError("Explicit one-to-one mapping must cover every source/native cup")
    measured = []
    for source_id, native_id in mapping.items():
        s, n = source[source_id], native[native_id]
        if s.get("internalGeometryRigid") is not True:
            raise ValueError("Moving cup leaf needs rigid internal geometry or a fresh leaf-state witness")
        center = _inverse(_apply(_vector(s["centerModuleLocalMeters"], 3), source_pose), base_pose)
        source_normal_world = _apply(_unit(s["openingNormalModuleLocal"]), source_pose, direction=True)
        normal = [_dot(source_normal_world, base_pose[i:i+3]) for i in (0, 3, 6)]
        native_center = _inverse(_vector(n["centerSourceAssemblyWorldMeters"], 3), native_base)
        native_normal = [_dot(_unit(n["openingNormalSourceAssemblyWorld"]), native_base[i:i+3]) for i in (0, 3, 6)]
        delta = _subtract(native_center, center)
        height = _dot(delta, normal)
        planar = math.sqrt(max(0, _dot(delta, delta)-height**2))
        angle = math.degrees(math.acos(max(-1, min(1, _dot(normal, native_normal)))))
        usable = _positive(s["openingRadiusMeters"], "Opening radius")-radial_margin_meters
        if usable <= 0:
            raise ValueError("Margin consumes the cup opening")
        passed = abs(height) <= plane_tol and planar <= usable and angle <= angle_tol
        measured.append({"sourcePointId": source_id, "nativePointId": native_id,
                         "sourceCenterBaseLocalMeters": center, "nativeCenterBaseLocalMeters": native_center,
                         "planeErrorMeters": height, "radialErrorMeters": planar,
                         "directionErrorDegrees": angle, "usableOpeningRadiusMeters": usable,
                         "nativeDischargePointInsideObservedOpening": passed})
    return {"schemaVersion": "cup-native-station-comparison/v1", "measurements": measured,
            "functionalPointGeometryPassed": all(x["nativeDischargePointInsideObservedOpening"] for x in measured),
            "tolerances": {"planeMeters": plane_tol, "angleDegrees": angle_tol, "radialMarginMeters": radial_margin_meters},
            "authority": "target_base_native_cup_center_as_demo_discharge_target",
            "nativeRegionMeaning": "native cup centers; not nozzle reach, motion or process verification",
            "demoOnly": True, "nativeStationAuthorityVerified": False,
            "actualDischargeValidated": False, "newCadExecuted": False,
            "cadLaunchAllowed": False, "collisionOrBrep": "not_evaluated", "actualFastening": "not_verified"}


def suggest_cup_aligned_planar_station(*, source_points, native_points, mapping, graph,
                                      source_token, base_token, source_datum_capture_transform,
                                      observed_source_transform, observed_base_transform,
                                      graph_base_capture_transform, native_module_transform,
                                      native_base_transform, parameter_mate_names,
                                      alignment_policy=None):
    """Derive two explicit distances from target-native cup projections.

This returns measured parameter suggestions, never an executable Transform.
The native module pose calibrates the *target* station. The moving P000's
source pose is used only to convert recorded datum points into module-local
coordinates. Support gap stays zero, so different cup heights stay visible.
    """
    source_pose, base_pose, graph_base, source_datum, native_pose, native_base = map(_transform, (
        observed_source_transform, observed_base_transform, graph_base_capture_transform,
        source_datum_capture_transform, native_module_transform, native_base_transform))
    source, native = ({p["pointId"]: p for p in points} for points in (source_points, native_points))
    if (not source or len(source) != len(source_points) or len(native) != len(native_points)
            or set(mapping) != set(source) or set(mapping.values()) != set(native)
            or len(mapping) != len(set(mapping.values()))):
        raise ValueError("Suggestion requires explicit complete one-to-one cup mapping")
    def endpoint(mate, token):
        rows = [e for e in mate["Endpoints"] if e["ModuleToken"] == token]
        if len(rows) != 1 or not rows[0].get("SourceAssemblyPersistentReferenceBase64"):
            raise ValueError("Expected one stable datum endpoint per module")
        return rows[0]
    supports = [m for m in graph["Mates"] if m.get("MateType") == 0]
    if len(supports) != 1 or set(parameter_mate_names) != {"longitudinal", "lateral"}:
        raise ValueError("Exactly one support and two named planar distances are required")
    fixed_support = endpoint(supports[0], base_token)
    world_normal = _unit(fixed_support["FaceNormalWorld"])
    normal = [_dot(world_normal, graph_base[i:i+3]) for i in (0, 3, 6)]
    observations, shifts = [], []
    for sid, nid in mapping.items():
        s, n = source[sid], native[nid]
        if s.get("internalGeometryRigid") is not True:
            raise ValueError("Moving cup geometry is not rigid")
        actual = _inverse(_apply(s["centerModuleLocalMeters"], source_pose), base_pose)
        target = _inverse(_apply(n["centerModuleLocalMeters"], native_pose), native_base)
        delta = _subtract(target, actual)
        height = _dot(delta, normal)
        tangent = [delta[i]-height*normal[i] for i in range(3)]
        shifts.append(tangent)
        observations.append({"sourcePointId": sid, "nativePointId": nid,
                             "observedCenterBaseLocalMeters": actual,
                             "nativeTargetCenterBaseLocalMeters": target,
                             "normalHeightMismatchMeters": height,
                             "requiredPlanarTranslationMeters": tangent})
    mean = [sum(s[i] for s in shifts)/len(shifts) for i in range(3)]
    residuals = [math.dist(shift, mean) for shift in shifts]
    residual = max(residuals)
    policy = alignment_policy or {"mode": "exact_center_projection"}
    if not isinstance(policy, dict) or policy.get("mode") not in {
            "exact_center_projection", "native_points_inside_source_openings"}:
        raise ValueError("Unsupported cup station alignment policy")
    margin = policy.get("radialMarginMeters", 0)
    if type(margin) not in (int, float) or not math.isfinite(margin) or margin < 0:
        raise ValueError("Cup station radial margin must be finite and non-negative")
    point_rows = []
    for (source_id, native_id), point_residual in zip(mapping.items(), residuals, strict=True):
        radius = _positive(source[source_id]["openingRadiusMeters"], "Opening radius")
        usable = radius-margin
        if usable <= 0:
            raise ValueError("Cup station radial margin consumes the opening")
        point_rows.append({"sourcePointId": source_id, "nativePointId": native_id,
                           "centerResidualAfterCommonTranslationMeters": point_residual,
                           "openingRadiusMeters": radius, "radialMarginMeters": margin,
                           "usableOpeningRadiusMeters": usable,
                           "nativePointInsideSourceOpeningAfterTranslation": point_residual <= usable})
    if policy["mode"] == "exact_center_projection":
        if residual > 1e-6:
            raise ValueError("Cup spacing/order cannot match target projections by a single planar translation")
    elif not all(row["nativePointInsideSourceOpeningAfterTranslation"] for row in point_rows):
        raise ValueError("Target native points cannot fit inside source openings after one planar translation")
    moving_support = endpoint(supports[0], source_token)
    moving_local = _inverse(_vector(moving_support["FaceCenterWorld"], 3), source_datum)
    fixed_local = _inverse(_vector(fixed_support["FaceCenterWorld"], 3), graph_base)
    moving_actual = _inverse(_apply(moving_local, source_pose), base_pose)
    if abs(_dot(_subtract(moving_actual, fixed_local), normal)) > 1e-6:
        raise ValueError("Observed candidate does not preserve zero support gap")
    parameters, mate_rows = {}, []
    for parameter, name in parameter_mate_names.items():
        mates = [m for m in graph["Mates"] if m.get("MateName") == name and m.get("MateType") == 5]
        if len(mates) != 1:
            raise ValueError("Parameter must bind one existing distance mate")
        mate = mates[0]
        moving, fixed = endpoint(mate, source_token), endpoint(mate, base_token)
        moving_point = _inverse(_apply(_inverse(_vector(moving["FaceCenterWorld"], 3), source_datum), source_pose), base_pose)
        fixed_point = _inverse(_vector(fixed["FaceCenterWorld"], 3), graph_base)
        dimension_normal = [_dot(_unit(fixed["FaceNormalWorld"]), graph_base[i:i+3]) for i in (0, 3, 6)]
        if abs(_dot(dimension_normal, normal)) > 1e-6:
            raise ValueError("Position distance is not tangent to the support plane")
        signed_before = _dot(_subtract(moving_point, fixed_point), dimension_normal)
        if abs(abs(signed_before)-mate["Distance"]) > 1e-6:
            raise ValueError("Measured source pose does not satisfy the bound distance recipe")
        signed_after = signed_before+_dot(mean, dimension_normal)
        before_flip = (mate.get("AdvancedOptions") or {}).get("DistanceFlipDimension")
        if type(before_flip) is not bool:
            raise ValueError("Distance direction must be explicit")
        flip = before_flip ^ (signed_before*signed_after < 0)
        parameters[parameter] = abs(signed_after)
        mate_rows.append({"mateName": name, "parameter": parameter,
                          "beforeSignedMeters": signed_before, "suggestedSignedMeters": signed_after,
                          "suggestedDistanceMeters": abs(signed_after), "suggestedDistanceFlipDimension": flip})
    parameters["supportGap"] = 0
    return {"schemaVersion": "cup-native-projection-parameter-suggestion/v1",
            "status": "demo_planar_function_point_candidate_requires_new_cad",
            "positionParametersMeters": parameters, "mateParameters": mate_rows,
            "mapping": mapping, "functionPointMeasurements": observations,
            "planarTranslationBaseLocalMeters": mean, "maximumPlanarMappingResidualMeters": residual,
            "alignmentPolicy": policy, "projectionResidualChecks": point_rows,
            "functionalProjectionCandidatePassed": True,
            "threeDimensionalCentersCoincident": all(abs(x["normalHeightMismatchMeters"]) <= 1e-6 for x in observations),
            "supportGapPreservedMeters": 0, "derivedTransformUsedForExecution": False,
            "targetNativePoseUsedForStationMeasurementOnly": True,
            "sourcePrototypePoseUsedForPlacement": False, "newCadExecuted": False,
            "cadLaunchAllowed": False, "demoOnly": True, "actualDischargeValidated": False,
            "collisionOrBrep": "not_evaluated", "actualFastening": "not_verified"}


def screen_mapped_cup_planar_translation(*, source_points, native_points, mapping,
                                         source_pose, base_pose, native_pose,
                                         native_base_pose, support_normal_base_local,
                                         radial_margin_meters=0):
    """Screen one fixed orientation before attempting to compile station distances.

    A common planar translation may move the source cup cluster, but this screen
    never rotates it and never authorizes CAD.  It is therefore useful for
    separating "measurement can be reused" from "the currently published
    installation orientation can satisfy the target functional station".
    """

    margin = radial_margin_meters
    if type(margin) not in (int, float) or not math.isfinite(margin) or margin < 0:
        raise ValueError("Cup station radial margin must be finite and non-negative")
    source = {row["pointId"]: row for row in source_points}
    native = {row["pointId"]: row for row in native_points}
    if (
        not source
        or len(source) != len(source_points)
        or len(native) != len(native_points)
        or set(mapping) != set(source)
        or set(mapping.values()) != set(native)
        or len(mapping) != len(set(mapping.values()))
    ):
        raise ValueError("Screening requires explicit complete one-to-one cup mapping")
    source_pose, base_pose, native_pose, native_base_pose = map(
        _transform, (source_pose, base_pose, native_pose, native_base_pose)
    )
    normal = _unit(support_normal_base_local)
    observations, shifts = [], []
    for source_id, native_id in mapping.items():
        source_point, native_point = source[source_id], native[native_id]
        if source_point.get("internalGeometryRigid") is not True:
            raise ValueError("Moving cup geometry is not rigid")
        actual = _inverse(
            _apply(source_point["centerModuleLocalMeters"], source_pose), base_pose
        )
        target = _inverse(
            _apply(native_point["centerModuleLocalMeters"], native_pose),
            native_base_pose,
        )
        delta = _subtract(target, actual)
        height = _dot(delta, normal)
        tangent = [delta[i] - height * normal[i] for i in range(3)]
        shifts.append(tangent)
        observations.append(
            {
                "sourcePointId": source_id,
                "nativePointId": native_id,
                "sourceCenterBaseLocalMeters": actual,
                "nativeTargetCenterBaseLocalMeters": target,
                "normalHeightMismatchMeters": height,
                "requiredPlanarTranslationMeters": tangent,
            }
        )
    common = [sum(row[i] for row in shifts) / len(shifts) for i in range(3)]
    residuals = [math.dist(row, common) for row in shifts]
    checks = []
    for (source_id, native_id), residual in zip(
        mapping.items(), residuals, strict=True
    ):
        radius = _positive(source[source_id]["openingRadiusMeters"], "Opening radius")
        usable = radius - margin
        if usable <= 0:
            raise ValueError("Cup station radial margin consumes the opening")
        checks.append(
            {
                "sourcePointId": source_id,
                "nativePointId": native_id,
                "centerResidualAfterCommonTranslationMeters": residual,
                "openingRadiusMeters": radius,
                "radialMarginMeters": margin,
                "usableOpeningRadiusMeters": usable,
                "nativePointInsideSourceOpeningAfterTranslation": residual <= usable,
            }
        )
    passed = all(row["nativePointInsideSourceOpeningAfterTranslation"] for row in checks)
    return {
        "schemaVersion": "cup-published-pose-planar-screening/v1",
        "status": (
            "published_orientation_translation_candidate"
            if passed
            else "published_orientation_cannot_reach_target_by_translation"
        ),
        "passed": passed,
        "commonPlanarTranslationBaseLocalMeters": common,
        "maximumPlanarMappingResidualMeters": max(residuals),
        "pointChecks": checks,
        "observations": observations,
        "cadLaunchAllowed": False,
        "newCadExecuted": False,
        "readOnlyPostcheckPerformed": False,
        "boundary": (
            "This uses the published reopened target transform only as an offline "
            "orientation screen. It does not replace independent saved-output "
            "inspection, target-station CAD validation, fastening or collision/B-rep."
        ),
    }


def build_published_cup_station_screening(request_path, cad_result_path):
    """Build a digest-bound functional screen without launching or reopening CAD."""

    started, clock = datetime.now(timezone.utc).isoformat(), perf_counter()
    request_path, cad_result_path = Path(request_path).resolve(), Path(cad_result_path).resolve()
    evidence = []

    def read(path):
        path = Path(path).resolve()
        raw = path.read_bytes()
        evidence.append({"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()})
        return json.loads(raw.decode("utf-8-sig"))

    def resolve(value):
        path = Path(value)
        return path.resolve() if path.is_absolute() else (request_path.parent / path).resolve()

    def one(rows, key, value):
        matches = [row for row in rows if row.get(key) == value]
        if len(matches) != 1:
            raise ValueError(f"Expected unique {key}={value}")
        return matches[0]

    request, cad = read(request_path), read(cad_result_path)
    if cad.get("success") is not True:
        raise ValueError("Published-pose screen requires a successful CAD result")
    tool = cad.get("toolResult") or {}
    if any(tool.get(key) is not True for key in (
            "Success", "Reopened", "ReopenedMateParametersMatch", "MateSolveClean",
            "TargetFullyConstrained", "IndependentComponentInserted")):
        raise ValueError("Published-pose screen requires a complete non-prototype CAD closure")
    if tool.get("TargetCaseAnchored") not in (False, 0, None) or int(
            tool.get("AppliedTargetLeafPoseAnchorCount") or 0) != 0:
        raise ValueError("Anchored CAD evidence cannot screen an independent station")
    output = Path(cad["outputAssemblyPath"]).resolve()
    if not output.is_file() or hashlib.sha256(output.read_bytes()).hexdigest() != cad["outputAssemblySha256"]:
        raise ValueError("Published CAD output changed")
    evidence.append({"path": str(output), "sha256": cad["outputAssemblySha256"]})

    spec = request["stationSuggestion"]
    graph_path = resolve(spec["existingMateGraphPath"])
    graph = read(graph_path)
    if (graph_path != Path(cad["executionEffectiveGraphPath"]).resolve()
            or hashlib.sha256(graph_path.read_bytes()).hexdigest() != cad["executionEffectiveGraphSha256"]):
        raise ValueError("Cup request and CAD result use different effective graphs")
    native_graph = read(resolve(spec["nativeGraphPath"]))
    geometry = {}
    for role in ("source", "native"):
        rows = []
        for catalog_path in request[role]["catalogPaths"]:
            catalog = read(resolve(catalog_path))
            report = extract_cup_mouth_points(
                catalog,
                module_definition_id=request[role]["moduleDefinitionId"],
                opening_direction_world=request[role]["openingDirectionWorld"],
            )
            rows.extend(report["points"])
        geometry[role] = rows
    source_by_leaf = {row["leafPath"]: row for row in geometry["source"]}
    native_by_leaf = {row["leafPath"]: row for row in geometry["native"]}
    mapping = {
        one(list(source_by_leaf.values()), "leafPath", source_leaf)["pointId"]:
        one(list(native_by_leaf.values()), "leafPath", native_leaf)["pointId"]
        for source_leaf, native_leaf in spec["mappingByLeaf"].items()
    }
    modules = {row["ModuleToken"]: row for row in graph["Modules"]}
    native_modules = {row["ModuleToken"]: row for row in native_graph["Modules"]}
    if tool.get("TargetModuleToken") != spec["sourceToken"]:
        raise ValueError("Cup request source differs from the published target")
    supports = [row for row in graph["Mates"] if row.get("MateType") == 0]
    if len(supports) != 1:
        raise ValueError("Published-pose screen requires one support mate")
    fixed = one(supports[0]["Endpoints"], "ModuleToken", spec["baseToken"])
    graph_base = _transform(modules[spec["baseToken"]]["SourceTransform"])
    world_normal = _unit(fixed["FaceNormalWorld"])
    base_normal = [_dot(world_normal, graph_base[i:i+3]) for i in (0, 3, 6)]
    screening = screen_mapped_cup_planar_translation(
        source_points=geometry["source"],
        native_points=geometry["native"],
        mapping=mapping,
        source_pose=tool["ReopenedTargetRootTransform"],
        base_pose=modules[spec["baseToken"]]["SourceTransform"],
        native_pose=native_modules[spec["nativeGraphModuleToken"]]["SourceTransform"],
        native_base_pose=native_modules[spec["nativeGraphBaseToken"]]["SourceTransform"],
        support_normal_base_local=base_normal,
        radial_margin_meters=(spec.get("alignmentPolicy") or {}).get("radialMarginMeters", 0),
    )
    return {
        "schemaVersion": "published-cup-station-screening-report/v1",
        "sourceModuleDefinitionId": request["source"]["moduleDefinitionId"],
        "targetBaseDefinitionId": next(
            row["moduleDefinitionId"]
            for row in request.get("publishedPoseScreeningTargets", [])
            if row.get("moduleToken") == spec["baseToken"]
        ) if request.get("publishedPoseScreeningTargets") else None,
        "role": "WasteCup",
        "screening": screening,
        "evidence": evidence,
        "startedAtUtc": started,
        "finishedAtUtc": datetime.now(timezone.utc).isoformat(),
        "durationSeconds": perf_counter() - clock,
        "cadExecuted": False,
        "claimBoundary": screening["boundary"],
    }


def compare_two_cup_layouts(source_points, native_points, tolerance_meters=1e-6):
    """A necessary spacing test, not authority to install or a process verdict.

    Parallel mouth axes allow comparing planar separation in each module's own
    coordinates, independent of its captured world pose. Equal spacing alone
    does not select a mapping, orientation, installation face or target station.
    """
    tolerance = _positive(tolerance_meters, "Cup layout tolerance")
    result = {"status": "not_evaluated", "centerAlignmentPossible": None,
              "cadLaunchAllowed": False, "functionalPassed": None}
    spacings = []
    for points in (source_points, native_points):
        if len(points) != 2 or len({p["pointId"] for p in points}) != 2:
            return {**result, "reason": "requires_two_distinct_mouths_per_module"}
        if any(p.get("internalGeometryRigid") is not True for p in points):
            return {**result, "reason": "rigid_geometry_not_established"}
        axes = [_unit(p["openingNormalModuleLocal"]) for p in points]
        if _dot(*axes) < 1-1e-7:
            return {**result, "reason": "mouth_opening_axes_not_parallel_same_direction"}
        delta = _subtract(*[_vector(p["centerModuleLocalMeters"], 3) for p in points])
        height = _dot(delta, axes[0])
        spacings.append(math.sqrt(sum((delta[i]-height*axes[0][i])**2 for i in range(3))))
    mismatch = abs(spacings[0]-spacings[1])
    # A maximum per-center error e can absorb at most 2e of pair-spacing mismatch.
    impossible = mismatch > 2*tolerance
    return {**result, "status": "center_spacing_mismatch" if impossible else "necessary_spacing_check_passed",
            "centerAlignmentPossible": False if impossible else None,
            "sourcePlanarSpacingMeters": spacings[0], "nativePlanarSpacingMeters": spacings[1],
            "spacingDifferenceMeters": mismatch,
            "minimumMaximumCenterErrorLowerBoundMeters": mismatch/2,
            "centerToleranceMeters": tolerance,
            "boundary": "Only exact planar center matching is screened. Offset points inside a cup, nozzle movement, fastening and real dispensing are not evaluated."}


def build_cup_function_point_report(request_path):
    """Offline file entry point; bind every geometry source by path and SHA-256."""
    started, clock = datetime.now(timezone.utc).isoformat(), perf_counter()
    request_path = Path(request_path).resolve()
    evidence = []
    def read(path):
        path = Path(path).resolve()
        raw = path.read_bytes()
        evidence.append({"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()})
        return json.loads(raw.decode("utf-8-sig"))
    def resolve(path):
        path = Path(path)
        return path if path.is_absolute() else request_path.parent/path
    def one(rows, key, value):
        matches = [r for r in rows if r.get(key) == value]
        if len(matches) != 1:
            raise ValueError(f"Expected unique {key}={value}")
        return matches[0]
    request = read(request_path)
    for value in request.get("measurementEvidence", {}).values():
        read(resolve(value))
    results = {}
    for role in ("source", "native"):
        spec = request[role]
        rows = []
        for path in spec["catalogPaths"]:
            catalog_path = Path(path)
            if not catalog_path.is_absolute():
                catalog_path = request_path.parent/catalog_path
            catalog = read(catalog_path)
            for leaf in {r["Endpoint"].get("LeafComponentPath") for r in catalog.get("Endpoints", [])} - {None}:
                physical = Path(leaf).resolve()
                evidence.append({"path": str(physical), "sha256": hashlib.sha256(physical.read_bytes()).hexdigest(),
                                 "purpose": "source_geometry_hash_at_analysis"})
            geometry = extract_cup_mouth_points(catalog, module_definition_id=spec["moduleDefinitionId"],
                                               opening_direction_world=spec["openingDirectionWorld"])
            rows.append({"catalogPath": str(catalog_path.resolve()), **geometry})
        if len({row["sourceAssemblyPath"] for row in rows}) > 1:
            raise ValueError("One role's cup catalogs must share the same source coordinate frame")
        ids = [p["pointId"] for row in rows for p in row["points"]]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate physical cup evidence cannot be counted twice")
        poses = {tuple(row["moduleSourceTransformForMeasurementOnly"]) for row in rows}
        if len(poses) > 1:
            raise ValueError("Cup catalogs captured inconsistent module poses")
        results[role] = rows
        witness_path = (request.get("captureWitnesses") or {}).get(role)
        if witness_path:
            witness = read(resolve(witness_path))
            assembly = Path(witness["assemblyPath"]).resolve()
            actual_sha = hashlib.sha256(assembly.read_bytes()).hexdigest()
            evidence.append({"path": str(assembly), "sha256": actual_sha})
            if (witness.get("success") is not True or witness.get("observed", {}).get("readOnly") is not True
                    or not witness.get("checks") or not all(v is True for v in witness["checks"].values())
                    or actual_sha != witness.get("assemblySha256")):
                raise ValueError("Geometry-only capture witness is not valid")
            for row in rows:
                observed = one(witness["observed"]["components"], "sourcePath", row["modulePath"])
                if (Path(row["sourceAssemblyPath"]).resolve() != assembly or
                        max(abs(a-b) for a,b in zip(_transform(observed["transform"]),
                            _transform(row["moduleSourceTransformForMeasurementOnly"]), strict=True)) > 1e-8):
                    raise ValueError("Geometry-only capture pose or assembly identity differs")
    suggestion = None
    if "stationSuggestion" in request:
        spec = request["stationSuggestion"]
        independent_roles = set(spec.get("independentGeometryCaptureRoles") or [])
        if not independent_roles <= {"source", "native"}:
            raise ValueError("Independent geometry capture roles must be source/native")
        if any(role not in (request.get("captureWitnesses") or {}) for role in independent_roles):
            raise ValueError("Independent geometry capture requires an explicit capture witness")
        graph = read(resolve(spec["existingMateGraphPath"]))
        source_capture = read(resolve(spec["sourceDatumCapturePath"]))
        native_graph = read(resolve(spec["nativeGraphPath"]))
        state = read(resolve(spec["observedStatePath"]))
        source_rows, native_rows = results["source"], results["native"]
        if not source_rows or not native_rows:
            raise ValueError("Station suggestion needs source and native cup geometry")
        # Native station geometry may be measured in a separate assembly.
        # Keep each capture bound to its own saved-state witness, then use
        # module-local points below; never mix the two world coordinate frames.
        native_state = read(resolve(spec["nativeObservedStatePath"])) if spec.get("nativeObservedStatePath") else state
        for role, witness in (("source", state), ("native", native_state)):
            if (witness.get("success") is not True or not witness.get("checks")
                    or not all(v is True for v in witness["checks"].values())
                    or (spec.get("nativeObservedStatePath") and witness.get("observed", {}).get("readOnly") is not True)):
                raise ValueError("Captured component state did not pass read-only checks")
            assembly_path = Path(witness["assemblyPath"]).resolve()
            digest = hashlib.sha256(assembly_path.read_bytes()).hexdigest()
            evidence.append({"path": str(assembly_path), "sha256": digest})
            if digest != witness["assemblySha256"] or (role not in independent_roles and any(
                    Path(r["sourceAssemblyPath"]).resolve() != assembly_path for r in results[role])):
                raise ValueError("Cup geometry is not bound to the observed saved assembly")
        source_points = [p for row in source_rows for p in row["points"]]
        native_points = [p for row in native_rows for p in row["points"]]
        mapping = {one(source_points, "leafPath", s)["pointId"]: one(native_points, "leafPath", n)["pointId"]
                   for s, n in spec["mappingByLeaf"].items()}
        base = one(graph["Modules"], "ModuleToken", spec["baseToken"])
        native = one(native_graph["Modules"], "ModuleToken", spec["nativeGraphModuleToken"])
        native_base = one(native_graph["Modules"], "ModuleToken", spec["nativeGraphBaseToken"])
        source_datum = one(source_capture["Modules"], "ModuleToken", spec["sourceDatumModuleToken"])
        components = state["observed"]["components"]
        component = lambda path: one(components, "sourcePath", path)
        observed_base = component(base["Path"])
        observed_source = component(source_rows[0]["modulePath"])
        if observed_base.get("isFixed") is not True or observed_source.get("isFixed") is not False:
            raise ValueError("Only target base may be fixed in the measured pair")
        if Path(native["Path"]).resolve() != Path(native_rows[0]["modulePath"]).resolve():
            raise ValueError("Native station graph and captured module identities differ")
        for role, rows, witness in (("source", source_rows, state), ("native", native_rows, native_state)):
            for row in rows:
                observed = one(witness["observed"]["components"], "sourcePath", row["modulePath"])
                if role not in independent_roles and max(abs(a-b) for a, b in zip(_transform(observed["transform"]),
                        _transform(row["moduleSourceTransformForMeasurementOnly"]))) > 1e-8:
                    raise ValueError("Cup scan and component-state poses differ")
        suggestion = suggest_cup_aligned_planar_station(
            source_points=source_points, native_points=native_points, mapping=mapping, graph=graph,
            source_token=spec["sourceToken"], base_token=spec["baseToken"],
            source_datum_capture_transform=source_datum["SourceTransform"],
            observed_source_transform=observed_source["transform"], observed_base_transform=observed_base["transform"],
            graph_base_capture_transform=base["SourceTransform"], native_module_transform=native["SourceTransform"],
            native_base_transform=native_base["SourceTransform"], parameter_mate_names=spec["parameterMateNames"],
            alignment_policy=spec.get("alignmentPolicy"))
        suggestion["targetNativeCalibrationIdentity"] = {
            "moduleToken": native["ModuleToken"], "baseToken": native_base["ModuleToken"],
            "sourceAssemblyPath": native_graph["SourceAssemblyPath"],
            "currentNativeRootDiffersFromOriginal": max(abs(a-b) for a, b in zip(
                native["SourceTransform"], native_rows[0]["moduleSourceTransformForMeasurementOnly"])) > 1e-8,
            "independentGeometryCaptureRoles": sorted(independent_roles),
        }
    return {"schemaVersion": "cup-function-point-report/v1", "geometry": results,
            "layoutScreening": compare_two_cup_layouts(
                [p for r in results["source"] for p in r["points"]],
                [p for r in results["native"] for p in r["points"]]),
            "requestPath": str(request_path),
            "stationSuggestion": suggestion,
            "allRequestedCatalogsHaveMouthEvidence": all(r["points"] for rows in results.values() for r in rows)
                and all(results.values()),
            "evidence": evidence, "startedAtUtc": started,
            "finishedAtUtc": datetime.now(timezone.utc).isoformat(), "durationSeconds": perf_counter()-clock,
            "status": "geometry_only_not_cad_or_process_acceptance", "newCadExecuted": False,
            "cadLaunchAllowed": False, "prototypePoseExecutionAuthorized": False,
            "collisionOrBrep": "not_evaluated", "actualFastening": "not_verified"}


def verify_saved_cup_projection(*, geometry_report_path=None, geometry_report=None,
                                cad_result_path, saved_state_path, parameter_mate_names=None,
                                projection_tolerance_meters=1e-6, angular_tolerance_degrees=1):
    """Recompute mouth projections from hash-bound saved CAD component poses.

2-D target station agreement and 3-D mouth agreement are separate verdicts.
Even a 2-D pass is not a statement about nozzle reach or actual dispensing.
    """
    clock, started = perf_counter(), datetime.now(timezone.utc).isoformat()
    projection_tol = _positive(projection_tolerance_meters, "Projection tolerance")
    evidence = []
    def read(path):
        path = Path(path).resolve()
        raw = path.read_bytes()
        evidence.append({"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()})
        return json.loads(raw.decode("utf-8-sig"))
    if (geometry_report_path is None) == (geometry_report is None):
        raise ValueError("Provide exactly one cup geometry report or report path")
    report = read(geometry_report_path) if geometry_report_path is not None else geometry_report
    if parameter_mate_names is not None and (
            not isinstance(parameter_mate_names, dict) or set(parameter_mate_names) != {"longitudinal", "lateral"}
            or any(not isinstance(v, str) or not v for v in parameter_mate_names.values())
            or len(set(parameter_mate_names.values())) != 2):
        raise ValueError("Explicit candidate mate mapping must identify two distinct position mates")
    if report.get("allRequestedCatalogsHaveMouthEvidence") is not True or not report.get("stationSuggestion"):
        raise ValueError("Complete cup geometry and target-station suggestion are required")
    for row in report["evidence"]:
        if hashlib.sha256(Path(row["path"]).read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError("Cup geometry source evidence changed")
    request_path = Path(report["requestPath"])
    if not any(Path(row["path"]).resolve() == request_path.resolve() for row in report["evidence"]):
        raise ValueError("Cup request is not bound by geometry evidence")
    rebuilt = build_cup_function_point_report(request_path)
    if any(report.get(key) != rebuilt.get(key) for key in ("geometry", "stationSuggestion")):
        raise ValueError("Derived cup report differs from its bound geometry sources")
    request = read(request_path)
    spec = request["stationSuggestion"]
    native_path = Path(spec["nativeGraphPath"])
    native_graph = read(native_path if native_path.is_absolute() else request_path.parent/native_path)
    native_modules = {m["ModuleToken"]: m for m in native_graph["Modules"]}
    native_module = native_modules[spec["nativeGraphModuleToken"]]
    native_base = native_modules[spec["nativeGraphBaseToken"]]
    cad, state = read(cad_result_path), read(saved_state_path)
    tool = cad.get("toolResult") or {}
    if (cad.get("success") is not True or any(tool.get(k) is not True for k in (
            "Success", "Reopened", "ReopenedMateParametersMatch", "MateSolveClean", "TargetFullyConstrained"))
            or tool.get("TargetModuleToken") != spec["sourceToken"]):
        raise ValueError("Fresh target CAD solve/reopen evidence did not pass")
    if (state.get("success") is not True or state.get("observed", {}).get("readOnly") is not True
            or not state.get("checks") or not all(v is True for v in state["checks"].values())):
        raise ValueError("Independent saved CAD state did not pass")
    output = Path(cad["outputAssemblyPath"]).resolve()
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    if (digest != cad["outputAssemblySha256"] or digest != state["assemblySha256"]
            or Path(state["assemblyPath"]).resolve() != output):
        raise ValueError("CAD and saved-state artifact identities disagree")
    evidence.append({"path": str(output), "sha256": digest})
    graph_path = Path(cad["executionEffectiveGraphPath"])
    graph = read(graph_path)
    if hashlib.sha256(graph_path.read_bytes()).hexdigest() != cad["executionEffectiveGraphSha256"]:
        raise ValueError("Executed CAD graph changed")
    for expected in report["stationSuggestion"]["mateParameters"]:
        # A new generic recipe can rename mates; the caller binds its exact
        # compiled parameter-role mapping. Geometry is always independently
        # recomputed below, and distances/directions may not be substituted.
        name = parameter_mate_names[expected["parameter"]] if parameter_mate_names is not None else expected["mateName"]
        matches = [m for m in graph["Mates"] if m["MateName"] == name]
        if (len(matches) != 1 or matches[0].get("MateType") != 5 or
                abs(matches[0]["Distance"]-expected["suggestedDistanceMeters"]) > 1e-9 or
                (matches[0].get("AdvancedOptions") or {}).get("DistanceFlipDimension") != expected["suggestedDistanceFlipDimension"]):
            raise ValueError("Executed distance/direction differs from cup-station suggestion")
    def component(path):
        rows = [c for c in state["observed"]["components"] if Path(c["sourcePath"]).resolve() == Path(path).resolve()]
        if len(rows) != 1:
            raise ValueError("Ambiguous saved component identity")
        return rows[0]
    source = component(report["geometry"]["source"][0]["modulePath"])
    base = component(native_base["Path"])
    if source.get("isFixed") is not False or base.get("isFixed") is not True:
        raise ValueError("Only base may be fixed")
    if max(abs(a-b) for a, b in zip(_transform(source["transform"]), _transform(tool["ReopenedTargetRootTransform"]))) > 1e-8:
        raise ValueError("Independent saved source pose differs from CAD reopen witness")
    source_points = [p for row in report["geometry"]["source"] for p in row["points"]]
    native_points = []
    for row in report["geometry"]["native"]:
        for point in row["points"]:
            p = dict(point)
            p["centerSourceAssemblyWorldMeters"] = _apply(p["centerModuleLocalMeters"], _transform(native_module["SourceTransform"]))
            p["openingNormalSourceAssemblyWorld"] = _apply(p["openingNormalModuleLocal"], _transform(native_module["SourceTransform"]), direction=True)
            native_points.append(p)
    policy = report["stationSuggestion"].get("alignmentPolicy") or {"mode": "exact_center_projection"}
    margin = policy.get("radialMarginMeters", 0) if policy.get("mode") == "native_points_inside_source_openings" else 0
    comparison = compare_cup_mouth_to_native_stations(
        source_points=source_points, native_points=native_points, mapping=report["stationSuggestion"]["mapping"],
        observed_source_transform=source["transform"], observed_base_transform=base["transform"],
        native_base_transform=native_base["SourceTransform"], plane_tolerance_meters=projection_tol,
        angular_tolerance_degrees=angular_tolerance_degrees, radial_margin_meters=margin)
    if policy.get("mode") == "native_points_inside_source_openings":
        projected = all(
            r["radialErrorMeters"] <= r["usableOpeningRadiusMeters"]
            and r["directionErrorDegrees"] <= angular_tolerance_degrees
            for r in comparison["measurements"])
    else:
        projected = all(r["radialErrorMeters"] <= projection_tol and r["directionErrorDegrees"] <= angular_tolerance_degrees
                        for r in comparison["measurements"])
    return {"schemaVersion": "cup-saved-cad-projection-verification/v1",
            "status": "saved_cad_2d_projection_pass_3d_height_separate" if projected else "saved_cad_2d_projection_failed",
            "targetCupProjectionPassed": projected,
            "threeDimensionalCupMouthAlignmentPassed": comparison["functionalPointGeometryPassed"],
            "comparison": comparison, "evidence": evidence,
            "cadResultSha256": hashlib.sha256(Path(cad_result_path).read_bytes()).hexdigest(),
            "cadResultPath": str(Path(cad_result_path).resolve()),
            "readOnlyStatePath": str(Path(saved_state_path).resolve()),
            "readOnlyStateSha256": hashlib.sha256(Path(saved_state_path).read_bytes()).hexdigest(),
            "outputAssemblySha256": digest, "outputAssemblyPath": str(output),
            "boundRealCadEvidence": True, "newCadExecutedByThisVerifier": False,
            "readOnly": True, "actualDischargeValidated": False, "cadLaunchAllowed": False,
            "collisionOrBrep": "not_evaluated", "actualFastening": "not_verified",
            "startedAtUtc": started, "finishedAtUtc": datetime.now(timezone.utc).isoformat(),
            "durationSeconds": perf_counter()-clock}
