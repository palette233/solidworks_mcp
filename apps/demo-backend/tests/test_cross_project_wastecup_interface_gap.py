import json
from pathlib import Path
import pytest

from demo_backend.cross_project_wastecup_interface_gap import (
    build_wastecup_mechanical_interface_gap_audit,
)


ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / "demo/cross_project_substitution/wastecup-project05-to-project02-v1"


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _build():
    return build_wastecup_mechanical_interface_gap_audit(
        catalog=_read(
            ROOT / "demo/global_assembly_catalog/v1/global_module_catalog.json"
        ),
        datum_closure=_read(PACKAGE / "datum-placement-demo-closure.json"),
        datum_effective_graph=_read(PACKAGE / "candidate_effective_mate_graph.json"),
        physical_attachment_candidate=_read(
            PACKAGE / "p000_physical_attachment_candidate.json"
        ),
    )


def test_datum_demo_does_not_claim_a_physical_attachment_interface():
    report = _build()

    assert report["status"] == (
        "source_slot_installation_confirmed_target_interface_pending"
    )
    assert report["sourceNativeInstallation"][
        "containsPhysicalHoleAxisOrSlotEvidence"
    ] is False
    assert report["crossProjectDatumDemo"][
        "directMechanicalInterfaceCompatible"
    ] is False
    assert len(report["missingEvidence"]) == 4
    assert report["sourceNativeInstallation"]["scope"] == (
        "legacy_template_only_not_complete_prototype_mates"
    )
    assert report["completePrototypeInstallation"]["mateStepCount"] == 3
    assert report["completePrototypeInstallation"]["containsPhysicalHoleAxisOrSlotEvidence"] is True
    candidate = report["sourcePhysicalAttachmentCandidate"]
    assert candidate["slotWidthMeters"] == pytest.approx(0.0066)
    assert candidate["slotCenterlineSpacingMeters"] == pytest.approx(0.082)
    assert candidate["mechanicalMeaningConfirmed"] is True


def test_distance_datums_remain_pose_parameters_and_fail_closed():
    report = _build()

    assert report["crossProjectDatumDemo"]["distanceParametersMeters"] == [
        0.08,
        0.39,
    ]
    assert report["semanticPortPublished"] is False
    assert report["cadLaunchAllowed"] is False
    assert report["collisionOrBrepRequiredAtThisStage"] is False
