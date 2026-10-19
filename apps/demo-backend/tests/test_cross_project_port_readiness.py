from pathlib import Path

from demo_backend.cross_project_port_readiness import audit_cross_project_port_readiness
from demo_backend.global_module_catalog import build_global_module_catalog


ROOT = Path(__file__).resolve().parents[3]


def test_projects_01_02_03_05_have_searchable_port_graph_coverage():
    catalog = build_global_module_catalog(
        ROOT, project_ids=("project01", "project02", "project03", "project05")
    )
    result = audit_cross_project_port_readiness(
        catalog, ("project01", "project02", "project03", "project05")
    )
    assert result["status"] == "ready"
    assert result["readyProjectIds"] == [
        "project01", "project02", "project03", "project05"
    ]
    assert all(row["moduleCount"] > 0 for row in result["projects"])
    assert all(
        row["moduleCount"] == row["semanticGraphReadyModuleCount"]
        for row in result["projects"]
    )


def test_missing_project_profile_is_explicitly_blocked_not_fabricated():
    catalog = build_global_module_catalog(ROOT, project_ids=("project02",))
    result = audit_cross_project_port_readiness(catalog, ("project02", "project06"))
    project06 = next(row for row in result["projects"] if row["projectId"] == "project06")
    assert result["status"] == "partial"
    assert project06["moduleCount"] == 0
    assert project06["blockers"] == ["NO_PROJECT_MODULE_PROFILE"]
