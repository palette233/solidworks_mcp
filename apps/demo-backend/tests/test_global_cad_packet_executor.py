import copy
import hashlib
import json
from pathlib import Path

import pytest

from demo_backend.global_cad_packet_executor import (
    GlobalCadPacketExecutionError,
    _resolve_effective_graph,
    build_global_cad_packet_execution_plan,
)


WORKSPACE = Path(__file__).resolve().parents[3]


def _load(relative: str):
    return json.loads((WORKSPACE / relative).read_text(encoding="utf-8-sig"))


def _digest(value):
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def test_effective_graph_resolver_prefers_nonprototype_graph_before_legacy(tmp_path):
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    nonprototype = evidence_dir / "assembly_plan_effective.nonprototype.json"
    legacy = evidence_dir / "effective_graph.json"
    nonprototype.write_text("{}", encoding="utf-8")
    legacy.write_text("{}", encoding="utf-8")

    resolved = _resolve_effective_graph(
        tmp_path,
        "evidence/assembly_plan_effective.json",
    )

    assert resolved == nonprototype


def test_effective_graph_resolver_keeps_legacy_fallback(tmp_path):
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    legacy = evidence_dir / "effective_graph.json"
    legacy.write_text("{}", encoding="utf-8")

    resolved = _resolve_effective_graph(
        tmp_path,
        "evidence/assembly_plan_effective.json",
    )

    assert resolved == legacy


def test_first_project05_packet_builds_project_independent_execution_plan(tmp_path):
    manifest = _load(
        "demo/global_assembly_contexts/project05-full-static-graph-v1.cad-transaction-manifest.json"
    )

    plan = build_global_cad_packet_execution_plan(
        WORKSPACE,
        manifest,
        "packet-001",
        output_path=tmp_path / "result.SLDASM",
    )

    assert plan["schemaVersion"] == "global-cad-packet-execution-plan/v1"
    assert plan["projectSequenceRequired"] is False
    assert plan["targetModuleToken"] == "D000"
    assert plan["sourceAssemblyPath"].endswith("FL9C254098A000.001.SLDASM")
    assert plan["cumulativeInputKind"] == "base_module_source"
    preparation = plan["sourcePreparation"]
    assert preparation["mode"] == "wrap_root_module_as_top_level_context"
    assert preparation["required"] is True
    assert preparation["baseContextModuleToken"] == "A000"
    assert preparation["baseContextTransform"] == [
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
    ]
    assert preparation["cachePolicy"] == "content_addressed_read_only_reuse"
    assert preparation["cacheRootRelativePath"].endswith("base_wrapper_cache")
    assert preparation["cacheDescriptor"]["inputs"] == {
        "sourceAssemblySha256": plan["sourceAssemblySha256"],
        "baseContextModuleToken": "A000",
        "baseContextTransform": preparation["baseContextTransform"],
        "adapterVersion": "create-global-cad-base-wrapper/v1",
    }
    assert len(preparation["cacheDescriptor"]["cacheKey"]) == 64
    assert plan["effectiveMateGraphPath"].endswith(
        "project05_global_installation_ports_v1\\D000\\assembly_plan_effective.json"
    )
    assert plan["collisionStatus"] == "not_evaluated"


def test_cross_project_slot_uses_target_alias_instead_of_slot_owner_project(tmp_path):
    manifest = _load(
        "demo/global_assembly_contexts/"
        "project02-a600-ah00-operation-side-v1.cad-transaction-manifest.json"
    )

    plan = build_global_cad_packet_execution_plan(
        WORKSPACE,
        manifest,
        "packet-001",
        output_path=tmp_path / "a600-ah00-result.SLDASM",
    )

    assert plan["targetModuleAlias"] == "AH00"
    assert plan["targetModuleToken"] == "FL9A24D063AH00"
    assert plan["sourcePreparation"]["baseContextModuleToken"] == "A600"
    assert plan["requestedMateCount"] == 3
    assert plan["releaseAuthority"]["status"] == "verified"


