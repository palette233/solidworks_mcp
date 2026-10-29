"""Read-only support-station measurements, including fail-closed semantics."""

import copy
import json
from pathlib import Path

import pytest

from demo_backend.wastecup_target_station import (
    build_p000_a600_target_station_audit,
    measure_support_position,
    match_native_signed_station,
    recover_leaf_measurement_transform,
)


ROOT = Path(__file__).resolve().parents[3]
IDENTITY = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]


@pytest.fixture
def measurement_inputs():
    """One static leaf with three orthogonal datum faces, independent of CAD."""
    mates = []
    for index, (suffix, distance, normal) in enumerate([
        ("DISTANCE_1", 0.08, [1, 0, 0]),
        ("DISTANCE_2", 0.39, [0, 1, 0]),
        ("SUPPORT", None, [0, 0, 1]),
    ]):
        moving = {
            "ModuleToken": "P000", "RelativeLeafHierarchyPath": "mount-plate-1",
            "FaceCenterLocal": [0, 0, 0], "FaceCenterWorld": [0, 0, 0],
            "FaceNormalLocal": normal.copy(), "FaceNormalWorld": normal.copy(),
            "FaceBoxLocal": [0, 0, 0, 0.1, 0.1, 0],
        }
        fixed = {
            "ModuleToken": "A600", "RelativeLeafHierarchyPath": "base-plate-1",
            "FaceCenterWorld": [0, 0, 0],
            "FaceNormalWorld": normal.copy() if index < 2 else [0, 0, -1],
        }
        mates.append({"MateName": f"P000_A600_DATUM_{suffix}",
                      "MateType": 5 if index < 2 else 0,
                      "Alignment": 0 if index < 2 else 1,
                      "Distance": distance,
                      "AdvancedOptions": {"DistanceFlipDimension": False} if index < 2 else None,
                      "Endpoints": [moving, fixed]})
    placed = IDENTITY.copy()
    placed[9:12] = [0.08, 0.39, 0]
    return {
        "graph": {"Mates": mates},
        "native_target_transform": IDENTITY.copy(),
        "observed_target_transform": placed,
        "observed_base_transform": IDENTITY.copy(),
        "frame": {"originWorldMeters": [0, 0, 0],
                  "axesWorld": {"xIntoMachine": [1, 0, 0],
                                "yTransportLateral": [0, 1, 0], "zUp": [0, 0, 1]}},
        "surface": {"installationPlatform": {"safeBoundary": {"minX": -1, "maxX": 1, "minY": -1, "maxY": 1}},
                    "transportSupportRegion": {"minX": 0.5, "maxX": 0.8, "minY": 0.5, "maxY": 0.8}},
        "native_station": {"longitudinal": 0.08, "lateral": 0.39, "supportGap": 0},
        "native_signed_station": {"P000_A600_DATUM_DISTANCE_1": 0.08,
                                  "P000_A600_DATUM_DISTANCE_2": 0.39,
                                  "P000_A600_DATUM_SUPPORT": 0},
    }


def test_synthetic_station_measures_requested_datum_magnitudes(measurement_inputs):
    result = measure_support_position(**measurement_inputs)
    assert result["requestedMatesMeasured"] is True
    assert result["nativeRoleDatumMagnitudesMatch"] is True
    assert result["nativeRoleSignedDatumsMatch"] is True
    assert result["supportFaceFootprintFrameMeters"] == pytest.approx({
        "minX": 0.08, "maxX": 0.18, "minY": 0.39, "maxY": 0.49})
    assert result["supportFaceWithinCoarsePlatform"] is True
    assert result["cupMouthPositionVerified"] is None
    assert result["exactTrimmedSupportContainmentVerified"] is None


def test_three_datums_recover_one_leaf_frame(measurement_inputs):
    endpoints = [mate["Endpoints"][0] for mate in measurement_inputs["graph"]["Mates"]]
    assert recover_leaf_measurement_transform(endpoints) == pytest.approx(IDENTITY)


