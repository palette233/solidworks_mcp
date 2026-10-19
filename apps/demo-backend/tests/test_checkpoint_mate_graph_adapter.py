import json
from pathlib import Path

import pytest

from demo_backend.checkpoint_mate_graph_adapter import (
    CheckpointMateGraphAdapterError,
    build_checkpoint_graph_export_spec,
    compile_temporary_connection_for_checkpoint,
    finalize_checkpoint_graph_export,
    load_checkpoint_graph_binding,
)
from demo_backend.temporary_semantic_ports import (
    preview_temporary_connection,
    register_captured_face,
    reset_temporary_ports,
)


def _context() -> dict:
    return {
        "contextId": "checkpoint-unit",
        "revision": 2,
        "contextDigest": "d" * 64,
        "instances": [
            {"instanceId": "case-001", "moduleDefinitionId": "global/case"},
            {"instanceId": "scanner-001", "moduleDefinitionId": "global/scanner"},
            {"instanceId": "service-001", "moduleDefinitionId": "global/service"},
        ],
    }


def _catalog() -> dict:
    return {
        "moduleDefinitions": [
            {
                "moduleDefinitionId": "global/case",
                "projectAliases": [{"projectId": "project02", "moduleToken": "A600"}],
            },
            {
                "moduleDefinitionId": "global/scanner",
                "projectAliases": [{"projectId": "project02", "moduleToken": "A180"}],
            },
            {
                "moduleDefinitionId": "global/service",
                "projectAliases": [{"projectId": "project02", "moduleToken": "A700"}],
            },
        ]
    }


def _conversation(assembly: Path) -> dict:
    return {
        "latestSuccessfulDemo": {
            "jobId": "project02-job-unit",
            "projectId": "project02",
            "contextRevision": 2,
            "contextDigest": "d" * 64,
            "assemblyPath": str(assembly),
        }
    }


def _endpoint(token: str, face_index: int) -> dict:
    return {
        "Index": 0,
        "ModuleToken": token,
        "ModuleHierarchyPath": f"{token}-1",
        "RelativeLeafHierarchyPath": f"{token}-leaf-1",
        "LeafComponentPath": f"D:/{token}.SLDPRT",
        "GeometryType": "Face",
        "BodyIndex": 0,
        "FaceIndexInBody": face_index,
        "FaceArea": 0.01 + face_index / 10000,
        "FaceCenterLocal": [0.0, 0.0, float(face_index)],
        "FaceNormalLocal": [0.0, 0.0, 1.0],
        "SourceAssemblyPersistentReferenceBase64": f"ref-{token}-{face_index}",
    }


def _captured(token: str, face_index: int) -> dict:
    return {
        "EndpointId": f"face:{token.lower()}:{face_index}",
        "ModulePath": f"D:/{token}.SLDASM",
        "GeometryClass": "Plane",
        "RecoveryConfidence": "USER_SELECTED",
        "Endpoint": _endpoint(token, face_index),
    }


def _captured_with_world_normal(
    token: str, face_index: int, normal: list[float]
) -> dict:
    captured = _captured(token, face_index)
    captured["Endpoint"]["FaceNormalWorld"] = normal
    return captured


def _mate(name: str, first: str, second: str, offset: int) -> dict:
    first_endpoint = _endpoint(first, offset)
    second_endpoint = _endpoint(second, offset + 1)
    first_endpoint["Index"] = 0
    second_endpoint["Index"] = 1
    return {
        "MateName": name,
        "MateType": 3,
        "MateTypeName": "swMatePARALLEL",
        "Alignment": 0,
        "AlignmentName": "swMateAlignALIGNED",
        "Distance": None,
        "Angle": None,
        "IsSuppressed": False,
        "ModuleTokens": [first, second],
        "ModuleHierarchyPaths": [f"{first}-1", f"{second}-1"],
        "Endpoints": [first_endpoint, second_endpoint],
    }


