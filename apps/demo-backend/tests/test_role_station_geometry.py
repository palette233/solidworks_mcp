import copy
import hashlib
from pathlib import Path

import pytest

from demo_backend import role_station_geometry as station


ROOT = Path(__file__).resolve().parents[3]


def _box(min_u=0.0, max_u=1.0, min_v=0.0, max_v=1.0):
    return {"minU": min_u, "maxU": max_u, "minV": min_v, "maxV": max_v, "minN": 0.0, "maxN": 1.0}


@pytest.mark.parametrize(
    "footprint,contained,overlap",
    [(_box(0.2, 0.8, 0.3, 0.9), True, 0.36),
     (_box(-0.2, 0.8, 0.3, 0.9), False, 0.48),
     (_box(1.1, 2.1, 0.0, 1.0), False, 0.0)],
)
def test_planar_relation_is_measurement_not_semantic_authority(footprint, contained, overlap):
    measured = station.planar_relation(footprint, _box())
    assert measured["envelopeContained"] is contained
    assert measured["overlapAreaSquareMeters"] == pytest.approx(overlap)
    assert "passed" not in measured


@pytest.mark.parametrize("bounds", [_box(1, 0), _box(float("nan"), 1)])
def test_planar_relation_rejects_invalid_geometry(bounds):
    with pytest.raises(ValueError):
        station.planar_relation(bounds, _box())


def test_rigid_coordinate_bridge_preserves_rotation_and_inverse():
    transform = station._transform([0, 1, 0, -1, 0, 0, 0, 0, 1, 2, 3, 4, 1, 0, 0, 0])
    assert station._point([1, 2, 3], transform) == pytest.approx([0, 4, 7])
    assert station._point([0, 4, 7], transform, inverse=True) == pytest.approx([1, 2, 3])
    with pytest.raises(ValueError, match="reflected"):
        station._transform([-1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0])


def test_gn00_reopened_geometry_is_measured_without_inventing_station_policy():
    report = station.build_gn00_aa00_station_witness(ROOT)
    assert report["schemaVersion"] == "role-station-witness/v1"
    assert report["caseId"] == "B8-GN00-AA00"
    assert report["stationValidationPassed"] is False
    assert report["cadLaunchAllowed"] is False
    assert {name: row["passed"] for name, row in report["checks"].items()} == {
        "slotMembership": None, "supportAndDirectionBound": None,
        "installationSideBound": True, "transportContext": None,
    }
    membership = report["checks"]["slotMembership"]["observations"]
    assert membership["nativeEnvelopeRelation"]["overlapAreaSquareMeters"] == 0
    assert membership["registeredAllowedRoleRegionAvailable"] is False
    assert membership["candidateFootprintInstallationMeters"]["minV"] == pytest.approx(-0.7538234706426438)
    support = report["checks"]["supportAndDirectionBound"]["observations"]
    assert support["planeAndDirectionPassed"] is True
    assert support["fullEnvelopeVsSupportFaceOuterBound"]["envelopeContained"] is False
    assert support["fullEnvelopeVsSupportFaceOuterBound"]["clearancesMeters"]["minV"] == pytest.approx(-0.6578234706426698)
    assert support["contactFaceVsSupportFaceOuterBound"]["envelopeContained"] is True
    assert support["fullEnvelopeContainmentPolicyRegistered"] is False
    transport = report["checks"]["transportContext"]["observations"]
    assert transport["currentCadModuleTokens"] == ["AA00", "GN00"]
    assert transport["nativeTransportEnvelopeRelation"]["overlapAreaSquareMeters"] > 0
    for row in report["checks"].values():
        for source in row["evidence"]:
            assert hashlib.sha256(Path(source["path"]).read_bytes()).hexdigest() == source["sha256"]


def test_missing_optional_geometry_stays_unknown(monkeypatch):
    original = Path.is_file
    monkeypatch.setattr(Path, "is_file", lambda path: False if path.name == "project03_module_occupancy.json" else original(path))
    report = station.build_gn00_aa00_station_witness(ROOT)
    assert all(row["passed"] is None for row in report["checks"].values())
    assert report["stationValidationPassed"] is False
    assert report["checks"]["slotMembership"]["observations"]["missingEvidencePaths"]


