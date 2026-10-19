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
ARTIFACT_ROOT = WORKSPACE / "demo/semantic_ports/project02_a200_t401_installations_v1"


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _definition(catalog, token):
    return next(
        row
        for row in catalog["moduleDefinitions"]
        if any(
            alias["projectId"] == "project02" and alias["moduleToken"] == token
            for alias in row["projectAliases"]
        )
    )


def _apply(catalog, context, token, requirement):
    definition = _definition(catalog, token)
    preview = preview_global_assembly_command(
        catalog,
        context,
        {"requirement": requirement, "moduleDefinitionId": definition["moduleDefinitionId"]},
    )
    assert preview["status"] == "ready", preview
    return apply_global_command_preview(
        context,
        preview,
        preview_digest=preview["previewDigest"],
        confirmed=True,
    )


def test_a200_slot_template_is_valid_and_keeps_three_source_mates():
    catalog = _read(ARTIFACT_ROOT / "A200/semantic_port_catalog.json")
    endpoints = _read(ARTIFACT_ROOT / "A200/face_endpoint_catalog.json")
    result = validate_semantic_port_catalog(catalog, endpoints)
    assert result["success"] is True
    steps = catalog["connectionTemplates"][0]["mateSteps"]
    assert [step["mateType"] for step in steps] == [0, 21, 21]
    assert all(
        step["advancedOptions"]["SlotConstraint"] is not None
        for step in steps
        if step["mateType"] == 21
    )


def test_project02_global_chain_compiles_a200_and_two_t401_adapters():
    catalog = build_global_module_catalog(WORKSPACE, project_ids=("project02",))
    for token in ("A200", "T401"):
        definition = _definition(catalog, token)
        assert definition["portCoverage"] == "portable_complete"
    context = create_global_assembly_context(
        "a200-t401-compiler-test", catalog_digest=catalog["catalogDigest"]
    )
    context = _apply(catalog, context, "A600", "安装A600箱体")
    context = _apply(catalog, context, "A200", "将A200 CCD安装到A600")
    context = _apply(catalog, context, "T401", "将第一套T401安装到A600")
    context = _apply(catalog, context, "T401", "将第二套T401连接到A200")

    manifest = compile_global_assembly_execution_manifest(WORKSPACE, catalog, context)
    assert manifest["status"] == "ready_for_project_adapter"
    assert manifest["stepCount"] == 3
    assert all(step["status"] == "ready_for_project_adapter" for step in manifest["steps"])
    assert manifest["executionBoundary"]["solidWorksExecuted"] is False
    assert manifest["executionBoundary"]["collisionGateExecuted"] is False
