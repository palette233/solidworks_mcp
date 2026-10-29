import copy
import json
from pathlib import Path

import pytest

from demo_backend.broad_combination_coverage import (
    BroadCombinationCoverageError,
    build_broad_combination_coverage,
    discover_global_relation_release_pairs,
    validate_broad_combination_coverage,
)
from demo_backend.mechanical_interface_contracts import (
    load_calibration_contract_catalog,
    load_cleaning_weighing_contract_catalog,
    load_contextual_scanner_contract_catalog,
    load_contextual_transport_contract_catalog,
    load_native_wastecup_contract_catalog,
    load_scanner_contract_catalog,
    load_transport_contract_catalog,
    load_wastecup_contract_catalog,
)


ROOT = Path(__file__).resolve().parents[3]


def _read(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8-sig"))


def _report() -> dict:
    readiness = _read(
        "demo/global_assembly_catalog/short-term-cross-project-scope-v1/readiness.json"
    )
    groups = {row["groupId"]: row for row in readiness["groups"]}
    bases = {
        row.replace(":", "::", 1)
        for row in groups["base_environment"]["projectModuleRefs"]
    }
    known = {
        row.replace(":", "::", 1)
        for group in readiness["groups"]
        for row in group["projectModuleRefs"]
    }
    return build_broad_combination_coverage(
        readiness=readiness,
        parameterized_queue=_read(
            "demo/cross_project_substitution/parameterized-datum-placement-v1/"
            "validation-queue-20261026-v15/validation-queue.json"
        ),
        direct_catalogs=[
            load_transport_contract_catalog(ROOT),
            load_contextual_transport_contract_catalog(ROOT),
            load_scanner_contract_catalog(ROOT),
            load_contextual_scanner_contract_catalog(ROOT),
            load_calibration_contract_catalog(ROOT),
            load_cleaning_weighing_contract_catalog(ROOT),
            load_wastecup_contract_catalog(ROOT),
            load_native_wastecup_contract_catalog(ROOT),
        ],
        released_relation_pairs=discover_global_relation_release_pairs(
            ROOT, known_definition_ids=known, base_definition_ids=bases
        ),
    )


def test_matrix_covers_every_model_against_every_base_without_unknown_state():
    report = _report()
    validate_broad_combination_coverage(report)
    assert report["summary"]["movingModuleCount"] == 17
    assert report["summary"]["baseCount"] == 4
    assert report["summary"]["expectedPairCount"] == 68
    assert len(report["pairs"]) == 68
    assert sum(report["summary"]["stateCounts"].values()) == 68
    assert "semantic_port_capture_required" not in report["summary"]["stateCounts"]


def test_released_native_relation_outranks_unconfirmed_datum_fallback():
    report = _report()
    pair = next(
        row
        for row in report["pairs"]
        if row["moduleDefinitionId"] == "project02::A180"
        and row["baseDefinitionId"] == "project02::A600"
    )
    assert pair["state"] == "native_relation_released"
    assert pair["cadLaunchAllowed"] is True
    assert pair["evidence"]["releaseId"] == (
        "relation-v30-project02-a800-a180-portable-driving-20261011"
    )


def test_a600_ah00_alternate_slot_is_now_present_in_the_role_catalog():
    report = _report()
    pair = next(
        row
        for row in report["pairs"]
        if row["moduleDefinitionId"] == "project03::AH00"
        and row["baseDefinitionId"] == "project02::A600"
    )
    assert pair["state"] == "native_relation_released"
    assert pair["cadLaunchAllowed"] is True
    assert pair["evidence"]["source"] == "released_direct_interface_catalog"
    assert pair["evidence"]["releaseId"].startswith("relation-v41-")


def test_bd00_reuses_a600_50mm_slot_after_exact_pair_cad_release():
    report = _report()
    pair = next(
        row
        for row in report["pairs"]
        if row["moduleDefinitionId"] == "project01::BD00"
        and row["baseDefinitionId"] == "project02::A600"
    )
    assert pair["state"] == "native_relation_released"
    assert pair["cadLaunchAllowed"] is True
    assert pair["prototypeTopLevelPoseAllowed"] is False
    assert pair["evidence"]["source"] == "released_direct_interface_catalog"
    assert pair["evidence"]["releaseId"].startswith(
        "relation-direct-project01-bd00-project02-a600-"
    )
@pytest.mark.parametrize(
    "module_id,base_id,expected",
    [
        (
            "project02::A300",
            "project01::JJ00",
            "native_relation_released",
        ),
        (
            "project05::G000",
            "project03::AA00",
            "native_relation_released",
        ),
    ],
)
def test_gap_states_are_topology_specific(module_id, base_id, expected):
    report = _report()
    pair = next(
        row
        for row in report["pairs"]
        if row["moduleDefinitionId"] == module_id
        and row["baseDefinitionId"] == base_id
    )
    assert pair["state"] == expected
    assert pair["cadLaunchAllowed"] is (expected == "native_relation_released")
    assert pair["prototypeTopLevelPoseAllowed"] is False


def test_unreleased_rows_can_never_enable_cad_launch():
    report = _report()
    assert all(
        row["cadLaunchAllowed"]
        == (
            row["state"]
            in {"native_relation_released", "parameterized_relation_released"}
        )
        for row in report["pairs"]
    )


def test_digest_and_cardinality_are_fail_closed():
    report = _report()
    broken = copy.deepcopy(report)
    broken["pairs"].pop()
    with pytest.raises(BroadCombinationCoverageError, match="digest mismatch"):
        validate_broad_combination_coverage(broken)
