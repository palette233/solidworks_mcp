from __future__ import annotations

import copy
import importlib.util
import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("six_role_order_comparison_target", ROOT / "scripts/compare_six_role_support_orders.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
from demo_backend.rigid_transform_interpolation import compose_transform

IDENTITY = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]


@pytest.fixture
def data() -> list[dict]:
    components = []
    for index, token in enumerate(MODULE.TOKENS):
        transform = list(IDENTITY)
        transform[9:12] = [index * 0.12, index * 0.05, index * 0.07]
        components.append({"name": f"CAD{token}.001-1", "sourcePath": f"D:/fixture/project/{token}.SLDASM",
                           "transform": transform, "isFixed": token == "AA00", "constrainedStatus": 3,
                           "configuration": "Default", "solvingState": 0})
    mates = [{"name": f"MATE_{index}", "mateType": 5 if index % 2 else 0, "alignment": 0,
              "isSuppressed": False, "errorCode": 0, "isWarning": False,
              "dimensionSystemValue": 0.12 if index % 2 else None} for index in range(15)]
    closure = {"schemaVersion": "six-role-support-position-chain-closure/v1", "success": True,
               "status": "PASSED_SIX_ROLE_SUPPORT_POSITION_CHAIN_DEMO", "checks": {"cadPassed": True},
               "topLevelModuleCount": 6, "moduleSequence": list(MODULE.TOKENS), "timingSeconds": {"totalMeasuredExecution": 100}}
    state = {"success": True, "observed": {"readOnly": True, "components": components, "allTopLevelMates": mates}}
    reordered = copy.deepcopy(closure)
    reordered["moduleSequence"] = ["AA00", "AG00", "BD00", "SS00", "AI00", "P000"]
    return [closure, state, reordered, copy.deepcopy(state)]


def assert_pass(data: list[dict]) -> dict:
    report = MODULE.compare_observations(*data)
    assert report["checks"] and all(report["checks"].values()), report["checks"]
    return report


def test_valid_orders_have_equivalent_geometry_and_fifteen_mates(data: list[dict]) -> None:
    before = copy.deepcopy(data)
    report = assert_pass(data)
    assert len(report["moduleComparisons"]) == 6
    assert len(report["mateComparisons"]) == 15
    assert data == before


def test_common_world_rotation_and_translation_are_ignored(data: list[dict]) -> None:
    world_transform = [0, 1, 0, -1, 0, 0, 0, 0, 1, 4, -3, 2, 1, 0, 0, 0]
    for component in data[3]["observed"]["components"]:
        component["transform"] = compose_transform(world_transform, component["transform"])
    report = assert_pass(data)
    assert max(row["translationErrorMeters"] for row in report["moduleComparisons"]) < 1e-12


def test_enumeration_order_and_instance_suffixes_are_not_geometry(data: list[dict]) -> None:
    data[3]["observed"]["components"].reverse()
    data[3]["observed"]["allTopLevelMates"].reverse()
    for component in data[3]["observed"]["components"]:
        component["name"] = component["name"].replace(".001-1", ".001-2")
    assert_pass(data)


def test_same_order_is_not_a_variation_test(data: list[dict]) -> None:
    data[2]["moduleSequence"] = data[0]["moduleSequence"]
    assert MODULE.compare_observations(*data)["checks"]["actualOrdersDiffer"] is False


@pytest.mark.parametrize("index", range(6))
def test_whole_source_path_identity_is_required(data: list[dict], index: int) -> None:
    row = data[3]["observed"]["components"][index]
    row["sourcePath"] = row["sourcePath"].replace("/project/", "/another-project/")
    report = MODULE.compare_observations(*data)
    assert report["checks"]["moduleSourceIdentitiesMatch"] is False


def test_windows_path_case_and_separator_do_not_change_identity(data: list[dict]) -> None:
    for row in data[3]["observed"]["components"]:
        row["sourcePath"] = row["sourcePath"].upper().replace("/", "\\")
    assert_pass(data)


@pytest.mark.parametrize("path", [None, "", "P000.SLDASM", "relative/P000.SLDASM"])
def test_missing_or_relative_source_path_fails(data: list[dict], path: object) -> None:
    for state in (data[1], data[3]):
        state["observed"]["components"][-1]["sourcePath"] = path
    assert MODULE.compare_observations(*data)["checks"]["moduleSourceIdentitiesMatch"] is False


