"""Read-only, evidence-bound station geometry checks; never CAD authority.

Prototype poses bridge captured geometry into a CAD result's coordinate system.
They are measurements only, never placement instructions. Face AABBs and native
module envelopes are explicitly weaker than registered installation regions.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from pathlib import Path
from typing import Any

from .project02_a700_role_station_audit import build_project02_a700_role_station_audit


SCHEMA = "role-station-witness/v1"
GN00_CASE = "demo/goal_role_station_and_matched_slot_cases_20261028/gn00-aa00-204mm"
CHECK_NAMES = (
    "slotMembership", "supportAndDirectionBound", "installationSideBound", "transportContext"
)


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _evidence(*paths: Path) -> list[dict[str, str]]:
    return [{"path": str(path.resolve()), "sha256": _sha256(path)} for path in paths]


def _check(passed: bool | None, method: str, evidence: list[dict[str, str]], **observations: Any) -> dict[str, Any]:
    return {
        "passed": passed,
        "status": "not_evaluated" if passed is None else "passed" if passed else "failed",
        "method": method,
        "evidence": evidence,
        "observations": observations,
    }


def _vector(value: Any, length: int = 3) -> list[float]:
    if not isinstance(value, list) or len(value) != length or any(
        isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item)
        for item in value
    ):
        raise ValueError(f"expected {length} finite geometry values")
    return [float(item) for item in value]


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def _transform(value: Any) -> list[float]:
    result = _vector(value, 16)
    axes = [result[i:i + 3] for i in (0, 3, 6)]
    if abs(result[12] - 1) > 1e-8 or any(
        abs(_dot(axes[i], axes[j]) - (1 if i == j else 0)) > 1e-8
        for i in range(3) for j in range(3)
    ):
        raise ValueError("station bridge requires a rigid unit-scale transform")
    cross = [axes[0][1] * axes[1][2] - axes[0][2] * axes[1][1],
             axes[0][2] * axes[1][0] - axes[0][0] * axes[1][2],
             axes[0][0] * axes[1][1] - axes[0][1] * axes[1][0]]
    if _dot(cross, axes[2]) < 1 - 1e-8:
        raise ValueError("station bridge transform is reflected")
    return result


def _point(point: list[float], transform: list[float], *, inverse: bool = False) -> list[float]:
    if inverse:
        delta = [point[i] - transform[9 + i] for i in range(3)]
        return [_dot(delta, transform[i:i + 3]) for i in (0, 3, 6)]
    return [transform[9 + i] + sum(point[j] * transform[3 * j + i] for j in range(3)) for i in range(3)]


def _direction(vector: list[float], transform: list[float], *, inverse: bool = False) -> list[float]:
    if inverse:
        return [_dot(vector, transform[i:i + 3]) for i in (0, 3, 6)]
    return [sum(vector[j] * transform[3 * j + i] for j in range(3)) for i in range(3)]


def _frame_transform(frame: dict[str, Any]) -> list[float]:
    axes = frame["axesWorld"]
    return _transform([*axes["u"], *axes["v"], *axes["n"], *frame["originWorldMeters"], 1, 0, 0, 0])


def _corners(bounds: dict[str, float]) -> list[list[float]]:
    values = _vector([bounds[key] for key in ("minU", "minV", "minN", "maxU", "maxV", "maxN")], 6)
    if any(values[i] > values[i + 3] for i in range(3)):
        raise ValueError("reversed occupancy bounds")
    return [list(row) for row in itertools.product(*[(values[i], values[i + 3]) for i in range(3)])]


def _bounds(points: list[list[float]]) -> dict[str, float]:
    return {prefix + axis: operation(p[i] for p in points)
            for prefix, operation in (("min", min), ("max", max))
            for i, axis in enumerate("UVN")}


def planar_relation(footprint: dict[str, float], boundary: dict[str, float], *, tolerance: float = 1e-8) -> dict[str, Any]:
    """Measure AABB containment/overlap, without assigning engineering meaning."""
    _corners(footprint)
    _corners(boundary)
    clearances = {key: (footprint[key] - boundary[key]) * (1 if key.startswith("min") else -1)
                  for key in ("minU", "maxU", "minV", "maxV")}
    overlap = [max(0.0, min(footprint["max" + axis], boundary["max" + axis])
                   - max(footprint["min" + axis], boundary["min" + axis])) for axis in "UV"]
    return {"envelopeContained": all(value >= -tolerance for value in clearances.values()),
            "clearancesMeters": clearances, "overlapAreaSquareMeters": math.prod(overlap),
            "toleranceMeters": tolerance}


def _module(graph: dict[str, Any], token: str) -> dict[str, Any]:
    rows = [row for row in graph["Modules"] if str(row["ModuleToken"]).upper().endswith(token)]
    if len(rows) != 1:
        raise ValueError(f"module identity does not resolve uniquely: {token}")
    return rows[0]


def _same_path(first: str, second: str) -> bool:
    return first.replace("\\", "/").casefold() == second.replace("\\", "/").casefold()


def _leaf_transform(catalog: dict[str, Any], selected: dict[str, Any]) -> list[float]:
    """Recover a measured leaf frame from three axis-aligned local plane normals.

    Every plane on that leaf must agree with the recovered transform. This is
    a coordinate bridge, not an assumption that leaf coordinates are root-local.
    """
    endpoints = [row["Endpoint"] for row in catalog["Endpoints"]
                 if row["Endpoint"].get("RelativeLeafHierarchyPath") == selected["RelativeLeafHierarchyPath"]
                 and row["Endpoint"].get("SurfaceType") == "Plane"]
    axes: dict[int, list[float]] = {}
    for endpoint in endpoints:
        local = _vector(endpoint["FaceNormalLocal"])
        world = _vector(endpoint["FaceNormalWorld"])
        for i in range(3):
            if abs(abs(local[i]) - 1) < 1e-8 and all(abs(local[j]) < 1e-8 for j in range(3) if i != j):
                axes[i] = [value * local[i] for value in world]
    if len(axes) != 3:
        raise ValueError("support leaf lacks three orthogonal normal witnesses")
    rotation = [*axes[0], *axes[1], *axes[2], 0, 0, 0, 1, 0, 0, 0]
    local_center = _point(_vector(selected["FaceCenterLocal"]), rotation)
    rotation[9:12] = [selected["FaceCenterWorld"][i] - local_center[i] for i in range(3)]
    result = _transform(rotation)
    for endpoint in endpoints:
        for local_key, world_key, operation in (
            ("FaceCenterLocal", "FaceCenterWorld", _point),
            ("FaceNormalLocal", "FaceNormalWorld", _direction),
        ):
            actual = operation(_vector(endpoint[local_key]), result)
            if max(abs(a - b) for a, b in zip(actual, _vector(endpoint[world_key]), strict=True)) > 1e-8:
                raise ValueError("support leaf coordinate witnesses disagree")
    return result


def _gn00_result(cad_path: Path, graph_path: Path, cad: dict[str, Any], checks: dict[str, Any]) -> dict[str, Any]:
    result = {"schemaVersion": SCHEMA, "caseId": "B8-GN00-AA00", "source": "project01::GN00", "target": "project03::AA00",
              "nativeRole": "project03::AG00", "cadResultPath": str(cad_path), "cadResultSha256": _sha256(cad_path),
              "effectiveGraphPath": str(graph_path), "effectiveGraphSha256": _sha256(graph_path),
              "outputAssemblyPath": cad["outputAssemblyPath"], "outputAssemblySha256": cad["outputAssemblySha256"],
              "checks": checks, "stationValidationPassed": all(row["passed"] is True for row in checks.values()),
              "cadLaunchAllowed": False, "reviewOnly": True, "prototypePoseUsedForMeasurementOnly": True,
              "claimBoundary": "Historical rigid-envelope projection and installation-side audit only; no collision/B-rep, fastening, load, process or execution authorization."}
    result["witnessDigest"] = hashlib.sha256(json.dumps(result, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    return result


def build_gn00_aa00_station_witness(workspace: Path) -> dict[str, Any]:
    root = workspace.resolve()
    cad_path = root / GN00_CASE / "cad-result.json"
    cad = _read(cad_path)
    graph_path = Path(cad["executionEffectiveGraphPath"])
    graph_hash = _sha256(graph_path)
    if graph_hash != cad.get("executionEffectiveGraphSha256"):
        raise ValueError("CAD effective graph digest changed")
    graph = _read(graph_path)
    tool = cad["toolResult"]
    if not all((cad.get("success") is True, tool.get("Success") is True,
                tool.get("Reopened") is True, tool.get("ReopenedMateParametersMatch") is True,
                tool.get("TargetFullyConstrained") is True, tool.get("MateSolveClean") is True)):
        raise ValueError("station geometry requires a successful reopened CAD result")
    output_path = Path(cad["outputAssemblyPath"])
    if _sha256(output_path) != cad.get("outputAssemblySha256"):
        raise ValueError("CAD output assembly digest changed")
    if {row.get("ModuleToken") for row in graph["Modules"]} != {"AA00", "GN00"} or tool.get("TargetModuleToken") != "GN00":
        raise ValueError("unexpected CAD context for GN00/AA00 pair audit")
    native_graph_path = root / "demo/semantic_ports/project01_GN00_fourth_increment_v1/assembly_plan_effective.json"
    moving_occupancy_path = root / "demo/layout_previews/project01_module_occupancy.json"
    target_occupancy_path = root / "demo/layout_previews/project03_module_occupancy.json"
    catalog_path = root / "demo/global_assembly_catalog/coverage-v2/ag00-datum-discovery-v1/aa00_ag00_mount_leaf_faces.json"
    moving_leaf_path = root / "demo/cross_project_substitution/cleaning-weighing-base-only-v1/project01_GN00_project03_AG00/gn00-support-mount-leaf-face-catalog.json"
    required_geometry = (native_graph_path, moving_occupancy_path, target_occupancy_path, catalog_path, moving_leaf_path)
    missing = [str(path) for path in required_geometry if not path.is_file()]
    if missing:
        return _gn00_result(cad_path, graph_path, cad, {
            name: _check(None, "geometry_evidence_missing", _evidence(cad_path, graph_path), missingEvidencePaths=missing)
            for name in CHECK_NAMES
        })
    moving_occupancy, target_occupancy = _read(moving_occupancy_path), _read(target_occupancy_path)
    native_module = _module(_read(native_graph_path), "GN00")
    moving_module, base_module = _module(graph, "GN00"), _module(graph, "AA00")
    catalog = _read(catalog_path)
    base_native = _module(catalog, "AA00")
    moving_capture = moving_occupancy["modules"]["GN00"]
    if not (_same_path(native_module["Path"], moving_module["Path"])
            and _same_path(moving_capture["filePath"], moving_module["Path"])
            and _same_path(base_native["Path"], base_module["Path"])
            and _same_path(target_occupancy["modules"]["AA00"]["filePath"], base_module["Path"])):
        raise ValueError("CAD/captured geometry module identities differ")
    source_frame = _frame_transform(moving_occupancy["installationFrame"])
    target_frame = _frame_transform(target_occupancy["installationFrame"])
    native_pose = _transform(native_module["SourceTransform"])
    target_pose = _transform(tool["ReopenedTargetRootTransform"])
    base_pose, base_native_pose = _transform(base_module["SourceTransform"]), _transform(base_native["SourceTransform"])
    anchor = _point(native_pose[9:12], source_frame, inverse=True)
    if max(abs(anchor[i] - moving_capture["prototypeAnchorInstallationMeters"][key]) for i, key in enumerate("uvn")) > 1e-8:
        raise ValueError("moving occupancy capture and native pose use different frames")

    def candidate_in_native_frame(point: list[float]) -> list[float]:
        return _point(_point(_point(point, base_pose, inverse=True), base_native_pose), target_frame, inverse=True)

    projected = [candidate_in_native_frame(_point(_point(_point(corner, source_frame), native_pose, inverse=True), target_pose))
                 for corner in _corners(moving_capture["topLevelBoundsInstallationMeters"])]
    footprint = _bounds(projected)
    native_station = target_occupancy["modules"]["AG00"]["topLevelBoundsInstallationMeters"]
    transport = target_occupancy["modules"]["AE00"]["topLevelBoundsInstallationMeters"]
    support_mates = [mate for mate in graph["Mates"] if mate.get("MateTypeName") == "swMateCOINCIDENT"]
    if len(support_mates) != 1:
        raise ValueError("support mate does not resolve uniquely")
    mate = support_mates[0]
    moving_support = next(ep for ep in mate["Endpoints"] if ep["ModuleToken"] == "GN00")
    base_support = next(ep for ep in mate["Endpoints"] if ep["ModuleToken"] == "AA00")
    endpoint_ids = base_support.get("SemanticEndpointIds") or []
    matches = [row["Endpoint"] for row in catalog["Endpoints"] if row["EndpointId"] in endpoint_ids]
    if len(matches) != 1 or matches[0].get("SourceAssemblyPersistentReferenceBase64") != base_support.get("SourceAssemblyPersistentReferenceBase64"):
        raise ValueError("selected support endpoint identity changed")
    support = matches[0]
    leaf_pose = _leaf_transform(catalog, support)
    box = _vector(support["FaceBoxLocal"], 6)
    support_bounds = _bounds([_point(_point(list(point), leaf_pose), target_frame, inverse=True)
                             for point in itertools.product(*[(box[i], box[i + 3]) for i in range(3)])])
    support_relation = planar_relation(footprint, support_bounds)
    moving_leaf = _leaf_transform(_read(moving_leaf_path), moving_support)
    contact_box = _vector(moving_support["FaceBoxLocal"], 6)
    contact_bounds = _bounds([
        candidate_in_native_frame(_point(_point(_point(list(point), moving_leaf), native_pose, inverse=True), target_pose))
        for point in itertools.product(*[(contact_box[i], contact_box[i + 3]) for i in range(3)])
    ])
    contact = candidate_in_native_frame(_point(_point(_vector(moving_support["FaceCenterWorld"]), native_pose, inverse=True), target_pose))
    support_center = _point(_vector(support["FaceCenterWorld"]), target_frame, inverse=True)
    moved_normal = _direction(_direction(_vector(moving_support["FaceNormalWorld"]), native_pose, inverse=True), target_pose)
    normal_in_native = _direction(_direction(moved_normal, base_pose, inverse=True), base_native_pose)
    normal_dot = _dot(normal_in_native, _vector(support["FaceNormalWorld"]))
    plane_gap = abs(contact[2] - support_center[2])
    plane_pass = plane_gap <= 1e-8 and abs(normal_dot - (-1 if mate["Alignment"] == 1 else 1)) <= 1e-8
    shared = _evidence(cad_path, graph_path, native_graph_path, moving_occupancy_path, target_occupancy_path, catalog_path, moving_leaf_path)
    # A face box is an outer bound, not a filled safe polygon (holes/cut-outs
    # are not represented). Full-module containment is not an authorized policy
    # for this slot: cantilevered or multi-plate support has not been reviewed.
    # Report the measured overhang without inventing an installation rejection.
    support_pass = False if not plane_pass else None
    below = footprint["minN"] - support_center[2]
    side_pass = below >= -1e-5 and plane_pass
    checks = {
        "slotMembership": _check(None, "native_role_envelope_comparison_not_registered_station", shared,
            candidateFootprintInstallationMeters=footprint, nativeRoleEnvelopeInstallationMeters=native_station,
            nativeEnvelopeRelation=planar_relation(footprint, native_station),
            registeredAllowedRoleRegionAvailable=False,
            reason="Native AG00 occupancy is a measured reference, not a registered permitted replacement region."),
        "supportAndDirectionBound": _check(support_pass, "support_plane_and_finite_face_outer_bound", shared,
            selectedSupportEndpointIds=endpoint_ids, planeResidualMeters=plane_gap, opposedNormalDot=normal_dot,
            planeAndDirectionPassed=plane_pass, supportFaceOuterBoundsInstallationMeters=support_bounds,
            fullEnvelopeVsSupportFaceOuterBound=support_relation, registeredSafeSupportRegionAvailable=False,
            contactFaceOuterBoundsInstallationMeters=contact_bounds,
            contactFaceVsSupportFaceOuterBound=planar_relation(contact_bounds, support_bounds),
            fullEnvelopeContainmentPolicyRegistered=False, findingSeverity="review_required",
            reason="AABB overhang is measured, not an installation failure: allowed cantilever/multi-plate support and the trimmed contact region are not registered."),
        "installationSideBound": _check(side_pass, "reopened_footprint_on_native_installation_up_side", shared,
            minimumHeightAboveSupportMeters=below, toleranceMeters=1e-5,
            installationNormalWorld=target_frame[6:9], boundary="Geometric installation half-space only; not service access or fastening."),
        "transportContext": _check(None, "pair_cad_has_no_transport_occupancy_witness", shared,
            currentCadModuleTokens=[row["ModuleToken"] for row in graph["Modules"]],
            nativeTransportReference="project03::AE00", nativeTransportEnvelopeInstallationMeters=transport,
            nativeTransportEnvelopeRelation=planar_relation(footprint, transport),
            reason="Prototype AE00 comparison is screening only; no current Transport component/pose is bound to this pair CAD."),
    }
    return _gn00_result(cad_path, graph_path, cad, checks)


def build_gn00_live_support_audit(
    workspace: Path, state_path: Path, moving_catalog_path: Path, base_catalog_path: Path,
) -> dict[str, Any]:
    """Recheck saved GN00 support geometry, without inserting or approving a station.

    Face indices and assembly-scoped persistent references can change on reopen.
    Match a unique local face fingerprint within the same body, leaf and config;
    report index drift rather than selecting the face now at the former index.
    """
    root = workspace.resolve()
    paths = [Path(path) if Path(path).is_absolute() else root / path
             for path in (state_path, moving_catalog_path, base_catalog_path)]
    state_path, moving_catalog_path, base_catalog_path = paths
    cad_path = root / GN00_CASE / "cad-result.json"
    cad = _read(cad_path)
    graph_path = Path(cad["executionEffectiveGraphPath"])
    output_path = Path(cad["outputAssemblyPath"])
    if _sha256(graph_path) != cad.get("executionEffectiveGraphSha256"):
        raise ValueError("CAD effective graph digest changed")
    if _sha256(output_path) != cad.get("outputAssemblySha256"):
        raise ValueError("CAD output assembly digest changed")
    tool = cad["toolResult"]
    if not all(value is True for value in (
        cad.get("success"), tool.get("Success"), tool.get("Reopened"),
        tool.get("ReopenedMateParametersMatch"), tool.get("TargetFullyConstrained"), tool.get("MateSolveClean"),
    )):
        raise ValueError("live support audit requires successful reopened CAD evidence")
    graph, state = _read(graph_path), _read(state_path)
    if (len(graph["Modules"]) != 2 or {row["ModuleToken"] for row in graph["Modules"]} != {"GN00", "AA00"}
            or tool.get("TargetModuleToken") != "GN00"):
        raise ValueError("live support audit requires the GN00/AA00 pair graph")
    if (state.get("success") is not True or state.get("observed", {}).get("readOnly") is not True
            or not state.get("checks") or not all(value is True for value in state["checks"].values())
            or not _same_path(str(state.get("assemblyPath", "")), str(output_path))
            or state.get("assemblySha256") != cad["outputAssemblySha256"]):
        raise ValueError("readonly snapshot does not bind the saved CAD output")

    def close(first: Any, second: Any, length: int = 3) -> bool:
        return max(abs(a - b) for a, b in zip(_vector(first, length), _vector(second, length), strict=True)) <= 1e-8

    components = state["observed"].get("components", [])
    if len(components) != 2:
        raise ValueError("readonly snapshot must contain exactly the two graph components")
    modules = {token: _module(graph, token) for token in ("GN00", "AA00")}
    poses = {"GN00": _transform(tool["ReopenedTargetRootTransform"]),
             "AA00": _transform(modules["AA00"]["SourceTransform"])}
    observed: dict[str, Any] = {}
    for token, module in modules.items():
        matches = [row for row in components if row.get("name") == module["Name"]
                   and _same_path(str(row.get("sourcePath", "")), module["Path"])]
        if len(matches) != 1:
            raise ValueError(f"snapshot component identity mismatch: {token}")
        component = observed[token] = matches[0]
        if (not component.get("configuration") or component.get("isFixed") is not (token == "AA00")
                or not close(_transform(component.get("transform")), poses[token], 16)):
            raise ValueError(f"snapshot component root pose/configuration mismatch: {token}")
    mates = [row for row in graph["Mates"] if row.get("MateTypeName") == "swMateCOINCIDENT"]
    if len(mates) != 1 or mates[0].get("Alignment") not in (0, 1):
        raise ValueError("support mate does not resolve uniquely with explicit alignment")
    mate = mates[0]
    if len(mate["Endpoints"]) != 2 or {ep["ModuleToken"] for ep in mate["Endpoints"]} != {"GN00", "AA00"}:
        raise ValueError("support mate endpoints do not bind the pair")
    selected = {ep["ModuleToken"]: ep for ep in mate["Endpoints"]}
    historical_paths = {
        "GN00": root / "demo/cross_project_substitution/cleaning-weighing-base-only-v1/project01_GN00_project03_AG00/gn00-support-mount-leaf-face-catalog.json",
        "AA00": root / "demo/global_assembly_catalog/coverage-v2/ag00-datum-discovery-v1/aa00_ag00_mount_leaf_faces.json",
    }
    native_path = root / "demo/semantic_ports/project01_GN00_fourth_increment_v1/assembly_plan_effective.json"
    native_pose = _transform(_module(_read(native_path), "GN00")["SourceTransform"])
    catalogs = {"GN00": _read(moving_catalog_path), "AA00": _read(base_catalog_path)}
    evidence_paths = [cad_path, graph_path, output_path, *paths, native_path, *historical_paths.values()]
    initial_evidence = _evidence(*evidence_paths)
    measured: dict[str, Any] = {}
    bridge_checks = []
    for token, catalog in catalogs.items():
        module, expected = modules[token], selected[token]
        if expected.get("ModuleHierarchyPath") != module["HierarchyPath"]:
            raise ValueError(f"support endpoint module hierarchy mismatch: {token}")
        historical = _read(historical_paths[token])

        def face_matches(row: dict[str, Any]) -> bool:
            ep = row["Endpoint"]
            return (row.get("GeometryClass") == "Plane" and ep.get("SurfaceType") == "Plane"
                    and ep.get("GeometryType") == "Face"
                    and _same_path(str(row.get("ModulePath", "")), module["Path"])
                    and ep.get("ModuleHierarchyPath") == module["HierarchyPath"]
                    and ep.get("RelativeLeafHierarchyPath") == expected["RelativeLeafHierarchyPath"]
                    and ep.get("LeafHierarchyPath") == expected["LeafHierarchyPath"]
                    and _same_path(str(ep.get("LeafComponentPath", "")), expected["LeafComponentPath"])
                    and type(ep.get("BodyIndex")) is int and ep["BodyIndex"] == expected["BodyIndex"]
                    and type(ep.get("FaceIndexInBody")) is int and ep["FaceIndexInBody"] >= 0
                    and close(ep.get("FaceBoxLocal"), expected["FaceBoxLocal"], 6)
                    and close(ep.get("FaceCenterLocal"), expected["FaceCenterLocal"])
                    and close(ep.get("FaceNormalLocal"), expected["FaceNormalLocal"])
                    and close([ep.get("FaceArea")], [expected["FaceArea"]], 1))

        old_rows = [row for row in historical["Endpoints"] if face_matches(row)]
        if len(old_rows) != 1:
            raise ValueError(f"historical support fingerprint does not resolve uniquely: {token}")
        old = old_rows[0]
        module_config, leaf_config = old.get("ModuleReferencedConfiguration"), old.get("LeafReferencedConfiguration")
        if not module_config or not leaf_config or observed[token]["configuration"] != module_config:
            raise ValueError(f"support configuration identity mismatch: {token}")
        if (catalog.get("SchemaVersion") != "solidworks-face-endpoint-catalog/v1"
                or not _same_path(str(catalog.get("SourceAssemblyPath", "")), str(output_path))
                or len(catalog.get("Modules", [])) != 1):
            raise ValueError(f"fresh catalog does not bind the saved CAD context: {token}")
        live_module = _module(catalog, token)
        if (live_module.get("ModuleToken") != token or live_module.get("Name") != module["Name"]
                or live_module.get("HierarchyPath") != module["HierarchyPath"]
                or not _same_path(live_module.get("Path", ""), module["Path"])
                or live_module.get("ReferencedConfiguration") != module_config
                or not close(_transform(live_module.get("SourceTransform")), poses[token], 16)):
            raise ValueError(f"fresh catalog module identity/root pose mismatch: {token}")
        rows = [row for row in catalog["Endpoints"] if face_matches(row)
                and row.get("ModuleReferencedConfiguration") == module_config
                and row.get("LeafReferencedConfiguration") == leaf_config
                and row["Endpoint"].get("ModuleToken") == token]
        if len(rows) != 1:
            raise ValueError(f"fresh support fingerprint/configuration does not resolve uniquely: {token}")
        row, fresh = rows[0], rows[0]["Endpoint"]
        reference = fresh.get("SourceAssemblyPersistentReferenceBase64")
        if not isinstance(reference, str) or not reference:
            raise ValueError(f"fresh support endpoint lacks its current-context persistent reference: {token}")
        center, normal = _vector(fresh["FaceCenterWorld"]), _vector(fresh["FaceNormalWorld"])
        if abs(_dot(normal, normal) - 1) > 1e-8:
            raise ValueError(f"fresh support normal is not unit length: {token}")
        old_modules = [item for item in historical["Modules"]
                       if _same_path(item["Path"], module["Path"]) and item["HierarchyPath"] == module["HierarchyPath"]]
        if len(old_modules) != 1:
            raise ValueError(f"historical support module identity mismatch: {token}")
        old_pose = _transform(old_modules[0]["SourceTransform"])
        if token == "GN00" and not close(old_pose, native_pose, 16):
            raise ValueError("historical GN00 support and native graph root poses differ")
        # These old world fields are the original graph's bridge inputs. Only
        # the fresh fields above measure the current saved assembly context.
        bridged_center = _point(_point(_vector(expected["FaceCenterWorld"]), old_pose, inverse=True), poses[token])
        bridged_normal = _direction(_direction(_vector(expected["FaceNormalWorld"]), old_pose, inverse=True), poses[token])
        center_error = math.dist(center, bridged_center)
        normal_error = math.dist(normal, bridged_normal)
        bridge_checks.append(center_error <= 1e-8 and normal_error <= 1e-8)
        measured[token] = {
            "modulePath": module["Path"], "moduleConfiguration": module_config, "leafConfiguration": leaf_config,
            "leafPath": fresh["LeafComponentPath"], "relativeLeafHierarchyPath": fresh["RelativeLeafHierarchyPath"],
            "bodyIndex": fresh["BodyIndex"], "graphFaceIndexInBody": expected["FaceIndexInBody"],
            "freshFaceIndexInBody": fresh["FaceIndexInBody"],
            "faceIndexChanged": fresh["FaceIndexInBody"] != expected["FaceIndexInBody"],
            "freshEndpointId": row["EndpointId"], "freshPersistentReferenceSha256": hashlib.sha256(reference.encode()).hexdigest(),
            "graphPersistentReferenceBase64": expected.get("SourceAssemblyPersistentReferenceBase64"),
            "freshPersistentReferenceBase64": reference,
            "faceCenterWorld": center, "faceNormalWorld": normal, "faceBoxLocal": fresh["FaceBoxLocal"],
            "bridgePredictedCenterWorld": bridged_center, "bridgePredictedNormalWorld": bridged_normal,
            "bridgeCenterErrorMeters": center_error, "bridgeNormalError": normal_error,
            "selectionMethod": "unique_leaf_configuration_body_and_local_face_fingerprint_not_cross_context_reference",
        }
    moving, base = measured["GN00"], measured["AA00"]
    gap = abs(_dot([moving["faceCenterWorld"][i] - base["faceCenterWorld"][i] for i in range(3)], base["faceNormalWorld"]))
    normal_dot = _dot(moving["faceNormalWorld"], base["faceNormalWorld"])
    bridge_gap = abs(_dot([moving["bridgePredictedCenterWorld"][i] - base["bridgePredictedCenterWorld"][i] for i in range(3)],
                         base["bridgePredictedNormalWorld"]))
    bridge_dot = _dot(moving["bridgePredictedNormalWorld"], base["bridgePredictedNormalWorld"])
    bridge_passed = all(bridge_checks) and abs(gap - bridge_gap) <= 1e-8 and abs(normal_dot - bridge_dot) <= 1e-8
    plane_passed = gap <= 1e-8 and abs(normal_dot - (-1 if mate["Alignment"] == 1 else 1)) <= 1e-8
    if initial_evidence != _evidence(*evidence_paths):
        raise ValueError("support evidence changed during readonly measurement")
    return {
        "schemaVersion": "gn00-live-support-audit/v1", "caseId": "B8-GN00-AA00",
        "measurementKind": "readonly_reopen_of_existing_saved_cad", "readOnly": True,
        "newCadInsertionPerformed": False, "cadLaunchAllowed": False, "bindingVerified": True,
        "cadResultSha256": _sha256(cad_path), "effectiveGraphSha256": _sha256(graph_path),
        "outputAssemblyPath": str(output_path), "outputAssemblySha256": cad["outputAssemblySha256"],
        "statePath": str(state_path), "stateSha256": _sha256(state_path), "evidence": initial_evidence,
        "endpoints": measured, "planeResidualMeters": gap, "normalDot": normal_dot,
        "historicalBridgePlaneResidualMeters": bridge_gap, "historicalBridgeNormalDot": bridge_dot,
        "planeAndDirectionPassed": plane_passed, "historicalBridgeConsistencyPassed": bridge_passed,
        "supportGeometryMeasurementPassed": plane_passed and bridge_passed, "toleranceMeters": 1e-8,
        "slotMembership": None, "transportContext": None, "stationReady": False, "stationValidationPassed": False,
        "claimBoundary": "Fresh face-box centers/normals from an existing saved pair CAD only; not new insertion, trimmed contact/finite support approval, native role membership, transport context or execution authority.",
    }


def build_n000_a600_station_witness(workspace: Path) -> dict[str, Any]:
    root = workspace.resolve()
    try:
        audit = build_project02_a700_role_station_audit(root)
    except FileNotFoundError as error:
        return {"schemaVersion": SCHEMA, "caseId": "A5-N000-A600-A700-role-station", "source": "project05::N000", "target": "project02::A600",
                "nativeRole": "project02::A700", "cadResultSha256": None, "effectiveGraphSha256": None,
                "checks": {name: _check(None, "geometry_evidence_missing", [], missingEvidence=str(error)) for name in CHECK_NAMES},
                "stationValidationPassed": False, "cadLaunchAllowed": False, "reviewOnly": True,
                "status": "blocked_before_cad_missing_geometry_evidence"}
    catalog_path = root / "demo/cross_project_substitution/parameterized-datum-placement-v1/interface-contract-catalog.json"
    sources = _evidence(*(Path(path) for path in audit["evidencePaths"]), catalog_path)
    observations = {
        "nativeRoleEnvelopeInstallationMeters": audit["nativeRoleStationBoundsMeters"],
        "replacementEnvelopeFitsRoleStation": audit["replacementEnvelopeFitsRoleStation"],
        "allowedReplacementDatumIntervalMeters": audit["allowedReplacementDatumIntervalMeters"],
        "nativeStationOverlapsTransportSupportAabb": audit["nativeStationOverlapsTransportSupportAabb"],
        "actualReplacementPoseAvailable": False, "nativeEndpointBundleAvailable": False,
    }
    return {"schemaVersion": SCHEMA, "caseId": "A5-N000-A600-A700-role-station", "source": "project05::N000", "target": "project02::A600",
            "nativeRole": "project02::A700", "cadResultSha256": None, "effectiveGraphSha256": None,
            "checks": {name: _check(None, "native_role_envelope_only_missing_endpoint_bundle_and_candidate_pose", sources, **observations) for name in CHECK_NAMES},
            "stationValidationPassed": False, "cadLaunchAllowed": False, "reviewOnly": True,
            "status": audit["status"], "blockers": audit["blockers"], "forbiddenFallback": audit["forbiddenFallback"],
            "nativeAuditDigest": audit["auditDigest"], "claimBoundary": audit["claimBoundary"]}
