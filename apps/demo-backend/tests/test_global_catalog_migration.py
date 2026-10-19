import hashlib
import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest

from demo_backend.global_assembly_context import (
    apply_global_command_preview,
    create_global_assembly_context,
    preview_global_assembly_command,
)
from demo_backend.global_assembly_workbench import (
    GlobalAssemblyWorkbenchError,
    commit_catalog_migration,
    compile_transaction_dag,
    preview_catalog_migration,
)
from demo_backend.global_catalog_migration import (
    GlobalCatalogMigrationError,
    assess_context_catalog_migration,
    build_catalog_migration_plan,
    migrate_context_catalog_binding,
)


WORKSPACE = Path(__file__).resolve().parents[3]
SOURCE_CATALOG_PATH = WORKSPACE / "demo/global_assembly_catalog/v1/global_module_catalog.json"
CANDIDATE_CATALOG_PATH = (
    WORKSPACE / "demo/global_assembly_catalog/v1/global_module_catalog.refresh-preview.json"
)
CONTEXT_PATH = WORKSPACE / "demo/global_assembly_contexts/project02-full-static-graph-v1.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def definition(catalog, project_id, token):
    return next(
        row
        for row in catalog["moduleDefinitions"]
        if any(
            alias["projectId"] == project_id and alias["moduleToken"] == token
            for alias in row["projectAliases"]
        )
    )


@pytest.fixture(scope="module")
def source_catalog():
    return load(SOURCE_CATALOG_PATH)


@pytest.fixture(scope="module")
def candidate_catalog():
    return load(CANDIDATE_CATALOG_PATH)


@pytest.fixture(scope="module")
def project02_context():
    return load(CONTEXT_PATH)


def test_real_project02_context_has_safe_monotonic_catalog_migration(
    source_catalog, candidate_catalog, project02_context
):
    plan = build_catalog_migration_plan(
        source_catalog, candidate_catalog, [project02_context]
    )

    assert plan["summary"] == {
        "contextCount": 1,
        "readyContextCount": 1,
        "blockedContextCount": 0,
    }
    assert plan["catalogDiff"]["compatibility"]["portableUpgrades"] == 1
    assessment = plan["contextAssessments"][0]
    assert assessment["status"] == "ready"
    assert assessment["blockers"] == []
    assert len(assessment["assessmentDigest"]) == 64


def test_removed_used_port_blocks_migration(
    source_catalog, candidate_catalog, project02_context
):
    broken = deepcopy(candidate_catalog)
    used_port = project02_context["connections"][0]["portAId"]
    broken["semanticPorts"] = [
        row for row in broken["semanticPorts"] if row["globalPortId"] != used_port
    ]
    broken["compatibility"] = [
        row
        for row in broken["compatibility"]
        if row["portAId"] != used_port and row["portBId"] != used_port
    ]
    broken["catalogDigest"] = digest(
        {key: value for key, value in broken.items() if key != "catalogDigest"}
    )

    assessment = assess_context_catalog_migration(
        source_catalog, broken, project02_context
    )
    codes = {row["code"] for row in assessment["blockers"]}
    assert assessment["status"] == "blocked"
    assert "CANDIDATE_PORT_MISSING" in codes
    assert "CANDIDATE_COMPATIBILITY_MISSING" in codes


def test_commit_requires_confirmation_and_fresh_assessment_digest(
    source_catalog, candidate_catalog, project02_context
):
    assessment = assess_context_catalog_migration(
        source_catalog, candidate_catalog, project02_context
    )
    with pytest.raises(GlobalCatalogMigrationError, match="confirmed=true"):
        migrate_context_catalog_binding(
            source_catalog,
            candidate_catalog,
            project02_context,
            target_context_id="migrated-project02",
            expected_assessment_digest=assessment["assessmentDigest"],
            confirmed=False,
        )
    with pytest.raises(GlobalCatalogMigrationError, match="评估摘要已过期"):
        migrate_context_catalog_binding(
            source_catalog,
            candidate_catalog,
            project02_context,
            target_context_id="migrated-project02",
            expected_assessment_digest="0" * 64,
            confirmed=True,
        )


