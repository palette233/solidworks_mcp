import json
from pathlib import Path

from demo_backend.project05_g000_static_port import build_g000_static_candidate


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "demo/semantic_ports/project05_global_installation_ports_v1/G000"


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _candidate():
    return build_g000_static_candidate(
        _read(SOURCE / "semantic_port_catalog.json"),
        _read(SOURCE / "face_endpoint_catalog.json"),
        _read(SOURCE / "assembly_plan_effective.json"),
        _read(ROOT / "demo/layout_previews/project05_module_mate_graph_v2_axes.json"),
    )


def test_restores_source_slot_and_removes_all_pose_anchors():
    candidate, graph = _candidate()

    assert [row["MateType"] for row in graph["Mates"]] == [0, 3, 5, 21]
    assert graph["Mates"][3]["AdvancedOptions"]["SlotConstraint"] == 0
    assert graph["EditPolicy"]["caseAnchoredModuleTokens"] == []
    assert graph["EditPolicy"]["targetLeafPoseAnchors"] == []
    assert candidate["connectionTemplates"][0]["constraintEffect"][
        "externalPlacementWitnessRequired"
    ] is True


def test_candidate_uses_only_registered_persistent_endpoints():
    candidate, _ = _candidate()
    endpoint_catalog = _read(SOURCE / "face_endpoint_catalog.json")
    endpoint_ids = {row["EndpointId"] for row in endpoint_catalog["Endpoints"]}
    ports = {row["moduleToken"]: row for row in candidate["ports"]}

    assert len(ports["G000"]["endpointBindings"]) == 4
    assert len(ports["A000"]["endpointBindings"]) == 4
    for port in ports.values():
        assert all(
            binding["endpointId"] in endpoint_ids
            for binding in port["endpointBindings"]
        )


def test_static_distance_authority_is_explicitly_limited():
    candidate, _ = _candidate()
    upgraded = {row["mateName"]: row for row in candidate["upgradedSourceRelations"]}

    assert upgraded["距离2"]["sourceSuppressed"] is True
    assert upgraded["距离2"]["candidateMode"] == "driving_static_travel_datum"
    assert candidate["drivingScope"]["productionReady"] is False
