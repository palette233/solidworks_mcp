from pathlib import Path

import pytest

from demo_backend.global_assembly_context import (
    GlobalAssemblyContextError,
    apply_global_command_preview,
    create_global_assembly_context,
    preview_global_assembly_command,
    search_global_modules,
)
from demo_backend.global_module_catalog import build_global_module_catalog


WORKSPACE = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def catalog():
    return build_global_module_catalog(WORKSPACE, project_ids=("project02",))


def _definition(catalog, token):
    return next(
        item
        for item in catalog["moduleDefinitions"]
        if any(alias["moduleToken"] == token for alias in item["projectAliases"])
    )


def test_search_returns_cross_project_style_metadata(catalog):
    rows = search_global_modules(catalog, "扫描模组")
    assert rows
    assert rows[0]["category"] == "scanner"
    assert rows[0]["projectAliases"][0]["moduleToken"] == "A180"


def test_natural_language_context_patch_round_trip_without_collision_gate(catalog):
    context = create_global_assembly_context(
        "unit-demo", catalog_digest=catalog["catalogDigest"]
    )
    frame = _definition(catalog, "A600")
    base_preview = preview_global_assembly_command(
        catalog,
        context,
        {"requirement": "请先安装箱体", "moduleDefinitionId": frame["moduleDefinitionId"]},
    )
    assert base_preview["status"] == "ready"
    context = apply_global_command_preview(
        context,
        base_preview,
        preview_digest=base_preview["previewDigest"],
        confirmed=True,
    )

    transport = _definition(catalog, "A800")
    transport_preview = preview_global_assembly_command(
        catalog,
        context,
        {
            "requirement": "然后添加项目02的传输模组",
            "moduleDefinitionId": transport["moduleDefinitionId"],
        },
    )
    assert transport_preview["status"] in {"ready", "needs_confirmation"}
    assert transport_preview["collisionAssessment"]["status"] == "not_evaluated"
    assert transport_preview["cadExecution"]["status"] == "not_executed"
    assert transport_preview["connectionCandidates"]


def test_generic_alias_is_ambiguous_across_projects():
    catalog = build_global_module_catalog(
        WORKSPACE, project_ids=("project01", "project02", "project03")
    )
    context = create_global_assembly_context("ambiguous", catalog_digest=catalog["catalogDigest"])
    preview = preview_global_assembly_command(
        catalog, context, {"requirement": "请添加扫描模组"}
    )

    assert preview["status"] == "needs_confirmation"
    assert len(preview["moduleAlternatives"]) >= 3
    assert preview["blockers"][0]["code"] == "MODULE_SELECTION_REQUIRED"


def test_project_qualifier_and_role_semantics_select_project05_calibration():
    catalog = build_global_module_catalog(
        WORKSPACE, project_ids=("project01", "project03", "project05")
    )
    context = create_global_assembly_context(
        "project-qualified-role", catalog_digest=catalog["catalogDigest"]
    )

    preview = preview_global_assembly_command(
        catalog,
        context,
        {"requirement": "请添加项目05的喷嘴校准模组"},
    )

    selected = next(
        item
        for item in catalog["moduleDefinitions"]
        if item["moduleDefinitionId"] == preview["selectedModuleDefinitionId"]
    )
    assert preview["status"] == "ready"
    assert preview["resolution"] == "unique_natural_language_match"
    assert {
        alias["projectId"] for alias in selected["projectAliases"]
    } == {"project05"}
    assert {
        alias["moduleToken"] for alias in selected["projectAliases"]
    } == {"G000"}
    assert selected["category"] == "calibration"


