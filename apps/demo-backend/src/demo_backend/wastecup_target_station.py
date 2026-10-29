"""Read-only target-station measurements for the existing P000/A600 Demo.

Prototype geometry is a measurement reference, never a CAD placement command.
Matching datum distances is kept separate from cup-mouth/process equivalence.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import itertools
import json
import math
from pathlib import Path
from time import perf_counter


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _hash(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _vector(value, size):
    if (not isinstance(value, list) or len(value) != size or
            any(type(x) not in (int, float) or not math.isfinite(x) for x in value)):
        raise ValueError(f"Expected {size} finite numbers")
    return [float(x) for x in value]


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b, strict=True))


def _transform(value):
    t = _vector(value, 16)
    rows = [t[i:i+3] for i in (0, 3, 6)]
    if any(abs(_dot(a, b) - (i == j)) > 1e-6
           for i, a in enumerate(rows) for j, b in enumerate(rows)):
        raise ValueError("Non-rigid transform")
    a, b, c = rows
    det = a[0]*(b[1]*c[2]-b[2]*c[1])-a[1]*(b[0]*c[2]-b[2]*c[0])+a[2]*(b[0]*c[1]-b[1]*c[0])
    if abs(det - 1) > 1e-6 or abs(t[12] - 1) > 1e-6:
        raise ValueError("Expected proper unit-scale rigid transform")
    return t


def _apply(p, t, *, direction=False):
    return [sum(p[i]*t[3*i+j] for i in range(3)) + (0 if direction else t[9+j])
            for j in range(3)]


def _inverse(p, t):
    delta = [p[i]-t[9+i] for i in range(3)]
    return [_dot(delta, t[3*i:3*i+3]) for i in range(3)]


def recover_leaf_measurement_transform(endpoints):
    """Recover a measurement frame from three witnessed orthogonal normals."""
    if len(endpoints) != 3 or len({e["RelativeLeafHierarchyPath"] for e in endpoints}) != 1:
        raise ValueError("Three datums must belong to one static leaf")
    local = [_vector(e["FaceNormalLocal"], 3) for e in endpoints]
    world = [_vector(e["FaceNormalWorld"], 3) for e in endpoints]
    for normals in (local, world):
        if any(abs(_dot(a, b)-(i == j)) > 1e-6
               for i, a in enumerate(normals) for j, b in enumerate(normals)):
            raise ValueError("Datum normals are not orthonormal")
    rotation = [sum(local[k][i]*world[k][j] for k in range(3))
                for i in range(3) for j in range(3)]
    first = endpoints[0]
    delta = [first["FaceCenterWorld"][j] - sum(first["FaceCenterLocal"][i]*rotation[3*i+j]
             for i in range(3)) for j in range(3)]
    t = _transform(rotation + delta + [1, 0, 0, 0])
    if any(math.dist(_apply(_vector(e["FaceCenterLocal"], 3), t),
                     _vector(e["FaceCenterWorld"], 3)) > 1e-6 for e in endpoints):
        raise ValueError("Same-leaf datum points do not share the measured frame")
    return t


def _one(rows, key, value):
    matches = [r for r in rows if r.get(key) == value]
    if len(matches) != 1:
        raise ValueError(f"Expected unique {key}={value}")
    return matches[0]


def match_native_signed_station(graph, native_graph):
    """Match base face identities before comparing the *side* of a station.

    A distance magnitude alone accepts a mirrored installation. These signed
    witnesses come from the native A300 faces, not from candidate mate values.
    Both graphs retain the original A600 coordinate system; the builder also
    checks that A600 is identity in that source assembly.
    """
    result = {}
    for mate in graph["Mates"]:
        base = _one(mate["Endpoints"], "ModuleToken", "A600")
        ref = base.get("SourceAssemblyPersistentReferenceBase64")
        if not ref:
            raise ValueError("Missing stable base-face identity for native station")
        matches = [m for m in native_graph["Mates"] if any(
            e.get("ModuleToken") == "A600" and
            e.get("SourceAssemblyPersistentReferenceBase64") == ref
            for e in m["Endpoints"])]
        if len(matches) != 1:
            raise ValueError("Native station face identity is absent or ambiguous")
        original = matches[0]
        if original.get("IsSuppressed") is True or original.get("MateType") != mate["MateType"]:
            raise ValueError("Native station datum semantics differ")
        native_base = _one(original["Endpoints"], "ModuleToken", "A600")
        native_module = _one(original["Endpoints"], "ModuleToken", "A300")
        for key in ("FaceCenterWorld", "FaceNormalWorld"):
            if math.dist(_vector(base[key], 3), _vector(native_base[key], 3)) > 1e-8:
                raise ValueError("Native and candidate base datum geometry disagree")
        signed = _dot([a-b for a, b in zip(_vector(native_module["FaceCenterWorld"], 3),
                                           _vector(native_base["FaceCenterWorld"], 3))],
                      _vector(native_base["FaceNormalWorld"], 3))
        result[mate["MateName"]] = signed
    return result


def measure_support_position(*, graph, native_target_transform, observed_target_transform,
                             observed_base_transform, frame, surface, native_station,
                             native_signed_station=None):
    """Measure existing CAD, not predict/authorize a new mate solution."""
    mates = graph["Mates"]
    target_endpoints = [_one(m["Endpoints"], "ModuleToken", "P000") for m in mates]
    if len(mates) != 3:
        raise ValueError("Expected exactly three support-position mates")
    leaf = recover_leaf_measurement_transform(target_endpoints)
    native_t = _transform(native_target_transform)
    target_t = _transform(observed_target_transform)
    base_t = _transform(observed_base_transform)
    origin = _vector(frame["originWorldMeters"], 3)
    axes = [_vector(frame["axesWorld"][k], 3) for k in
            ("xIntoMachine", "yTransportLateral", "zUp")]
    _transform([v for axis in axes for v in axis] + origin + [1, 0, 0, 0])

    def in_base(local_point):
        module_point = _inverse(_apply(local_point, leaf), native_t)
        return _inverse(_apply(module_point, target_t), base_t)

    def in_frame(local_point):
        delta = [a-b for a, b in zip(in_base(local_point), origin)]
        return [_dot(delta, axis) for axis in axes]

    distances = []
    support = None
    for mate in mates:
        support_mate = mate["MateName"] == "P000_A600_DATUM_SUPPORT"
        if mate.get("MateType") != (0 if support_mate else 5) or mate.get("IsSuppressed") is True:
            raise ValueError("Expected active coincident support and two distance mates")
        alignment = mate.get("Alignment")
        if type(alignment) is not int or alignment not in (0, 1):
            raise ValueError("Unsupported alignment")
        moving = _one(mate["Endpoints"], "ModuleToken", "P000")
        fixed = _one(mate["Endpoints"], "ModuleToken", "A600")
        actual = in_base(_vector(moving["FaceCenterLocal"], 3))
        base_point = _vector(fixed["FaceCenterWorld"], 3)
        base_normal = _vector(fixed["FaceNormalWorld"], 3)
        if abs(_dot(base_normal, base_normal) - 1) > 1e-6:
            raise ValueError("Expected unit base normal")
        signed = _dot([a-b for a, b in zip(actual, base_point)], base_normal)
        # Base A600 is identity in the original raw graph, verified by builder.
        raw_distance = mate.get("Distance")
        if not support_mate and type(raw_distance) not in (int, float):
            raise ValueError("Distance mate requires a numeric magnitude")
        expected = float(raw_distance or 0)
        if not math.isfinite(expected) or expected < 0:
            raise ValueError("Expected nonnegative finite distance")
        flipped = (mate.get("AdvancedOptions") or {}).get("DistanceFlipDimension", False)
        if type(flipped) is not bool:
            raise ValueError("Distance direction must be boolean")
        # This adapter uses the verified P000/A600 endpoint order: moving face
        # first, base face second. It is not a generic SW distance-sign rule.
        signed_expected = -expected if flipped else expected
        normal = _apply(_vector(moving["FaceNormalLocal"], 3), leaf, direction=True)
        normal = [_dot(normal, native_t[i:i+3]) for i in (0, 3, 6)]
        normal = _apply(normal, target_t, direction=True)
        normal = [_dot(normal, base_t[i:i+3]) for i in (0, 3, 6)]
        normal_dot = _dot(normal, base_normal)
        direction_matches = abs(normal_dot - (1 if alignment == 0 else -1)) <= 1e-6
        row = {"mateName": mate["MateName"], "signedDistanceMeters": signed,
               "magnitudeMeters": abs(signed), "requestedMagnitudeMeters": expected,
               "requestedSignedDistanceMeters": signed_expected,
               "distanceResidualMeters": abs(signed-signed_expected),
               "normalDot": normal_dot, "alignmentMatches": direction_matches}
        distances.append(row)
        if mate.get("MateType") == 0:
            support = moving
    if support is None:
        raise ValueError("Missing coincident support datum")
    box = _vector(support["FaceBoxLocal"], 6)
    if any(box[i] > box[i+3] for i in range(3)):
        raise ValueError("Invalid support-face bounds")
    corners = [in_frame(list(p)) for p in itertools.product(*[(box[i], box[i+3]) for i in range(3)])]
    footprint = {"minX": min(p[0] for p in corners), "maxX": max(p[0] for p in corners),
                 "minY": min(p[1] for p in corners), "maxY": max(p[1] for p in corners)}
    safe = surface["installationPlatform"]["safeBoundary"]
    inside = all(footprint[k] >= safe[k]-1e-6 for k in ("minX", "minY")) and all(
        footprint[k] <= safe[k]+1e-6 for k in ("maxX", "maxY"))
    transport = surface["transportSupportRegion"]
    overlap = max(0, min(footprint["maxX"], transport["maxX"])-max(footprint["minX"], transport["minX"])) * max(
        0, min(footprint["maxY"], transport["maxY"])-max(footprint["minY"], transport["minY"]))
    parameter_for_mate = {"P000_A600_DATUM_DISTANCE_1": "longitudinal",
                          "P000_A600_DATUM_DISTANCE_2": "lateral",
                          "P000_A600_DATUM_SUPPORT": "supportGap"}
    if {row["mateName"] for row in distances} != set(parameter_for_mate):
        raise ValueError("Unknown datum-to-role-parameter mapping")
    return {
        "signedDatumMeasurements": distances,
        "requestedMatesMeasured": all(row["distanceResidualMeters"] <= 1e-6 and row["alignmentMatches"] for row in distances),
        "nativeRoleDatumMagnitudesMatch": all(abs(row["magnitudeMeters"] - native_station[parameter_for_mate[row["mateName"]]]) <= 1e-6 for row in distances),
        # Missing directional evidence stays unknown, even if magnitudes match.
        "nativeRoleSignedDatumsMatch": None if native_signed_station is None else all(
            row["mateName"] in native_signed_station and
            type(native_signed_station[row["mateName"]]) in (int, float) and
            math.isfinite(native_signed_station[row["mateName"]]) and
            abs(row["signedDistanceMeters"] - native_signed_station[row["mateName"]]) <= 1e-6
            for row in distances),
        "nativeSignedStationMeters": native_signed_station,
        "supportFaceFootprintFrameMeters": footprint,
        "supportFaceWithinCoarsePlatform": inside,
        "maximumSupportPlaneHeightErrorMeters": max(abs(p[2]) for p in corners),
        "transportSupportProxyOverlapAreaSquareMeters": overlap,
        "transportProxyMeaning": "support-face footprint versus prototype transport-support region; not a collision test",
        "cupMouthPositionVerified": None,
        "exactTrimmedSupportContainmentVerified": None,
    }


def build_p000_a600_target_station_audit(workspace: Path, *, state_path: Path | None = None,
                                       cad_path: Path | None = None):
    from .native_role_station_evidence import build_native_role_station_evidence
    clock, started = perf_counter(), datetime.now(timezone.utc).isoformat()
    pair = workspace / "demo/cross_project_substitution/wastecup-project05-to-project02-v1/support-position-demo-v2"
    cad_path = cad_path or pair / "project02-A600-project05-P000-support-demo-v2.context-insert.result.json"
    cad = _read(cad_path)
    graph_path = Path(cad["executionEffectiveGraphPath"])
    state_path = state_path or pair / "read-only-state-verification.json"
    frame_path = workspace / "demo/layout_previews/project02_a600_installation_frame.json"
    surface_path = workspace / "demo/layout_previews/project02_a600_installation_surface.json"
    target_native_path = workspace / "demo/global_assembly_catalog/v1/combination-v1-preview/project05-nonanchor-driving-v6/P000/assembly_plan_effective.json"
    base_native_path = workspace / "demo/layout_previews/project02_module_mate_graph_v2.json"
    station_native_path = workspace / "demo/global_assembly_catalog/v1/combination-v1-preview/project02-seven-addon-driving-v6/A300/assembly_plan_effective.json"
    paths = [graph_path, cad_path, state_path, frame_path, surface_path, target_native_path, base_native_path, station_native_path]
    state, graph = _read(state_path), _read(graph_path)
    identity = [1,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0]
    if _one(_read(base_native_path)["Modules"], "ModuleToken", "A600")["SourceTransform"] != identity:
        raise ValueError("A600 geometry witness is not in base-local coordinates")
    if cad["executionEffectiveGraphSha256"] != _hash(graph_path):
        raise ValueError("CAD execution graph changed")
    state_checks = state.get("checks") or {}
    if (state.get("success") is not True or state["observed"].get("readOnly") is not True
            or not state_checks or not all(v is True for v in state_checks.values())):
        raise ValueError("Expected successful read-only saved CAD state")
    tool = cad.get("toolResult") or {}
    if (cad.get("success") is not True or tool.get("Success") is not True or
            tool.get("MateSolveClean") is not True or tool.get("ReopenedMateParametersMatch") is not True):
        raise ValueError("CAD solve/reopen evidence did not pass")
    if _hash(Path(state["assemblyPath"])) != state["assemblySha256"]:
        raise ValueError("Saved CAD state artifact changed")
    if Path(state["assemblyPath"]).resolve() != Path(cad["outputAssemblyPath"]).resolve():
        raise ValueError("State does not belong to the precise pair CAD result")
    if state["assemblySha256"] != cad["outputAssemblySha256"]:
        raise ValueError("State and CAD result hashes differ")
    components = state["observed"]["components"]
    def component(token):
        rows = [r for r in components if f"{token}.001-" in r["name"]]
        if len(rows) != 1:
            raise ValueError(f"Ambiguous {token} component")
        return rows[0]
    if component("A600").get("isFixed") is not True or component("P000").get("isFixed") is not False:
        raise ValueError("Only base may be fixed; target cannot be a pose anchor")
    saved_root = _transform(tool.get("ReopenedTargetRootTransform"))
    if max(abs(a-b) for a,b in zip(saved_root, _transform(component("P000")["transform"]))) > 1e-8:
        raise ValueError("Read-only state target differs from the bound CAD reopen")
    stations = build_native_role_station_evidence(workspace)
    station = _one(stations["stations"], "moduleDefinitionId", "project02::A300")
    measured = measure_support_position(
        graph=graph,
        native_target_transform=_one(_read(target_native_path)["Modules"], "ModuleToken", "P000")["SourceTransform"],
        observed_target_transform=component("P000")["transform"],
        observed_base_transform=component("A600")["transform"],
        frame=_read(frame_path), surface=_read(surface_path), native_station=station["parametersMeters"],
        native_signed_station=match_native_signed_station(graph, _read(station_native_path)),
    )
    transport_rows = [r for r in components if "A800.001-" in r["name"]]
    transport_pose_error = None
    if len(transport_rows) == 1:
        native_transport = _one(_read(base_native_path)["Modules"], "ModuleToken", "A800")["SourceTransform"]
        base_transform = _transform(component("A600")["transform"])
        actual_transform = _transform(transport_rows[0]["transform"])
        # The saved context must preserve the reference transport placement in
        # the base frame before its prototype support proxy can be reused.
        points = [[0,0,0], [1,0,0], [0,1,0], [0,0,1]]
        transport_pose_error = max(math.dist(_inverse(_apply(p, actual_transform), base_transform),
                                            _apply(p, _transform(native_transport))) for p in points)
    measured["transportProxyBoundToObservedContext"] = (
        None if transport_pose_error is None else transport_pose_error <= 1e-8)
    measured["transportContextPoseWitnessErrorMeters"] = transport_pose_error
    position_verified = (measured["requestedMatesMeasured"] and measured["nativeRoleDatumMagnitudesMatch"]
                         and measured["nativeRoleSignedDatumsMatch"] is True
                         and measured["supportFaceWithinCoarsePlatform"]
                         and measured["maximumSupportPlaneHeightErrorMeters"] <= 1e-6)
    return {
        "schemaVersion": "wastecup-target-station-audit/v1",
        "caseId": "P000-A600-native-A300-station", "source": "project05::P000", "target": "project02::A600",
        "nativeRoleModule": "project02::A300", "coordinateFrame": "A600_INSTALLATION_FRAME",
        "status": "target_datum_position_verified_functional_point_pending" if position_verified else "target_datum_position_failed",
        "targetDatumPositionVerified": position_verified,
        "nativeStationEvidence": station, "measurements": measured,
        "evidence": [{"path": str(p.resolve()), "sha256": _hash(p)} for p in paths],
        "cadResultSha256": _hash(cad_path), "effectiveGraphSha256": _hash(graph_path),
        "historicalCadReanalysis": True, "newCadExecuted": False,
        "observedComponentCount": len(components), "readOnlyStatePath": str(state_path),
        "prototypeGeometryUsedForMeasurementOnly": True, "prototypePoseExecutionAuthorized": False,
        "cadLaunchAllowed": False, "stationReady": False,
        "remainingEvidence": ["cup-mouth center/direction and target discharge location", "fresh CAD/leaf-geometry witness and repeatability", "exact support boundary if needed"],
        "collisionOrBrep": "not_evaluated", "actualFastening": "not_verified",
        "startedAtUtc": started, "finishedAtUtc": datetime.now(timezone.utc).isoformat(), "durationSeconds": perf_counter()-clock,
    }
