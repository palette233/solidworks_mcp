from pathlib import Path

from demo_backend.global_module_catalog import build_global_module_catalog
from demo_backend.global_module_port_coverage import (
    assess_module_selection_readiness,
    build_global_module_port_coverage_matrix,
    validate_global_module_port_coverage_matrix,
)
from demo_backend.global_assembly_workbench import (
    assess_module_selection,
    load_module_port_coverage,
)


ROOT = Path(__file__).resolve().parents[3]


def _matrix(*projects: str):
    catalog = build_global_module_catalog(ROOT, project_ids=projects)
    return build_global_module_port_coverage_matrix(catalog)


def test_real_catalog_coverage_matrix_is_deterministic_and_valid():
    first = _matrix("project01", "project02", "project03", "project05", "project06")
    second = _matrix("project01", "project02", "project03", "project05", "project06")
    assert first["matrixDigest"] == second["matrixDigest"]
    result = validate_global_module_port_coverage_matrix(first)
    assert result["success"] is True
    assert first["summary"]["moduleCount"] == 43
    assert first["summary"]["cadEndpointReadyModuleCount"] > 0
    assert first["summary"]["blockedModuleCount"] > 0
    # The validated A600/AH00 cross-project slot contributes two additional
    # directed compatibility rows to the previous 69-row catalog.
    assert first["summary"]["connectionPairCount"] == 71


def test_project06_missing_ports_are_structured_p0_or_p1_gaps():
    matrix = _matrix("project01", "project02", "project03", "project05", "project06")
    project06_rows = [
        row
        for row in matrix["modules"]
        if any(alias["projectId"] == "project06" for alias in row["projectAliases"])
    ]
    assert project06_rows
    assert all(row["status"] == "blocked" for row in project06_rows)
    assert all("NO_SEMANTIC_PORT" in row["blockers"] for row in project06_rows)
    assert any(
        gap["code"] == "NO_SEMANTIC_PORT"
        and any(alias["projectId"] == "project06" for alias in gap["projectAliases"])
        for gap in matrix["gaps"]
    )


def test_project02_a600_a800_a180_selection_is_cad_graph_ready():
    matrix = _matrix("project02")
    result = assess_module_selection_readiness(
        matrix, ["project02:A600", "project02:A800", "project02:A180"]
    )
    assert result["status"] == "ready"
    assert len(result["resolvedModuleDefinitionIds"]) == 3
    assert result["selectedConnectionPairIds"]
    assert result["collisionStatus"] == "not_evaluated"


def test_unknown_and_disconnected_selections_are_explicitly_blocked():
    matrix = _matrix("project02", "project06")
    unknown = assess_module_selection_readiness(matrix, ["project02:A600", "missing-module"])
    assert unknown["status"] == "blocked"
    assert any(row["code"] == "UNKNOWN_MODULE_REFERENCE" for row in unknown["blockers"])

    project06 = assess_module_selection_readiness(
        matrix, ["project06:A000", "project06:D000"]
    )
    assert project06["status"] == "blocked"
    assert any(row["code"] == "MODULE_NOT_CAD_ENDPOINT_READY" for row in project06["blockers"])


def test_bare_token_ambiguity_is_not_silently_resolved():
    matrix = _matrix("project05", "project06")
    result = assess_module_selection_readiness(matrix, ["A000"])
    assert result["status"] == "blocked"
    assert any(row["code"] == "AMBIGUOUS_MODULE_REFERENCE" for row in result["blockers"])


def test_workbench_exposes_read_only_matrix_and_selection_assessment():
    matrix = load_module_port_coverage(ROOT)
    assert matrix["schemaVersion"] == "global-module-port-coverage-matrix/v1"
    result = assess_module_selection(
        ROOT,
        {
            "moduleReferences": [
                "project02:A600",
                "project02:A800",
                "project02:A180",
            ]
        },
    )
    assert result["status"] == "ready"
    assert result["collisionStatus"] == "not_evaluated"
