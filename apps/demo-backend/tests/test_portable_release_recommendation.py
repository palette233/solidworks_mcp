from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from demo_backend import main
from demo_backend.global_assembly_context import validate_global_assembly_context
from demo_backend.portable_release_recommendation import (
    build_portable_release_context,
    recommend_portable_relation_release,
)
from demo_backend import global_assembly_workbench as workbench


WORKSPACE = Path(__file__).resolve().parents[3]
SOURCE = WORKSPACE / "demo/global_assembly_contexts/global-demo.json"


def _source_context() -> dict:
    return json.loads(SOURCE.read_text(encoding="utf-8-sig"))


def test_project02_legacy_graph_recommends_smallest_latest_portable_release():
    context = _source_context()
    before = deepcopy(context)

    preview = recommend_portable_relation_release(WORKSPACE, context)

    assert context == before
    assert preview["status"] == "ready"
    assert preview["recommendation"]["releaseId"] == (
        "relation-v30-project02-a800-a180-portable-driving-20261011"
    )
    assert preview["recommendation"]["authorizedTemplateCount"] == 2
    assert len(preview["recommendation"]["replacements"]) == 2
    assert all(
        "nonanchor-driving" in row["portableTemplateId"]
        for row in preview["recommendation"]["replacements"]
    )
    assert preview["executionBoundary"]["sourceContextMutated"] is False
    assert preview["executionBoundary"]["solidWorksExecuted"] is False


def test_confirmed_upgrade_builds_new_context_and_preserves_source():
    context = _source_context()
    before = deepcopy(context)
    preview = recommend_portable_relation_release(WORKSPACE, context)
    release_id = preview["recommendation"]["releaseId"]

    upgraded, evidence = build_portable_release_context(
        WORKSPACE,
        context,
        expected_preview_digest=preview["previewDigest"],
        release_id=release_id,
        target_context_id="global-demo-portable-unit",
    )

    assert context == before
    assert upgraded["contextId"] == "global-demo-portable-unit"
    assert upgraded["revision"] == context["revision"] + 1
    assert upgraded["relationReleaseBinding"]["releaseId"] == release_id
    assert all(
        "nonanchor-driving" in row["globalTemplateId"]
        for row in upgraded["connections"]
    )
    assert all(
        row["relationProfile"]["constraintExplanation"]["state"]
        == "declared_closed"
        for row in upgraded["connections"]
    )
    assert validate_global_assembly_context(upgraded)["success"] is True
    assert evidence["sourceContextDigest"] == context["contextDigest"]
    assert evidence["targetContextDigest"] == upgraded["contextDigest"]
    assert evidence["solidWorksExecuted"] is False


def test_portable_release_routes_are_exposed():
    paths = main.app.openapi()["paths"]
    assert (
        "/api/demo/global-assembly-contexts/{context_id}/portable-release-recommendation"
        in paths
    )
    assert (
        "/api/demo/global-assembly-contexts/{context_id}/portable-release-upgrades"
        in paths
    )


def _definition(catalog: dict, token: str) -> dict:
    return _project_definition(catalog, "project02", token)


def _project_definition(catalog: dict, project_id: str, token: str) -> dict:
    return next(
        row
        for row in catalog["moduleDefinitions"]
        if any(
            alias.get("projectId") == project_id and alias.get("moduleToken") == token
            for alias in row.get("projectAliases") or []
        )
    )


