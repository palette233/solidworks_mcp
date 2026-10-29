"""Reuse captured rigid cup geometry at an explicitly selected native station.

The native transform is measurement input only. Actual placement remains the
existing mechanical recipe, and this checker cannot grant CAD authority.
"""
import math
from pathlib import Path
from .cup_function_point import extract_cup_mouth_points, _unit, _positive
from .wastecup_target_station import _apply, _inverse, _transform, _dot
from .station_rule_registry import read, sha, workspace_file


def one(rows):
    if len(rows) != 1:
        raise ValueError("Native cup station requires an unambiguous instance")
    return rows[0]


def same_path(a, b):
    return str(Path(a).resolve()).casefold() == str(Path(b).resolve()).casefold()


def build_native_cup_station(workspace, config, state=None):
    root = Path(workspace)
    acceptance = config["acceptance"]
    _positive(acceptance["projectionToleranceMeters"], "Projection tolerance")
    if _positive(acceptance["angularToleranceDegrees"], "Angular tolerance") > 180:
        raise ValueError("Angular tolerance exceeds 180 degrees")
    if type(acceptance.get("equalMouthHeightRequired")) is not bool:
        raise ValueError("Equal-mouth-height policy must be explicit boolean")
    if config.get("sourceModuleDefinitionId") != config.get("nativeRoleModuleDefinitionId"):
        raise ValueError("Different cup models require explicit functional point correspondence")
    evidence = {}
    def load(value):
        path = workspace_file(root, value)
        evidence[str(path)] = sha(path)
        return read(path)
    inputs = config["inputs"]
    witness = load(inputs["captureState"])
    assembly = Path(witness["assemblyPath"])
    if (witness.get("success") is not True or witness.get("observed", {}).get("readOnly") is not True
            or sha(assembly) != witness.get("assemblySha256")):
        raise ValueError("Cup capture state or saved assembly changed")
    evidence[str(assembly.resolve())] = sha(assembly)
    graph = load(inputs["nativeGraph"])
    native = one([m for m in graph["Modules"] if m["ModuleToken"] == config["sourceToken"]
                  and m.get("HierarchyPath") == config["nativeInstanceHierarchyPath"]])
    base = one([m for m in graph["Modules"] if m["ModuleToken"] == config["baseToken"]
                and m.get("HierarchyPath") == config["baseInstanceHierarchyPath"]])
    nt, bt = _transform(native["SourceTransform"]), _transform(base["SourceTransform"])
    points = []
    for key in config["cupCatalogInputKeys"]:
        catalog = load(inputs[key])
        geometry = extract_cup_mouth_points(catalog, module_definition_id=config["sourceModuleDefinitionId"],
                                          opening_direction_world=config["captureOpeningDirectionWorld"])
        if not same_path(geometry["sourceAssemblyPath"], assembly) or not same_path(geometry["modulePath"], native["Path"]):
            raise ValueError("Cup capture identity differs from native station")
        observed = one([m for m in witness["observed"]["components"] if same_path(m["sourcePath"], native["Path"])])
        if max(abs(a-b) for a,b in zip(_transform(observed["transform"]), geometry["moduleSourceTransformForMeasurementOnly"], strict=True)) > 1e-8:
            raise ValueError("Cup capture and observed poses differ")
        for endpoint in catalog["Endpoints"]:
            path = endpoint["Endpoint"].get("LeafComponentPath")
            if path:
                evidence[str(Path(path).resolve())] = sha(path)
        if not geometry["points"] or any(p.get("internalGeometryRigid") is not True for p in geometry["points"]):
            raise ValueError("Rigid analytic cup-mouth geometry required")
        points.extend(geometry["points"])
    if not points or len({p["pointId"] for p in points}) != len(points):
        raise ValueError("Missing or duplicated cup mouth geometry")
    expected = []
    for point in points:
        normal_world = _apply(point["openingNormalModuleLocal"], nt, direction=True)
        normal_base = _unit([_dot(normal_world, bt[i:i+3]) for i in (0,3,6)])
        expected.append({"pointId": point["pointId"], "centerModuleLocalMeters": point["centerModuleLocalMeters"],
                         "openingNormalModuleLocal": point["openingNormalModuleLocal"],
                         "centerBaseLocalMeters": _inverse(_apply(point["centerModuleLocalMeters"], nt), bt),
                         "openingNormalBaseLocal": normal_base})
    checks = None
    passed = None
    if state is not None:
        if state.get("success") is not True or state.get("observed", {}).get("readOnly") is not True or sha(state["assemblyPath"]) != state["assemblySha256"]:
            raise ValueError("Current saved CAD state is not verified")
        components = state["observed"]["components"]
        actual = one([m for m in components if same_path(m["sourcePath"], native["Path"])])
        actual_base = one([m for m in components if same_path(m["sourcePath"], base["Path"])])
        if actual.get("isFixed") is not False or actual_base.get("isFixed") is not True or actual.get("solvingState") != 0:
            raise ValueError("Cup must be rigid and movable; only the base may be fixed")
        at, ab = _transform(actual["transform"]), _transform(actual_base["transform"])
        checks = []
        for point in expected:
            center = _inverse(_apply(point["centerModuleLocalMeters"], at), ab)
            world = _apply(point["openingNormalModuleLocal"], at, direction=True)
            normal = _unit([_dot(world, ab[i:i+3]) for i in (0,3,6)])
            delta = [a-b for a,b in zip(center, point["centerBaseLocalMeters"], strict=True)]
            up = point["openingNormalBaseLocal"]
            height = _dot(delta, up)
            error = math.sqrt(sum((delta[i]-height*up[i])**2 for i in range(3)))
            angle = math.degrees(math.acos(max(-1, min(1, _dot(normal, up)))))
            acceptance = config["acceptance"]
            good = error <= acceptance["projectionToleranceMeters"] and angle <= acceptance["angularToleranceDegrees"]
            if acceptance.get("equalMouthHeightRequired") is True:
                good = good and abs(height) <= acceptance["projectionToleranceMeters"]
            checks.append({"pointId": point["pointId"], "projectionErrorMeters": error,
                           "heightDifferenceMeters": height, "angleDegrees": angle, "passed": good})
        passed = all(c["passed"] for c in checks)
    return {"nativeInstanceHierarchyPath": native["HierarchyPath"], "expectedMouths": expected,
            "observations": checks, "proxyGeometryPassed": passed, "functionalPassed": None,
            "evidence": [{"path": p, "sha256": h} for p,h in sorted(evidence.items())],
            "sourceWorldPoseExecutionAuthorized": False, "newCadExecuted": False}