@pytest.mark.parametrize("change,error", [
    ("stale_graph", "graph digest changed"),
    ("stale_output", "output assembly digest changed"),
    ("failed_cad", "successful reopened CAD result"),
    ("wrong_module", "module identities differ"),
    ("wrong_frame", "different frames"),
])
def test_stale_or_inconsistent_inputs_fail_closed(monkeypatch, change, error):
    original = station._read

    def changed(path):
        payload = copy.deepcopy(original(path))
        if path.name == "cad-result.json":
            if change == "stale_graph":
                payload["executionEffectiveGraphSha256"] = "0" * 64
            elif change == "stale_output":
                payload["outputAssemblySha256"] = "0" * 64
            elif change == "failed_cad":
                payload["toolResult"]["Reopened"] = False
        if path.name == "project01_module_occupancy.json":
            if change == "wrong_module":
                payload["modules"]["GN00"]["filePath"] = "other.SLDASM"
            elif change == "wrong_frame":
                payload["modules"]["GN00"]["prototypeAnchorInstallationMeters"]["u"] += 0.1
        return payload

    monkeypatch.setattr(station, "_read", changed)
    with pytest.raises(ValueError, match=error):
        station.build_gn00_aa00_station_witness(ROOT)


def test_n000_envelope_fit_does_not_fill_missing_endpoint_or_pose_evidence():
    report = station.build_n000_a600_station_witness(ROOT)
    assert report["cadLaunchAllowed"] is False
    assert report["stationValidationPassed"] is False
    assert report["cadResultSha256"] is None
    assert report["effectiveGraphSha256"] is None
    assert all(row["passed"] is None for row in report["checks"].values())
    observations = report["checks"]["slotMembership"]["observations"]
    assert observations["replacementEnvelopeFitsRoleStation"] is True
    assert observations["actualReplacementPoseAvailable"] is False
    assert observations["nativeEndpointBundleAvailable"] is False
    assert report["forbiddenFallback"]["longitudinalMeters"] == 0.465
    assert {row["code"] for row in report["blockers"]} >= {"A700_A600_NATIVE_ENDPOINT_BUNDLE_NOT_CAPTURED"}


def test_n000_missing_geometry_remains_unknown_and_nonexecuting(monkeypatch):
    def missing(_):
        raise FileNotFoundError("native geometry missing")

    monkeypatch.setattr(station, "build_project02_a700_role_station_audit", missing)
    report = station.build_n000_a600_station_witness(ROOT)
    assert report["stationValidationPassed"] is False
    assert report["cadLaunchAllowed"] is False
    assert all(row["passed"] is None for row in report["checks"].values())


def test_wrong_reopened_installation_side_is_a_measured_failure(monkeypatch):
    original = station._read

    def changed(path):
        payload = copy.deepcopy(original(path))
        if path.name == "cad-result.json":
            payload["toolResult"]["ReopenedTargetRootTransform"][10] -= 1
        return payload

    monkeypatch.setattr(station, "_read", changed)
    report = station.build_gn00_aa00_station_witness(ROOT)
    assert report["checks"]["installationSideBound"]["passed"] is False
    assert report["checks"]["supportAndDirectionBound"]["passed"] is False
    assert report["stationValidationPassed"] is False


LIVE_SUPPORT = ROOT / "demo/role_station_strengthening_20261028"
LIVE_STATE = LIVE_SUPPORT / "gn00-live-reopen-0413.json"
LIVE_MOVING = LIVE_SUPPORT / "gn00-support-leaf-live-0418.json"
LIVE_BASE = LIVE_SUPPORT / "aa00-support-leaf-live-0418.json"


def _live_support():
    return station.build_gn00_live_support_audit(ROOT, LIVE_STATE, LIVE_MOVING, LIVE_BASE)


