from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "six_role_direct_stage_test_target",
    ROOT / "scripts/compile_project03_six_role_direct_stage.py",
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _manifest(order_name="standard"):
    packets = []
    for index, token in enumerate(MODULE.ORDERS[order_name]):
        packets.append({
            "packetId": f"packet-{index + 1:03}",
            "targetProjectAliases": [{"projectId": MODULE.MODULE_PROJECTS[token], "moduleToken": token}],
            "cumulativeInput": (
                {"kind": "base_module_source", "instanceId": "fl9a24d063aa00-001-001"}
                if index == 0 else
                {"kind": "previous_transaction_checkpoint", "packetId": f"packet-{index:03}"}
            ),
        })
    return {"status": "ready_for_generic_executor_implementation", "packetCount": 4, "packets": packets}


def test_release_is_exact_four_verified_direct_templates():
    selected = MODULE.selected_template_entries()
    assert len(selected) == 4
    assert {row["legacyTemplateId"] for row in selected} == set(MODULE.TEMPLATE_BY_TOKEN.values())
    assert all(row["expectedMateCount"] == 3 for row in selected)
    assert not any("P000" in row["legacyTemplateId"] or "partial" in row["legacyTemplateId"] for row in selected)


def test_selection_does_not_mutate_historical_evidence_list():
    historical = copy.deepcopy(MODULE.TEMPLATES)
    selected = MODULE.selected_template_entries()
    selected[0]["evidencePath"] = "changed"
    assert MODULE.TEMPLATES == historical


@pytest.mark.parametrize("order_name", MODULE.ORDERS)
def test_compiler_preserves_explicit_order_and_direct_mode(order_name):
    payload = MODULE.build_compile_payload(order_name, "test-context", "release.json")
    assert payload["autoOrderByReleasedDependencies"] is False
    assert payload["overwrite"] is False
    assert payload["relationExecutionMode"] == "direct_installation"
    assert len(payload["requirements"]) == 5
    assert "AA00" in payload["requirements"][0]
    assert [next(token for token in MODULE.MODULE_PROJECTS if token in text)
            for text in payload["requirements"][1:]] == list(MODULE.ORDERS[order_name])
    assert not any("P000" in text for text in payload["requirements"])


@pytest.mark.parametrize("order_name", MODULE.ORDERS)
def test_manifest_keeps_exact_order_from_base(order_name):
    assert all(MODULE.validate_direct_manifest(_manifest(order_name), MODULE.ORDERS[order_name]).values())


def test_role_sort_cannot_hide_the_permutation():
    with pytest.raises(ValueError, match="requestedOrderPreserved"):
        MODULE.validate_direct_manifest(_manifest("standard"), MODULE.ORDERS["reordered"])


def test_wrong_project_alias_is_rejected():
    manifest = _manifest()
    manifest["packets"][0]["targetProjectAliases"][0]["projectId"] = "project03"
    with pytest.raises(ValueError, match="项目正确"):
        MODULE.validate_direct_manifest(manifest, MODULE.ORDERS["standard"])


def test_missing_or_extra_packet_is_rejected():
    manifest = _manifest()
    manifest["packets"].pop()
    with pytest.raises(ValueError, match="exactFourPackets"):
        MODULE.validate_direct_manifest(manifest, MODULE.ORDERS["standard"])


def test_old_checkpoint_must_not_replace_clean_base_start():
    manifest = _manifest()
    manifest["packets"][0]["cumulativeInput"] = {"kind": "previous_transaction_checkpoint", "packetId": "old-final"}
    with pytest.raises(ValueError, match="startsFromRegisteredBase"):
        MODULE.validate_direct_manifest(manifest, MODULE.ORDERS["standard"])


def test_other_base_is_rejected():
    manifest = _manifest()
    manifest["packets"][0]["cumulativeInput"]["instanceId"] = "fl9a24d062a600-001-001"
    with pytest.raises(ValueError, match="baseIsAA00"):
        MODULE.validate_direct_manifest(manifest, MODULE.ORDERS["standard"])


def test_cumulative_input_cannot_skip_previous_packet():
    manifest = _manifest()
    manifest["packets"][2]["cumulativeInput"]["packetId"] = "packet-001"
    with pytest.raises(ValueError, match="remainingPacketsConsumePreviousCheckpoint"):
        MODULE.validate_direct_manifest(manifest, MODULE.ORDERS["standard"])


def test_demo_cannot_be_mixed_into_direct_stage():
    manifest = _manifest()
    manifest["packets"][3]["targetProjectAliases"] = [{"projectId": "project05", "moduleToken": "P000"}]
    with pytest.raises(ValueError, match="项目正确"):
        MODULE.validate_direct_manifest(manifest, MODULE.ORDERS["standard"])


def test_blocked_manifest_is_not_reported_ready():
    manifest = _manifest()
    manifest["status"] = "blocked"
    with pytest.raises(ValueError, match="manifestReady"):
        MODULE.validate_direct_manifest(manifest, MODULE.ORDERS["standard"])


def test_distinct_orders_have_same_modules_and_keep_transport_before_scanner():
    standard = MODULE.ORDERS["standard"]
    reordered = MODULE.ORDERS["reordered"]
    assert standard != reordered
    assert set(standard) == set(reordered)
    assert all(order.index("SS00") < order.index("AI00") for order in (standard, reordered))
