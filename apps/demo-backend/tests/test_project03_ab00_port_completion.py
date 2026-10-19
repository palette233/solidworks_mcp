import json
from pathlib import Path

from demo_backend.project03_ab00_port_completion import (
    AB00,
    build_project03_ab00_complete_port_candidate,
    finalize_project03_ab00_complete_port,
)
from demo_backend.semantic_port_catalog import validate_semantic_port_catalog


WORKSPACE = Path(__file__).resolve().parents[3]
SOURCE_GRAPH = WORKSPACE / "demo/layout_previews/project03_module_mate_graph.json"
PROTOTYPE = Path(
    r"D:\zengshuang\workspace\cuhksz\cad_data\001-给港中文AI训练用资料_20260624\项目03\01-项目3D图纸\FL9A24D063A000.001-0415\FL9A24D063A000.001.SLDASM"
)


def test_ab00_complete_candidate_reuses_all_source_mate_faces_without_anchor():
    source = json.loads(SOURCE_GRAPH.read_text(encoding="utf-8-sig"))
    packet = build_project03_ab00_complete_port_candidate(source, PROTOTYPE)

    assert packet["summary"]["endpointCount"] == 8
    assert packet["summary"]["drivingMateCount"] == 3
    assert packet["summary"]["caseAnchorUsed"] is False
    assert packet["summary"]["pathRecoveryPassed"] is True
    assert validate_semantic_port_catalog(
        packet["semanticCatalog"], packet["endpointCatalog"]
    )["success"] is True

    graph = packet["effectiveGraph"]
    assert (graph["EditPolicy"] or {})["caseAnchoredModuleTokens"] == []
    assert {row["MateTypeName"] for row in graph["Mates"]} == {
        "swMateCOINCIDENT",
        "swMateWIDTH",
        "swMateDISTANCE",
    }
    width = next(row for row in graph["Mates"] if row["MateTypeName"] == "swMateWIDTH")
    assert len(width["Endpoints"]) == 4
    assert width["AdvancedOptions"]["WidthEndpointIndices"] == [0, 1]
    assert width["AdvancedOptions"]["TabEndpointIndices"] == [2, 3]
    assert width["AdvancedOptions"]["WidthConstraintType"] == 0
    distance = next(
        row for row in graph["Mates"] if row["MateTypeName"] == "swMateDISTANCE"
    )
    assert distance["Distance"] == 0.04
    assert distance["AdvancedOptions"]["DistanceFlipDimension"] is False
    assert any(row["ModuleToken"] == AB00 for row in graph["Modules"])


def test_ab00_live_result_promotes_candidate_without_collision_gate():
    root = WORKSPACE / "demo/semantic_ports/project03_AB00_complete_port_candidate_v1"
    result = json.loads(
        (root / "cad/project03_AB00_complete_nonanchor_v1.result.json").read_text(
            encoding="utf-8-sig"
        )
    )
    semantic = json.loads(
        (root / "semantic_port_catalog.json").read_text(encoding="utf-8-sig")
    )
    summary = json.loads(
        (root / "work_packet_summary.json").read_text(encoding="utf-8-sig")
    )
    finalized, finalized_summary, validation = finalize_project03_ab00_complete_port(
        semantic,
        summary,
        result,
        effective_graph_path="assembly_plan_effective.json",
        validation_evidence_path="cad/project03_AB00_complete_nonanchor_v1.result.json",
    )

    assert validation["success"] is True
    assert all(validation["checks"].values())
    assert {row["status"] for row in finalized["ports"]} == {
        "real-cad-confirmed"
    }
    assert finalized["connectionTemplates"][0]["constraintEffect"][
        "drivingAuthorization"
    ] == "real_cad_validated_nonprototype_initial_pose"
    assert finalized_summary["realCadValidated"] is True
    assert "B-rep" in finalized_summary["knownLimits"][1]

