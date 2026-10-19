import json
from pathlib import Path

from demo_backend.global_cad_transaction_packets import (
    compile_global_cad_transaction_manifest,
)
from demo_backend.project02_positioning_standard import (
    load_project02_positioning_standard,
)


WORKSPACE = Path(__file__).resolve().parents[3]


def _load(relative: str):
    return json.loads((WORKSPACE / relative).read_text(encoding="utf-8-sig"))


def test_project05_builds_eight_endpoint_complete_generic_packets():
    catalog = _load("demo/global_assembly_catalog/v1/global_module_catalog.json")
    context = _load("demo/global_assembly_contexts/project05-full-static-graph-v1.json")

    manifest = compile_global_cad_transaction_manifest(catalog, context)

    assert manifest["status"] == "ready_for_generic_executor_implementation"
    assert manifest["projectSequenceRequired"] is False
    assert manifest["packetCount"] == 8
    assert not manifest["blockers"]
    assert all(packet["status"] == "ready_for_executor_implementation" for packet in manifest["packets"])
    assert manifest["packets"][0]["cumulativeInput"]["kind"] == "base_module_source"
    assert manifest["packets"][1]["cumulativeInput"] == {
        "kind": "previous_transaction_checkpoint",
        "packetId": "packet-001",
    }
    assert all(
        all(role["candidates"] for role in mate["endpointsA"]["roles"])
        and all(role["candidates"] for role in mate["endpointsB"]["roles"])
        for packet in manifest["packets"]
        for connection in packet["connections"]
        for mate in connection["mates"]
    )
    distance_mate = next(
        mate
        for mate in manifest["packets"][0]["connections"][0]["mates"]
        if mate["mateName"] == "距离1"
    )
    assert distance_mate["advancedOptions"]["advancedOptions"][
        "DistanceFlipDimension"
    ] is True


def test_project02_packets_retain_underconstraint_blockers():
    catalog = _load("demo/global_assembly_catalog/v1/global_module_catalog.json")
    context = _load("demo/global_assembly_contexts/project02-full-static-graph-v1.json")

    manifest = compile_global_cad_transaction_manifest(catalog, context)

    assert manifest["status"] == "blocked"
    assert manifest["packetCount"] == 9
    blocked = [packet for packet in manifest["packets"] if packet["status"] == "blocked"]
    assert [packet["packetId"] for packet in blocked[:2]] == ["packet-001", "packet-002"]
    assert any(
        blocker["code"] == "DAG_STEP_NOT_EXECUTION_READY"
        for blocker in manifest["blockers"]
    )
    assert manifest["executionBoundary"]["solidWorksExecuted"] is False
    assert manifest["executionBoundary"]["collisionStatus"] == "not_evaluated"


def test_project02_packets_are_ready_only_after_explicit_standard_selection():
    catalog = _load("demo/global_assembly_catalog/v1/global_module_catalog.json")
    context = _load(
        "demo/global_assembly_contexts/project02-a800-a180-readiness-v1.json"
    )

    manifest = compile_global_cad_transaction_manifest(
        catalog,
        context,
        positioning_standard=load_project02_positioning_standard(),
    )

    assert manifest["status"] == "ready_for_generic_executor_implementation"
    assert manifest["positioningStandard"]["explicitlySelected"] is True
    assert manifest["positioningStandard"]["scope"] == "project02-only"
    assert not manifest["blockers"]
    bound = {
        packet["positioningStandardBinding"]["moduleToken"]: packet
        for packet in manifest["packets"]
        if packet["positioningStandardBinding"]
    }
    assert set(bound) == {"A800", "A180"}
    assert all(packet["status"] == "ready_for_executor_implementation" for packet in manifest["packets"])


def test_relation_packet_records_both_existing_module_tokens():
    catalog = _load(
        "demo/global_assembly_catalog/v1/global_module_catalog.relation-v2-preview.json"
    )
    context = _load(
        "demo/global_assembly_contexts/project02-full-static-graph-spacing-validation-v2.json"
    )

    manifest = compile_global_cad_transaction_manifest(catalog, context)
    packet = manifest["packets"][-1]

    assert packet["operation"] == "VERIFY_RELATION"
    assert packet["relationModuleTokens"] == ["A500", "A700"]
    assert packet["status"] == "ready_for_executor_implementation"


