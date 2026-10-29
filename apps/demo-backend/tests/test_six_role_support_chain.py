from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("six_role_support_chain_test_target", ROOT / "scripts/finalize_six_role_support_chain.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
validate_cumulative_state = MODULE.validate_cumulative_state


def component(token: str) -> dict:
    return {"name": f"CAD{token}.001-1", "sourcePath": f"D:/fixture/{token}.SLDASM",
            "transform": list(MODULE.IDENTITY), "isFixed": token == "AA00", "constrainedStatus": 3,
            "configuration": "Default", "solvingState": 0}


def mate(name: str) -> dict:
    return {"name": name, "isSuppressed": False, "errorCode": 0, "alignment": 0, "distanceMeters": 0.1}


@pytest.fixture
def state() -> dict:
    components = [component(token) for token in MODULE.CONTEXT]
    mates = [mate(f"MCP_GRAPH_{token}_INSTALL_{index}") for token in MODULE.CONTEXT[1:] for index in range(3)]
    target = [mate(name) for name in sorted(MODULE.TARGET_MATES)]
    return {"sourceObserved": {"components": components, "allTopLevelMates": mates},
            "observed": {"components": copy.deepcopy(components) + [component("P000")],
                         "allTopLevelMates": copy.deepcopy(mates + target), "mates": target}}


def test_six_role_state_passes_without_mutation(state: dict) -> None:
    before = copy.deepcopy(state)
    checks = validate_cumulative_state(state)
    assert checks and all(checks.values())
    assert checks["fiveModuleSourceObserved"]
    assert checks["sixModulesReopened"]
    assert checks["targetNotFixedAndFullyConstrained"]
    assert state == before


def test_component_and_mate_enumeration_order_is_not_execution_order(state: dict) -> None:
    state["observed"]["components"].reverse()
    state["observed"]["allTopLevelMates"].reverse()
    assert all(validate_cumulative_state(state).values())


@pytest.mark.parametrize("index", range(5))
def test_moved_upstream_rejected(state: dict, index: int) -> None:
    state["observed"]["components"][index]["transform"][9] += 0.001
    with pytest.raises(ValueError, match="upstreamComponentsUnchanged"):
        validate_cumulative_state(state)


@pytest.mark.parametrize("stage", ["sourceObserved", "observed"])
@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), True, "0"])
def test_invalid_transform_rejected(state: dict, stage: str, invalid: object) -> None:
    state[stage]["components"][1]["transform"][9] = invalid
    with pytest.raises(ValueError, match="upstreamComponentsUnchanged"):
        validate_cumulative_state(state)


@pytest.mark.parametrize("index", range(6))
def test_missing_component_rejected(state: dict, index: int) -> None:
    state["observed"]["components"].pop(index)
    with pytest.raises(ValueError, match="sixModulesReopened"):
        validate_cumulative_state(state)


@pytest.mark.parametrize("stage", ["sourceObserved", "observed"])
def test_wrong_module_rejected(state: dict, stage: str) -> None:
    state[stage]["components"][1] = component("D000")
    with pytest.raises(ValueError, match="fiveModuleSourceObserved|sixModulesReopened"):
        validate_cumulative_state(state)


@pytest.mark.parametrize("field,value", [("sourcePath", "D:/wrong.SLDASM"), ("configuration", "Other"), ("solvingState", 1), ("isFixed", True), ("constrainedStatus", 2)])
def test_changed_component_semantics_rejected(state: dict, field: str, value: object) -> None:
    state["observed"]["components"][1][field] = value
    with pytest.raises(ValueError, match="upstreamComponentsUnchanged"):
        validate_cumulative_state(state)


@pytest.mark.parametrize("field,value", [("isSuppressed", True), ("errorCode", 1), ("alignment", 1), ("distanceMeters", 0.2)])
def test_changed_upstream_mate_rejected(state: dict, field: str, value: object) -> None:
    state["observed"]["allTopLevelMates"][0][field] = value
    with pytest.raises(ValueError, match="upstreamMatesUnchanged"):
        validate_cumulative_state(state)