def test_released_project05_packet_revalidates_authority_and_width_mate(tmp_path):
    manifest = _load(
        "demo/global_assembly_contexts/project05-a000-d000-v7-driving-v1/"
        "cad-transaction-manifest.json"
    )

    plan = build_global_cad_packet_execution_plan(
        WORKSPACE,
        manifest,
        "packet-001",
        output_path=tmp_path / "released-result.SLDASM",
    )

    assert plan["releaseAuthority"]["status"] == "verified"
    assert plan["relationReleaseBinding"]["releaseId"] == (
        "relation-v7-project05-driving-independent-20261011"
    )
    assert plan["effectiveGraphMateCoverage"]["status"] == "exact"
    assert plan["requestedMateCount"] == 3
    assert plan["requestedDrivingMateCount"] == 3
    assert plan["requestedValidationRelationCount"] == 0
    assert plan["requestedRelationCount"] == 3
    assert plan["effectiveGraphMateCoverage"]["graphTargetMateCount"] == 3
    assert "宽度17" in {
        row["mateName"]
        for row in plan["effectiveGraphMateCoverage"]["graphTargetMates"]
    }


def test_structurally_complete_free_slot_is_rebuildable():
    from demo_backend.global_cad_packet_executor import _is_context_insert_rebuildable

    assert _is_context_insert_rebuildable(
        {
            "MateType": 21,
            "IsBasicTwoFaceRebuildable": False,
            "Endpoints": [{}, {}],
            "AdvancedOptions": {"SlotConstraint": 0},
        }
    ) is True
    assert _is_context_insert_rebuildable(
        {
            "MateType": 21,
            "IsBasicTwoFaceRebuildable": False,
            "Endpoints": [{}, {}],
            "AdvancedOptions": {},
        }
    ) is False


def test_released_packet_rejects_unauthorized_template_even_with_fresh_digests(tmp_path):
    manifest = copy.deepcopy(
        _load(
            "demo/global_assembly_contexts/project05-a000-d000-v7-driving-v1/"
            "cad-transaction-manifest.json"
        )
    )
    packet = manifest["packets"][0]
    packet["connections"][0]["globalTemplateId"] = "template/unreleased/diagnostic"
    packet["packetDigest"] = _digest(
        {key: value for key, value in packet.items() if key != "packetDigest"}
    )
    manifest["manifestDigest"] = _digest(
        {key: value for key, value in manifest.items() if key != "manifestDigest"}
    )

    with pytest.raises(GlobalCadPacketExecutionError, match="未获驱动授权"):
        build_global_cad_packet_execution_plan(
            WORKSPACE,
            manifest,
            "packet-001",
            output_path=tmp_path / "rejected.SLDASM",
        )


def test_later_packet_requires_explicit_previous_checkpoint(tmp_path):
    manifest = _load(
        "demo/global_assembly_contexts/project05-full-static-graph-v1.cad-transaction-manifest.json"
    )

    with pytest.raises(GlobalCadPacketExecutionError, match="上一事务检查点"):
        build_global_cad_packet_execution_plan(
            WORKSPACE,
            manifest,
            "packet-002",
            output_path=tmp_path / "result.SLDASM",
        )


def test_project03_first_packet_reuses_verified_composite_base_context(tmp_path):
    manifest = _load(
        "demo/global_assembly_contexts/project03-cross-family-smoke-v1.cad-transaction-manifest.json"
    )

    plan = build_global_cad_packet_execution_plan(
        WORKSPACE,
        manifest,
        "packet-001",
        output_path=tmp_path / "project03-result.SLDASM",
    )

    assert plan["targetModuleAlias"] == "AE00"
    assert plan["targetModuleToken"] == "FL9A24D063AE00"
    assert plan["sourceAssemblyPath"].endswith(
        "project03_AE00_first_increment_v1\\step00_AA00_AF00_context.SLDASM"
    )
    assert plan["sourcePreparation"]["mode"] == "use_verified_composite_base_context"
    assert plan["sourcePreparation"]["required"] is False
    assert plan["sourcePreparation"]["baseContextModuleTokens"] == [
        "FL9A24D063AA00",
        "FL9A24D063AF00",
    ]
    assert Path(plan["sourcePreparation"]["evidencePath"]).is_file()


