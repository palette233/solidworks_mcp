import json
from copy import deepcopy
from pathlib import Path

from demo_backend.global_assembly_context import context_digest
from demo_backend.global_assembly_transactions import (
    compile_global_assembly_transaction_dag,
)
from demo_backend.global_cad_transaction_packets import (
    compile_global_cad_transaction_manifest,
)
from demo_backend.global_module_catalog import (
    _digest as catalog_digest,
    build_global_module_catalog,
)


WORKSPACE = Path(__file__).resolve().parents[3]
CATALOG_PATH = (
    WORKSPACE
    / "demo/global_assembly_catalog/v1/global_module_catalog.relation-v2-preview.json"
)
CONTEXT_PATH = (
    WORKSPACE
    / "demo/global_assembly_contexts/project01-cross-family-relation-v2-v1.json"
)


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _template(catalog, legacy_id):
    return next(
        row
        for row in catalog["connectionTemplates"]
        if row["legacyTemplateId"] == legacy_id
    )


def test_candidate_catalog_exposes_three_portable_standalone_project01_relations():
    catalog = _load(CATALOG_PATH)
    templates = {
        legacy_id: _template(catalog, legacy_id)
        for legacy_id in (
            "GN00_JJ00_standalone_coincident",
            "GN00_JJ00_standalone_concentric",
            "GN00_SS00_standalone_parallel",
        )
    }

    assert all(row["purposes"] == ["relation"] for row in templates.values())
    assert [len(row["mateSteps"]) for row in templates.values()] == [1, 1, 1]
    parallel_effect = templates["GN00_SS00_standalone_parallel"][
        "constraintEffect"
    ]
    assert parallel_effect["expectedResidualDof"] == 4
    assert parallel_effect["completesWithLegacyTemplateIds"] == [
        "GN00_to_JJ00_primary"
    ]
    assert parallel_effect["combinedExpectedResidualDof"] == 0


def test_declared_primary_plus_anti_rotation_combination_closes_one_insert_step():
    catalog = _load(CATALOG_PATH)
    context = _load(CONTEXT_PATH)

    dag = compile_global_assembly_transaction_dag(catalog, context)

    assert dag["status"] == "ready_for_generic_cad_executor"
    assert not dag["blockers"]
    closure = next(
        step
        for step in dag["steps"]
        if step["constraintAssessment"]["state"]
        == "closed_by_declared_template_combination"
    )
    assert closure["operation"] == "INSERT_AND_CONNECT"
    assert len(closure["connections"]) == 2
    assert closure["constraintAssessment"]["expectedResidualDof"] == 0
    assert closure["constraintAssessment"]["declaredTemplateCombination"][
        "matchedLegacyTemplateIds"
    ] == ["GN00_to_JJ00_primary"]


def test_first_class_combination_record_drives_the_same_closed_assessment():
    catalog = build_global_module_catalog(WORKSPACE, project_ids=("project01",))
    for template in catalog["connectionTemplates"]:
        if template.get("legacyTemplateId") == "GN00_SS00_standalone_parallel":
            template["constraintEffect"].pop(
                "completesWithLegacyTemplateIds", None
            )
            template["constraintEffect"].pop("combinedExpectedResidualDof", None)
    catalog["catalogDigest"] = catalog_digest(
        {key: value for key, value in catalog.items() if key != "catalogDigest"}
    )
    context = _load(CONTEXT_PATH)
    context["catalogDigest"] = catalog["catalogDigest"]
    context["contextDigest"] = context_digest(context)

    dag = compile_global_assembly_transaction_dag(catalog, context)

    closure = next(
        step
        for step in dag["steps"]
        if step["constraintAssessment"]["state"]
        == "closed_by_declared_template_combination"
    )
    combination = closure["constraintAssessment"]["declaredTemplateCombination"]
    assert combination["globalCombinationId"].startswith(
        "combination/project01/gn00-primary-plus-ss00-anti-rotation/"
    )
    assert combination["evidence"] == "catalog_template_combination"
    assert set(combination["memberGlobalTemplateIds"]) == {
        connection["globalTemplateId"] for connection in closure["connections"]
    }


