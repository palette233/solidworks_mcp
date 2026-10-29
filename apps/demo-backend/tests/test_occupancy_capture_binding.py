import json
from pathlib import Path

import pytest

from demo_backend.occupancy_capture_binding import bind_occupancy_capture
from demo_backend import role_station_geometry as geometry
from demo_backend.cleaning_service_region import _native_instance

ROOT = Path(__file__).resolve().parents[3]
OCC = ROOT / "demo/layout_previews/project05_module_occupancy.json"
CAP = ROOT / "demo/layout_previews/project05_n000_world_leaf_envelopes.json"


def test_native_duplicate_requires_explicit_capture_matching_instance():
    graph = geometry._read(ROOT / "demo/layout_previews/project05_module_mate_graph.json")
    module = geometry._read(OCC)["modules"]["N000"]
    with pytest.raises(ValueError, match="uniquely"):
        _native_instance(graph, "N000", None, module)
    with pytest.raises(ValueError, match="capture identity"):
        _native_instance(graph, "N000", "FL9C251093N000.001-3", module)
    selected = _native_instance(graph, "N000", "FL9C251093N000.001-4", module)
    captured = geometry._read(CAP)["instanceCaptures"][0]["moduleTopLevelPose"]
    assert selected["SourceTransform"] == pytest.approx(captured["Transform"])


def test_historical_capture_binds_without_graph_or_cad():
    original = OCC.read_bytes()
    result = bind_occupancy_capture(OCC, CAP, "N000")
    module = result["modules"]["N000"]
    assert module["prototypeAnchorInstallationMeters"] == pytest.approx({"u": .2715, "v": .725, "n": 0})
    assert module["captureFrameBinding"]["verifiedLeafBodyCount"] == 251
    assert module["captureFrameBinding"]["verifiedSubtreeCount"] == 4
    assert module["captureFrameBinding"]["cadAcceptanceEvaluated"] is False
    assert OCC.read_bytes() == original
    geometry._frame_transform(result["installationFrame"])


@pytest.mark.parametrize("mutation, error", [
    ("identity", "identity mismatch"),
    ("multiple", "exactly one"),
    ("incomplete", "complete leaf"),
    ("bounds", "coordinates disagree"),
    ("leaf", "leaf coordinates disagree"),
    ("anchor", "existing capture anchor"),
    ("count", "coverage/count"),
    ("transform", "rigid unit-scale"),
])
def test_rejects_inconsistent_evidence(tmp_path, mutation, error):
    occupancy = geometry._read(OCC)
    capture = geometry._read(CAP)
    module = occupancy["modules"]["N000"]
    if mutation == "identity":
        capture["sourceStandaloneAssemblyPath"] = "C:/wrong.SLDASM"
    elif mutation == "multiple":
        capture["instanceCount"] = 2
    elif mutation == "incomplete":
        capture["coverageComplete"] = False
    elif mutation == "bounds":
        module["occupancyBoxes"][0]["installationBoundsMeters"]["minU"] += .01
    elif mutation == "leaf":
        module["leafBodyOccupancyBoxes"][0]["installationBoundsMeters"]["minU"] += .01
    elif mutation == "anchor":
        module["prototypeAnchorInstallationMeters"] = dict(u=9, v=9, n=9)
    elif mutation == "count":
        capture["bodyCount"] -= 1
    elif mutation == "transform":
        capture["instanceCaptures"][0]["moduleTopLevelPose"]["Transform"][12] = 2
    occ, cap = tmp_path / "occupancy.json", tmp_path / "capture.json"
    occ.write_text(json.dumps(occupancy), encoding="utf-8")
    cap.write_text(json.dumps(capture), encoding="utf-8")
    with pytest.raises(ValueError, match=error):
        bind_occupancy_capture(occ, cap, "N000")
