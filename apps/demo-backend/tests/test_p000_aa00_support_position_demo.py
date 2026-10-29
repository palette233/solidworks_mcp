from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("p000_aa00_support_candidate_test_target", ROOT / "scripts/build_p000_aa00_support_position_demo.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@pytest.fixture
def inputs():
    return {
        "aa00_catalog": MODULE.read(MODULE.AA00_CATALOG),
        "p000_graph": MODULE.read(MODULE.P05 / "assembly_plan_effective.json"),
        "p000_semantic_catalog": MODULE.read(MODULE.P05 / "semantic_port_catalog.json"),
        "p000_endpoint_catalog": MODULE.read(MODULE.P05 / "face_endpoint_catalog.json"),
    }


def test_real_aa00_faces_bound_and_no_prototype_pose_anchor(inputs):
    before = copy.deepcopy(inputs)
    result = MODULE.build_candidate(**inputs)
    graph, audit = result["effectiveGraph"], result["audit"]
    assert inputs == before
    assert [m["ModuleToken"] for m in graph["Modules"]] == ["AA00", "P000"]
    assert graph["Modules"][1]["SourceTransform"] == MODULE.IDENTITY
    assert graph["EditPolicy"]["fixedModuleTokens"] == ["AA00"]
    assert graph["EditPolicy"]["initialPlacementVariant"] == 1
    assert not graph["CaseAnchor"] and not graph["TargetLeafPoseAnchors"]
    assert all(m["ModuleTokens"] == ["P000", "AA00"] for m in graph["Mates"])
    assert [m["Distance"] for m in graph["Mates"]] == [.4, .2, None]
    assert [m["Alignment"] for m in graph["Mates"]] == [0, 0, 1]
    assert audit["targetProjectId"] == "project03"
    assert audit["targetBaseToken"] == "AA00"
    assert audit["actualFixationMethod"] == "not_verified"
    assert audit["holePatternMatchRequired"] is False
    assert audit["directMechanicalCompatibilityClaim"] is False
    assert audit["prototypeTopLevelTargetPoseUsed"] is False
    assert audit["effectiveGraphDigest"] == MODULE._digest(graph)
    for mate, key in zip(graph["Mates"], MODULE.AA00_IDS):
        original = next(r["Endpoint"] for r in inputs["aa00_catalog"]["Endpoints"] if r["EndpointId"] == key)
        copied = copy.deepcopy(original)
        copied["Index"] = 1
        assert mate["Endpoints"][1] == copied
    assert result["endpointCatalog"]["EndpointCount"] == 6
    assert set(r["Endpoint"]["ModuleToken"] for r in result["endpointCatalog"]["Endpoints"]) == {"AA00", "P000"}


def test_support_footprint_is_inside_finite_plate_but_not_brep(inputs):
    check = MODULE.build_candidate(**inputs)["audit"]["finiteSupportRegionCheck"]
    assert check["targetSupportFootprintBoundingBoxMeters"] == pytest.approx([.3735, .4, .018, .4735, .5, .018])
    assert check["withinFiniteSupportBoundingRegion"] is True
    assert check["intersectingSmallFaceBoundingBoxes"] == []
    assert check["trimLoopContainment"] == "not_evaluated"
    assert check["derivedGeometryUsedAsPoseAnchor"] is False


def test_readonly_geometric_witness_is_not_an_execution_pose(inputs):
    result = MODULE.build_candidate(**inputs)
    witness = result["audit"]["geometricWitness"]
    points = witness["referencePoints"]
    assert points[0]["expectedBaseModulePointMeters"] == pytest.approx([.72, .655, .4235])
    assert points[1]["expectedBaseModulePointMeters"] == pytest.approx([.62, .659, .4235])
    assert points[2]["expectedBaseModulePointMeters"] == pytest.approx([.67, .659, .4735])
    assert points[3]["expectedBaseModulePointMeters"] == pytest.approx([.67, .655, .4235])
    assert witness["notAnExecutablePoseAnchor"] is True
    assert "geometricWitness" not in result["effectiveGraph"]
    assert "geometricWitness" not in result["effectiveGraph"]["CrossProjectWasteCupDatumAudit"]


def test_explicit_parameter_change_changes_real_distances_not_face_identity(inputs):
    a = MODULE.build_candidate(**inputs)
    b = MODULE.build_candidate(**inputs, longitudinal_m=.41, lateral_m=.21)
    assert [m["Distance"] for m in b["effectiveGraph"]["Mates"]] == [.41, .21, None]
    assert a["audit"]["effectiveGraphDigest"] != b["audit"]["effectiveGraphDigest"]
    assert [m["Endpoints"] for m in a["effectiveGraph"]["Mates"]] == [m["Endpoints"] for m in b["effectiveGraph"]["Mates"]]


@pytest.mark.parametrize("parameter", ["longitudinal_m", "lateral_m"])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, True])
def test_invalid_parameter_rejected(inputs, parameter, value):
    with pytest.raises(ValueError, match="finite non-negative"):
        MODULE.build_candidate(**inputs, **{parameter: value})


@pytest.mark.parametrize("parameters", [{"longitudinal_m": .6}, {"lateral_m": 1.3}])
def test_footprint_outside_finite_support_rejected(inputs, parameters):
    with pytest.raises(ValueError, match="outside the finite"):
        MODULE.build_candidate(**inputs, **parameters)


@pytest.mark.parametrize("endpoint_id", MODULE.AA00_IDS)
def test_missing_real_context_endpoint_rejected(inputs, endpoint_id):
    inputs["aa00_catalog"]["Endpoints"] = [r for r in inputs["aa00_catalog"]["Endpoints"] if r["EndpointId"] != endpoint_id]
    with pytest.raises(ValueError, match="Missing AA00 real face"):
        MODULE.build_candidate(**inputs)


def test_wrong_context_direction_not_silently_accepted(inputs):
    row = next(r for r in inputs["aa00_catalog"]["Endpoints"] if r["EndpointId"] == MODULE.AA00_IDS[1])
    row["Endpoint"]["FaceNormalLocal"] = [1, 0, 0]
    with pytest.raises(ValueError, match="local normal"):
        MODULE.build_candidate(**inputs)


def test_no_target_pose_dependence(inputs):
    before = MODULE.build_candidate(**inputs)
    module = next(r for r in inputs["p000_graph"]["Modules"] if r["ModuleToken"] == "P000")
    module["SourceTransform"] = [123] * 16
    after = MODULE.build_candidate(**inputs)
    assert before == after


@pytest.mark.parametrize("value", [True, -1, 1.5])
def test_invalid_initial_variant_rejected(inputs, value):
    with pytest.raises(ValueError, match="non-negative integer"):
        MODULE.build_candidate(**inputs, initial_placement_variant=value)