@pytest.mark.parametrize("field", ["configuration", "solvingState", "constrainedStatus"])
def test_both_missing_component_semantics_do_not_count_as_equal(data: list[dict], field: str) -> None:
    for state in (data[1], data[3]):
        state["observed"]["components"][1].pop(field)
    report = MODULE.compare_observations(*data)
    assert report["checks"]["componentSemanticsEquivalent"] is False
    assert report["moduleComparisons"][1]["componentSemanticsObservedAndValid"] is False


@pytest.mark.parametrize("field,value", [
    ("configuration", None), ("configuration", ""), ("configuration", " "), ("configuration", 1),
    ("solvingState", None), ("solvingState", True), ("solvingState", "0"), ("solvingState", -1),
    ("solvingState", 2), ("solvingState", 999), ("solvingState", float("nan")),
    ("constrainedStatus", None), ("constrainedStatus", True), ("constrainedStatus", "3"),
    ("constrainedStatus", 0), ("constrainedStatus", 1), ("constrainedStatus", 4),
    ("constrainedStatus", 5), ("constrainedStatus", 6), ("constrainedStatus", 7),
    ("constrainedStatus", 999),
])
def test_both_invalid_component_semantics_do_not_count_as_equal(data: list[dict], field: str, value: object) -> None:
    for state in (data[1], data[3]):
        state["observed"]["components"][1][field] = value
    assert MODULE.compare_observations(*data)["checks"]["componentSemanticsEquivalent"] is False


@pytest.mark.parametrize("field,value", [("configuration", "Other"), ("solvingState", 1), ("constrainedStatus", 2)])
def test_different_observed_component_semantics_fail(data: list[dict], field: str, value: object) -> None:
    data[3]["observed"]["components"][1][field] = value
    assert MODULE.compare_observations(*data)["checks"]["componentSemanticsEquivalent"] is False


@pytest.mark.parametrize("amount,passes", [(0.5e-6, True), (2e-6, False)])
def test_translation_tolerance_is_one_micrometre(data: list[dict], amount: float, passes: bool) -> None:
    data[3]["observed"]["components"][2]["transform"][9] += amount
    assert MODULE.compare_observations(*data)["checks"]["relativePosesEquivalent"] is passes


@pytest.mark.parametrize("angle,passes", [(0.5e-6, True), (2e-6, False)])
def test_rotation_tolerance_is_one_microradian(data: list[dict], angle: float, passes: bool) -> None:
    row = data[3]["observed"]["components"][2]
    row["transform"][:9] = [math.cos(angle), math.sin(angle), 0, -math.sin(angle), math.cos(angle), 0, 0, 0, 1]
    assert MODULE.compare_observations(*data)["checks"]["relativePosesEquivalent"] is passes


@pytest.mark.parametrize("index,value", [(0, -1), (0, 0.9), (9, float("nan")), (9, float("inf")), (12, 2), (13, 1), (9, True)])
def test_invalid_rigid_transforms_fail(data: list[dict], index: int, value: object) -> None:
    data[3]["observed"]["components"][2]["transform"][index] = value
    assert MODULE.compare_observations(*data)["checks"]["relativePosesEquivalent"] is False


@pytest.mark.parametrize("index", [0, 2])
def test_only_base_may_be_fixed(data: list[dict], index: int) -> None:
    data[3]["observed"]["components"][index]["isFixed"] = index != 0
    assert MODULE.compare_observations(*data)["checks"]["onlyAA00Fixed"] is False


@pytest.mark.parametrize("count", [14, 16])
def test_exactly_fifteen_mates_required(data: list[dict], count: int) -> None:
    rows = data[3]["observed"]["allTopLevelMates"]
    if count == 14:
        rows.pop()
    else:
        rows.append({**rows[0], "name": "UNREQUESTED"})
    assert MODULE.compare_observations(*data)["checks"]["fifteenNamedMatesEach"] is False


@pytest.mark.parametrize("field,value", [("mateType", 1), ("alignment", 1), ("isSuppressed", True), ("errorCode", 1), ("isWarning", True), ("dimensionSystemValue", 0.2)])
def test_changed_mate_type_parameter_or_state_fails(data: list[dict], field: str, value: object) -> None:
    data[3]["observed"]["allTopLevelMates"][1][field] = value
    assert MODULE.compare_observations(*data)["checks"]["mateTypesParametersStatesEquivalent"] is False


