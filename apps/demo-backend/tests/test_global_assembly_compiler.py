from copy import deepcopy
import hashlib
import json
from pathlib import Path

from demo_backend.global_assembly_compiler import compile_global_assembly_execution_manifest
from demo_backend.global_assembly_context import (
    apply_global_command_preview,
    create_global_assembly_context,
    preview_global_assembly_command,
)
from demo_backend.global_module_catalog import build_global_module_catalog


WORKSPACE = Path(__file__).resolve().parents[3]


def _definition(catalog, token):
    return next(
        item
        for item in catalog["moduleDefinitions"]
        if any(alias["moduleToken"] == token for alias in item["projectAliases"])
    )


def _digest(value):
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _refresh_catalog_digest(catalog):
    result = deepcopy(catalog)
    result.pop("catalogDigest", None)
    result["catalogDigest"] = _digest(result)
    return result


def _refresh_context_digest(context):
    result = deepcopy(context)
    result.pop("contextDigest", None)
    result["contextDigest"] = _digest(result)
    return result


def test_project02_three_instance_context_compiles_to_two_legacy_requests():
    catalog = build_global_module_catalog(WORKSPACE, project_ids=("project02",))
    context = create_global_assembly_context("compiler-demo", catalog_digest=catalog["catalogDigest"])
    for token in ("A600", "A800", "A180"):
        preview = preview_global_assembly_command(
            catalog,
            context,
            {
                "requirement": f"安装{token}",
                "moduleDefinitionId": _definition(catalog, token)["moduleDefinitionId"],
            },
        )
        assert preview["status"] == "ready"
        context = apply_global_command_preview(
            context,
            preview,
            preview_digest=preview["previewDigest"],
            confirmed=True,
        )

    manifest = compile_global_assembly_execution_manifest(WORKSPACE, catalog, context)

    assert manifest["status"] == "ready_for_project_adapter"
    assert manifest["stepCount"] == 2
    assert [step["semanticConnectionRequest"]["portAId"] for step in manifest["steps"]] == [
        "A800.frame_installation",
        "A180.frame_installation",
    ]
    assert all(step["sourceGraphCandidates"] for step in manifest["steps"])
    assert manifest["executionBoundary"]["solidWorksExecuted"] is False
    assert manifest["executionBoundary"]["collisionGateExecuted"] is False


def test_compiler_requires_explicit_mode_for_datum_demo_template():
    catalog = build_global_module_catalog(WORKSPACE, project_ids=("project02",))
    context = create_global_assembly_context(
        "compiler-datum-policy", catalog_digest=catalog["catalogDigest"]
    )
    for token in ("A600", "A300"):
        preview = preview_global_assembly_command(
            catalog,
            context,
            {
                "requirement": f"安装{token}",
                "moduleDefinitionId": _definition(catalog, token)[
                    "moduleDefinitionId"
                ],
            },
        )
        assert preview["status"] == "ready"
        context = apply_global_command_preview(
            context,
            preview,
            preview_digest=preview["previewDigest"],
            confirmed=True,
        )

    template_id = context["connections"][0]["globalTemplateId"]
    datum_catalog = deepcopy(catalog)
    template = next(
        row
        for row in datum_catalog["connectionTemplates"]
        if row["globalTemplateId"] == template_id
    )
    template["purposes"] = sorted(
        set(template.get("purposes") or [])
        | {"installation", "datum_placement_demo"}
    )
    datum_catalog = _refresh_catalog_digest(datum_catalog)
    direct_context = deepcopy(context)
    direct_context["catalogDigest"] = datum_catalog["catalogDigest"]
    direct_context = _refresh_context_digest(direct_context)

    blocked = compile_global_assembly_execution_manifest(
        WORKSPACE, datum_catalog, direct_context
    )
    assert blocked["status"] == "blocked"
    assert any(
        row["code"] == "RELATION_EXECUTION_MODE_MISMATCH"
        for row in blocked["blockers"]
    )

    demo_context = deepcopy(direct_context)
    demo_context["connections"][0][
        "relationExecutionMode"
    ] = "datum_placement_demo"
    demo_context["connections"][0][
        "templateEvidenceClass"
    ] = "datum_placement_demo"
    demo_context = _refresh_context_digest(demo_context)
    ready = compile_global_assembly_execution_manifest(
        WORKSPACE, datum_catalog, demo_context
    )
    assert ready["status"] == "ready_for_project_adapter"
    assert ready["steps"][0]["semanticConnectionRequest"][
        "relationExecutionMode"
    ] == "datum_placement_demo"
