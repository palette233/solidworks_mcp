"""Synthetic geometry and existing captured files only; no CAD is launched."""
import copy
import hashlib
import json
import math
from pathlib import Path

import pytest

from demo_backend.cup_function_point import (
    extract_cup_mouth_points, compare_cup_mouth_to_native_stations,
    build_cup_function_point_report, suggest_cup_aligned_planar_station, verify_saved_cup_projection,
    screen_mapped_cup_planar_translation, build_published_cup_station_screening,
)


def test_real_a300_a000_published_pose_is_screened_without_cad():
    request = ROOT / "data/assembly_stations/a300-a000-cup-functional-request-v1.json"
    cad = ROOT / (
        "demo/cross_project_substitution/parameterized-datum-placement-v1/"
        "validation-queue-20261026-v46/validation-a300-a000-v1/cad-result.json"
    )
    report = build_published_cup_station_screening(request, cad)
    assert report["cadExecuted"] is False
    assert report["screening"]["passed"] is False
    assert report["screening"]["status"] == (
        "published_orientation_cannot_reach_target_by_translation"
    )
    assert report["screening"]["maximumPlanarMappingResidualMeters"] > .02

ROOT = Path(__file__).resolve().parents[3]
IDENTITY = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]


@pytest.fixture
def catalog():
    rows = []
    common = {"ModuleToken": "P000", "RelativeLeafHierarchyPath": "cup-1", "BodyIndex": 0}
    for index, radius, bottom in ((1, .034, .0735), (2, .0345, .073)):
        endpoint = {**common, "SurfaceType": "Cylinder", "FaceArea": 2*math.pi*radius*(.075-bottom),
                    "FaceBoxLocal": [-radius, -radius, bottom, radius, radius, .075],
                    "CylinderAxisLocal": [0, 0, 1], "CylinderOriginLocal": [0, 0, .075],
                    "CylinderAxisWorld": [0, 0, 1], "CylinderOriginWorld": [0, 0, .075],
                    "CylinderRadius": radius, "SourceAssemblyPersistentReferenceBase64": f"cyl-{index}"}
        rows.append({"EndpointId": f"cylinder-{index}", "Endpoint": endpoint})
    rows.append({"EndpointId": "rim", "Endpoint": {
        **common, "SurfaceType": "Plane", "FaceArea": math.pi*(.0345**2-.034**2),
        "FaceBoxLocal": [-.0345, -.0345, .075, .0345, .0345, .075],
        "FaceCenterLocal": [0, 0, .075], "FaceCenterWorld": [0, 0, .075],
        "FaceNormalLocal": [0, 0, -1], "FaceNormalWorld": [0, 0, -1],
        "SourceAssemblyPersistentReferenceBase64": "rim-ref"}})
    return {"SourceAssemblyPath": "captured.SLDASM", "Modules": [{
        "ModuleToken": "P000", "Path": "p000.SLDASM", "SourceTransform": IDENTITY.copy(),
        "SolvingState": 0, "IsSuppressed": False}], "Endpoints": rows}


def extract(catalog, up=None):
    return extract_cup_mouth_points(catalog, module_definition_id="project05::P000",
                                   opening_direction_world=up or [0, 0, 1])


def test_analytic_rim_recovers_center_opening_radius_and_direction(catalog):
    report = extract(catalog)
    assert len(report["points"]) == 1
    point = report["points"][0]
    assert point["centerModuleLocalMeters"] == pytest.approx([0, 0, .075])
    assert point["openingRadiusMeters"] == .034
    assert point["openingNormalModuleLocal"] == [0, 0, 1]
    assert point["rimEndpointId"] == "rim"
    assert report["cadLaunchAllowed"] is False
    assert report["newCadExecuted"] is False
    assert report["collisionOrBrep"] == "not_evaluated"


@pytest.mark.parametrize("failure", ["partial_cylinder", "noncoaxial", "wrong_area", "wrong_rim_box",
                                     "missing_reference", "cross_leaf", "cross_body", "missing_cylinder", "module_bbox_only"])