@pytest.mark.parametrize("mutation", ["different_leaf", "nonorthogonal_local", "nonorthogonal_world", "inconsistent_center", "missing_datum"])
def test_bad_same_leaf_geometry_is_rejected(measurement_inputs, mutation):
    endpoints = [copy.deepcopy(mate["Endpoints"][0]) for mate in measurement_inputs["graph"]["Mates"]]
    if mutation == "different_leaf":
        endpoints[1]["RelativeLeafHierarchyPath"] = "other-leaf"
    elif mutation == "nonorthogonal_local":
        endpoints[1]["FaceNormalLocal"] = [1, 0, 0]
    elif mutation == "nonorthogonal_world":
        endpoints[1]["FaceNormalWorld"] = [1, 0, 0]
    elif mutation == "inconsistent_center":
        endpoints[1]["FaceCenterWorld"] = [0.2, 0, 0]
    elif mutation == "missing_datum":
        endpoints.pop()
    with pytest.raises(ValueError):
        recover_leaf_measurement_transform(endpoints)


@pytest.mark.parametrize("transform_key", ["native_target_transform", "observed_target_transform", "observed_base_transform"])
@pytest.mark.parametrize("mutation", ["mirror", "nan", "nonrigid"])
def test_invalid_transform_is_rejected(measurement_inputs, transform_key, mutation):
    transform = measurement_inputs[transform_key]
    if mutation == "mirror":
        transform[0] = -1
    elif mutation == "nan":
        transform[10] = float("nan")
    elif mutation == "nonrigid":
        transform[0] = 2
    with pytest.raises(ValueError):
        measure_support_position(**measurement_inputs)


@pytest.mark.parametrize("transform_key,expected_min_x", [
    ("observed_target_transform", 0.1), ("observed_base_transform", 0.06)])
def test_observed_pose_change_changes_measurement(measurement_inputs, transform_key, expected_min_x):
    before = measure_support_position(**measurement_inputs)
    measurement_inputs[transform_key][9] += 0.02
    after = measure_support_position(**measurement_inputs)
    assert after["supportFaceFootprintFrameMeters"]["minX"] == pytest.approx(expected_min_x)
    assert after["supportFaceFootprintFrameMeters"] != before["supportFaceFootprintFrameMeters"]
    assert after["requestedMatesMeasured"] is False
    assert after["nativeRoleDatumMagnitudesMatch"] is False


def test_lifted_support_reports_height_error(measurement_inputs):
    measurement_inputs["observed_target_transform"][11] = 0.03
    result = measure_support_position(**measurement_inputs)
    assert result["requestedMatesMeasured"] is False
    assert result["maximumSupportPlaneHeightErrorMeters"] == pytest.approx(0.03)


def test_changed_distance_value_is_not_reported_as_match(measurement_inputs):
    measurement_inputs["graph"]["Mates"][0]["Distance"] = 0.09
    result = measure_support_position(**measurement_inputs)
    assert result["requestedMatesMeasured"] is False
    # The actual pose still occupies the old native station: do not conflate it
    # with the changed requested dimension.
    assert result["nativeRoleDatumMagnitudesMatch"] is True


@pytest.mark.parametrize("mutation", ["wrong_type", "opposite_alignment", "flipped_distance"])
def test_changed_distance_semantics_cannot_silently_pass(measurement_inputs, mutation):
    mate = measurement_inputs["graph"]["Mates"][0]
    if mutation == "wrong_type":
        mate["MateType"] = 3  # parallel is not a distance relation
    elif mutation == "opposite_alignment":
        mate["Alignment"] = 1
    elif mutation == "flipped_distance":
        mate["AdvancedOptions"]["DistanceFlipDimension"] = True
    try:
        result = measure_support_position(**measurement_inputs)
    except ValueError:
        return
    assert result["requestedMatesMeasured"] is False, "Changed mate semantics were ignored by the measurement audit"


def test_nonorthogonal_installation_frame_is_rejected(measurement_inputs):
    measurement_inputs["frame"]["axesWorld"]["yTransportLateral"] = [1, 0, 0]
    with pytest.raises(ValueError):
        measure_support_position(**measurement_inputs)


