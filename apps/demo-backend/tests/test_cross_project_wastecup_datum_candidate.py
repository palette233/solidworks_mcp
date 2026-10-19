import copy
import json
from pathlib import Path

import pytest

from demo_backend.cross_project_wastecup_datum_candidate import (
    CrossProjectWasteCupDatumError,
    build_project05_p000_to_project02_a600_datum_candidate,
)


ROOT = Path(__file__).resolve().parents[3]
P02 = ROOT / (
    "demo/global_assembly_catalog/v1/combination-v1-preview/"
    "project02-seven-addon-driving-v6/A300"
)
P05 = ROOT / (
    "demo/global_assembly_catalog/v1/combination-v1-preview/"
    "project05-nonanchor-driving-v6/P000"
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _inputs() -> dict:
    return {
        "a300_graph": _read(P02 / "assembly_plan_effective.json"),
        "a300_semantic_catalog": _read(P02 / "semantic_port_catalog.json"),
        "a300_endpoint_catalog": _read(P02 / "face_endpoint_catalog.json"),
        "p000_graph": _read(P05 / "assembly_plan_effective.json"),
        "p000_semantic_catalog": _read(P05 / "semantic_port_catalog.json"),
        "p000_endpoint_catalog": _read(P05 / "face_endpoint_catalog.json"),
    }


def test_candidate_uses_three_orthogonal_planes_without_pose_anchors():
    package = build_project05_p000_to_project02_a600_datum_candidate(**_inputs())
    graph = package["effectiveGraph"]
    audit = package["audit"]

    assert audit["status"] == "ready_for_nonprototype_cad_validation"
    assert audit["cadLaunchAllowed"] is True
    assert audit["expectedResidualExternalDof"] == 0
    assert audit["prototypeTopLevelTargetPoseUsed"] is False
    assert audit["caseAnchorUsed"] is False
    assert audit["targetLeafPoseAnchorsUsed"] is False
    assert audit["physicalFastenerCompatibility"] == "not_evaluated"
    assert graph["CaseAnchor"] is None
    assert graph["TargetLeafPoseAnchors"] == []
    assert [row["ModuleToken"] for row in graph["Modules"]] == ["A600", "P000"]
    assert [row["MateTypeName"] for row in graph["Mates"]] == [
        "swMateDISTANCE",
        "swMateDISTANCE",
        "swMateCOINCIDENT",
    ]
    assert [row["Distance"] for row in graph["Mates"]] == [0.08, 0.39, None]
    assert all(
        set(row["ModuleTokens"]) == {"A600", "P000"}
        for row in graph["Mates"]
    )


def test_candidate_fails_closed_when_one_required_planar_datum_is_missing():
    values = _inputs()
    semantic = copy.deepcopy(values["p000_semantic_catalog"])
    port = next(row for row in semantic["ports"] if row["portId"] == "P000.frame_installation")
    port["endpointBindings"] = [
        row
        for row in port["endpointBindings"]
        if row["endpointId"] != "face:p000:locator:02131bc386306bb8"
    ]
    values["p000_semantic_catalog"] = semantic

    with pytest.raises(CrossProjectWasteCupDatumError, match="local normal"):
        build_project05_p000_to_project02_a600_datum_candidate(**values)

