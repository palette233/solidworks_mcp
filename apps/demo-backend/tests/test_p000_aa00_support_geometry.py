from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("p000_aa00_support_geometry_test_target", ROOT / "scripts/verify_p000_aa00_support_geometry.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
IDENTITY = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]
RELATIVE = [0, 0, -1, -1, 0, 0, 0, 1, 0, .72, .655, .4235, 1, 0, 0, 0]


@pytest.fixture
def data():
    audit = {
        "mode": "support_position_demo", "actualFixationMethod": "not_verified", "holePatternMatchRequired": False,
        "geometricWitness": {
            "baseModuleToken": "AA00", "coordinateFrame": "AA00_module_local", "notAnExecutablePoseAnchor": True,
            "targetModuleTopLevelTransformUsed": False, "targetLeafRelativePath": "FL5C254098P000002.01-1",
            "positionToleranceMeters": 1e-6,
            "referencePoints": [
                {"name": "origin", "targetLeafPointMeters": [0, 0, 0], "expectedBaseModulePointMeters": [.72, .655, .4235]},
                {"name": "side1", "targetLeafPointMeters": [0, .1, .004], "expectedBaseModulePointMeters": [.62, .659, .4235]},
                {"name": "side2", "targetLeafPointMeters": [-.05, .05, .004], "expectedBaseModulePointMeters": [.67, .659, .4735]},
                {"name": "support", "targetLeafPointMeters": [0, .05, 0], "expectedBaseModulePointMeters": [.67, .655, .4235]},
            ],
        },
    }
    state = {
        "assemblyPath": "fixture.SLDASM", "assemblySha256": "a"*64, "success": True, "checks": {"outputFileUnchanged": True},
        "observed": {"readOnly": True, "components": [{"name": "FL9A24D063AA00.001-1", "transform": list(IDENTITY)}],
                     "targetLeafWitness": {"name": "FL9C254098P000.001-1/FL5C254098P000002.01-1", "transform": list(RELATIVE)}},
    }
    return state, audit


def test_correct_signed_geometry_passes_without_mutation(data):
    before = copy.deepcopy(data)
    report = MODULE.verify_geometry(*data, current_assembly_sha256="a"*64)
    assert report["success"] is True
    assert all(report["checks"].values())
    assert report["maximumResidualMeters"] < 1e-12
    assert report["assemblySha256"] == "a"*64
    assert data == before


def test_rotated_translated_base_uses_total_leaf_transform(data):
    state, audit = data
    base = [0, 1, 0, -1, 0, 0, 0, 0, 1, .12, -.34, .56, 1, 0, 0, 0]
    origin = MODULE.apply_transform(RELATIVE[9:12], base)
    rotation = []
    for row in (RELATIVE[0:3], RELATIVE[3:6], RELATIVE[6:9]):
        point = MODULE.apply_transform(row, base)
        rotation.extend(point[j]-base[9+j] for j in range(3))
    state["observed"]["components"][0]["transform"] = base
    state["observed"]["targetLeafWitness"]["transform"] = rotation+origin+[1, 0, 0, 0]
    assert MODULE.verify_geometry(state, audit)["success"] is True


@pytest.mark.parametrize(("index", "offset"), [(9, -.8), (11, .4), (10, .01)])
def test_wrong_distance_side_or_support_height_rejected(data, index, offset):
    state, audit = data
    state["observed"]["targetLeafWitness"]["transform"][index] += offset
    report = MODULE.verify_geometry(state, audit)
    assert report["success"] is False
    assert report["checks"]["inputsValid"] is True
    assert report["checks"]["signedPositionsMatchDesignSide"] is False


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), True])
def test_nonfinite_and_boolean_transform_rejected(data, value):
    state, audit = data
    state["observed"]["targetLeafWitness"]["transform"][9] = value
    report = MODULE.verify_geometry(state, audit)
    assert not report["success"] and not report["checks"]["inputsValid"]


def test_reflected_rotation_rejected(data):
    state, audit = data
    state["observed"]["targetLeafWitness"]["transform"][2] = 1
    assert not MODULE.verify_geometry(state, audit)["checks"]["inputsValid"]


def test_missing_leaf_evidence_rejected(data):
    state, audit = data
    state["observed"].pop("targetLeafWitness")
    assert not MODULE.verify_geometry(state, audit)["success"]


def test_wrong_leaf_identity_rejected(data):
    state, audit = data
    state["observed"]["targetLeafWitness"]["name"] = "P000/another-part-1"
    assert not MODULE.verify_geometry(state, audit)["checks"]["targetLeafIdentityMatches"]


def test_changed_assembly_hash_rejected(data):
    report = MODULE.verify_geometry(*data, current_assembly_sha256="b"*64)
    assert not report["success"] and not report["checks"]["sourceAssemblyHashMatchesCurrentFile"]


def test_failed_readonly_state_cannot_promote(data):
    state, audit = data
    state["success"] = False
    assert not MODULE.verify_geometry(state, audit)["success"]


@pytest.mark.parametrize("field", ["baseModuleToken", "coordinateFrame"])
def test_wrong_reference_frame_rejected(data, field):
    state, audit = data
    audit["geometricWitness"][field] = "A600"
    assert not MODULE.verify_geometry(state, audit)["success"]


@pytest.mark.parametrize("tolerance", [0, 1e-3, float("nan"), True])
def test_weak_or_invalid_tolerance_rejected(data, tolerance):
    state, audit = data
    audit["geometricWitness"]["positionToleranceMeters"] = tolerance
    assert not MODULE.verify_geometry(state, audit)["success"]


def test_collinear_points_rejected(data):
    state, audit = data
    references = audit["geometricWitness"]["referencePoints"]
    for i, row in enumerate(references):
        row["targetLeafPointMeters"] = [0, i*.01, 0]
    report = MODULE.verify_geometry(state, audit)
    assert not report["success"] and "collinear" in report["errors"][0]


def test_cli_binds_inputs_and_refuses_overwrite(data, tmp_path, monkeypatch, capsys):
    state, audit = data
    assembly = tmp_path / "test.SLDASM"
    assembly.write_bytes(b"test artifact bytes")
    state["assemblyPath"] = str(assembly)
    state["assemblySha256"] = hashlib.sha256(assembly.read_bytes()).hexdigest()
    state_path, audit_path, output = tmp_path/"state.json", tmp_path/"audit.json", tmp_path/"result.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    audit_path.write_text(json.dumps(audit), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["verify", "--state", str(state_path), "--audit", str(audit_path), "--output", str(output)])
    assert MODULE.main() == 0
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["stateSha256"] == hashlib.sha256(state_path.read_bytes()).hexdigest()
    assert result["auditSha256"] == hashlib.sha256(audit_path.read_bytes()).hexdigest()
    assert result["success"]
    with pytest.raises(FileExistsError):
        MODULE.main()


def test_cli_missing_input_preserves_failure_report(tmp_path, monkeypatch, capsys):
    output = tmp_path/"failure.json"
    monkeypatch.setattr(sys, "argv", ["verify", "--state", str(tmp_path/"missing.json"), "--output", str(output)])
    assert MODULE.main() == 2
    result = json.loads(output.read_text(encoding="utf-8"))
    assert not result["success"] and result["errors"]
