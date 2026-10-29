import json
from pathlib import Path

import pytest

from demo_backend.project05_p000_physical_attachment_candidate import (
    Project05P000PhysicalAttachmentCandidateError,
    build_project05_p000_physical_attachment_candidate,
    validate_project05_p000_physical_attachment_candidate,
)

ROOT = Path(__file__).resolve().parents[3]
LOCATORS = ROOT / "demo/semantic_ports/project05_p000_locator_discovery_v1"


def _read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _inputs():
    return {
        "catalog": _read(ROOT / "demo/global_assembly_catalog/v1/global_module_catalog.json"),
        "face_catalog": _read(LOCATORS / "p000-mount-leaf-face-catalog-attempt02.json"),
        "source_graph": _read(ROOT / "demo/layout_previews/project05_module_mate_graph_v2_axes.json"),
        "base_face_catalog": _read(LOCATORS / "a000-p000-support-leaf-face-catalog.json"),
    }


def test_full_source_graph_recovers_slot_omitted_by_legacy_template():
    report = build_project05_p000_physical_attachment_candidate(**_inputs())
    source = report["originalTopLevelEvidence"]
    assert source["mateNames"] == ["重合43", "平行14", "槽口6"]
    assert source["matesMissingFromLegacyTemplate"] == ["槽口6"]
    assert source["persistentEndpointRecoveryPassed"] is True
    assert source["dofAnalysis"]["residualDof"] == 1
    assert source["sufficientForIndependentPortableInstallation"] is False


def test_four_half_cylinders_are_two_closed_slots_not_four_rejected_holes():
    report = build_project05_p000_physical_attachment_candidate(**_inputs())
    signature = report["candidateInterfaceSignature"]
    assert signature["slotCount"] == 2
    assert signature["slotWidthMeters"] == pytest.approx(0.0066)
    assert signature["slotCenterlineSpacingMeters"] == pytest.approx(0.082)
    for slot in signature["slots"]:
        assert len(slot["arcEndpointIds"]) == len(slot["wallEndpointIds"]) == 2
        assert slot["endCenterSpacingMeters"] == pytest.approx(0.05)
        assert slot["overallLengthMeters"] == pytest.approx(0.0566)
        match, = slot["nativeBaseAxisMatches"]
        assert match["crossTrackErrorMeters"] < 1e-7
        assert 0 < match["positionAlongSlotMeters"] < 0.05
    assert sum(slot["sourceMateReferenced"] for slot in signature["slots"]) == 1
    assert report["unassignedRoundHoles"]["count"] == 2
    assert report["unassignedRoundHoles"]["externalInstallationUseConfirmed"] is False


def test_source_confirmation_enables_discovery_only_not_cross_project_cad():
    report = build_project05_p000_physical_attachment_candidate(**_inputs())
    assert report["targetSlotSearchAllowed"] is True
    assert report["semanticPortPublished"] is report["cadLaunchAllowed"] is False
    assert report["candidateInterfaceSignature"]["fastenerSpecificationConfirmed"] is False
    assert validate_project05_p000_physical_attachment_candidate(report)["success"] is True


@pytest.mark.parametrize("corruption", ["missing_slot", "suppressed_slot", "changed_reference",
                                         "missing_straight_wall", "misaligned_base"])
def test_incomplete_or_conflicting_evidence_cannot_confirm_installation(corruption):
    inputs = _inputs()
    graph = inputs["source_graph"]
    slot = next(row for row in graph["Mates"] if row["MateName"] == "槽口6")
    if corruption == "missing_slot":
        graph["Mates"].remove(slot)
    elif corruption == "suppressed_slot":
        slot["IsSuppressed"] = True
    elif corruption == "changed_reference":
        next(row for row in slot["Endpoints"] if row["ModuleToken"] == "P000")[
            "SourceAssemblyPersistentReferenceBase64"
        ] = "unresolved"
    elif corruption == "missing_straight_wall":
        inputs["face_catalog"]["Endpoints"] = [
            row for row in inputs["face_catalog"]["Endpoints"]
            if row["Endpoint"]["FaceIndexInBody"] != 15
        ]
    else:
        base = next(row["Endpoint"] for row in inputs["base_face_catalog"]["Endpoints"]
                    if row["Endpoint"]["FaceIndexInBody"] == 154)
        base["CylinderOriginWorld"][2] += 0.01
    with pytest.raises(Project05P000PhysicalAttachmentCandidateError):
        build_project05_p000_physical_attachment_candidate(**inputs)


def test_modified_report_does_not_override_publication_boundary():
    report = build_project05_p000_physical_attachment_candidate(**_inputs())
    report["cadLaunchAllowed"] = True
    with pytest.raises(Project05P000PhysicalAttachmentCandidateError):
        validate_project05_p000_physical_attachment_candidate(report)
