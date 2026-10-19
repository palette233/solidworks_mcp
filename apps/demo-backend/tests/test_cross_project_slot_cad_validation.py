import json
from pathlib import Path

from demo_backend.cross_project_slot_cad_validation import (
    build_a600_ah00_candidate_validation_plan,
)


ROOT = Path(__file__).resolve().parents[3]
DIRECTORY = (
    ROOT
    / "demo/cross_project_substitution/alternate-slot-discovery-v1/"
    "project02_A600_calibration_slot_acquisition"
)
WRAPPER = (
    ROOT
    / "demo/global_assembly_contexts/manifest_jobs/"
    "project02-job-6e3c1b72de5d/packet-runs/packet-001-attempt-01/"
    "base-context-wrapper.SLDASM"
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _plan() -> dict:
    return build_a600_ah00_candidate_validation_plan(
        acquisition_request=_read(DIRECTORY / "slot_acquisition_request.json"),
        candidate_port=_read(DIRECTORY / "candidate_semantic_port.json"),
        a600_face_catalog=_read(
            DIRECTORY / "a600-native-service-leaf-face-catalog-v1.json"
        ),
        ah00_semantic_catalog=_read(
            ROOT
            / "demo/semantic_ports/project03_AH00_fifth_increment_v1/"
            "semantic_port_catalog.json"
        ),
        ah00_face_catalog=_read(
            ROOT
            / "demo/semantic_ports/project03_AH00_fifth_increment_v1/"
            "face_endpoint_catalog.json"
        ),
        base_wrapper_path=WRAPPER,
    )


def test_candidate_validation_graph_is_three_mates_without_case_anchor():
    plan = _plan()
    graph = plan["effectiveMateGraph"]

    assert plan["status"] == "ready_for_candidate_cad_validation"
    assert plan["prototypeTopLevelTargetPoseUsed"] is False
    assert plan["caseAnchorUsed"] is False
    assert graph["ModuleCount"] == 2
    assert graph["InterModuleMateCount"] == 3
    assert [row["MateType"] for row in graph["Mates"]] == [0, 1, 1]
    assert graph["EditPolicy"]["caseAnchoredModuleTokens"] == []
    assert graph["EditPolicy"]["targetLeafPoseAnchors"] == []
    assert graph["EditPolicy"]["sourceMateNamesToSuppress"] == []
    assert graph["SemanticAssemblyPlanAudit"]["constraintAssessment"][
        "expectedResidualDof"
    ] == 0


def test_candidate_validation_graph_uses_explicit_role_mapping_not_hash_order():
    plan = _plan()
    graph = plan["effectiveMateGraph"]
    by_name = {row["MateName"]: row for row in graph["Mates"]}

    first_target = by_name["A600_AH00_同心1"]["Endpoints"][1]
    second_target = by_name["A600_AH00_同心2"]["Endpoints"][1]
    assert first_target["FaceIndexInBody"] == 13
    assert second_target["FaceIndexInBody"] == 11
    assert first_target["ModuleToken"] == "A600"
    assert second_target["ModuleToken"] == "A600"
    assert first_target["RelativeLeafHierarchyPath"] == (
        second_target["RelativeLeafHierarchyPath"]
    )
    assert all(
        row["Endpoints"][0]["ModuleToken"] == "FL9A24D063AH00"
        for row in graph["Mates"]
    )


def test_candidate_validation_plan_preserves_fail_closed_release_boundary():
    plan = _plan()

    assert plan["acceptance"] == {
        "semanticPortPublishedBeforeRun": False,
        "collisionOrBrepInScope": False,
        "publishPortOnlyAfterCadPass": True,
    }
    policy = plan["effectiveMateGraph"]["CandidateValidationPolicy"]
    assert policy["semanticPortPublished"] is False
    assert policy["collisionOrBrepRequired"] is False
    assert "target fully constrained" in policy["requiredCadChecks"]