@pytest.mark.parametrize("field,value", [("isSuppressed", True), ("errorCode", 1), ("dimensionSystemValue", None), ("dimensionSystemValue", float("nan"))])
def test_matching_but_invalid_mates_cannot_pass(data: list[dict], field: str, value: object) -> None:
    for state in (data[1], data[3]):
        state["observed"]["allTopLevelMates"][1][field] = value
    assert MODULE.compare_observations(*data)["checks"]["mateTypesParametersStatesEquivalent"] is False


def test_missing_mate_parameter_does_not_equal_null(data: list[dict]) -> None:
    for state in (data[1], data[3]):
        state["observed"]["allTopLevelMates"][0].pop("dimensionSystemValue")
    assert MODULE.compare_observations(*data)["checks"]["mateTypesParametersStatesEquivalent"] is False


def populate(root: Path, closure: dict, state: dict, payload: bytes) -> None:
    root.mkdir()
    assembly = root / "result.SLDASM"
    assembly.write_bytes(payload)
    closure = copy.deepcopy(closure)
    state = copy.deepcopy(state)
    closure.update(outputAssemblyPath=str(assembly), outputAssemblySha256=MODULE.file_sha(assembly))
    state.update(assemblyPath=str(assembly), assemblySha256=MODULE.file_sha(assembly))
    (root / "chain-closure.json").write_text(json.dumps(closure), encoding="utf-8")
    (root / "read-only-chain-verification.json").write_text(json.dumps(state), encoding="utf-8")


def test_distinct_output_file_hashes_can_pass_and_inputs_are_hashed(tmp_path: Path, data: list[dict]) -> None:
    first, second = tmp_path / "standard", tmp_path / "reordered"
    populate(first, *data[:2], b"first CAD file")
    populate(second, *data[2:], b"different CAD file")
    report = MODULE.build_comparison(first, second)
    assert report["success"] is True
    assert report["outputBindings"][0]["sha256"] != report["outputBindings"][1]["sha256"]
    assert all(row["sha256"] for row in report["inputEvidence"])
    assert len(report["inputEvidence"]) == 4
    assert report["durationSeconds"] >= 0
    MODULE.write_report(tmp_path / "comparison", report)
    assert (tmp_path / "comparison/order-comparison-CN.md").exists()


def test_tampered_output_is_a_preserved_failure_report(tmp_path: Path, data: list[dict]) -> None:
    first, second = tmp_path / "standard", tmp_path / "reordered"
    populate(first, *data[:2], b"first")
    populate(second, *data[2:], b"second")
    (second / "result.SLDASM").write_bytes(b"modified")
    report = MODULE.build_comparison(first, second)
    assert report["success"] is False
    assert "bothOutputFilesBoundIndependently" in report["failedChecks"]
    MODULE.write_report(tmp_path / "comparison", report)
    saved = json.loads((tmp_path / "comparison/order-comparison.json").read_text(encoding="utf-8"))
    assert saved["status"] == "FAILED_SIX_ROLE_ORDER_EQUIVALENCE"
    with pytest.raises(FileExistsError):
        MODULE.write_report(tmp_path / "comparison", report)


def test_missing_inputs_produce_failure_report(tmp_path: Path) -> None:
    report = MODULE.build_comparison(tmp_path / "missing-a", tmp_path / "missing-b")
    assert report["success"] is False
    assert report["errors"]
    MODULE.write_report(tmp_path / "comparison", report)
    assert (tmp_path / "comparison/order-comparison.json").exists()


def test_malformed_evidence_structure_is_preserved_as_failure(tmp_path: Path, data: list[dict]) -> None:
    first, second = tmp_path / "standard", tmp_path / "reordered"
    populate(first, *data[:2], b"first")
    populate(second, *data[2:], b"second")
    (second / "read-only-chain-verification.json").write_text('{"observed": [1, 2]}', encoding="utf-8")
    report = MODULE.build_comparison(first, second)
    assert report["success"] is False
    assert report["checks"]["inputStructureValid"] is False
    MODULE.write_report(tmp_path / "comparison", report)


@pytest.mark.parametrize("name", ["order-comparison.json", "order-comparison-CN.md"])
def test_any_existing_report_prevents_overwrite(tmp_path: Path, name: str) -> None:
    (tmp_path / name).write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError):
        MODULE.write_report(tmp_path, {})
    assert (tmp_path / name).read_text(encoding="utf-8") == "keep"
