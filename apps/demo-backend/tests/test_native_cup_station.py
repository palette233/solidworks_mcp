import json
from copy import deepcopy
import pytest
from demo_backend import native_cup_station as cup

IDENTITY = [1,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0]


@pytest.fixture
def setup(tmp_path, monkeypatch):
    def save(name, value):
        (tmp_path/name).write_text(json.dumps(value), encoding="utf-8")
        return name
    assembly = tmp_path / "measured.SLDASM"
    assembly.write_bytes(b"offline synthetic fixture; not CAD")
    source_path, base_path = str(tmp_path/"cup.SLDASM"), str(tmp_path/"base.SLDASM")
    source = {"ModuleToken": "CUP", "HierarchyPath": "cup-2", "Path": source_path, "SourceTransform": IDENTITY.copy()}
    base = {"ModuleToken": "BASE", "HierarchyPath": "base-1", "Path": base_path, "SourceTransform": IDENTITY.copy()}
    graph = {"Modules": [source, base, {**source, "HierarchyPath": "cup-1"}]}
    observed = {"name": "cup", "sourcePath": source_path, "transform": IDENTITY.copy(), "isFixed": False, "solvingState": 0}
    state = {"success": True, "assemblyPath": str(assembly), "assemblySha256": cup.sha(assembly),
             "observed": {"readOnly": True, "components": [observed, {"sourcePath": base_path, "transform": IDENTITY.copy(), "isFixed": True}]}}
    config = {"sourceModuleDefinitionId": "p::CUP", "nativeRoleModuleDefinitionId": "p::CUP", "sourceToken": "CUP", "baseToken": "BASE",
              "nativeInstanceHierarchyPath": "cup-2", "baseInstanceHierarchyPath": "base-1", "cupCatalogInputKeys": ["cup1"],
              "captureOpeningDirectionWorld": [0,1,0], "inputs": {
                  "captureState": save("state.json", state), "nativeGraph": save("graph.json", graph), "cup1": save("catalog.json", {"Endpoints": []})},
              "acceptance": {"projectionToleranceMeters": 1e-6, "angularToleranceDegrees": 1, "equalMouthHeightRequired": False}}
    monkeypatch.setattr(cup, "extract_cup_mouth_points", lambda *a, **kw: {
        "sourceAssemblyPath": str(assembly), "modulePath": source_path, "moduleSourceTransformForMeasurementOnly": IDENTITY.copy(),
        "points": [{"pointId": "mouth", "internalGeometryRigid": True, "centerModuleLocalMeters": [0,.2,0], "openingNormalModuleLocal": [0,1,0]}]})
    return tmp_path, config, state


def test_native_instance_is_explicit_and_projection_separates_height(setup):
    root, config, state = setup
    result = cup.build_native_cup_station(root, config, state)
    assert result["nativeInstanceHierarchyPath"] == "cup-2"
    assert result["proxyGeometryPassed"] is True and result["functionalPassed"] is None
    state["observed"]["components"][0]["transform"][10] += .1
    assert cup.build_native_cup_station(root, config, state)["proxyGeometryPassed"] is True
    config["acceptance"]["equalMouthHeightRequired"] = True
    assert cup.build_native_cup_station(root, config, state)["proxyGeometryPassed"] is False


def test_wrong_projection_is_not_accepted(setup):
    root, config, state = setup
    state["observed"]["components"][0]["transform"][9] += .1
    assert cup.build_native_cup_station(root, config, state)["proxyGeometryPassed"] is False


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, 0, True])
def test_invalid_tolerance_rejected(setup, value):
    root, config, state = setup
    config["acceptance"]["projectionToleranceMeters"] = value
    with pytest.raises(ValueError):
        cup.build_native_cup_station(root, config, state)


@pytest.mark.parametrize("failure", ["different_model", "unknown_instance", "fixed", "flexible", "duplicate", "changed_assembly"])
def test_identity_semantics_and_changed_evidence_rejected(setup, failure):
    root, config, state = setup
    if failure == "different_model": config["sourceModuleDefinitionId"] = "other::CUP"
    if failure == "unknown_instance": config["nativeInstanceHierarchyPath"] = "missing"
    if failure == "fixed": state["observed"]["components"][0]["isFixed"] = True
    if failure == "flexible": state["observed"]["components"][0]["solvingState"] = 1
    if failure == "duplicate": state["observed"]["components"].append(deepcopy(state["observed"]["components"][0]))
    if failure == "changed_assembly": (root/"measured.SLDASM").write_bytes(b"changed")
    with pytest.raises(ValueError):
        cup.build_native_cup_station(root, config, state)