def test_completion_relation_is_not_treated_as_generic_dof_subtraction():
    catalog = _load(CATALOG_PATH)
    context = _load(CONTEXT_PATH)
    without_completion = deepcopy(context)
    without_completion["connections"] = [
        row
        for row in without_completion["connections"]
        if row["globalTemplateId"]
        != _template(catalog, "GN00_SS00_standalone_parallel")["globalTemplateId"]
    ]
    without_completion["contextDigest"] = context_digest(without_completion)

    dag = compile_global_assembly_transaction_dag(catalog, without_completion)

    gn00_step = next(
        step
        for step in dag["steps"]
        if any(
            connection["globalTemplateId"]
            == _template(catalog, "GN00_to_JJ00_primary")["globalTemplateId"]
            for connection in step["connections"]
        )
    )
    assert gn00_step["status"] == "blocked"
    assert gn00_step["constraintAssessment"]["expectedResidualDof"] == 1
    assert any(
        row["code"] == "TARGET_UNDERCONSTRAINED_BY_DECLARED_TEMPLATE"
        for row in gn00_step["blockers"]
    )


def test_declared_combination_compiles_to_one_three_mate_cad_packet():
    catalog = _load(CATALOG_PATH)
    context = _load(CONTEXT_PATH)

    manifest = compile_global_cad_transaction_manifest(catalog, context)

    assert manifest["status"] == "ready_for_generic_executor_implementation"
    assert not manifest["blockers"]
    closure = next(
        packet
        for packet in manifest["packets"]
        if packet["constraintAssessment"]["state"]
        == "closed_by_declared_template_combination"
    )
    assert closure["operation"] == "INSERT_AND_CONNECT"
    assert len(closure["connections"]) == 2
    assert sum(len(row["mates"]) for row in closure["connections"]) == 3
    assert closure["status"] == "ready_for_executor_implementation"
    assert closure["collisionAssessment"]["status"] == "not_evaluated"


def test_three_project_independent_graph_shapes_compile_without_fixed_sequences():
    signed_catalog = _load(
        WORKSPACE / "demo/global_assembly_catalog/v1/global_module_catalog.json"
    )
    candidate_catalog = _load(CATALOG_PATH)
    cases = [
        (
            candidate_catalog,
            _load(CONTEXT_PATH),
            "closed_by_declared_template_combination",
        ),
        (
            signed_catalog,
            _load(
                WORKSPACE
                / "demo/global_assembly_contexts/project03-cross-family-smoke-v1.json"
            ),
            None,
        ),
        (
            signed_catalog,
            _load(
                WORKSPACE
                / "demo/global_assembly_contexts/project05-full-static-graph-v1.json"
            ),
            None,
        ),
    ]

    dags = [
        compile_global_assembly_transaction_dag(catalog, context)
        for catalog, context, _ in cases
    ]

    assert [dag["status"] for dag in dags] == [
        "ready_for_generic_cad_executor",
        "ready_for_generic_cad_executor",
        "ready_for_generic_cad_executor",
    ]
    assert [dag["transactionCount"] for dag in dags] == [2, 1, 8]
    assert all(dag["projectSequenceRequired"] is False for dag in dags)
    assert any(
        step["constraintAssessment"]["state"]
        == "closed_by_declared_template_combination"
        for step in dags[0]["steps"]
    )


def test_stage_c_command_matrix_records_twelve_closed_cases():
    report = _load(
        WORKSPACE
        / "demo/global_assembly_catalog/v1/relation-v2-preview/global_relation_command_matrix.json"
    )

    assert report["schemaVersion"] == "global-relation-command-matrix/v1"
    assert report["caseCount"] == 12
    assert report["passedCount"] == 12
    assert report["failedCount"] == 0
    assert all(row["passed"] for row in report["cases"])
    assert report["solidWorksExecuted"] is False
    assert report["collisionStatus"] == "not_evaluated"