def _graph(assembly: Path, *, include_service_mate: bool = True) -> dict:
    mates = [_mate("scanner-to-case", "A180", "A600", 10)]
    if include_service_mate:
        mates.append(_mate("case-to-service", "A600", "A700", 20))
    return {
        "SchemaVersion": "solidworks-module-mate-graph/v1.3",
        "SourceAssemblyPath": str(assembly),
        "Modules": [
            {"ModuleToken": token, "HierarchyPath": f"{token}-1", "Path": f"D:/{token}.SLDASM"}
            for token in ("A600", "A180", "A700")
        ],
        "Mates": mates,
    }


def _bound_fixture(tmp_path: Path, *, include_service_mate: bool = True):
    workspace = tmp_path / "workspace"
    context_path = workspace / "demo" / "global_assembly_contexts" / "checkpoint-unit.json"
    context_path.parent.mkdir(parents=True)
    assembly = tmp_path / "checkpoint.SLDASM"
    assembly.write_bytes(b"assembly-v1")
    spec = build_checkpoint_graph_export_spec(
        workspace,
        context_path,
        _context(),
        _catalog(),
        _conversation(assembly),
        expected_demo_job_id="project02-job-unit",
    )
    graph_path = Path(spec["outputGraphPath"])
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    graph_path.write_text(
        json.dumps(_graph(assembly, include_service_mate=include_service_mate)),
        encoding="utf-8",
    )
    finalized = finalize_checkpoint_graph_export(spec, "ok")
    return context_path, assembly, spec, finalized["binding"]


def test_checkpoint_export_is_bound_to_context_job_and_file_hash(tmp_path: Path):
    context_path, assembly, spec, binding = _bound_fixture(tmp_path)

    assert spec["toolCall"]["tool"] == "export_module_mate_graph"
    assert spec["moduleTokens"] == ["A600", "A180", "A700"]
    assert binding["demoJobId"] == "project02-job-unit"
    assert binding["mateGraph"]["moduleCount"] == 3
    assert binding["mateGraph"]["mateCount"] == 2
    assert Path(spec["bindingPath"]).is_file()
    repeated = build_checkpoint_graph_export_spec(
        tmp_path / "workspace",
        context_path,
        _context(),
        _catalog(),
        _conversation(assembly),
    )
    assert repeated["specDigest"] == spec["specDigest"]
    assert load_checkpoint_graph_binding(repeated)["bindingDigest"] == binding["bindingDigest"]


def test_generic_checkpoint_resolves_each_instance_from_its_source_project(
    tmp_path: Path,
):
    assembly = tmp_path / "cross-project.SLDASM"
    assembly.write_bytes(b"cross-project-assembly")
    context = {
        "contextId": "cross-project-unit",
        "revision": 2,
        "contextDigest": "e" * 64,
        "instances": [
            {"instanceId": "base-001", "moduleDefinitionId": "cad/project03/aa00"},
            {"instanceId": "transport-001", "moduleDefinitionId": "cad/project01/ss00"},
        ],
    }
    catalog = {
        "moduleDefinitions": [
            {
                "moduleDefinitionId": "cad/project03/aa00",
                "projectAliases": [{"projectId": "project03", "moduleToken": "AA00"}],
            },
            {
                "moduleDefinitionId": "cad/project01/ss00",
                "projectAliases": [{"projectId": "project01", "moduleToken": "SS00"}],
            },
        ]
    }
    conversation = {
        "latestSuccessfulDemo": {
            "jobId": "project-global-job-unit",
            "projectId": "project-global",
            "contextRevision": 2,
            "contextDigest": "e" * 64,
            "assemblyPath": str(assembly),
        }
    }

    spec = build_checkpoint_graph_export_spec(
        tmp_path,
        tmp_path / "cross-project-unit.json",
        context,
        catalog,
        conversation,
    )

    assert spec["moduleTokens"] == ["AA00", "SS00"]
    assert spec["moduleTokenByInstanceId"] == {
        "base-001": "AA00",
        "transport-001": "SS00",
    }
    assert spec["sourceProjectByInstanceId"] == {
        "base-001": "project03",
        "transport-001": "project01",
    }