def test_workbench_commit_creates_new_context_and_preserves_source(
    tmp_path, source_catalog, candidate_catalog, project02_context
):
    source_catalog_target = tmp_path / "demo/global_assembly_catalog/v1/global_module_catalog.json"
    candidate_target = (
        tmp_path / "demo/global_assembly_catalog/v1/global_module_catalog.refresh-preview.json"
    )
    source_context_target = (
        tmp_path / "demo/global_assembly_contexts/project02-full-static-graph-v1.json"
    )
    for source, target in (
        (SOURCE_CATALOG_PATH, source_catalog_target),
        (CANDIDATE_CATALOG_PATH, candidate_target),
        (CONTEXT_PATH, source_context_target),
    ):
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    source_bytes = source_context_target.read_bytes()

    preview = preview_catalog_migration(
        tmp_path,
        {
            "candidateCatalogPath": "demo/global_assembly_catalog/v1/global_module_catalog.refresh-preview.json",
            "contextIds": ["project02-full-static-graph-v1"],
        },
    )
    assessment = preview["contextAssessments"][0]
    result = commit_catalog_migration(
        tmp_path,
        {
            "candidateCatalogPath": "demo/global_assembly_catalog/v1/global_module_catalog.refresh-preview.json",
            "sourceContextId": "project02-full-static-graph-v1",
            "targetContextId": "project02-full-static-graph-refresh-v1",
            "expectedAssessmentDigest": assessment["assessmentDigest"],
            "confirmed": True,
        },
    )

    assert result["success"] is True
    assert source_context_target.read_bytes() == source_bytes
    assert result["context"]["catalogDigest"] == candidate_catalog["catalogDigest"]
    assert result["context"]["contextId"] == "project02-full-static-graph-refresh-v1"
    assert result["context"]["revision"] == project02_context["revision"] + 1
    assert result["context"]["history"][-1]["operation"] == "catalog_binding_migration"
    assert Path(result["bindingPath"]).is_file()
    assert result["binding"]["sourcePreserved"] is True
    dag = compile_transaction_dag(
        tmp_path,
        "project02-full-static-graph-refresh-v1",
        catalog_path="demo/global_assembly_catalog/v1/global_module_catalog.refresh-preview.json",
    )
    assert dag["schemaVersion"] == "global-assembly-transaction-dag/v1"
    with pytest.raises(GlobalAssemblyWorkbenchError, match="目录版本"):
        compile_transaction_dag(tmp_path, "project02-full-static-graph-refresh-v1")


def test_migrated_context_can_select_refreshed_a500_a700_spacing(
    source_catalog, candidate_catalog
):
    a500 = definition(source_catalog, "project02", "A500")
    source_context = create_global_assembly_context(
        "a500-source-catalog", catalog_digest=source_catalog["catalogDigest"]
    )
    add_a500 = preview_global_assembly_command(
        source_catalog,
        source_context,
        {
            "requirement": "安装项目02 A500校准模组",
            "moduleDefinitionId": a500["moduleDefinitionId"],
        },
    )
    source_context = apply_global_command_preview(
        source_context,
        add_a500,
        preview_digest=add_a500["previewDigest"],
        confirmed=True,
    )
    assessment = assess_context_catalog_migration(
        source_catalog, candidate_catalog, source_context
    )
    migrated, _ = migrate_context_catalog_binding(
        source_catalog,
        candidate_catalog,
        source_context,
        target_context_id="a500-refreshed-catalog",
        expected_assessment_digest=assessment["assessmentDigest"],
        confirmed=True,
    )
    a700 = definition(candidate_catalog, "project02", "A700")
    preview = preview_global_assembly_command(
        candidate_catalog,
        migrated,
        {
            "requirement": "将项目02 A700与A500保持50mm间距",
            "moduleDefinitionId": a700["moduleDefinitionId"],
        },
    )

    assert preview["status"] == "needs_confirmation"
    assert any(
        row["portable"]
        and row["relationAssessment"]["templateProfile"]["drivesPlacement"]
        for row in preview["connectionCandidates"]
    )