@pytest.mark.parametrize("field,value", [("isSuppressed", True), ("errorCode", 1)])
def test_unchanged_invalid_upstream_mate_rejected(state: dict, field: str, value: object) -> None:
    for stage in ("sourceObserved", "observed"):
        state[stage]["allTopLevelMates"][0][field] = value
    with pytest.raises(ValueError, match="upstreamMatesActiveAndClean"):
        validate_cumulative_state(state)


@pytest.mark.parametrize("field,value", [("isSuppressed", True), ("errorCode", 1)])
def test_target_mate_inactive_or_invalid_rejected(state: dict, field: str, value: object) -> None:
    target = state["observed"]["mates"][0]
    target[field] = value
    next(row for row in state["observed"]["allTopLevelMates"] if row["name"] == target["name"])[field] = value
    with pytest.raises(ValueError, match="threeActiveTargetMates"):
        validate_cumulative_state(state)


@pytest.mark.parametrize("field,value", [("isFixed", True), ("constrainedStatus", 2)])
def test_target_fixed_or_underconstrained_rejected(state: dict, field: str, value: object) -> None:
    state["observed"]["components"][-1][field] = value
    with pytest.raises(ValueError, match="targetNotFixedAndFullyConstrained"):
        validate_cumulative_state(state)


def test_extra_mate_rejected(state: dict) -> None:
    state["observed"]["allTopLevelMates"].append(mate("UNREQUESTED"))
    with pytest.raises(ValueError, match="onlyThreeTargetMatesAdded"):
        validate_cumulative_state(state)


@pytest.mark.parametrize("stage,key", [("sourceObserved", "components"), ("observed", "components"), ("sourceObserved", "allTopLevelMates"), ("observed", "allTopLevelMates"), ("observed", "mates")])
def test_duplicate_name_cannot_hide_extra_row(state: dict, stage: str, key: str) -> None:
    rows = state[stage][key]
    rows.append(copy.deepcopy(rows[0]))
    with pytest.raises(ValueError):
        validate_cumulative_state(state)


def manifest_and_closure(order: list[str]) -> tuple[dict, dict]:
    return ({"packetCount": 4, "packets": [
        {"order": index, "targetProjectAliases": [{"moduleToken": token}]}
        for index, token in enumerate(order, 1)]},
        {"actualOrder": order, "steps": [{"moduleToken": token} for token in order]})


@pytest.mark.parametrize("order", [["SS00", "AI00", "BD00", "AG00"], ["AG00", "BD00", "SS00", "AI00"]])
def test_real_manifest_and_closure_determine_sequence(order: list[str]) -> None:
    manifest, closure = manifest_and_closure(order)
    expected = ["AA00", *order, "P000"]
    assert MODULE.derive_module_sequence(manifest, closure) == expected
    assert MODULE.derive_module_sequence(manifest, closure, expected) == expected


def test_cli_cannot_override_actual_sequence() -> None:
    manifest, closure = manifest_and_closure(["SS00", "AI00", "BD00", "AG00"])
    with pytest.raises(ValueError, match="不能改写实际顺序"):
        MODULE.derive_module_sequence(manifest, closure, ["AA00", "BD00", "AG00", "SS00", "AI00", "P000"])


@pytest.mark.parametrize("change", ["extra", "duplicate_token", "order_index", "ambiguous_alias", "wrong_closure", "wrong_step"])
def test_inconsistent_execution_sequence_rejected(change: str) -> None:
    manifest, closure = manifest_and_closure(["SS00", "AI00", "BD00", "AG00"])
    if change == "extra":
        manifest["packets"].append(copy.deepcopy(manifest["packets"][0]))
    elif change == "duplicate_token":
        manifest["packets"][1]["targetProjectAliases"][0]["moduleToken"] = "SS00"
    elif change == "order_index":
        manifest["packets"][0]["order"] = 4
    elif change == "ambiguous_alias":
        manifest["packets"][0]["targetProjectAliases"].append({"moduleToken": "D000"})
    elif change == "wrong_closure":
        closure["actualOrder"] = list(reversed(closure["actualOrder"]))
    else:
        closure["steps"][0]["moduleToken"] = "D000"
    with pytest.raises(ValueError):
        MODULE.derive_module_sequence(manifest, closure)