def test_export_rejects_stale_revision_and_changed_job(tmp_path: Path):
    assembly = tmp_path / "checkpoint.SLDASM"
    assembly.write_bytes(b"assembly")
    conversation = _conversation(assembly)
    conversation["latestSuccessfulDemo"]["contextRevision"] = 1
    with pytest.raises(CheckpointMateGraphAdapterError, match="不是当前图修订"):
        build_checkpoint_graph_export_spec(
            tmp_path, tmp_path / "context.json", _context(), _catalog(), conversation
        )

    conversation = _conversation(assembly)
    with pytest.raises(CheckpointMateGraphAdapterError, match="已从other-job变化"):
        build_checkpoint_graph_export_spec(
            tmp_path,
            tmp_path / "context.json",
            _context(),
            _catalog(),
            conversation,
            expected_demo_job_id="other-job",
        )


def test_compile_preserves_target_mates_adds_selected_face_mate_and_excludes_unrelated(
    tmp_path: Path,
):
    context_path, _, _, binding = _bound_fixture(tmp_path)
    context = _context()
    reset_temporary_ports(context_path, context)
    scanner = register_captured_face(
        context_path,
        context,
        _captured("A180", 101),
        instance_id="scanner-001",
        module_token="A180",
        display_name="扫描安装面",
        interface_type="temporary_planar_mount",
    )
    case = register_captured_face(
        context_path,
        context,
        _captured("A600", 102),
        instance_id="case-001",
        module_token="A600",
        display_name="箱体承载面",
        interface_type="temporary_planar_mount",
    )
    preview = preview_temporary_connection(
        context_path,
        context,
        "将扫描安装面与箱体承载面建立距离60mm配合",
        port_ids=[scanner["port"]["portId"], case["port"]["portId"]],
    )
    endpoint_catalog = json.loads(
        context_path.with_suffix(".temporary-face-catalog.json").read_text(encoding="utf-8")
    )
    result = compile_temporary_connection_for_checkpoint(
        context,
        binding,
        preview,
        endpoint_catalog,
        target_module_token="A180",
        output_dir=tmp_path / "compiled",
    )

    assert result["status"] == "ready_for_explicit_direct_mate_edit_confirmation"
    assert result["preservedExistingMateNames"] == ["scanner-to-case"]
    names = [row["MateName"] for row in result["effectiveGraph"]["Mates"]]
    assert "scanner-to-case" in names
    assert "case-to-service" not in names
    assert result["newMateName"] in names
    new_mate = next(
        row for row in result["effectiveGraph"]["Mates"] if row["MateName"] == result["newMateName"]
    )
    assert new_mate["Distance"] == pytest.approx(0.06)
    assert result["effectiveGraph"]["EditPolicy"]["fixedModuleTokens"] == ["A600"]
    assert Path(result["artifacts"]["compiledPreviewPath"]).is_file()
    assert result["executionBoundary"]["solidWorksModified"] is False


