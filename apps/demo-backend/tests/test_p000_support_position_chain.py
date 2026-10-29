from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "finalize_p000_support_position_chain_test_target",
    ROOT / "scripts/finalize_p000_support_position_chain.py",
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
validate_cumulative_state = MODULE.validate_cumulative_state

IDENTITY = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]


def _component(token: str) -> dict:
    stem = "FL9C254098" if token == "P000" else "FL9A24D062"
    return {
        "name": f"{stem}{token}.001-1",
        "sourcePath": f"D:/fixture/{stem}{token}.001.SLDASM",
        "transform": list(IDENTITY),
        "isFixed": token == "A600",
        "constrainedStatus": 3,
        "configuration": "Default",
        "solvingState": 0,
    }


def _mate(name: str, distance: float | None) -> dict:
    return {
        "name": name,
        "isSuppressed": False,
        "errorCode": 0,
        "type": 0 if distance is None else 5,
        "alignment": 1 if distance is None else 0,
        "distanceMeters": distance,
        "angleRadians": None,
    }


@pytest.fixture
def chain_state() -> dict:
    old_components = [_component(token) for token in ("A600", "A800", "A180", "A500")]
    old_mates = [
        _mate("MCP_GRAPH_A800_INSTALL_SUPPORT", None),
        _mate("MCP_GRAPH_A180_INSTALL_DISTANCE", 0.05),
        _mate("MCP_GRAPH_A500_INSTALL_DISTANCE", 0.12),
    ]
    target_mates = [
        _mate("MCP_GRAPH_P000_A600_DATUM_DISTANCE_1", 0.08),
        _mate("MCP_GRAPH_P000_A600_DATUM_DISTANCE_2", 0.39),
        _mate("MCP_GRAPH_P000_A600_DATUM_SUPPORT", None),
    ]
    return {
        "sourceObserved": {
            "components": old_components,
            "allTopLevelMates": old_mates,
        },
        "observed": {
            "components": copy.deepcopy(old_components) + [_component("P000")],
            "allTopLevelMates": copy.deepcopy(old_mates + target_mates),
            "mates": copy.deepcopy(target_mates),
        },
    }


def test_valid_support_append_preserves_four_components_and_mates(chain_state: dict) -> None:
    before = copy.deepcopy(chain_state)
    checks = validate_cumulative_state(chain_state)
    assert checks == {
        "fourModuleSourceObserved": True,
        "fiveModulesReopened": True,
        "upstreamComponentsUnchanged": True,
        "upstreamMatesUnchanged": True,
        "onlyThreeTargetMatesAdded": True,
        "upstreamMatesActiveAndClean": True,
    }
    assert chain_state == before


@pytest.mark.parametrize("component_index", range(4))
def test_existing_component_displacement_rejected(chain_state: dict, component_index: int) -> None:
    chain_state["observed"]["components"][component_index]["transform"][9] += 0.001
    with pytest.raises(ValueError, match="upstreamComponentsUnchanged"):
        validate_cumulative_state(chain_state)


@pytest.mark.parametrize("component_index", [1, 4])
def test_missing_upstream_or_target_component_rejected(chain_state: dict, component_index: int) -> None:
    chain_state["observed"]["components"].pop(component_index)
    with pytest.raises(ValueError, match="fiveModulesReopened"):
        validate_cumulative_state(chain_state)


@pytest.mark.parametrize("stage", ["sourceObserved", "observed"])
def test_wrong_upstream_module_rejected(chain_state: dict, stage: str) -> None:
    chain_state[stage]["components"][1] = _component("A300")
    with pytest.raises(ValueError, match="fourModuleSourceObserved|fiveModulesReopened"):
        validate_cumulative_state(chain_state)


def test_wrong_added_module_rejected(chain_state: dict) -> None:
    chain_state["observed"]["components"][-1] = _component("N000")
    with pytest.raises(ValueError, match="fiveModulesReopened"):
        validate_cumulative_state(chain_state)


@pytest.mark.parametrize("component_index", [0, 1])
def test_upstream_fixed_state_change_rejected(chain_state: dict, component_index: int) -> None:
    row = chain_state["observed"]["components"][component_index]
    row["isFixed"] = not row["isFixed"]
    with pytest.raises(ValueError, match="upstreamComponentsUnchanged"):
        validate_cumulative_state(chain_state)


def test_missing_upstream_mate_rejected(chain_state: dict) -> None:
    chain_state["observed"]["allTopLevelMates"].pop(0)
    with pytest.raises(ValueError, match="upstreamMatesUnchanged"):
        validate_cumulative_state(chain_state)


def test_changed_upstream_mate_distance_rejected(chain_state: dict) -> None:
    chain_state["observed"]["allTopLevelMates"][1]["distanceMeters"] = 0.06
    with pytest.raises(ValueError, match="upstreamMatesUnchanged"):
        validate_cumulative_state(chain_state)


def test_newly_suppressed_upstream_mate_rejected(chain_state: dict) -> None:
    chain_state["observed"]["allTopLevelMates"][0]["isSuppressed"] = True
    with pytest.raises(ValueError, match="upstreamMatesUnchanged"):
        validate_cumulative_state(chain_state)


@pytest.mark.parametrize(("field", "value"), [("isSuppressed", True), ("errorCode", 1)])
def test_unchanged_but_invalid_upstream_mate_rejected(chain_state: dict, field: str, value: object) -> None:
    for stage in ("sourceObserved", "observed"):
        chain_state[stage]["allTopLevelMates"][0][field] = value
    with pytest.raises(ValueError, match="upstreamMatesActiveAndClean"):
        validate_cumulative_state(chain_state)


def test_unexpected_extra_mate_rejected(chain_state: dict) -> None:
    chain_state["observed"]["allTopLevelMates"].append(_mate("MCP_GRAPH_UNREQUESTED", 0.01))
    with pytest.raises(ValueError, match="onlyThreeTargetMatesAdded"):
        validate_cumulative_state(chain_state)


@pytest.mark.parametrize("stage", ["sourceObserved", "observed"])
@pytest.mark.parametrize("nonfinite", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_upstream_transform_rejected(chain_state: dict, stage: str, nonfinite: float) -> None:
    chain_state[stage]["components"][1]["transform"][9] = nonfinite
    with pytest.raises(ValueError, match="upstreamComponentsUnchanged"):
        validate_cumulative_state(chain_state)