def test_insufficient_or_wrong_geometry_never_becomes_a_mouth(catalog, failure):
    if failure == "partial_cylinder":
        catalog["Endpoints"][0]["Endpoint"]["FaceArea"] /= 2
    elif failure == "noncoaxial":
        catalog["Endpoints"][0]["Endpoint"]["CylinderOriginLocal"][0] = .01
    elif failure == "wrong_area":
        catalog["Endpoints"][2]["Endpoint"]["FaceArea"] = .1
    elif failure == "wrong_rim_box":
        catalog["Endpoints"][2]["Endpoint"]["FaceBoxLocal"][0] += .001
    elif failure == "missing_reference":
        catalog["Endpoints"][2]["Endpoint"].pop("SourceAssemblyPersistentReferenceBase64")
    elif failure == "cross_leaf":
        catalog["Endpoints"][0]["Endpoint"]["RelativeLeafHierarchyPath"] = "other"
    elif failure == "cross_body":
        catalog["Endpoints"][0]["Endpoint"]["BodyIndex"] = 1
    elif failure == "missing_cylinder":
        catalog["Endpoints"].pop(0)
    else:
        catalog["Endpoints"] = []
        catalog["Modules"][0]["BoundingBox"] = [-1, -1, -1, 1, 1, 1]
    result = extract(catalog)
    assert result["points"] == []
    assert result["status"] == "cup_geometry_missing"


def test_wrong_opening_direction_does_not_select_bottom_or_side(catalog):
    assert extract(catalog, [0, 0, -1])["points"] == []
    assert extract(catalog, [0, 1, 0])["points"] == []


def test_ambiguous_rim_is_rejected_instead_of_ranked(catalog):
    duplicate = copy.deepcopy(catalog["Endpoints"][-1])
    duplicate["EndpointId"] = "second-rim"
    duplicate["Endpoint"]["SourceAssemblyPersistentReferenceBase64"] = "second-rim-ref"
    catalog["Endpoints"].append(duplicate)
    with pytest.raises(ValueError, match="Ambiguous"):
        extract(catalog)


def test_module_pose_only_converts_measurement_not_execution(catalog):
    catalog["Modules"][0]["SourceTransform"][9] = .4
    for row in catalog["Endpoints"]:
        e = row["Endpoint"]
        if e["SurfaceType"] == "Cylinder":
            e["CylinderOriginWorld"][0] += .4
        else:
            e["FaceCenterWorld"][0] += .4
    p = extract(catalog)["points"][0]
    assert p["centerModuleLocalMeters"] == pytest.approx([0, 0, .075])
    assert p["centerSourceAssemblyWorldMeters"] == pytest.approx([.4, 0, .075])


@pytest.fixture
def comparison(catalog):
    source = extract(catalog)["points"]
    native = copy.deepcopy(source)
    native[0]["pointId"] = "native-cup-1"
    return {"source_points": source, "native_points": native,
            "mapping": {source[0]["pointId"]: "native-cup-1"},
            "observed_source_transform": IDENTITY.copy(), "observed_base_transform": IDENTITY.copy(),
            "native_base_transform": IDENTITY.copy(), "plane_tolerance_meters": .001,
            "angular_tolerance_degrees": 1, "radial_margin_meters": .002}


def test_matching_real_functional_point_passes_geometry_not_process(comparison):
    result = compare_cup_mouth_to_native_stations(**comparison)
    assert result["functionalPointGeometryPassed"] is True
    assert result["actualDischargeValidated"] is False
    assert result["nativeStationAuthorityVerified"] is False
    assert result["cadLaunchAllowed"] is False


@pytest.mark.parametrize("failure", ["off_center", "wrong_height", "upside_down"])
def test_wrong_cup_position_or_orientation_fails(comparison, failure):
    if failure == "off_center":
        comparison["observed_source_transform"][9] = .1
    elif failure == "wrong_height":
        comparison["observed_source_transform"][11] = .01
    else:
        comparison["observed_source_transform"][4] = -1
        comparison["observed_source_transform"][8] = -1
    assert compare_cup_mouth_to_native_stations(**comparison)["functionalPointGeometryPassed"] is False