def test_released_ag00_first_packet_uses_required_aa00_not_historical_context(tmp_path):
    """A reordered released chain must not require unrelated prototype modules."""
    manifest = _load(
        "demo/global_assembly_contexts/"
        "six-role-project03-direct-20261023-v1-reordered.cad-transaction-manifest.json"
    )
    manifest_before = copy.deepcopy(manifest)
    graph_path = WORKSPACE / (
        "demo/global_assembly_catalog/coverage-v2/ag00-three-datum-candidate-v1/"
        "assembly_plan_effective.nonprototype.json"
    )
    graph_bytes = graph_path.read_bytes()
    graph = json.loads(graph_bytes.decode("utf-8-sig"))
    assert len(graph["BaseGraphPolicy"]["moduleTokens"]) == 5
    plan = build_global_cad_packet_execution_plan(
        WORKSPACE, manifest, "packet-001", output_path=tmp_path / "ag00-first.SLDASM",
    )
    assert plan["releaseAuthority"]["status"] == "verified"
    assert plan["targetModuleAlias"] == "AG00"
    assert plan["effectiveGraphMateCoverage"]["status"] == "exact"
    assert plan["requestedDrivingMateCount"] == 3
    assert plan["sourcePreparation"]["mode"] == "wrap_root_module_as_top_level_context"
    assert plan["sourcePreparation"]["baseContextModuleToken"] == "FL9A24D063AA00"
    assert plan["sourceAssemblyPath"].endswith("FL9A24D063AA00.001.SLDASM")
    projected = plan["effectiveMateGraphExecutionView"]
    assert projected["BaseGraphPolicy"]["moduleTokens"] == ["FL9A24D063AA00"]
    assert {row["ModuleToken"] for row in projected["Modules"]} == {"FL9A24D063AA00", "FL9A24D063AG00"}
    assert not projected["EditPolicy"]["caseAnchoredModuleTokens"]
    assert manifest == manifest_before
    assert graph_path.read_bytes() == graph_bytes


def test_released_single_context_projection_rejects_wrong_registered_root(tmp_path):
    manifest = copy.deepcopy(_load(
        "demo/global_assembly_contexts/"
        "six-role-project03-direct-20261023-v1-reordered.cad-transaction-manifest.json"
    ))
    packet = manifest["packets"][0]
    packet["cumulativeInput"]["cadSources"][0]["path"] = packet["targetCadSources"][0]["path"]
    packet["packetDigest"] = _digest({key: value for key, value in packet.items() if key != "packetDigest"})
    manifest["manifestDigest"] = _digest({key: value for key, value in manifest.items() if key != "manifestDigest"})
    with pytest.raises(GlobalCadPacketExecutionError, match="唯一基座与登记的原始输入文件不一致"):
        build_global_cad_packet_execution_plan(
            WORKSPACE, manifest, "packet-001", output_path=tmp_path / "wrong-base.SLDASM",
        )


def test_later_packet_uses_checkpoint_without_root_wrapper(tmp_path):
    manifest = _load(
        "demo/global_assembly_contexts/project05-full-static-graph-v1.cad-transaction-manifest.json"
    )
    checkpoint = tmp_path / "packet-001.SLDASM"
    checkpoint.write_bytes(b"checkpoint")

    plan = build_global_cad_packet_execution_plan(
        WORKSPACE,
        manifest,
        "packet-002",
        output_path=tmp_path / "result.SLDASM",
        input_checkpoint=checkpoint,
    )

    assert plan["cumulativeInputKind"] == "previous_transaction_checkpoint"
    assert plan["sourcePreparation"] == {
        "mode": "use_previous_committed_checkpoint",
        "required": False,
    }
    assert plan["sourceAssemblyPath"] == str(checkpoint.resolve())


def test_project03_ai00_splits_driving_mates_from_read_only_validations(tmp_path):
    manifest = _load(
        "demo/global_assembly_contexts/project03-aa00-ae00-ad00-ai00-v13-driving-v1/"
        "cad-transaction-manifest.json"
    )
    checkpoint = tmp_path / "packet-002.SLDASM"
    checkpoint.write_bytes(b"checkpoint")

    plan = build_global_cad_packet_execution_plan(
        WORKSPACE,
        manifest,
        "packet-003",
        output_path=tmp_path / "result.SLDASM",
        input_checkpoint=checkpoint,
    )

    coverage = plan["effectiveGraphMateCoverage"]
    assert plan["requestedMateCount"] == 3
    assert plan["requestedDrivingMateCount"] == 3
    assert plan["requestedValidationRelationCount"] == 2
    assert plan["requestedRelationCount"] == 5
    assert coverage["requestedMateCount"] == 3
    assert coverage["graphTargetMateCount"] == 3
    assert coverage["requestedValidationRelationCount"] == 2
    assert coverage["graphMatchedValidationRelationCount"] == 2
    assert {row["relationName"] for row in coverage["validationRelations"]} == {
        "距离1",
        "距离2",
    }


