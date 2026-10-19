import json
from copy import deepcopy
from pathlib import Path

from demo_backend.global_assembly_context import (
    context_digest,
    create_global_assembly_context,
    preview_global_assembly_command,
)
from demo_backend.global_assembly_transactions import (
    compile_global_assembly_transaction_dag,
)
from demo_backend.global_module_catalog import build_global_module_catalog
from demo_backend.project02_positioning_standard import (
    load_project02_positioning_standard,
)


WORKSPACE = Path(__file__).resolve().parents[3]


def _load(relative: str):
    return json.loads((WORKSPACE / relative).read_text(encoding="utf-8-sig"))


def _definition(catalog, token):
    return next(
        item
        for item in catalog["moduleDefinitions"]
        if any(alias["moduleToken"] == token for alias in item["projectAliases"])
    )


def test_preview_exposes_project_independent_add_command_ir():
    catalog = build_global_module_catalog(WORKSPACE, project_ids=("project02",))
    context = create_global_assembly_context("command-ir", catalog_digest=catalog["catalogDigest"])
    base = _definition(catalog, "A600")

    preview = preview_global_assembly_command(
        catalog,
        context,
        {
            "requirement": "请先添加A600箱体",
            "moduleDefinitionId": base["moduleDefinitionId"],
        },
    )

    assert preview["commandIr"]["schemaVersion"] == "global-assembly-command-ir/v1"
    assert preview["commandIr"]["operations"] == [
        {
            "operation": "ADD",
            "instanceId": preview["proposedPatch"]["instance"]["instanceId"],
            "moduleDefinitionId": base["moduleDefinitionId"],
            "displayName": base["displayName"],
        }
    ]
    assert preview["commandIr"]["executionBoundary"]["collisionStatus"] == "not_evaluated"


def test_project02_full_graph_compiles_without_project_fixed_sequence():
    catalog = _load("demo/global_assembly_catalog/v1/global_module_catalog.json")
    context = _load("demo/global_assembly_contexts/project02-full-static-graph-v1.json")

    dag = compile_global_assembly_transaction_dag(catalog, context)

    assert dag["schemaVersion"] == "global-assembly-transaction-dag/v1"
    assert dag["planningMode"] == "project_independent_semantic_graph"
    assert dag["projectSequenceRequired"] is False
    assert dag["instanceCount"] == 10
    assert dag["transactionCount"] == 9
    assert dag["collisionAssessment"]["status"] == "not_evaluated"
    assert [step["order"] for step in dag["steps"]] == list(range(1, 10))
    assert dag["steps"][-1]["contextInstanceIds"] == [
        "fl9a24d062a200-001-1-001"
    ]
    assert dag["steps"][-1]["dependsOn"] == ["transaction-007"]
    assert any(
        blocker["code"] == "TARGET_UNDERCONSTRAINED_BY_DECLARED_TEMPLATE"
        for blocker in dag["blockers"]
    )


def test_project02_explicit_positioning_standard_closes_only_declared_case_gaps():
    catalog = _load("demo/global_assembly_catalog/v1/global_module_catalog.json")
    context = _load(
        "demo/global_assembly_contexts/project02-a800-a180-readiness-v1.json"
    )
    standard = load_project02_positioning_standard()

    dag = compile_global_assembly_transaction_dag(
        catalog,
        context,
        positioning_standard=standard,
    )

    assert dag["status"] == "ready_for_generic_cad_executor"
    assert dag["positioningStandard"]["explicitlySelected"] is True
    bound = {
        step["positioningStandardBinding"]["moduleToken"]: step
        for step in dag["steps"]
        if step["positioningStandardBinding"]
    }
    assert set(bound) == {"A800", "A180"}
    assert all(
        step["constraintAssessment"]["state"]
        == "closed_by_explicit_project_baseline"
        for step in bound.values()
    )
    assert not any(
        blocker["code"] == "TARGET_UNDERCONSTRAINED_BY_DECLARED_TEMPLATE"
        for blocker in dag["blockers"]
    )


def test_valid_subgraph_can_be_reordered_without_project_sequence_profile():
    catalog = _load("demo/global_assembly_catalog/v1/global_module_catalog.json")
    source = _load("demo/global_assembly_contexts/project02-full-static-graph-v1.json")
    kept_ids = {
        "fl9a24d062a600-001-1-001",
        "fl9a24d062a300-001-1-001",
        "fl9a24d062a500-001-1-001",
        "a100-with-a150-slot0-rigid-v3-1-001",
        "fl9a24d062a200-001-1-001",
    }
    context = deepcopy(source)
    instances = [row for row in source["instances"] if row["instanceId"] in kept_ids]
    base = next(row for row in instances if row["placementStatus"] == "base_context_unlocated")
    non_base = [row for row in instances if row is not base]
    context["instances"] = [base, *reversed(non_base)]
    context["connections"] = [
        row
        for row in source["connections"]
        if row["instanceAId"] in kept_ids and row["instanceBId"] in kept_ids
    ]
    context["contextId"] = "project-independent-reordered-subgraph"
    context["revision"] = len(context["instances"])
    context["history"] = []
    context["contextDigest"] = context_digest(context)

    dag = compile_global_assembly_transaction_dag(catalog, context)

    assert dag["projectSequenceRequired"] is False
    assert dag["transactionCount"] == 4
    assert [step["targetDisplayName"] for step in dag["steps"]] == [
        row["displayName"] for row in reversed(non_base)
    ]
    assert not any(blocker["code"] == "INSTANCE_NOT_REACHABLE_FROM_BASE" for blocker in dag["blockers"])


def test_disconnected_instance_fails_closed_before_cad():
    catalog = _load("demo/global_assembly_catalog/v1/global_module_catalog.json")
    source = _load("demo/global_assembly_contexts/project02-full-static-graph-v1.json")
    context = deepcopy(source)
    context["connections"] = context["connections"][:-1]
    context["contextId"] = "disconnected-instance"
    context["contextDigest"] = context_digest(context)

    dag = compile_global_assembly_transaction_dag(catalog, context)

    assert dag["status"] == "blocked"
    assert dag["unresolvedInstanceIds"] == ["t401aa-07388-0-002"]
    assert any(blocker["code"] == "INSTANCE_NOT_REACHABLE_FROM_BASE" for blocker in dag["blockers"])
    assert dag["executionBoundary"]["solidWorksExecuted"] is False