@pytest.mark.parametrize("failure", ["unmapped", "wrong_id", "flexible", "nan", "large_margin"])
def test_invalid_matching_evidence_rejected(comparison, failure):
    if failure == "unmapped":
        comparison["mapping"] = {}
    elif failure == "wrong_id":
        comparison["mapping"][comparison["source_points"][0]["pointId"]] = "wrong-cup"
    elif failure == "flexible":
        comparison["source_points"][0]["internalGeometryRigid"] = False
    elif failure == "nan":
        comparison["observed_source_transform"][9] = float("nan")
    else:
        comparison["radial_margin_meters"] = .1
    with pytest.raises(ValueError):
        compare_cup_mouth_to_native_stations(**comparison)


def test_file_report_binds_geometry_evidence_by_digest(catalog, tmp_path):
    path = tmp_path/"catalog.json"
    path.write_text(json.dumps(catalog), encoding="utf-8")
    spec = {"moduleDefinitionId": "project05::P000", "catalogPaths": [path.name], "openingDirectionWorld": [0, 0, 1]}
    request = tmp_path/"request.json"
    request.write_text(json.dumps({"source": spec, "native": spec}), encoding="utf-8")
    result = build_cup_function_point_report(request)
    assert result["allRequestedCatalogsHaveMouthEvidence"] is True
    assert result["evidence"][1]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert result["durationSeconds"] >= 0
    spec["catalogPaths"].append(path.name)
    request.write_text(json.dumps({"source": spec, "native": spec}), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate"):
        build_cup_function_point_report(request)


def test_real_captured_p000_cup_rim_if_available():
    path = ROOT/"demo/role_station_strengthening_20261028/functional-chain-v1/geometry/p000-cup-1.json"
    if not path.exists():
        pytest.skip("Live-captured evidence is not checked into source")
    result = extract(json.loads(path.read_text(encoding="utf-8-sig")), [0, 1, 0])
    p = result["points"][0]
    assert p["centerLeafLocalMeters"] == pytest.approx([0, .075, 0])
    assert p["centerModuleLocalMeters"] == pytest.approx([-.065, 0, .075])
    assert p["openingRadiusMeters"] == .034
    assert p["rimEndpointId"] == "face:p000:8a9e8d62a0cd7b1d"


@pytest.fixture
def station(catalog):
    points = extract(catalog)["points"]
    native = copy.deepcopy(points)
    native[0]["pointId"] = "native-cup"
    graph = {"Mates": []}
    for name, axis, kind, distance in (("long", [1, 0, 0], 5, .1),
                                        ("lat", [0, 1, 0], 5, .2), ("support", [0, 0, 1], 0, None)):
        graph["Mates"].append({"MateName": name, "MateType": kind, "Distance": distance,
            "AdvancedOptions": {"DistanceFlipDimension": False},
            "Endpoints": [{"ModuleToken": token, "FaceCenterWorld": [0, 0, 0],
                           "FaceNormalWorld": axis, "SourceAssemblyPersistentReferenceBase64": token+name}
                          for token in ("P000", "AA00")]})
    pose = IDENTITY.copy()
    pose[9:12] = [.1, .2, 0]
    target = IDENTITY.copy()
    target[9:12] = [.3, .4, .045]
    return {"source_points": points, "native_points": native,
            "mapping": {points[0]["pointId"]: "native-cup"}, "graph": graph,
            "source_token": "P000", "base_token": "AA00",
            "source_datum_capture_transform": IDENTITY.copy(),
            "observed_source_transform": pose, "observed_base_transform": IDENTITY.copy(),
            "graph_base_capture_transform": IDENTITY.copy(), "native_module_transform": target,
            "native_base_transform": IDENTITY.copy(),
            "parameter_mate_names": {"longitudinal": "long", "lateral": "lat"}}


def test_station_suggestion_updates_distances_but_not_support_height(station):
    report = suggest_cup_aligned_planar_station(**station)
    assert report["positionParametersMeters"] == pytest.approx({"longitudinal": .3, "lateral": .4, "supportGap": 0})
    assert report["threeDimensionalCentersCoincident"] is False
    assert report["functionPointMeasurements"][0]["normalHeightMismatchMeters"] == pytest.approx(.045)
    assert report["sourcePrototypePoseUsedForPlacement"] is False
    assert report["derivedTransformUsedForExecution"] is False
    assert report["cadLaunchAllowed"] is False


def test_station_distance_sign_changes_are_explicit(station):
    station["native_module_transform"][9] = -.3
    result = suggest_cup_aligned_planar_station(**station)
    first = result["mateParameters"][0]
    assert first["suggestedDistanceMeters"] == pytest.approx(.3)
    assert first["suggestedSignedMeters"] == pytest.approx(-.3)
    assert first["suggestedDistanceFlipDimension"] is True


def test_unequal_spacing_can_use_explicit_inside_opening_policy(station):
    for name in ("source_points", "native_points"):
        point = copy.deepcopy(station[name][0])
        point["pointId"] += "-2"
        point["centerModuleLocalMeters"][0] += .13 if name == "source_points" else .09
        station[name].append(point)
    station["mapping"][station["source_points"][1]["pointId"]] = station["native_points"][1]["pointId"]
    station["alignment_policy"] = {
        "mode": "native_points_inside_source_openings",
        "radialMarginMeters": .005,
    }
    result = suggest_cup_aligned_planar_station(**station)
    assert result["maximumPlanarMappingResidualMeters"] == pytest.approx(.02)
    assert result["functionalProjectionCandidatePassed"] is True
    assert all(row["nativePointInsideSourceOpeningAfterTranslation"]
               for row in result["projectionResidualChecks"])


def test_inside_opening_policy_rejects_spacing_beyond_usable_radius(station):
    for name in ("source_points", "native_points"):
        point = copy.deepcopy(station[name][0])
        point["pointId"] += "-2"
        point["centerModuleLocalMeters"][0] += .13 if name == "source_points" else .01
        station[name].append(point)
    station["mapping"][station["source_points"][1]["pointId"]] = station["native_points"][1]["pointId"]
    station["alignment_policy"] = {
        "mode": "native_points_inside_source_openings",
        "radialMarginMeters": .005,
    }
    with pytest.raises(ValueError, match="cannot fit inside"):
        suggest_cup_aligned_planar_station(**station)


@pytest.mark.parametrize("failure", ["wrong_recipe_pose", "lifted_support", "missing_direction", "flexible_source", "missing_reference", "unequal_spacing"])
def test_bad_station_suggestion_is_rejected(station, failure):
    if failure == "wrong_recipe_pose":
        station["observed_source_transform"][9] += .01
    elif failure == "lifted_support":
        station["observed_source_transform"][11] += .01
    elif failure == "missing_direction":
        station["graph"]["Mates"][0]["AdvancedOptions"] = {}
    elif failure == "flexible_source":
        station["source_points"][0]["internalGeometryRigid"] = False
    elif failure == "missing_reference":
        station["graph"]["Mates"][0]["Endpoints"][0].pop("SourceAssemblyPersistentReferenceBase64")
    else:
        for name in ("source_points", "native_points"):
            point = copy.deepcopy(station[name][0])
            point["pointId"] += "-2"
            point["centerModuleLocalMeters"][0] += .1 if name == "source_points" else .2
            station[name].append(point)
        station["mapping"][station["source_points"][1]["pointId"]] = station["native_points"][1]["pointId"]
    with pytest.raises(ValueError):
        suggest_cup_aligned_planar_station(**station)


@pytest.fixture
def saved_cup(tmp_path, catalog, station):
    def write(name, value):
        path = tmp_path/name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path
    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()
    captured = tmp_path/"capture.SLDASM"
    captured.write_bytes(b"captured-assembly")
    paths = {}
    for role, token, pose in (("source", "P000", station["observed_source_transform"]),
                              ("native", "AG00", station["native_module_transform"])):
        copycat = copy.deepcopy(catalog)
        copycat["SourceAssemblyPath"] = str(captured)
        copycat["Modules"][0].update(ModuleToken=token, Path=str(tmp_path/f"{token}.SLDASM"), SourceTransform=pose)
        for row in copycat["Endpoints"]:
            e = row["Endpoint"]
            e["ModuleToken"] = token
            for field in ("FaceCenterWorld", "CylinderOriginWorld"):
                if field in e:
                    e[field] = [e[field][i]+pose[9+i] for i in range(3)]
        paths[role] = write(f"{role}.json", copycat)
    base = {"ModuleToken": "AA00", "Path": str(tmp_path/"AA00.SLDASM"), "SourceTransform": IDENTITY.copy()}
    native_module = {"ModuleToken": "AG00", "Path": str(tmp_path/"AG00.SLDASM"), "SourceTransform": station["native_module_transform"]}
    graph = copy.deepcopy(station["graph"])
    graph["Modules"] = [base]
    graph_path = write("recipe.json", graph)
    native_path = write("native-graph.json", {"Modules": [base, native_module], "SourceAssemblyPath": "native.SLDASM"})
    capture_path = write("datum-capture.json", {"Modules": [{"ModuleToken": "P000", "SourceTransform": IDENTITY.copy()}]})
    components = [{"sourcePath": base["Path"], "isFixed": True, "transform": IDENTITY.copy()},
                  {"sourcePath": str(tmp_path/"P000.SLDASM"), "isFixed": False, "transform": station["observed_source_transform"]},
                  {"sourcePath": native_module["Path"], "isFixed": False, "transform": native_module["SourceTransform"]}]
    measured_state = write("capture-state.json", {"success": True, "checks": {"bound": True},
        "assemblyPath": str(captured), "assemblySha256": digest(captured), "observed": {"components": components}})
    request = {role: {"moduleDefinitionId": "project05::P000" if role == "source" else "project03::AG00",
                     "catalogPaths": [str(paths[role])], "openingDirectionWorld": [0, 0, 1]} for role in paths}
    request["stationSuggestion"] = {"existingMateGraphPath": str(graph_path), "sourceDatumCapturePath": str(capture_path),
        "nativeGraphPath": str(native_path), "observedStatePath": str(measured_state), "sourceToken": "P000", "baseToken": "AA00",
        "sourceDatumModuleToken": "P000", "nativeGraphModuleToken": "AG00", "nativeGraphBaseToken": "AA00",
        "mappingByLeaf": {"cup-1": "cup-1"}, "parameterMateNames": station["parameter_mate_names"]}
    request_path = write("request.json", request)
    report = build_cup_function_point_report(request_path)
    report_path = write("geometry-report.json", report)
    output = tmp_path/"result.SLDASM"
    output.write_bytes(b"new-saved-cad")
    result_pose = IDENTITY.copy()
    result_pose[9:12] = [.3, .4, 0]
    for m in graph["Mates"]:
        if m["MateName"] == "long": m["Distance"] = .3
        if m["MateName"] == "lat": m["Distance"] = .4
    executed_graph_path = write("executed-graph.json", graph)
    cad = {"success": True, "outputAssemblyPath": str(output), "outputAssemblySha256": digest(output),
           "executionEffectiveGraphPath": str(executed_graph_path), "executionEffectiveGraphSha256": digest(executed_graph_path),
           "toolResult": {**{k: True for k in ("Success", "Reopened", "ReopenedMateParametersMatch", "MateSolveClean", "TargetFullyConstrained")},
                          "TargetModuleToken": "P000", "ReopenedTargetRootTransform": result_pose}}
    final_components = copy.deepcopy(components[:2])
    final_components[1]["transform"] = result_pose
    state = {"success": True, "checks": {"bound": True}, "assemblyPath": str(output), "assemblySha256": digest(output),
             "observed": {"readOnly": True, "components": final_components}}
    return {"geometry_report_path": report_path, "cad_result_path": write("cad.json", cad),
            "saved_state_path": write("state.json", state)}, write


@pytest.mark.parametrize("failure", [None, "hash", "pose", "assembly", "readonly", "identity"])
def test_native_cup_capture_can_use_its_own_verified_coordinate_frame(saved_cup, failure):
    args, write = saved_cup
    original = json.loads(args["geometry_report_path"].read_text())
    request_path = Path(original["requestPath"])
    request = json.loads(request_path.read_text())
    spec = request["stationSuggestion"]
    state = json.loads(Path(spec["observedStatePath"]).read_text())
    state["observed"]["readOnly"] = True
    write("capture-state.json", state)
    native_state = copy.deepcopy(state)
    native_file = request_path.parent / "native-capture.SLDASM"
    native_file.write_bytes(b"separate-native-capture")
    native_state.update(assemblyPath=str(native_file), assemblySha256=hashlib.sha256(native_file.read_bytes()).hexdigest())
    native_catalog = json.loads(Path(request["native"]["catalogPaths"][0]).read_text())
    native_catalog["SourceAssemblyPath"] = str(native_file)
    native_path = native_catalog["Modules"][0]["Path"]
    native_catalog["Modules"][0]["SourceTransform"][9] += 5
    for row in native_catalog["Endpoints"]:
        for field in ("FaceCenterWorld", "CylinderOriginWorld"):
            if field in row["Endpoint"]:
                row["Endpoint"][field][0] += 5
    native_component = next(c for c in native_state["observed"]["components"] if c["sourcePath"] == native_path)
    native_component["transform"][9] += 5
    native_state["observed"]["components"] = [native_component]
    state["observed"]["components"] = [c for c in state["observed"]["components"] if c["sourcePath"] != native_path]
    write("capture-state.json", state)
    if failure == "hash": native_state["assemblySha256"] = "incorrect"
    if failure == "pose": native_component["transform"][9] += .1
    if failure == "assembly": native_catalog["SourceAssemblyPath"] = state["assemblyPath"]
    if failure == "readonly": native_state["observed"]["readOnly"] = False
    if failure == "identity":
        native_graph = json.loads(Path(spec["nativeGraphPath"]).read_text())
        native_graph["Modules"][1]["Path"] = str(request_path.parent / "other.SLDASM")
        write("native-graph.json", native_graph)
    spec["nativeObservedStatePath"] = str(write("native-state.json", native_state))
    write("native.json", native_catalog)
    write("request.json", request)
    if failure:
        with pytest.raises(ValueError):
            build_cup_function_point_report(request_path)
    else:
        result = build_cup_function_point_report(request_path)
        assert result["stationSuggestion"]["positionParametersMeters"] == pytest.approx(
            original["stationSuggestion"]["positionParametersMeters"])
        assert result["newCadExecuted"] is False
        assert any(e["path"] == str(native_file) for e in result["evidence"])


def test_source_local_geometry_can_be_reused_from_explicit_independent_capture(saved_cup):
    inputs, write = saved_cup
    original = json.loads(inputs["geometry_report_path"].read_text())
    request_path = Path(original["requestPath"])
    request = json.loads(request_path.read_text())
    spec = request["stationSuggestion"]
    capture = json.loads(Path(spec["observedStatePath"]).read_text())
    capture["observed"]["readOnly"] = True
    capture_witness = write("source-geometry-capture.json", capture)
    station_file = request_path.parent / "different-station.SLDASM"
    station_file.write_bytes(b"different-station")
    station = copy.deepcopy(capture)
    station.update(assemblyPath=str(station_file),
                   assemblySha256=hashlib.sha256(station_file.read_bytes()).hexdigest())
    # The station assembly differs from the geometry-capture assembly; rigid
    # module-local cup points are reused while the station pose still has to
    # satisfy its own bound datum recipe below.
    station_state = write("different-station-state.json", station)
    request["captureWitnesses"] = {"source": str(capture_witness)}
    spec["independentGeometryCaptureRoles"] = ["source"]
    spec["observedStatePath"] = str(station_state)
    spec["nativeObservedStatePath"] = str(capture_witness)
    write("request.json", request)
    report = build_cup_function_point_report(request_path)
    assert report["stationSuggestion"]["targetNativeCalibrationIdentity"][
        "independentGeometryCaptureRoles"] == ["source"]


def test_independent_capture_cannot_be_enabled_without_witness(saved_cup):
    inputs, write = saved_cup
    original = json.loads(inputs["geometry_report_path"].read_text())
    request_path = Path(original["requestPath"])
    request = json.loads(request_path.read_text())
    request["stationSuggestion"]["independentGeometryCaptureRoles"] = ["source"]
    write("request.json", request)
    with pytest.raises(ValueError, match="explicit capture witness"):
        build_cup_function_point_report(request_path)


def test_saved_cad_recheck_separates_planar_pass_from_height_failure(saved_cup):
    inputs, _ = saved_cup
    result = verify_saved_cup_projection(**inputs)
    assert result["targetCupProjectionPassed"] is True
    assert result["threeDimensionalCupMouthAlignmentPassed"] is False
    assert result["comparison"]["measurements"][0]["planeErrorMeters"] == pytest.approx(.045)
    assert result["readOnlyStateSha256"]
    assert result["newCadExecutedByThisVerifier"] is False


@pytest.mark.parametrize("failure", [None, "hash", "pose", "readonly", "duplicate"])
def test_geometry_only_report_binds_capture_witness_without_assembly_acceptance(saved_cup, failure):
    inputs, write = saved_cup
    original = json.loads(inputs["geometry_report_path"].read_text())
    request_path = Path(original["requestPath"])
    request = json.loads(request_path.read_text())
    spec = request.pop("stationSuggestion")
    state = json.loads(Path(spec["observedStatePath"]).read_text())
    state["observed"]["readOnly"] = True
    catalog = json.loads(Path(request["source"]["catalogPaths"][0]).read_text())
    component = next(c for c in state["observed"]["components"] if c["sourcePath"] == catalog["Modules"][0]["Path"])
    if failure == "hash": state["assemblySha256"] = "wrong"
    if failure == "pose": component["transform"][9] += .1
    if failure == "readonly": state["observed"]["readOnly"] = False
    if failure == "duplicate": state["observed"]["components"].append(copy.deepcopy(component))
    request["captureWitnesses"] = {"source": str(write("only-capture.json", state))}
    write("request.json", request)
    if failure:
        with pytest.raises(ValueError): build_cup_function_point_report(request_path)
    else:
        result = build_cup_function_point_report(request_path)
        assert result["stationSuggestion"] is None and not result["newCadExecuted"]
        assert any(row["path"] == state["assemblyPath"] for row in result["evidence"])


def test_generic_recipe_mate_names_require_explicit_parameter_binding(saved_cup):
    inputs, write = saved_cup
    cad = json.loads(inputs["cad_result_path"].read_text())
    path = Path(cad["executionEffectiveGraphPath"])
    graph = json.loads(path.read_text())
    names = {"long": "GENERATED_LONGITUDINAL", "lat": "GENERATED_LATERAL"}
    for mate in graph["Mates"]:
        mate["MateName"] = names.get(mate["MateName"], mate["MateName"])
    write(path.name, graph)
    cad["executionEffectiveGraphSha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    write("cad.json", cad)
    with pytest.raises(ValueError, match="Executed distance"):
        verify_saved_cup_projection(**inputs)
    report = json.loads(inputs["geometry_report_path"].read_text())
    result = verify_saved_cup_projection(geometry_report=report,
        cad_result_path=inputs["cad_result_path"], saved_state_path=inputs["saved_state_path"],
        parameter_mate_names={"longitudinal": names["long"], "lateral": names["lat"]})
    assert result["targetCupProjectionPassed"]
    with pytest.raises(ValueError, match="Executed distance"):
        verify_saved_cup_projection(**inputs, parameter_mate_names={"longitudinal": names["lat"], "lateral": names["long"]})


@pytest.mark.parametrize("failure", ["output_changed", "state_pose", "fixed_source", "cad_failed", "graph_changed", "report_geometry", "source_changed"])
def test_tampered_or_failed_saved_cad_evidence_rejected(saved_cup, failure):
    inputs, write = saved_cup
    cad = json.loads(inputs["cad_result_path"].read_text())
    state = json.loads(inputs["saved_state_path"].read_text())
    report = json.loads(inputs["geometry_report_path"].read_text())
    if failure == "output_changed":
        Path(cad["outputAssemblyPath"]).write_bytes(b"changed")
    elif failure == "state_pose":
        state["observed"]["components"][1]["transform"][9] += .1
    elif failure == "fixed_source":
        state["observed"]["components"][1]["isFixed"] = True
    elif failure == "cad_failed":
        cad["toolResult"]["Success"] = False
    elif failure == "graph_changed":
        Path(cad["executionEffectiveGraphPath"]).write_text('{}')
    elif failure == "report_geometry":
        report["geometry"]["source"][0]["points"][0]["centerModuleLocalMeters"][0] += .1
    else:
        Path(report["evidence"][1]["path"]).write_text('{}')
    write("cad.json", cad)
    write("state.json", state)
    write("geometry-report.json", report)
    with pytest.raises(ValueError):
        verify_saved_cup_projection(**inputs)