def test_blocked_packet_cannot_build_execution_plan(tmp_path):
    manifest = _load(
        "demo/global_assembly_contexts/project02-full-static-graph-v1.cad-transaction-manifest.json"
    )

    with pytest.raises(GlobalCadPacketExecutionError, match="尚未满足执行条件"):
        build_global_cad_packet_execution_plan(
            WORKSPACE,
            manifest,
            "packet-001",
            output_path=tmp_path / "result.SLDASM",
        )


def test_project01_combined_packet_requires_exact_three_mate_graph_coverage(tmp_path):
    manifest = _load(
        "demo/global_assembly_contexts/"
        "project01-cross-family-relation-v2-v1.cad-transaction-manifest.json"
    )
    checkpoint = tmp_path / "packet-001.SLDASM"
    checkpoint.write_bytes(b"checkpoint")

    plan = build_global_cad_packet_execution_plan(
        WORKSPACE,
        manifest,
        "packet-002",
        output_path=tmp_path / "result.SLDASM",
        input_checkpoint=checkpoint,
    )

    assert plan["targetModuleToken"] == "GN00"
    assert plan["connectionCount"] == 2
    assert plan["requestedMateCount"] == 3
    assert plan["effectiveGraphMateCoverage"]["status"] == "exact"
    assert plan["effectiveGraphMateCoverage"]["requestedMateCount"] == 3
    assert plan["effectiveGraphMateCoverage"]["graphTargetMateCount"] == 3
    assert {
        row["mateName"] for row in plan["effectiveGraphMateCoverage"]["requestedMates"]
    } == {"重合6", "同心11", "平行1"}
    execution_view = plan["effectiveMateGraphExecutionView"]
    assert {
        row["ModuleToken"] for row in execution_view["Modules"]
    } == {"GN00", "JJ00", "SS00"}
    assert {row["MateName"] for row in execution_view["Mates"]} == {
        "重合6",
        "同心11",
        "平行1",
    }
    assert execution_view["BaseGraphPolicy"]["moduleTokens"] == ["JJ00", "SS00"]
    assert execution_view["TransactionExecutionProjection"]["targetModuleToken"] == "GN00"