def test_compile_zero_mate_target_uses_explicit_checkpoint_pose_anchor(tmp_path: Path):
    context_path, _, _, binding = _bound_fixture(
        tmp_path, include_service_mate=False
    )
    context = _context()
    reset_temporary_ports(context_path, context)
    service = register_captured_face(
        context_path,
        context,
        _captured_with_world_normal("A700", 201, [0.0, 1.0, 0.0]),
        instance_id="service-001",
        module_token="A700",
        display_name="服务模组安装面",
        interface_type="temporary_planar_mount",
    )
    case = register_captured_face(
        context_path,
        context,
        _captured_with_world_normal("A600", 202, [0.0, -1.0, 0.0]),
        instance_id="case-001",
        module_token="A600",
        display_name="箱体安装面",
        interface_type="temporary_planar_mount",
    )
    preview = preview_temporary_connection(
        context_path,
        context,
        "将服务模组安装面与箱体安装面建立重合配合",
        port_ids=[service["port"]["portId"], case["port"]["portId"]],
    )
    endpoint_catalog = json.loads(
        context_path.with_suffix(".temporary-face-catalog.json").read_text(
            encoding="utf-8"
        )
    )
    result = compile_temporary_connection_for_checkpoint(
        context,
        binding,
        preview,
        endpoint_catalog,
        target_module_token="A700",
        target_leaf_pose_anchors=[
            {
                "relativeLeafHierarchyPath": "A700-moving-branch-1",
                "transform": [
                    1.0, 0.0, 0.0, 0.0,
                    1.0, 0.0, 0.0, 0.0,
                    1.0, 0.1, 0.2, 0.3,
                    1.0, 0.0, 0.0, 0.0,
                ],
                "evidence": "unit-test checkpoint flexible state",
            }
        ],
    )

    assert result["status"] == "ready_for_explicit_direct_mate_edit_confirmation"
    assert result["preservedExistingMateNames"] == []
    assert result["patch"]["caseAnchoredModuleTokens"] == ["A700"]
    assert result["effectiveGraph"]["EditPolicy"]["caseAnchoredModuleTokens"] == [
        "A700"
    ]
    assert result["patch"]["sourceMateNamesToSuppress"] == []
    assert result["effectiveGraph"]["EditPolicy"]["sourceMateNamesToSuppress"] == []
    new_mate = next(
        row
        for row in result["effectiveGraph"]["Mates"]
        if row["MateName"] == result["newMateName"]
    )
    assert new_mate["Alignment"] == 1
    assert new_mate["AlignmentName"] == "swMateAlignANTI_ALIGNED"
    assert result["constraintSafety"]["selectedFaceAlignment"]["normalDot"] == pytest.approx(-1.0)
    assert result["constraintSafety"]["targetLeafPoseAnchorCount"] == 1
    assert len(result["effectiveGraph"]["EditPolicy"]["targetLeafPoseAnchors"]) == 1
    assert result["constraintSafety"]["usesCheckpointPoseAnchor"] is True
    assert result["executionBoundary"]["nextTool"] == (
        "remate_component_in_assembly_context_from_mate_graph"
    )


def test_compile_fails_if_checkpoint_or_target_identity_changes(tmp_path: Path):
    context_path, assembly, _, binding = _bound_fixture(tmp_path)
    context = _context()
    reset_temporary_ports(context_path, context)
    first = register_captured_face(
        context_path,
        context,
        _captured("A180", 101),
        instance_id="scanner-001",
        module_token="A180",
        display_name="扫描安装面",
        interface_type="temporary_planar_mount",
    )
    second = register_captured_face(
        context_path,
        context,
        _captured("A600", 102),
        instance_id="case-001",
        module_token="A600",
        display_name="箱体承载面",
        interface_type="temporary_planar_mount",
    )
    preview = preview_temporary_connection(
        context_path,
        context,
        "将扫描安装面与箱体承载面建立重合配合",
        port_ids=[first["port"]["portId"], second["port"]["portId"]],
    )
    catalog = json.loads(
        context_path.with_suffix(".temporary-face-catalog.json").read_text(encoding="utf-8")
    )
    with pytest.raises(CheckpointMateGraphAdapterError, match="目标重配模组"):
        compile_temporary_connection_for_checkpoint(
            context, binding, preview, catalog, target_module_token="A700"
        )

    assembly.write_bytes(b"assembly-was-modified")
    with pytest.raises(CheckpointMateGraphAdapterError, match="Demo检查点已变化"):
        compile_temporary_connection_for_checkpoint(
            context, binding, preview, catalog, target_module_token="A180"
        )
