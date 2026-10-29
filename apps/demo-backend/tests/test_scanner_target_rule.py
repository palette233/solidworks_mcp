import copy
import hashlib
import json
from pathlib import Path

import pytest

from demo_backend.scanner_target_rule import (
    build_current_scanner_target, validate_current_scanner_target_report,
)
from demo_backend.scanner_target_association import preflight_scanner_target_for_cumulative_chain

ROOT = Path(__file__).resolve().parents[3]
IDENTITY = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]


def _write(path, value):
    path.write_text(json.dumps(value, allow_nan=False), encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def current(tmp_path):
    def module(token):
        return {"ModuleToken": token, "HierarchyPath": token + "-reference", "Path": token + ".SLDASM",
                "SourceTransform": IDENTITY.copy()}
    process = {
        "sourceScanner": {"projectId": "source", "moduleToken": "SC00",
            "opticalOriginWorldMeters": [0, 0, 0], "opticalDirectionWorld": [0, 1, 0],
            "cadBeamEndpointProxyWorldMeters": [0, .1, 0]},
        "targetTransport": {"projectId": "target", "moduleToken": "TR00",
            "sourceTransform": IDENTITY.copy(), "installedTransform": IDENTITY.copy(),
            "installationFrameWorld": {"origin": [0, 0, 0], "flowAxis": [1, 0, 0],
                                       "transverseAxis": [0, 1, 0], "upAxis": [0, 0, 1]},
            "conservativeFlowEnvelopeMeters": [-1, 1], "barcodeLaneReference": {
                "source": "fixture prototype beam", "transverseCoordinateMeters": .1,
                "normalCoordinateMeters": 0, "engineeringConfirmedBarcodeSurface": False}},
        "readOnlyChecks": {"workingDistanceRangeEvidence": {"minimumMeters": .07, "maximumMeters": 1,
            "authority": "synthetic fixture READER-1 specifications", "sourceUrl": "fixture://range"}},
    }
    scanner = {"SourceAssemblyPath": "reference-world", "Modules": [module("SC00")],
               "SemanticAssemblyPlanAudit": {"opticalValidation": {"modeledWorkingDistanceMeters": .1,
                   "opticalDirectionWorld": [0, 1, 0], "targetProxyWorldMeters": [0, .1, 0]}}}
    transport = {"SourceAssemblyPath": "target-world", "Modules": [module("TR00"), module("BA00")]}
    contents = {"processEvidencePath": process, "scannerGraphPath": scanner,
                "transportGraphPath": transport, "targetBaseGraphPath": transport,
                "targetFaceCatalogPath": {"SourceAssemblyPath": "target-world"}}
    rule = {"schemaVersion": "scanner-target-rule/v1", "ruleId": "synthetic",
            "sourceModuleDefinitionId": "source::SC00", "transportModuleDefinitionId": "target::TR00",
            "targetBaseDefinitionId": "target::BA00", "referenceBaseDefinitionId": "target::BA00",
            "inputs": {}, "inputSha256": {}}
    for key, value in contents.items():
        rule["inputs"][key] = key + ".json"
        rule["inputSha256"][key] = _write(tmp_path / rule["inputs"][key], value)
    assembly = tmp_path / "fixture.SLDASM"
    assembly.write_bytes(b"synthetic offline fixture; not CAD evidence")
    state = {"success": True, "assemblyPath": str(assembly),
             "assemblySha256": hashlib.sha256(assembly.read_bytes()).hexdigest(),
             "observed": {"readOnly": True, "components": [
                 {"name": token + "-current", "sourcePath": token + ".SLDASM", "configuration": "Default",
                  "transform": IDENTITY.copy()} for token in ("SC00", "TR00", "BA00")]}}
    state_path = tmp_path / "state.json"
    _write(state_path, state)
    return {"root": tmp_path, "rule": rule, "state": state, "state_path": state_path,
            "contents": contents}


def _args(current):
    return {"state_path": current["state_path"], "rule": current["rule"],
            "repository_root": current["root"], "authorize_prototype_estimate": True}


def _change_input(current, key):
    current["rule"]["inputSha256"][key] = _write(
        current["root"] / current["rule"]["inputs"][key], current["contents"][key])


def test_generic_unique_selection_and_non_cad_boundary(current):
    result = build_current_scanner_target(**_args(current))
    assert result["summary"]["processCandidateCompileAllowed"] is True
    assert result["summary"]["instanceSelection"] == {
        "scanner": "SC00-current", "transport": "TR00-current", "targetBase": "BA00-current"}
    assert result["summary"]["newCadExecuted"] is False
    assert result["summary"]["measuredScanSuccess"] is False
    assert result["association"]["workpieceTarget"]["physicalBarcodeFaceId"] is None
    assert validate_current_scanner_target_report(report=result, **_args(current))["passed"] is True


@pytest.mark.parametrize("role,index", [("scanner", 0), ("transport", 1), ("targetBase", 2)])
def test_duplicate_current_role_requires_exact_selector(current, role, index):
    duplicate = copy.deepcopy(current["state"]["observed"]["components"][index])
    duplicate["name"] += "-second"
    current["state"]["observed"]["components"].append(duplicate)
    _write(current["state_path"], current["state"])
    with pytest.raises(ValueError, match="explicit.*instance selector"):
        build_current_scanner_target(**_args(current))
    report = build_current_scanner_target(**_args(current), instance_selectors={role: duplicate["name"]})
    assert report["summary"]["instanceSelection"][role] == duplicate["name"]
    with pytest.raises(ValueError, match="exactly one"):
        build_current_scanner_target(**_args(current), instance_selectors={role: "not-this-source"})


@pytest.mark.parametrize("selector", [{"transprot": "TR00-current"}, {"scanner": ""}, {"scanner": 4}])
def test_invalid_selector_is_not_ignored(current, selector):
    with pytest.raises(ValueError, match="Instance selectors"):
        build_current_scanner_target(**_args(current), instance_selectors=selector)


@pytest.mark.parametrize("role,index", [("transport", 1), ("targetBase", 2)])
def test_replacing_instance_rebinds_and_rejects_old_report(current, role, index):
    old = build_current_scanner_target(**_args(current))
    current["state"]["observed"]["components"][index]["name"] += "-replacement"
    _write(current["state_path"], current["state"])
    fresh = build_current_scanner_target(**_args(current))
    assert fresh["association"][role]["instanceId"] != old["association"][role]["instanceId"]
    assert validate_current_scanner_target_report(report=old, **_args(current))["passed"] is False
    stale = preflight_scanner_target_for_cumulative_chain(
        association=old["association"], evaluation=old["evaluation"],
        planned_components=fresh["contextComponents"],
        world_frame_id=old["association"]["coordinateFrame"]["worldFrameId"], allow_prototype_proxy=True)
    assert stale["processCandidateCompileAllowed"] is False


@pytest.mark.parametrize("index,expected_distance", [(0, .02), (1, .18), (2, .1)])
def test_pose_changes_recompute_not_historical_pass(current, index, expected_distance):
    old = build_current_scanner_target(**_args(current))
    current["state"]["observed"]["components"][index]["transform"][10] = .08
    _write(current["state_path"], current["state"])
    fresh = build_current_scanner_target(**_args(current))
    assert fresh["summary"]["processProxyChecks"]["requiredWorkingDistanceMeters"] == pytest.approx(expected_distance)
    assert fresh["evaluation"]["processProxyValidationPassed"] is (index != 0)
    assert validate_current_scanner_target_report(report=old, **_args(current))["passed"] is False
    assert fresh["association"]["associationDigest"] != old["association"]["associationDigest"]


def test_new_transport_definition_cannot_reuse_old_lane_report(current):
    current["rule"]["transportModuleDefinitionId"] = "target::OTHER"
    current["contents"]["transportGraphPath"]["Modules"][0]["ModuleToken"] = "OTHER"
    _change_input(current, "transportGraphPath")
    with pytest.raises(ValueError, match="Different transport"):
        build_current_scanner_target(**_args(current))


def test_new_base_definition_has_new_binding_not_old_report(current):
    old = build_current_scanner_target(**_args(current))
    current["rule"]["targetBaseDefinitionId"] = "other::NEWBASE"
    current["contents"]["targetBaseGraphPath"]["Modules"][1]["ModuleToken"] = "NEWBASE"
    current["contents"]["targetBaseGraphPath"]["Modules"][1]["Path"] = "NEWBASE.SLDASM"
    _change_input(current, "targetBaseGraphPath")
    current["state"]["observed"]["components"][2]["sourcePath"] = "NEWBASE.SLDASM"
    _write(current["state_path"], current["state"])
    fresh = build_current_scanner_target(**_args(current))
    assert fresh["association"]["targetBase"]["moduleDefinitionId"] == "other::NEWBASE"
    assert validate_current_scanner_target_report(report=old, **_args(current))["passed"] is False


def test_pinned_input_and_configuration_fail_closed(current):
    current["rule"]["configurations"] = {"scanner": "Other"}
    with pytest.raises(ValueError, match="configuration"):
        build_current_scanner_target(**_args(current))
    current["rule"].pop("configurations")
    path = current["root"] / current["rule"]["inputs"]["scannerGraphPath"]
    _write(path, {**current["contents"]["scannerGraphPath"], "changed": True})
    with pytest.raises(ValueError, match="input hash changed"):
        build_current_scanner_target(**_args(current))


@pytest.mark.parametrize("role,index", [("transport", 1), ("targetBase", 2)])
@pytest.mark.parametrize("field,value", [("sourcePath", "other.SLDASM"), ("configuration", "Other")])
def test_same_named_same_pose_part_or_configuration_change_rejects_old_report(current, role, index, field, value):
    old = build_current_scanner_target(**_args(current))
    components = copy.deepcopy(old["contextComponents"])
    components[index][field] = value
    stale = preflight_scanner_target_for_cumulative_chain(
        association=old["association"], evaluation=old["evaluation"], planned_components=components,
        world_frame_id=old["association"]["coordinateFrame"]["worldFrameId"], allow_prototype_proxy=True)
    assert stale["processCandidateCompileAllowed"] is False
    assert any(role.upper() in code and "CHANGED" in code for code in stale["blockingReasonCodes"])


@pytest.mark.parametrize("change", ["wrong_member", "wrong_project", "wrong_model", "ambiguous_pointer"])
def test_optical_override_cannot_borrow_other_module_or_model(current, change):
    optical = {"projectId": "source", "scannerModel": "READER-1", "scanners": [{
        "componentName": "SC00-reference/head-1", "modeledWorkingDistanceMeters": .1,
        "opticalOriginWorldMeters": [0, 0, 0], "opticalDirectionWorld": [0, 1, 0],
        "targetProxyWorldMeters": [0, .1, 0]}]}
    current["rule"]["opticalMeasurementSelector"] = {"jsonPointer": "/scanners/0", "scannerModel": "READER-1"}
    if change == "wrong_member":
        optical["scanners"][0]["componentName"] = "another-module/head-1"
    elif change == "wrong_project":
        optical["projectId"] = "other"
    elif change == "wrong_model":
        optical["scannerModel"] = "READER-2"
    else:
        current["rule"]["opticalMeasurementSelector"]["jsonPointer"] = "/scanners"
    current["rule"]["inputs"]["opticalGeometryPath"] = "optical.json"
    _write(current["root"] / "optical.json", optical)
    with pytest.raises(ValueError):
        build_current_scanner_target(**_args(current))


def test_second_rule_uses_real_sm00_product_head_measurement_with_synthetic_poses(tmp_path):
    # Real reference measurements + synthetic identity-preserving current state;
    # deliberately not called a new CAD run or a new measured saved state.
    rule_path = ROOT / "data/assembly_stations/scanner-sm00-ss00-jj00-v1.json"
    rule = json.loads(rule_path.read_text(encoding="utf-8"))
    graph = json.loads((ROOT / rule["inputs"]["scannerGraphPath"]).read_text(encoding="utf-8-sig"))
    rows = [row for row in graph["Modules"] if row["ModuleToken"] in ("SM00", "SS00", "JJ00")]
    fixture = tmp_path / "fixture.SLDASM"
    fixture.write_bytes(b"synthetic current state, not CAD")
    state = {"success": True, "assemblyPath": str(fixture),
             "assemblySha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
             "observed": {"readOnly": True, "components": [{"name": row["HierarchyPath"],
                 "sourcePath": row["Path"], "transform": row["SourceTransform"]} for row in rows]}}
    state_path = tmp_path / "synthetic-state.json"
    _write(state_path, state)
    result = build_current_scanner_target(state_path=state_path, rule_path=rule_path,
                                          authorize_prototype_estimate=True)
    assert result["association"]["scanner"]["moduleDefinitionId"] == "project01::SM00"
    assert result["summary"]["processProxyChecks"]["requiredWorkingDistanceMeters"] == pytest.approx(.2)
    assert result["summary"]["processProxyChecks"]["crossTrackErrorMeters"] == pytest.approx(0, abs=1e-9)
    assert result["evaluation"]["processProxyValidationPassed"] is True
    assert result["summary"]["measuredScanSuccess"] is False


def test_default_rule_and_explicit_rule_same_runtime_binding():
    state = ROOT / "demo/role_station_strengthening_20261028/functional-chain-v1/s06-p000/reopened-state.json"
    default = build_current_scanner_target(state_path=state, authorize_prototype_estimate=True)
    explicit = build_current_scanner_target(state_path=state, authorize_prototype_estimate=True,
        rule_path=ROOT / "data/assembly_stations/scanner-ai00-ss00-aa00-v1.json")
    assert default["association"] == explicit["association"]
    assert default["summary"]["processProxyChecks"]["requiredWorkingDistanceMeters"] == pytest.approx(.0745)
    assert default["summary"]["newCadExecuted"] is False