def test_relation_packet_blocks_state_dependent_validation_before_cad():
    catalog = _load(
        "demo/global_assembly_catalog/v1/global_module_catalog.relation-v2-preview.json"
    )
    context = _load(
        "demo/global_assembly_contexts/project02-full-static-graph-spacing-validation-v2.json"
    )
    registry = _load(
        "demo/global_assembly_catalog/relation-validation-preconditions-v1.json"
    )

    manifest = compile_global_cad_transaction_manifest(
        catalog,
        context,
        validation_precondition_registry=registry,
        validation_precondition_registry_path=(
            "demo/global_assembly_catalog/relation-validation-preconditions-v1.json"
        ),
    )
    packet = manifest["packets"][-1]

    assert manifest["status"] == "blocked"
    assert packet["status"] == "blocked"
    assert packet["validationPreconditions"][0]["status"] == "evidence_required"
    assert any(
        blocker["code"]
        == "VALIDATION_EXTERNAL_PLACEMENT_EQUIVALENCE_REQUIRED"
        for blocker in packet["blockers"]
    )
    assert manifest["validationPreconditionRegistryBinding"]["registryDigest"]


def test_project02_a700_unsafe_driver_is_revoked_before_cad():
    catalog = _load(
        "demo/global_assembly_catalog/releases/"
        "relation-v33-project02-five-addon-portable-driving-20261011/"
        "global_module_catalog.json"
    )
    context = _load(
        "demo/global_assembly_contexts/project02-release-five-addon-v5.json"
    )
    registry = _load("demo/global_assembly_catalog/relation-driving-safety-v1.json")

    manifest = compile_global_cad_transaction_manifest(
        catalog,
        context,
        driving_safety_registry=registry,
        driving_safety_registry_path=(
            "demo/global_assembly_catalog/relation-driving-safety-v1.json"
        ),
    )
    packet = next(
        row
        for row in manifest["packets"]
        if any(
            connection.get("globalTemplateId")
            == "template/project02/a700-to-a600-nonanchor-driving-v1/32804d30f3"
            for connection in row["connections"]
        )
    )

    assert manifest["status"] == "blocked"
    assert packet["status"] == "blocked"
    assert packet["drivingSafetyAssessments"][0]["status"] == (
        "blocked_external_pose_branch"
    )
    assert any(
        blocker["code"]
        == "DRIVING_TEMPLATE_EXTERNAL_POSE_EQUIVALENCE_REQUIRED"
        for blocker in packet["blockers"]
    )
    assert manifest["drivingSafetyRegistryBinding"]["registryDigest"]


def test_project02_a700_explicit_calibrated_fallback_compiles_as_nonportable():
    catalog = _load(
        "demo/global_assembly_catalog/releases/"
        "relation-v33-project02-five-addon-portable-driving-20261011/"
        "global_module_catalog.json"
    )
    context = _load(
        "demo/global_assembly_contexts/project02-release-five-addon-v5.json"
    )
    registry = _load("demo/global_assembly_catalog/relation-driving-safety-v1.json")

    manifest = compile_global_cad_transaction_manifest(
        catalog,
        context,
        driving_safety_registry=registry,
        driving_strategy_selections=[
            {
                "globalTemplateId": (
                    "template/project02/a700-to-a600-nonanchor-driving-v1/"
                    "32804d30f3"
                ),
                "strategyId": (
                    "project02/a700/prototype-calibrated-static-snapshot-v1"
                ),
                "confirmed": True,
            }
        ],
    )
    packet = manifest["packets"][3]

    assert manifest["status"] == "ready_for_generic_executor_implementation"
    assert packet["executionStrategy"] == "calibrated_static_snapshot_insert"
    assert packet["drivingExecutionOverride"]["portable"] is False
    assert packet["drivingExecutionOverride"]["scope"] == "project02-only"
    assert packet["connections"][0]["effectiveMateGraphCandidate"].endswith(
        "project02_service_installations_v1/A700/static_snapshot_effective.json"
    )
    assert "case_anchor_pose_match" in packet["verificationRequirements"]