def test_real_p000_a600_historical_measurements_and_non_cad_boundary():
    audit = build_p000_a600_target_station_audit(ROOT)
    result = audit["measurements"]
    station = audit["nativeStationEvidence"]["parametersMeters"]
    assert station == pytest.approx({"longitudinal": 0.08, "lateral": 0.39, "supportGap": 0})
    assert result["requestedMatesMeasured"] is True
    assert result["nativeRoleDatumMagnitudesMatch"] is True
    assert result["supportFaceFootprintFrameMeters"] == pytest.approx({
        "minX": 0.0798, "maxX": 0.1798, "minY": -0.41, "maxY": -0.31}, abs=1e-6)
    assert result["maximumSupportPlaneHeightErrorMeters"] < 1e-6
    assert result["cupMouthPositionVerified"] is None
    assert result["exactTrimmedSupportContainmentVerified"] is None
    assert audit["historicalCadReanalysis"] is True
    assert audit["newCadExecuted"] is False
    assert audit["cadLaunchAllowed"] is False
    assert audit["prototypeGeometryUsedForMeasurementOnly"] is True
    assert audit["prototypePoseExecutionAuthorized"] is False
    assert audit["stationReady"] is False
    assert audit["collisionOrBrep"] == "not_evaluated"
    assert audit["actualFastening"] == "not_verified"


def test_swapped_station_dimensions_do_not_count_as_role_match(measurement_inputs):
    measurement_inputs["native_station"].update(longitudinal=0.39, lateral=0.08)
    result = measure_support_position(**measurement_inputs)
    assert result["requestedMatesMeasured"] is True
    assert result["nativeRoleDatumMagnitudesMatch"] is False


def test_mirrored_candidate_satisfies_own_mates_but_not_native_station(measurement_inputs):
    measurement_inputs["graph"]["Mates"][0]["AdvancedOptions"]["DistanceFlipDimension"] = True
    measurement_inputs["observed_target_transform"][9] = -0.08
    result = measure_support_position(**measurement_inputs)
    assert result["requestedMatesMeasured"] is True
    assert result["nativeRoleDatumMagnitudesMatch"] is True
    assert result["supportFaceWithinCoarsePlatform"] is True
    assert result["nativeRoleSignedDatumsMatch"] is False


def test_missing_native_signed_evidence_is_unknown(measurement_inputs):
    measurement_inputs.pop("native_signed_station")
    assert measure_support_position(**measurement_inputs)["nativeRoleSignedDatumsMatch"] is None


@pytest.mark.parametrize("mutation", [None, "missing", "ambiguous", "changed_geometry"])
def test_signed_station_requires_stable_matching_base_face(measurement_inputs, mutation):
    graph = measurement_inputs["graph"]
    native = copy.deepcopy(graph)
    for idx, (candidate, original) in enumerate(zip(graph["Mates"], native["Mates"])):
        candidate["Endpoints"][1]["SourceAssemblyPersistentReferenceBase64"] = f"base-face-{idx}"
        original["Endpoints"][1]["SourceAssemblyPersistentReferenceBase64"] = f"base-face-{idx}"
        original["Endpoints"][0]["ModuleToken"] = "A300"
        original["Endpoints"][0]["FaceCenterWorld"] = [0.08, 0.39, 0]
    if mutation == "missing":
        native["Mates"].pop()
    elif mutation == "ambiguous":
        native["Mates"].append(copy.deepcopy(native["Mates"][0]))
    elif mutation == "changed_geometry":
        native["Mates"][0]["Endpoints"][1]["FaceNormalWorld"] = [-1, 0, 0]
    if mutation:
        with pytest.raises(ValueError):
            match_native_signed_station(graph, native)
    else:
        assert match_native_signed_station(graph, native) == pytest.approx(measurement_inputs["native_signed_station"])


def test_historical_cumulative_transport_proxy_requires_unchanged_relative_pose(tmp_path):
    chain = ROOT / "demo/cross_project_substitution/wastecup-project05-to-project02-v1/support-position-chain-v3"
    state_path = chain / "read-only-chain-verification.json"
    cad_path = chain / "live-run/cad-result.json"
    result = build_p000_a600_target_station_audit(ROOT, state_path=state_path, cad_path=cad_path)
    assert result["observedComponentCount"] == 5
    assert result["measurements"]["transportProxyBoundToObservedContext"] is True
    assert result["targetDatumPositionVerified"] is True
    assert result["newCadExecuted"] is False
    state = json.loads(state_path.read_text(encoding="utf-8-sig"))
    next(c for c in state["observed"]["components"] if "A800.001-" in c["name"])["transform"][9] += 0.02
    changed = tmp_path / "changed-state.json"
    changed.write_text(json.dumps(state), encoding="utf-8")
    result = build_p000_a600_target_station_audit(ROOT, state_path=changed, cad_path=cad_path)
    assert result["measurements"]["transportProxyBoundToObservedContext"] is False
    assert result["measurements"]["transportContextPoseWitnessErrorMeters"] > 0.01