def test_effective_graph_with_unrequested_target_mate_is_rejected(tmp_path):
    manifest = copy.deepcopy(
        _load(
            "demo/global_assembly_contexts/"
            "project01-cross-family-relation-v2-v1.cad-transaction-manifest.json"
        )
    )
    graph = _load(
        "demo/semantic_ports/project01_GN00_fourth_increment_v1/"
        "assembly_plan_effective.json"
    )
    extra = copy.deepcopy(graph["Mates"][0])
    extra["MateName"] = "诊断多余配合"
    graph["Mates"].append(extra)
    graph_path = tmp_path / "graph-with-extra-mate.json"
    graph_path.write_text(
        json.dumps(graph, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    packet = manifest["packets"][1]
    for connection in packet["connections"]:
        connection["effectiveMateGraphCandidate"] = str(graph_path)
    packet["packetDigest"] = _digest(
        {key: value for key, value in packet.items() if key != "packetDigest"}
    )
    manifest["manifestDigest"] = _digest(
        {key: value for key, value in manifest.items() if key != "manifestDigest"}
    )
    checkpoint = tmp_path / "packet-001.SLDASM"
    checkpoint.write_bytes(b"checkpoint")

    with pytest.raises(GlobalCadPacketExecutionError, match="配合覆盖不一致"):
        build_global_cad_packet_execution_plan(
            WORKSPACE,
            manifest,
            "packet-002",
            output_path=tmp_path / "result.SLDASM",
            input_checkpoint=checkpoint,
        )


def _relation_manifest(operation: str, candidate: str) -> dict:
    packet = {
        "schemaVersion": "global-cad-transaction-packet/v1",
        "packetId": "packet-010",
        "order": 10,
        "operation": operation,
        "executionStrategy": (
            "direct_existing_component_mate_edit"
            if operation == "ADD_RELATION"
            else "read_only_existing_relation_verification"
        ),
        "targetInstanceId": None,
        "targetModuleDefinitionId": None,
        "targetCadSources": [],
        "targetProjectAliases": [],
        "semanticDependsOn": ["transaction-003", "transaction-005"],
        "cumulativeInput": {
            "kind": "previous_transaction_checkpoint",
            "packetId": "packet-009",
        },
        "connections": [
            {
                "connectionId": "connection-010",
                "instanceAId": "a500",
                "portAId": "a500-port",
                "instanceBId": "a700",
                "portBId": "a700-port",
                "globalTemplateId": "spacing",
                "templateEvidenceSource": {"projectId": "project02"},
                "effectiveMateGraphCandidate": candidate,
                "mates": [
                    {
                        "mateName": "距离8_语义端口重建",
                        "mateType": 5,
                        "alignment": 1,
                        "distance": None,
                        "angle": None,
                        "advancedOptions": {"distanceMeters": 0.05},
                    }
                ],
            }
        ],
        "verificationRequirements": [],
        "collisionAssessment": {"status": "not_evaluated"},
        "status": "ready_for_executor_implementation",
        "blockers": [],
    }
    packet["packetDigest"] = _digest(packet)
    manifest = {
        "schemaVersion": "global-cad-transaction-manifest/v1",
        "contextId": "relation-test",
        "contextDigest": "context",
        "packets": [packet],
    }
    manifest["manifestDigest"] = _digest(manifest)
    return manifest


def test_add_relation_builds_direct_existing_component_edit_plan(tmp_path):
    manifest = _relation_manifest(
        "ADD_RELATION",
        "demo/semantic_ports/project02_incremental_A500_A700_v1/assembly_plan_effective.json",
    )
    checkpoint = tmp_path / "packet-009.SLDASM"
    checkpoint.write_bytes(b"ten-installed-modules")

    plan = build_global_cad_packet_execution_plan(
        WORKSPACE,
        manifest,
        "packet-010",
        output_path=tmp_path / "relation-result.SLDASM",
        input_checkpoint=checkpoint,
    )

    assert plan["executionStrategy"] == "direct_existing_component_mate_edit"
    assert plan["targetModuleToken"] == "A500"
    assert plan["effectiveMateGraphPath"].endswith("effective_graph.json")
    assert plan["effectiveGraphMateCoverage"]["requestedMateCount"] == 1
    execution = plan["effectiveMateGraphExecutionView"]
    assert {row["ModuleToken"] for row in execution["Modules"]} == {"A500", "A700"}
    assert [row["operation"] for row in execution["PatchAudit"]["operations"]] == [
        "addMate"
    ]
    assert execution["PatchAudit"]["operations"][0]["mateName"] == "距离8_语义端口重建"


def test_verify_relation_builds_read_only_plan_without_patch_rewrite(tmp_path):
    manifest = _relation_manifest(
        "VERIFY_RELATION",
        "demo/semantic_ports/project02_incremental_A500_A700_v1/effective_graph.json",
    )
    checkpoint = tmp_path / "packet-009.SLDASM"
    checkpoint.write_bytes(b"ten-installed-modules")

    plan = build_global_cad_packet_execution_plan(
        WORKSPACE,
        manifest,
        "packet-010",
        output_path=tmp_path / "verified-copy.SLDASM",
        input_checkpoint=checkpoint,
    )

    assert plan["executionStrategy"] == "read_only_existing_relation_verification"
    assert plan["targetModuleToken"] == "A500"
    assert plan["sourcePreparation"]["required"] is False
    assert plan["effectiveMateGraphExecutionView"]["TransactionExecutionProjection"][
        "operation"
    ] == "VERIFY_RELATION"
    execution = plan["effectiveMateGraphExecutionView"]
    assert execution["ModuleCount"] == 2
    assert execution["InterModuleMateCount"] == 0
    assert execution["MateBundleCount"] == 0


def test_project03_distance_validation_accepts_source_audit_without_alignment(tmp_path):
    manifest = json.loads(
        (
            WORKSPACE
            / "demo/global_assembly_contexts/project03-relation-validation-v1/"
            "project03-aa00-ab00-distance5-validation-v1.cad-transaction-manifest.json"
        ).read_text(encoding="utf-8-sig")
    )
    checkpoint = tmp_path / "packet-001.SLDASM"
    checkpoint.write_bytes(b"project03-existing-assembly")

    plan = build_global_cad_packet_execution_plan(
        WORKSPACE,
        manifest,
        "packet-002",
        output_path=tmp_path / "verified-copy.SLDASM",
        input_checkpoint=checkpoint,
    )

    assert plan["executionStrategy"] == "read_only_existing_relation_verification"
    projection = plan["effectiveMateGraphExecutionView"][
        "TransactionExecutionProjection"
    ]
    assert projection["moduleTokens"] == ["FL9A24D063AA00", "FL9A24D063AB00"]
    assert projection["mateNames"] == ["距离5"]
    assert plan["effectiveGraphMateCoverage"]["requestedMateCount"] == 1
    assert projection["operation"] == "VERIFY_RELATION"