def test_first_connection_binds_portable_release_in_same_confirmed_revision(
    tmp_path, monkeypatch
):
    context_dir = Path(".tmp") / f"portable-first-bind-{tmp_path.name}"
    monkeypatch.setattr(workbench, "DEFAULT_CONTEXT_DIR", context_dir)
    catalog = workbench.load_global_catalog(WORKSPACE)
    base = _definition(catalog, "A600")
    transport = _definition(catalog, "A800")
    scanner = _definition(catalog, "A180")
    calibration = _definition(catalog, "A500")
    cleaning_weighing = _definition(catalog, "A700")
    context_id = "portable-first-bind"
    workbench.create_context(
        WORKSPACE, {"contextId": context_id, "overwrite": True}
    )

    base_preview = workbench.preview_command(
        WORKSPACE,
        context_id,
        {
            "requirement": "建立设备箱体与安装基座",
            "moduleDefinitionId": base["moduleDefinitionId"],
        },
    )
    base_context = workbench.apply_command(
        WORKSPACE,
        context_id,
        {
            "preview": base_preview,
            "previewDigest": base_preview["previewDigest"],
            "confirmed": True,
        },
    )["context"]
    assert base_context.get("relationReleaseBinding") is None

    transport_preview = workbench.preview_command(
        WORKSPACE,
        context_id,
        {
            "requirement": "在当前设备箱体上安装产品传输模组",
            "moduleDefinitionId": transport["moduleDefinitionId"],
        },
    )
    transition = transport_preview["portableReleaseTransition"]
    assert transition["releaseId"] == (
        "relation-v30-project02-a800-a180-portable-driving-20261011"
    )
    assert "nonanchor-driving" in transport_preview["proposedPatch"]["connection"][
        "globalTemplateId"
    ]
    transport_context = workbench.apply_command(
        WORKSPACE,
        context_id,
        {
            "preview": transport_preview,
            "previewDigest": transport_preview["previewDigest"],
            "confirmed": True,
        },
    )["context"]
    assert transport_context["revision"] == 2
    assert transport_context["relationReleaseBinding"]["releaseId"] == transition[
        "releaseId"
    ]

    scanner_preview = workbench.preview_command(
        WORKSPACE,
        context_id,
        {
            "requirement": "在传输线入口附近增加条码扫描模组",
            "moduleDefinitionId": scanner["moduleDefinitionId"],
        },
    )
    assert scanner_preview["status"] == "ready"
    assert scanner_preview.get("portableReleaseTransition") is None
    assert "nonanchor-driving" in scanner_preview["proposedPatch"]["connection"][
        "globalTemplateId"
    ]
    final_context = workbench.apply_command(
        WORKSPACE,
        context_id,
        {
            "preview": scanner_preview,
            "previewDigest": scanner_preview["previewDigest"],
            "confirmed": True,
        },
    )["context"]
    assert final_context["revision"] == 3
    assert len(final_context["connections"]) == 2

    side_specific_preview = workbench.preview_command(
        WORKSPACE,
        context_id,
        {
            "requirement": "在设备操作侧增加喷嘴校准模组",
            "moduleDefinitionId": calibration["moduleDefinitionId"],
        },
    )
    assert side_specific_preview["status"] == "blocked"
    assert side_specific_preview.get("portableReleaseTransition") is None
    assert any(
        row["code"] == "NO_COMPATIBLE_PORT_PAIR"
        for row in side_specific_preview["blockers"]
    )

    calibration_preview = workbench.preview_command(
        WORKSPACE,
        context_id,
        {
            "requirement": "在设备箱体上安装喷嘴校准模组",
            "moduleDefinitionId": calibration["moduleDefinitionId"],
        },
    )
    expansion = calibration_preview["portableReleaseTransition"]
    assert calibration_preview["status"] == "ready"
    assert expansion["transitionKind"] == "expand"
    assert expansion["sourceReleaseId"] == transition["releaseId"]
    assert expansion["releaseId"] == (
        "relation-v31-project02-a800-a180-a500-portable-driving-20261011"
    )
    assert len(expansion["upgradedConnections"]) == 2
    tampered = deepcopy(calibration_preview)
    tampered["portableReleaseTransition"]["releaseId"] = "forged-release"
    tampered.pop("previewDigest")
    tampered["previewDigest"] = hashlib.sha256(
        json.dumps(
            tampered,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    with pytest.raises(ValueError, match="便携发布编号与不可变绑定不一致"):
        workbench.apply_command(
            WORKSPACE,
            context_id,
            {
                "preview": tampered,
                "previewDigest": tampered["previewDigest"],
                "confirmed": True,
            },
        )
    calibration_context = workbench.apply_command(
        WORKSPACE,
        context_id,
        {
            "preview": calibration_preview,
            "previewDigest": calibration_preview["previewDigest"],
            "confirmed": True,
        },
    )["context"]
    assert calibration_context["revision"] == 4
    assert calibration_context["relationReleaseBinding"]["releaseId"] == expansion[
        "releaseId"
    ]
    assert len(calibration_context["connections"]) == 3
    calibration_manifest = workbench.compile_cad_transaction_manifest(
        WORKSPACE, context_id
    )
    assert calibration_manifest["status"] == (
        "ready_for_generic_executor_implementation"
    )
    assert calibration_manifest["packetCount"] == 3
    assert calibration_manifest["blockers"] == []

    cleaning_preview = workbench.preview_command(
        WORKSPACE,
        context_id,
        {
            "requirement": "在设备箱体上安装清洁称重模组",
            "moduleDefinitionId": cleaning_weighing["moduleDefinitionId"],
        },
    )
    cleaning_expansion = cleaning_preview["portableReleaseTransition"]
    assert cleaning_preview["status"] == "ready"
    assert cleaning_expansion["transitionKind"] == "expand"
    assert cleaning_expansion["sourceReleaseId"] == expansion["releaseId"]
    assert cleaning_expansion["releaseId"] == (
        "relation-v32-project02-a800-a180-a500-a700-portable-driving-20261011"
    )
    assert len(cleaning_expansion["upgradedConnections"]) == 3
    cleaning_context = workbench.apply_command(
        WORKSPACE,
        context_id,
        {
            "preview": cleaning_preview,
            "previewDigest": cleaning_preview["previewDigest"],
            "confirmed": True,
        },
    )["context"]
    assert cleaning_context["revision"] == 5
    assert cleaning_context["relationReleaseBinding"]["releaseId"] == (
        cleaning_expansion["releaseId"]
    )
    assert len(cleaning_context["connections"]) == 4

    manifest = workbench.compile_cad_transaction_manifest(WORKSPACE, context_id)
    assert manifest["status"] == "blocked"
    assert manifest["packetCount"] == 4
    assert any(
        row["code"] == "DRIVING_TEMPLATE_EXTERNAL_POSE_EQUIVALENCE_REQUIRED"
        for row in manifest["blockers"]
    )


def test_atomic_command_sequence_uses_same_portable_release_growth(
    tmp_path, monkeypatch
):
    context_dir = Path(".tmp") / f"portable-sequence-{tmp_path.name}"
    monkeypatch.setattr(workbench, "DEFAULT_CONTEXT_DIR", context_dir)
    catalog = workbench.load_global_catalog(WORKSPACE)
    definitions = {
        token: _definition(catalog, token)
        for token in ("A600", "A800", "A180", "A500", "A700")
    }
    context_id = "portable-sequence"
    workbench.create_context(
        WORKSPACE, {"contextId": context_id, "overwrite": True}
    )

    result = workbench.apply_command_sequence(
        WORKSPACE,
        context_id,
        {
            "confirmed": True,
            "commands": [
                {
                    "requirement": "建立设备箱体与安装基座",
                    "moduleDefinitionId": definitions["A600"]["moduleDefinitionId"],
                },
                {
                    "requirement": "在设备箱体上安装产品传输模组",
                    "moduleDefinitionId": definitions["A800"]["moduleDefinitionId"],
                },
                {
                    "requirement": "在传输线入口附近增加条码扫描模组",
                    "moduleDefinitionId": definitions["A180"]["moduleDefinitionId"],
                },
                {
                    "requirement": "在设备箱体上安装喷嘴校准模组",
                    "moduleDefinitionId": definitions["A500"]["moduleDefinitionId"],
                },
                {
                    "requirement": "在设备箱体上安装清洁称重模组",
                    "moduleDefinitionId": definitions["A700"]["moduleDefinitionId"],
                },
            ],
        },
    )

    assert result["success"] is True
    assert result["turnCount"] == 5
    context = result["context"]
    assert context["revision"] == 5
    assert len(context["instances"]) == 5
    assert len(context["connections"]) == 4
    assert context["relationReleaseBinding"]["releaseId"] == (
        "relation-v32-project02-a800-a180-a500-a700-portable-driving-20261011"
    )
    assert all(
        "nonanchor-driving" in row["globalTemplateId"]
        for row in context["connections"]
    )
    manifest = workbench.compile_cad_transaction_manifest(WORKSPACE, context_id)
    assert manifest["status"] == "blocked"
    assert manifest["packetCount"] == 4
    assert any(
        row["code"] == "DRIVING_TEMPLATE_EXTERNAL_POSE_EQUIVALENCE_REQUIRED"
        for row in manifest["blockers"]
    )


def test_project02_release_grows_to_v36_without_revoked_a700(
    tmp_path, monkeypatch
):
    context_dir = Path(".tmp") / f"portable-v36-{tmp_path.name}"
    monkeypatch.setattr(workbench, "DEFAULT_CONTEXT_DIR", context_dir)
    catalog = workbench.load_global_catalog(WORKSPACE)
    definitions = {
        token: _definition(catalog, token)
        for token in (
            "A600",
            "A800",
            "A180",
            "A500",
            "A300",
            "A200",
            "A100",
            "T401",
        )
    }
    context_id = "portable-v36-no-a700"
    workbench.create_context(
        WORKSPACE, {"contextId": context_id, "overwrite": True}
    )
    commands = [
        ("A600", "建立设备箱体与安装基座"),
        ("A800", "在A600设备箱体上安装产品传输模组"),
        ("A180", "在A600设备箱体上安装条码扫描模组"),
        ("A500", "在A600设备箱体上安装喷嘴校准模组"),
        ("A300", "在A600设备箱体上安装排胶回收模组"),
        ("A200", "在A600设备箱体上安装CCD视觉定位模组"),
        ("A100", "在A600设备箱体上安装XYZ龙门双阀点胶模组"),
        ("T401", "在A600设备箱体上安装第一套胶水供应模组"),
        ("T401", "将第二套胶水供应模组连接到A200 CCD视觉定位模组"),
    ]
    result = workbench.apply_command_sequence(
        WORKSPACE,
        context_id,
        {
            "confirmed": True,
            "commands": [
                {
                    "requirement": requirement,
                    "moduleDefinitionId": definitions[token]["moduleDefinitionId"],
                }
                for token, requirement in commands
            ],
        },
    )

    assert result["success"] is True
    context = result["context"]
    assert context["revision"] == 9
    assert len(context["instances"]) == 9
    assert len(context["connections"]) == 8
    assert context["relationReleaseBinding"]["releaseId"] == (
        "relation-v36-project02-nine-addon-portable-driving-20261011"
    )
    manifest = workbench.compile_cad_transaction_manifest(WORKSPACE, context_id)
    assert manifest["status"] == "ready_for_generic_executor_implementation"
    assert manifest["packetCount"] == 8
    assert manifest["blockers"] == []


def test_project02_base_accepts_project03_calibration_by_semantic_ports(
    tmp_path, monkeypatch
):
    context_dir = Path(".tmp") / f"portable-cross-project-calibration-{tmp_path.name}"
    monkeypatch.setattr(workbench, "DEFAULT_CONTEXT_DIR", context_dir)
    catalog = workbench.load_global_catalog(WORKSPACE)
    base = _project_definition(catalog, "project02", "A600")
    calibration = _project_definition(catalog, "project03", "AH00")
    context_id = "portable-cross-project-calibration"
    workbench.create_context(
        WORKSPACE, {"contextId": context_id, "overwrite": True}
    )

    base_preview = workbench.preview_command(
        WORKSPACE,
        context_id,
        {
            "requirement": "建立设备箱体与安装基座",
            "moduleDefinitionId": base["moduleDefinitionId"],
        },
    )
    workbench.apply_command(
        WORKSPACE,
        context_id,
        {
            "preview": base_preview,
            "previewDigest": base_preview["previewDigest"],
            "confirmed": True,
        },
    )

    calibration_preview = workbench.preview_command(
        WORKSPACE,
        context_id,
        {
            "requirement": "在设备操作侧安装喷嘴校准模组",
            "moduleDefinitionId": calibration["moduleDefinitionId"],
        },
    )
    assert calibration_preview["status"] == "ready"
    transition = calibration_preview["portableReleaseTransition"]
    assert transition["transitionKind"] == "first_bind"
    assert transition["discoveryMode"] == "immutable_release_port_discovery"
    assert transition["releaseId"] == (
        "relation-v42-project02-a600-ah00-operation-side-language-20261012"
    )
    connection = calibration_preview["proposedPatch"]["connection"]
    assert calibration_preview["proposedPatch"]["instance"][
        "moduleDefinitionId"
    ] == calibration["moduleDefinitionId"]
    port_ids = {connection["portAId"], connection["portBId"]}
    assert any(calibration["moduleDefinitionId"] in port_id for port_id in port_ids)
    assert any(base["moduleDefinitionId"] in port_id for port_id in port_ids)
    assert connection["relationProfile"]["drivesPlacement"] is True
    assert connection["relationProfile"]["constraintExplanation"]["state"] == (
        "declared_closed"
    )

    context = workbench.apply_command(
        WORKSPACE,
        context_id,
        {
            "preview": calibration_preview,
            "previewDigest": calibration_preview["previewDigest"],
            "confirmed": True,
        },
    )["context"]
    assert context["revision"] == 2
    assert context["relationReleaseBinding"]["releaseId"] == transition["releaseId"]
    assert len(context["connections"]) == 1
    manifest = workbench.compile_cad_transaction_manifest(WORKSPACE, context_id)
    assert manifest["status"] == "ready_for_generic_executor_implementation"
    assert manifest["packetCount"] == 1
    assert manifest["blockers"] == []


def test_project03_base_grows_cross_project_calibration_transport_scanner_chain(
    tmp_path, monkeypatch
):
    context_dir = Path(".tmp") / f"portable-cross-project-chain-{tmp_path.name}"
    monkeypatch.setattr(workbench, "DEFAULT_CONTEXT_DIR", context_dir)
    catalog = workbench.load_global_catalog(WORKSPACE)
    definitions = {
        ("project03", "AA00"): _project_definition(catalog, "project03", "AA00"),
        ("project01", "BD00"): _project_definition(catalog, "project01", "BD00"),
        ("project01", "SS00"): _project_definition(catalog, "project01", "SS00"),
        ("project03", "AI00"): _project_definition(catalog, "project03", "AI00"),
    }
    context_id = "portable-cross-project-chain"
    workbench.create_context(
        WORKSPACE, {"contextId": context_id, "overwrite": True}
    )

    commands = [
        (
            definitions[("project03", "AA00")],
            "建立箱体与回流固定安装环境",
            None,
        ),
        (
            definitions[("project01", "BD00")],
            "在当前箱体上安装喷嘴校准模组",
            "relation-v45-project03-aa00-project01-bd00-calibration-driving-20261012",
        ),
        (
            definitions[("project01", "SS00")],
            "在当前箱体上安装产品传输模组",
            "relation-v47-project03-aa00-project01-calibration-transport-driving-20261012",
        ),
        (
            definitions[("project03", "AI00")],
            "在传输线入口附近安装条码扫描模组",
            "relation-v48-project03-aa00-transport-scanner-calibration-driving-20261012",
        ),
    ]
    transition_kinds = []
    for definition, requirement, expected_release in commands:
        preview = workbench.preview_command(
            WORKSPACE,
            context_id,
            {
                "requirement": requirement,
                "moduleDefinitionId": definition["moduleDefinitionId"],
            },
        )
        assert preview["status"] == "ready"
        transition = preview.get("portableReleaseTransition")
        if expected_release is None:
            assert transition is None
        else:
            assert transition["releaseId"] == expected_release
            transition_kinds.append(transition["transitionKind"])
        workbench.apply_command(
            WORKSPACE,
            context_id,
            {
                "preview": preview,
                "previewDigest": preview["previewDigest"],
                "confirmed": True,
            },
        )

    context = workbench.load_context(WORKSPACE, context_id)
    assert transition_kinds == ["first_bind", "expand", "expand"]
    assert context["revision"] == 4
    assert len(context["instances"]) == 4
    assert len(context["connections"]) == 3
    assert context["relationReleaseBinding"]["releaseId"] == (
        "relation-v48-project03-aa00-transport-scanner-calibration-driving-20261012"
    )
    assert {
        row["moduleDefinitionId"] for row in context["instances"]
    } == {definition["moduleDefinitionId"] for definition, _, _ in commands}
    manifest = workbench.compile_cad_transaction_manifest(WORKSPACE, context_id)
    assert manifest["status"] == "ready_for_generic_executor_implementation"
    assert manifest["packetCount"] == 3
    assert manifest["blockers"] == []
