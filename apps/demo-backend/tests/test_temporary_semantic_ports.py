import json
from pathlib import Path

import pytest

from demo_backend.temporary_semantic_ports import (
    TemporarySemanticPortError,
    load_temporary_ports,
    parse_active_assembly_path,
    parse_captured_endpoint,
    preview_temporary_connection,
    register_captured_face,
    reset_temporary_ports,
)


def _context() -> dict:
    return {
        "contextId": "temporary-port-unit",
        "revision": 2,
        "contextDigest": "context-digest",
        "instances": [
            {
                "instanceId": "a600-001",
                "moduleDefinitionId": "cad/a600",
            },
            {
                "instanceId": "a180-001",
                "moduleDefinitionId": "cad/a180",
            },
        ],
    }


def _entry(token: str, suffix: str) -> dict:
    return {
        "EndpointId": f"face:{token.casefold()}:{suffix}",
        "ModulePath": f"D:/{token}.SLDASM",
        "GeometryClass": "Plane",
        "RecoveryConfidence": "USER_SELECTED_PERSISTENT_REFERENCE_PLUS_FINGERPRINT",
        "Endpoint": {
            "ModuleToken": token,
            "ModuleHierarchyPath": f"{token}-1",
            "RelativeLeafHierarchyPath": f"{token}-leaf-1",
            "BodyIndex": 0,
            "FaceIndexInBody": 3,
            "FaceArea": 0.01,
            "FaceCenterLocal": [0.0, 0.0, 0.0],
            "FaceNormalLocal": [0.0, 0.0, 1.0],
            "SourceAssemblyPersistentReferenceBase64": f"ref-{suffix}",
        },
    }


def test_selected_faces_become_context_local_ports_and_natural_language_draft(
    tmp_path: Path,
):
    context_file = tmp_path / "context.json"
    context = _context()
    reset_temporary_ports(context_file, context)

    frame = register_captured_face(
        context_file,
        context,
        _entry("A600", "frame"),
        instance_id="a600-001",
        module_token="A600",
        display_name="箱体承载面",
        interface_type="temporary_planar_mount",
        aliases=["箱体安装面"],
    )
    scanner = register_captured_face(
        context_file,
        context,
        _entry("A180", "scanner"),
        instance_id="a180-001",
        module_token="A180",
        display_name="扫描安装面",
        interface_type="temporary_planar_mount",
        aliases=["扫描模组安装面"],
    )
    repeated = register_captured_face(
        context_file,
        context,
        _entry("A180", "scanner"),
        instance_id="a180-001",
        module_token="A180",
        display_name="扫描安装面",
        interface_type="temporary_planar_mount",
        aliases=["扫描模组安装面"],
    )

    assert repeated["port"]["portId"] == scanner["port"]["portId"]
    assert len(load_temporary_ports(context_file, context)["ports"]) == 2

    preview = preview_temporary_connection(
        context_file,
        context,
        "将扫描安装面与箱体承载面建立重合配合",
    )
    assert preview["status"] == "ready"
    assert preview["mateDraft"]["mateType"] == 0
    assert preview["endpointIds"] == [
        scanner["port"]["endpointBindings"][0]["endpointId"],
        frame["port"]["endpointBindings"][0]["endpointId"],
    ]
    assert preview["executionBoundary"]["solidWorksModified"] is False


def test_distance_requires_value_and_modules_must_differ(tmp_path: Path):
    context_file = tmp_path / "context.json"
    context = _context()
    reset_temporary_ports(context_file, context)
    first = register_captured_face(
        context_file,
        context,
        _entry("A600", "one"),
        instance_id="a600-001",
        module_token="A600",
        display_name="箱体面一",
        interface_type="temporary_planar_mount",
    )
    second = register_captured_face(
        context_file,
        context,
        _entry("A600", "two"),
        instance_id="a600-001",
        module_token="A600",
        display_name="箱体面二",
        interface_type="temporary_planar_mount",
    )
    preview = preview_temporary_connection(
        context_file,
        context,
        "设置两个面的距离",
        port_ids=[first["port"]["portId"], second["port"]["portId"]],
    )
    assert preview["status"] == "blocked"
    assert {row["code"] for row in preview["blockers"]} == {
        "DISTINCT_MODULE_INSTANCES_REQUIRED",
        "DISTANCE_VALUE_REQUIRED",
    }


def test_capture_result_parser_is_fail_closed():
    entry = _entry("A180", "parser")
    parsed = parse_captured_endpoint(
        {
            "status": "ok",
            "toolResults": [{"text": [json.dumps(entry)]}],
        }
    )
    assert parsed["EndpointId"] == entry["EndpointId"]

    with pytest.raises(TemporarySemanticPortError):
        parse_captured_endpoint({"status": "dry-run", "message": "not connected"})


def test_capture_result_binds_selected_face_to_active_assembly():
    entry = _entry("A180", "bound")
    result = {
        "status": "ok",
        "toolResults": [
            {"text": [json.dumps({"Path": "D:/checkpoint.SLDASM", "Title": "checkpoint", "Type": 2})]},
            {"text": [json.dumps(entry)]},
        ],
    }

    assert parse_active_assembly_path(result) == "D:/checkpoint.SLDASM"
    assert parse_captured_endpoint(result)["EndpointId"] == entry["EndpointId"]
