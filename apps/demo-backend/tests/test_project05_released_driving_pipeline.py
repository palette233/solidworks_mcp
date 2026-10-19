from pathlib import Path
import shutil

import pytest

from demo_backend import global_assembly_workbench as workbench
from demo_backend.global_assembly_workbench import GlobalAssemblyWorkbenchError


WORKSPACE = Path(__file__).resolve().parents[3]
RELEASE = (
    "demo/global_assembly_catalog/releases/"
    "relation-v7-project05-driving-independent-20261011/release-manifest.json"
)
AUTHORIZED_TEMPLATE = "template/project05/d000-to-a000-scoped-driving-v2/465c1f471a"


def _definition(catalog: dict, token: str) -> dict:
    return next(
        row
        for row in catalog["moduleDefinitions"]
        if row["moduleDefinitionId"].startswith("cad/fl9c254098")
        and any(
            alias.get("projectId") == "project05"
            and alias.get("moduleToken") == token
            for alias in row.get("projectAliases") or []
        )
    )


def test_release_binding_survives_natural_language_context_dag_and_cad_packets(
    tmp_path, monkeypatch
):
    context_dir = Path(".tmp") / f"release-bound-{tmp_path.name}"
    monkeypatch.setattr(workbench, "DEFAULT_CONTEXT_DIR", context_dir)
    created = workbench.create_context(
        WORKSPACE,
        {
            "contextId": "project05-release-bound",
            "releaseManifestPath": RELEASE,
            "overwrite": True,
        },
    )
    binding = created["context"]["relationReleaseBinding"]
    assert binding["releaseId"] == "relation-v7-project05-driving-independent-20261011"
    assert binding["authorizedDrivingTemplateIds"] == [AUTHORIZED_TEMPLATE]

    catalog, _ = workbench.load_released_relation_catalog(WORKSPACE, RELEASE)
    a000 = _definition(catalog, "A000")
    d000 = _definition(catalog, "D000")
    result = workbench.apply_command_sequence(
        WORKSPACE,
        "project05-release-bound",
        {
            "confirmed": True,
            "commands": [
                {
                    "requirement": "先安装项目05 A000机架基座",
                    "moduleDefinitionId": a000["moduleDefinitionId"],
                },
                {
                    "requirement": "在A000上安装项目05 D000输送模组",
                    "moduleDefinitionId": d000["moduleDefinitionId"],
                },
            ],
        },
    )
    assert result["success"] is True
    assert result["context"]["connections"][0]["globalTemplateId"] == AUTHORIZED_TEMPLATE

    dag = workbench.compile_transaction_dag(WORKSPACE, "project05-release-bound")
    cad = workbench.compile_cad_transaction_manifest(
        WORKSPACE, "project05-release-bound"
    )
    execution = workbench.compile_execution_manifest(
        WORKSPACE, "project05-release-bound"
    )
    assert dag["relationReleaseBinding"] == binding
    assert cad["relationReleaseBinding"] == binding
    assert cad["packets"][0]["relationReleaseBinding"] == binding
    assert execution["relationReleaseBinding"] == binding
    assert dag["status"] == "ready_for_generic_cad_executor"
    assert cad["status"] == "ready_for_generic_executor_implementation"
    assert not any(
        blocker["code"] == "TEMPLATE_NOT_AUTHORIZED_BY_BOUND_RELEASE"
        for blocker in cad["blockers"]
    )
    shutil.rmtree(WORKSPACE / context_dir)


def test_low_level_release_bound_context_rejects_catalog_override(tmp_path, monkeypatch):
    context_dir = Path(".tmp") / f"release-bound-{tmp_path.name}-override"
    monkeypatch.setattr(workbench, "DEFAULT_CONTEXT_DIR", context_dir)
    catalog = workbench.load_global_catalog(WORKSPACE)
    context = workbench.create_global_assembly_context(
        "project05-release-bound-override",
        catalog_digest=catalog["catalogDigest"],
        relation_release_binding={
            "releaseId": "synthetic-test",
            "releaseDigest": "a" * 64,
            "releaseManifestPath": RELEASE,
            "catalogDigest": catalog["catalogDigest"],
            "authorizedDrivingTemplateIds": [AUTHORIZED_TEMPLATE],
        },
    )
    workbench._write(
        workbench.context_path(WORKSPACE, "project05-release-bound-override"),
        context,
    )
    with pytest.raises(GlobalAssemblyWorkbenchError, match="不能再通过catalogPath替换目录"):
        workbench.preview_command(
            WORKSPACE,
            "project05-release-bound-override",
            {
                "requirement": "安装项目05 A000",
                "catalogPath": "demo/global_assembly_catalog/v1/global_module_catalog.json",
            },
        )
    shutil.rmtree(WORKSPACE / context_dir)
