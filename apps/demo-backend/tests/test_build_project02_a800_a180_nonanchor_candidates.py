from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/build_project02_a800_a180_nonanchor_candidates.py"
SPEC = importlib.util.spec_from_file_location("build_project02_a800_a180_nonanchor_candidates", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_project02_a800_a180_candidates_close_without_pose_anchors() -> None:
    root = ROOT / "demo/semantic_ports/project02_a800_a180_dof_audit_v1"
    report, a800, a180 = MODULE.build_candidates(
        MODULE._read(MODULE.SOURCE_GRAPH),
        MODULE._read(MODULE.A800_EFFECTIVE),
        MODULE._read(MODULE.A180_EFFECTIVE),
        MODULE._read(root / "a600-a180-support-leaf-face-catalog.json"),
        MODULE._read(root / "a800-mount-leaf-face-catalog.json"),
        MODULE._read(root / "a180-mount-leaf-face-catalog.json"),
    )
    assert report["status"] == "ready_for_authoritative_cad_checkpoint"
    assert report["modules"]["A800"]["dofAnalysis"]["residualDof"] == 0
    assert report["modules"]["A180"]["dofAnalysis"]["residualDof"] == 1
    assert report["modules"]["A800"]["derivedDistanceMeters"] == pytest.approx(0.0495)
    assert a800["EditPolicy"]["initialPlacementMode"] == "deterministic"
    assert a180["EditPolicy"]["initialPlacementMode"] == "deterministic"
    assert a800["EditPolicy"]["caseAnchoredModuleTokens"] == []
    assert a180["EditPolicy"]["caseAnchoredModuleTokens"] == []
    assert any(row["MateName"] == "槽口3" for row in a180["Mates"])
    assert all(row["MateName"] != "A180_LOCATING_DISTANCE_X" for row in a180["Mates"])
