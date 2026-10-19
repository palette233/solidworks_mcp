from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "validate_project02_a180_semantic_insertion.py"
SPEC = importlib.util.spec_from_file_location("a180_semantic_validation", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def run_payload(token: str) -> dict:
    return {
        "success": True,
        "toolResult": {
            "Success": True,
            "IndependentComponentInserted": True,
            "RequestedMateCount": 2,
            "CreatedMateCount": 2,
            "Reopened": True,
            "ReopenedMateParametersMatch": True,
            "CaseAnchorPoseMatch": True,
            "TargetFullyConstrained": True,
            "ComponentSemanticsMatch": True,
            "TargetModuleToken": token,
        },
    }


def optical_payload(distance: float = 0.127) -> dict:
    return {
        "entries": {
            "scanner": {
                "readyForCoarseLayout": True,
                "measurementStatus": "cad-inferred-symmetric-windows",
            },
            "barcode": {
                "measurementStatus": "direct-face-measured",
                "scannerRelationship": {
                    "prototypeScannerToBarcodeDistanceMeters": distance,
                },
            },
        }
    }


def test_accepts_mechanical_closure_but_keeps_optical_provisional() -> None:
    audit = MODULE.build_audit(run_payload("A180"), run_payload("A800"), optical_payload())
    assert audit["success"] is True
    assert audit["mechanicalCadClosed"] is True
    assert audit["coarseOpticalRelationPreserved"] is True
    assert audit["productionOpticalReady"] is False
    assert audit["status"] == "MECHANICAL_CAD_CLOSED_OPTICAL_PROVISIONAL"


def test_rejects_working_distance_outside_provisional_band() -> None:
    audit = MODULE.build_audit(run_payload("A180"), run_payload("A800"), optical_payload(0.200))
    assert audit["success"] is False
    assert audit["coarseOpticalRelationPreserved"] is False
    assert audit["status"] == "REJECTED"