@pytest.mark.parametrize("existing", ["chain-closure.json", "chain-closure-CN.md"])
def test_closure_refuses_to_overwrite_either_evidence_file(tmp_path: Path, existing: str) -> None:
    path = tmp_path / existing
    path.write_text("immutable", encoding="utf-8")
    with pytest.raises(FileExistsError):
        MODULE.write_closure(tmp_path, {})
    assert path.read_text(encoding="utf-8") == "immutable"
    assert len(list(tmp_path.iterdir())) == 1


@pytest.fixture
def geometry_inputs(tmp_path: Path) -> tuple[dict, dict, Path]:
    output = tmp_path / "six.SLDASM"
    output.write_bytes(b"synthetic-cad-for-pure-geometry-test")
    points = [[0, 0, 0], [1, 0, 0], [0, 1, 0]]
    state = {"success": True, "checks": {"statePassed": True},
             "assemblyPath": str(output), "assemblySha256": MODULE.sha(output),
             "observed": {"readOnly": True,
                          "components": [{"name": "AA00.001-1", "transform": list(MODULE.IDENTITY)}],
                          "targetLeafWitness": {"name": "P000.001-1/plate-1", "transform": list(MODULE.IDENTITY)}}}
    audit = {"mode": "support_position_demo", "actualFixationMethod": "not_verified", "holePatternMatchRequired": False,
             "geometricWitness": {"baseModuleToken": "AA00", "coordinateFrame": "AA00_module_local",
                                  "notAnExecutablePoseAnchor": True, "targetModuleTopLevelTransformUsed": False,
                                  "targetLeafRelativePath": "plate-1", "positionToleranceMeters": 1e-6,
                                  "referencePoints": [{"name": str(index), "targetLeafPointMeters": point,
                                                       "expectedBaseModulePointMeters": point}
                                                      for index, point in enumerate(points)]}}
    return state, audit, output


def test_finalizer_recomputes_geometry_from_new_chain_snapshot(geometry_inputs) -> None:
    state, audit, output = geometry_inputs
    report = MODULE.verify_signed_support_state(state, audit, output)
    assert report["success"] is True
    assert report["maximumResidualMeters"] == 0
    assert report["assemblySha256"] == MODULE.sha(output)


@pytest.mark.parametrize("failure", ["leaf_missing", "signed_branch", "changed_output", "wrong_leaf", "state_failed"])
def test_finalizer_rejects_invalid_appended_geometry_despite_other_cad_success(geometry_inputs, failure) -> None:
    state, audit, output = geometry_inputs
    if failure == "leaf_missing":
        state["observed"].pop("targetLeafWitness")
    elif failure == "signed_branch":
        state["observed"]["targetLeafWitness"]["transform"][9] = -0.4
    elif failure == "changed_output":
        output.write_bytes(b"changed")
    elif failure == "wrong_leaf":
        state["observed"]["targetLeafWitness"]["name"] = "other-leaf"
    else:
        state["success"] = False
    with pytest.raises(ValueError, match="signedSupportPositionMatches"):
        MODULE.verify_signed_support_state(state, audit, output)


def test_wastecup_publisher_names_current_base_in_boundary_statement() -> None:
    # No publication is performed: old immutable releases remain untouched.
    from publish_cross_project_wastecup_datum_demo_release import _derivation_statement
    assert "P000与AA00" in _derivation_statement("AA00")
    assert "A600" not in _derivation_statement("AA00")
    assert "P000与A600" in _derivation_statement("A600")
