import json
from pathlib import Path

from demo_backend.global_assembly_compiler import compile_global_assembly_execution_manifest
from demo_backend.global_assembly_context import (
    apply_global_command_preview,
    create_global_assembly_context,
    preview_global_assembly_command,
)
from demo_backend.global_module_catalog import build_global_module_catalog
from demo_backend.semantic_port_catalog import validate_semantic_port_catalog


WORKSPACE = Path(__file__).resolve().parents[3]
ARTIFACT_ROOT = WORKSPACE / "demo/semantic_ports/project05_global_installation_ports_v1"
TOKENS = ("D000", "K000", "F000", "M000", "G000", "N000", "P000", "B000")


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _definition(catalog, token):
    return next(
        row
        for row in catalog["moduleDefinitions"]
        if any(
            alias["projectId"] == "project05" and alias["moduleToken"] == token
            for alias in row["projectAliases"]
        )
    )


def test_all_project05_installation_catalogs_validate_without_guessed_advanced_options():
    for token in TOKENS:
        catalog = _read(ARTIFACT_ROOT / token / "semantic_port_catalog.json")
        endpoints = _read(ARTIFACT_ROOT / token / "face_endpoint_catalog.json")
        result = validate_semantic_port_catalog(catalog, endpoints)
        assert result["success"] is True
    d000 = _read(ARTIFACT_ROOT / "D000/semantic_port_catalog.json")
    g000 = _read(ARTIFACT_ROOT / "G000/semantic_port_catalog.json")
    assert d000["readOnlySourceRelations"][0]["mateType"] == 11
    assert g000["readOnlySourceRelations"][0]["mateType"] == 21
    assert all(
        step["mateType"] not in {11, 21}
        for row in (d000, g000)
        for step in row["connectionTemplates"][0]["mateSteps"]
    )


def test_project05_nine_object_global_graph_compiles_to_eight_adapter_steps():
    catalog = build_global_module_catalog(WORKSPACE, project_ids=("project05",))
    assert not [
        item
        for item in catalog["blockers"]
        if item.get("code") == "MODULE_HAS_NO_SEMANTIC_PORT"
    ]
    context = create_global_assembly_context(
        "project05-port-test", catalog_digest=catalog["catalogDigest"]
    )
    for token in ("A000", *TOKENS):
        definition = _definition(catalog, token)
        preview = preview_global_assembly_command(
            catalog,
            context,
            {
                "requirement": f"在A000上安装项目05的{token}",
                "moduleDefinitionId": definition["moduleDefinitionId"],
            },
        )
        assert preview["status"] == "ready", preview
        context = apply_global_command_preview(
            context,
            preview,
            preview_digest=preview["previewDigest"],
            confirmed=True,
        )
    manifest = compile_global_assembly_execution_manifest(WORKSPACE, catalog, context)
    assert manifest["status"] == "ready_for_project_adapter"
    assert manifest["stepCount"] == 8
    assert all(step["status"] == "ready_for_project_adapter" for step in manifest["steps"])


def test_composite_project05_groups_are_single_context_instances():
    catalog = build_global_module_catalog(WORKSPACE, project_ids=("project05",))
    context = create_global_assembly_context(
        "project05-composite-capacity", catalog_digest=catalog["catalogDigest"]
    )
    a000 = _definition(catalog, "A000")
    first = preview_global_assembly_command(
        catalog,
        context,
        {"requirement": "安装A000", "moduleDefinitionId": a000["moduleDefinitionId"]},
    )
    context = apply_global_command_preview(
        context,
        first,
        preview_digest=first["previewDigest"],
        confirmed=True,
    )
    duplicate = preview_global_assembly_command(
        catalog,
        context,
        {"requirement": "再装一个A000", "moduleDefinitionId": a000["moduleDefinitionId"]},
    )
    assert duplicate["status"] == "blocked"
    assert duplicate["blockers"][0]["code"] == "MODULE_INSTANCE_CAPACITY_REACHED"


def test_natural_language_prefers_the_only_definition_with_remaining_capacity():
    catalog = build_global_module_catalog(WORKSPACE, project_ids=("project02",))
    context = create_global_assembly_context(
        "project02-duplicate-capacity-selection", catalog_digest=catalog["catalogDigest"]
    )
    definitions = {
        token: next(
            row
            for row in catalog["moduleDefinitions"]
            if any(
                alias["projectId"] == "project02" and alias["moduleToken"] == token
                for alias in row["projectAliases"]
            )
        )
        for token in ("A600", "A200", "T401")
    }
    commands = (
        ("创建A600箱体基座", "A600"),
        ("在A600上安装A200 CCD模组", "A200"),
        ("在A600上安装第一套T401供胶系统", "T401"),
    )
    for requirement, token in commands:
        preview = preview_global_assembly_command(
            catalog,
            context,
            {
                "requirement": requirement,
                "moduleDefinitionId": definitions[token]["moduleDefinitionId"],
            },
        )
        assert preview["status"] in {"ready", "needs_confirmation"}, preview
        context = apply_global_command_preview(
            context,
            preview,
            preview_digest=preview["previewDigest"],
            confirmed=True,
        )

    preview = preview_global_assembly_command(
        catalog,
        context,
        {"requirement": "在A200 CCD模组上安装第二套T401供胶系统"},
    )
    assert preview["resolution"] == "unique_definition_with_remaining_instance_capacity"
    assert preview["selectedModuleDefinitionId"] == definitions["T401"]["moduleDefinitionId"]
    assert preview["proposedPatch"]["instance"]["instanceOrdinal"] == 2
    context = apply_global_command_preview(
        context,
        preview,
        preview_digest=preview["previewDigest"],
        confirmed=True,
    )

    overflow = preview_global_assembly_command(
        catalog,
        context,
        {"requirement": "再安装第三套T401供胶系统"},
    )
    assert overflow["status"] == "blocked"
    assert any(
        row["code"] == "MODULE_INSTANCE_CAPACITY_REACHED"
        for row in overflow["blockers"]
    )