def test_action_object_focus_excludes_context_target_from_module_alternatives():
    catalog = build_global_module_catalog(
        WORKSPACE, project_ids=("project01", "project02", "project03", "project05")
    )
    context = create_global_assembly_context(
        "action-object-focus", catalog_digest=catalog["catalogDigest"]
    )
    base = next(
        item
        for item in catalog["moduleDefinitions"]
        if any(
            alias["projectId"] == "project03" and alias["moduleToken"] == "AA00"
            for alias in item["projectAliases"]
        )
    )
    base_preview = preview_global_assembly_command(
        catalog,
        context,
        {
            "requirement": "请先建立一套箱体与回流固定环境，作为后续功能模组的安装基础。",
            "moduleDefinitionId": base["moduleDefinitionId"],
        },
    )
    context = apply_global_command_preview(
        context,
        base_preview,
        preview_digest=base_preview["previewDigest"],
        confirmed=True,
    )

    preview = preview_global_assembly_command(
        catalog,
        context,
        {
            "requirement": (
                "在当前固定环境上安装一套产品传输模组，"
                "用于承载产品并依次经过两个点胶工作区。"
            )
        },
    )

    assert preview["status"] == "needs_confirmation"
    assert preview["moduleSelectionEvidence"] == {
        "basis": "post_action_object",
        "text": "一套产品传输模组",
    }
    assert len(preview["moduleAlternatives"]) >= 3
    alternative_ids = {
        item["moduleDefinitionId"] for item in preview["moduleAlternatives"]
    }
    assert base["moduleDefinitionId"] not in alternative_ids
    categories = {
        item["category"]
        for item in catalog["moduleDefinitions"]
        if item["moduleDefinitionId"] in alternative_ids
    }
    assert categories == {"transport"}


def test_apply_rejects_unconfirmed_or_stale_preview(catalog):
    context = create_global_assembly_context("safe-write", catalog_digest=catalog["catalogDigest"])
    frame = _definition(catalog, "A600")
    preview = preview_global_assembly_command(
        catalog,
        context,
        {"requirement": "安装A600", "moduleDefinitionId": frame["moduleDefinitionId"]},
    )
    with pytest.raises(GlobalAssemblyContextError):
        apply_global_command_preview(
            context, preview, preview_digest=preview["previewDigest"], confirmed=False
        )
    with pytest.raises(GlobalAssemblyContextError):
        apply_global_command_preview(
            context, preview, preview_digest="0" * 64, confirmed=True
        )


def _apply_ready(catalog, context, payload):
    preview = preview_global_assembly_command(catalog, context, payload)
    assert preview["status"] == "ready", preview
    return apply_global_command_preview(
        context,
        preview,
        preview_digest=preview["previewDigest"],
        confirmed=True,
    ), preview


def test_project02_t401_allows_two_declared_instances_and_uses_target_hint(catalog):
    context = create_global_assembly_context(
        "t401-double-instance", catalog_digest=catalog["catalogDigest"]
    )
    frame = _definition(catalog, "A600")
    ccd = _definition(catalog, "A200")
    supply = _definition(catalog, "T401")
    context, _ = _apply_ready(
        catalog,
        context,
        {
            "requirement": "安装项目02的A600箱体",
            "moduleDefinitionId": frame["moduleDefinitionId"],
        },
    )
    context, _ = _apply_ready(
        catalog,
        context,
        {
            "requirement": "将A200 CCD安装到A600",
            "moduleDefinitionId": ccd["moduleDefinitionId"],
        },
    )
    context, first = _apply_ready(
        catalog,
        context,
        {
            "requirement": "将第一套T401供胶系统安装到A600",
            "moduleDefinitionId": supply["moduleDefinitionId"],
        },
    )
    context, second = _apply_ready(
        catalog,
        context,
        {
            "requirement": "将第二套T401供胶系统按距离关系安装到A200",
            "moduleDefinitionId": supply["moduleDefinitionId"],
        },
    )

    assert first["connectionCandidates"][0]["existingInstanceId"] == context["instances"][0]["instanceId"]
    assert second["connectionCandidates"][0]["existingInstanceId"] == context["instances"][1]["instanceId"]
    supplies = [
        item
        for item in context["instances"]
        if item["moduleDefinitionId"] == supply["moduleDefinitionId"]
    ]
    assert [item["instanceOrdinal"] for item in supplies] == [1, 2]
    assert all(item["declaredInstanceCapacity"] == 2 for item in supplies)

    blocked = preview_global_assembly_command(
        catalog,
        context,
        {
            "requirement": "再增加第三套T401",
            "moduleDefinitionId": supply["moduleDefinitionId"],
        },
    )
    assert blocked["status"] == "blocked"
    assert blocked["blockers"][0]["code"] == "MODULE_INSTANCE_CAPACITY_REACHED"