def test_live_support_real_saved_reopen_agrees_with_bridge_despite_face_index_drift():
    """Real readonly captures, not a synthetic new CAD insertion success."""
    report = _live_support()
    assert report["bindingVerified"] is True
    assert report["readOnly"] is True
    assert report["newCadInsertionPerformed"] is False
    assert report["supportGeometryMeasurementPassed"] is True
    assert report["historicalBridgeConsistencyPassed"] is True
    assert report["planeResidualMeters"] < 1e-12
    assert report["normalDot"] == pytest.approx(-1)
    assert report["slotMembership"] is None and report["transportContext"] is None
    assert report["stationReady"] is False and report["stationValidationPassed"] is False
    assert report["cadLaunchAllowed"] is False
    base = report["endpoints"]["AA00"]
    assert (base["graphFaceIndexInBody"], base["freshFaceIndexInBody"]) == (11, 7)
    assert base["faceIndexChanged"] is True
    assert base["graphPersistentReferenceBase64"] != base["freshPersistentReferenceBase64"]
    assert max(row["bridgeCenterErrorMeters"] for row in report["endpoints"].values()) < 1e-12
    for item in report["evidence"]:
        assert station._sha256(Path(item["path"])) == item["sha256"]


@pytest.mark.parametrize("change,error", [
    ("output_digest", "output assembly digest changed"),
    ("snapshot_digest", "snapshot does not bind"),
    ("readonly", "snapshot does not bind"),
    ("checks", "snapshot does not bind"),
    ("component", "component identity mismatch"),
    ("root_pose", "root pose/configuration mismatch"),
    ("catalog_context", "catalog does not bind"),
    ("catalog_pose", "module identity/root pose mismatch"),
    ("leaf_configuration", "fingerprint/configuration does not resolve uniquely"),
    ("body", "fingerprint/configuration does not resolve uniquely"),
    ("local_fingerprint", "fingerprint/configuration does not resolve uniquely"),
    ("ambiguous_fingerprint", "fingerprint/configuration does not resolve uniquely"),
])
def test_live_support_identity_or_ambiguous_geometry_fails_closed(monkeypatch, change, error):
    original = station._read

    def changed(path):
        payload = copy.deepcopy(original(path))
        if path.name == "cad-result.json" and change == "output_digest":
            payload["outputAssemblySha256"] = "0" * 64
        if path == LIVE_STATE:
            if change == "snapshot_digest":
                payload["assemblySha256"] = "0" * 64
            elif change == "readonly":
                payload["observed"]["readOnly"] = False
            elif change == "checks":
                payload["checks"] = {}
            elif change == "component":
                payload["observed"]["components"][0]["sourcePath"] = "other.SLDASM"
            elif change == "root_pose":
                payload["observed"]["components"][0]["transform"][9] += 0.001
        if path == LIVE_BASE:
            row = next(row for row in payload["Endpoints"] if row["Endpoint"]["FaceIndexInBody"] == 7)
            if change == "catalog_context":
                payload["SourceAssemblyPath"] = "other.SLDASM"
            elif change == "catalog_pose":
                payload["Modules"][0]["SourceTransform"][9] += 0.001
            elif change == "leaf_configuration":
                row["LeafReferencedConfiguration"] = "Other"
            elif change == "body":
                row["Endpoint"]["BodyIndex"] = 1
            elif change == "local_fingerprint":
                row["Endpoint"]["FaceBoxLocal"][0] += 0.001
            elif change == "ambiguous_fingerprint":
                duplicate = copy.deepcopy(row)
                duplicate["Endpoint"]["FaceIndexInBody"] = 999
                payload["Endpoints"].append(duplicate)
        return payload

    monkeypatch.setattr(station, "_read", changed)
    with pytest.raises(ValueError, match=error):
        _live_support()


def test_live_support_actual_geometry_disagreement_is_not_hidden_by_old_bridge(monkeypatch):
    original = station._read

    def changed(path):
        payload = copy.deepcopy(original(path))
        if path == LIVE_MOVING:
            endpoint = next(row["Endpoint"] for row in payload["Endpoints"] if row["Endpoint"]["FaceIndexInBody"] == 2)
            endpoint["FaceCenterWorld"][1] += 0.001
        return payload

    monkeypatch.setattr(station, "_read", changed)
    report = _live_support()
    assert report["bindingVerified"] is True
    assert report["planeResidualMeters"] == pytest.approx(0.001)
    assert report["historicalBridgePlaneResidualMeters"] < 1e-12
    assert report["planeAndDirectionPassed"] is False
    assert report["historicalBridgeConsistencyPassed"] is False
    assert report["supportGeometryMeasurementPassed"] is False
    assert report["stationReady"] is False
