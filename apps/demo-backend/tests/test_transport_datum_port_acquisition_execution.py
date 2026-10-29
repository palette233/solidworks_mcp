import copy
import json
from pathlib import Path

from demo_backend.transport_datum_port_acquisition import (
    ACQUISITION_ROOT,
    _digest,
    confirm_transport_datum_port_candidate,
)
from demo_backend.transport_datum_port_acquisition_execution import (
    STATUS_SCHEMA,
    inspect_transport_datum_port_acquisition,
    materialize_next_transport_datum_review,
)


ROOT = Path(__file__).resolve().parents[3]


def _row(endpoint_id, normal, face_index):
    return {
        "EndpointId": endpoint_id,
        "GeometryClass": "Plane",
        "RecoveryConfidence": "LEAF_SCOPED_PERSISTENT_REFERENCE_PLUS_FINGERPRINT",
        "Endpoint": {
            "ModuleToken": "SS00",
            "LeafHierarchyPath": "SS00-1/static-leaf-1",
            "RelativeLeafHierarchyPath": "static-leaf-1",
            "BodyIndex": 0,
            "FaceIndexInBody": face_index,
            "FaceArea": 0.01 - face_index * 0.001,
            "FaceCenterLocal": [float(face_index), 0.0, 0.0],
            "FaceNormalLocal": normal,
            "SourceAssemblyPersistentReferenceBase64": f"persistent-{face_index}",
            "SurfaceType": "Plane",
        },
    }


def _catalog(rows, *, leaf_scoped=False):
    result = {
        "SchemaVersion": "solidworks-face-endpoint-catalog/v1",
        "SourceAssemblyPath": "C:/cad/source.SLDASM",
        "EndpointCount": len(rows),
        "Endpoints": rows,
    }
    if leaf_scoped:
        result.update(
            {
                "CatalogMode": "leaf_scoped",
                "PlanarOnly": True,
                "RequestedModuleTokens": ["SS00"],
                "RequestedLeafSelectors": ["SS00-1/static-leaf-1"],
            }
        )
    return result


def _workspace(tmp_path):
    support = _row("face:ss00:support", [0.0, 0.0, 1.0], 0)
    seed = _catalog([support])
    seed_path = tmp_path / "seed.json"
    seed_path.write_text(json.dumps(seed), encoding="utf-8")
    item_core = {
        "moduleDefinitionId": "project01::SS00",
        "moduleToken": "SS00",
        "sourceReleaseId": "relation-source",
        "sourceAssemblyPath": "C:/cad/source.SLDASM",
        "seedCatalogPath": "seed.json",
        "seedCatalogDigest": _digest(seed),
        "existingSupportEndpointId": "face:ss00:support",
        "staticMountLeafSelector": "SS00-1/static-leaf-1",
        "scanOutputPath": f"{ACQUISITION_ROOT}/scan.json",
        "scanPolicy": {
            "planarOnly": True,
            "minimumFaceArea": 1e-8,
            "maximumFaceCount": 500,
            "siblingLeafTraversalAllowed": False,
        },
    }
    item = {
        **item_core,
        "itemId": "transport-datum-scan/" + _digest(item_core)[:16],
        "status": "bounded_leaf_scan_required",
        "cadExecutionAuthorized": False,
        "command": ["scan"],
    }
    core = {
        "schemaVersion": "transport-datum-port-acquisition-plan/v1",
        "purpose": "test",
        "items": [item],
        "safetyBoundary": {},
        "summary": {"itemCount": 1, "scanRequiredCount": 1, "confirmedPortCount": 0},
    }
    plan = {**core, "planDigest": _digest(core)}
    plan_path = tmp_path / ACQUISITION_ROOT / "scan-plan.json"
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    scan = _catalog(
        [
            support,
            _row("face:ss00:x", [1.0, 0.0, 0.0], 1),
            _row("face:ss00:y", [0.0, 1.0, 0.0], 2),
        ],
        leaf_scoped=True,
    )
    return plan_path, scan


def test_committed_workflow_reports_first_bounded_scan_without_cad_authority():
    status = inspect_transport_datum_port_acquisition(ROOT)
    assert status["schemaVersion"] == STATUS_SCHEMA
    assert status["summary"]["itemCount"] == 2
    assert sum(status["summary"]["stateCounts"].values()) == 2
    if status["summary"]["stateCounts"].get("bounded_leaf_scan_required"):
        assert status["nextAction"]["action"] == "run_bounded_leaf_scan"
        assert status["nextAction"]["requiresZeroDocumentSolidWorksSession"] is True
    assert status["summary"]["normalAssemblyExecutionAuthorizedCount"] == 0


def test_scan_review_confirmation_state_machine(tmp_path):
    plan_path, scan = _workspace(tmp_path)
    initial = inspect_transport_datum_port_acquisition(
        tmp_path, plan_path=plan_path
    )
    assert initial["nextAction"]["action"] == "run_bounded_leaf_scan"

    scan_path = tmp_path / ACQUISITION_ROOT / "scan.json"
    scan_path.write_text(json.dumps(scan), encoding="utf-8")
    scanned = inspect_transport_datum_port_acquisition(
        tmp_path, plan_path=plan_path
    )
    assert scanned["nextAction"]["action"] == "materialize_candidate_review"
    assert scanned["items"][0]["candidateCount"] == 1

    materialized = materialize_next_transport_datum_review(
        tmp_path, plan_path=plan_path
    )
    assert materialized["candidateCount"] == 1
    awaiting = inspect_transport_datum_port_acquisition(
        tmp_path, plan_path=plan_path
    )
    assert awaiting["nextAction"]["action"] == "confirm_candidate_and_direction_roles"
    assert awaiting["items"][0]["roleAssignmentRequired"] is True

    review = json.loads(
        Path(materialized["reviewPath"]).read_text(encoding="utf-8")
    )
    confirmed = confirm_transport_datum_port_candidate(
        review,
        selected_candidate_id=review["candidates"][0]["candidateId"],
        longitudinal_endpoint_id="face:ss00:x",
        lateral_endpoint_id="face:ss00:y",
        confirmation_source="test-review",
    )
    confirmed_path = (
        tmp_path / ACQUISITION_ROOT / "confirmed-ports/project01-ss00.json"
    )
    confirmed_path.parent.mkdir(parents=True)
    confirmed_path.write_text(json.dumps(confirmed), encoding="utf-8")

    ready = inspect_transport_datum_port_acquisition(
        tmp_path, plan_path=plan_path
    )
    assert ready["items"][0]["state"] == "confirmed_port_ready_for_catalog_registration"
    assert ready["nextAction"]["action"] == "refresh_parameterized_catalog_and_validation_queue"
    assert ready["summary"]["normalAssemblyExecutionAuthorizedCount"] == 0


def test_machine_actions_are_not_blocked_by_an_earlier_confirmation(tmp_path):
    plan_path, scan = _workspace(tmp_path)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    second = copy.deepcopy(plan["items"][0])
    second["moduleDefinitionId"] = "project99::SS00"
    second["scanOutputPath"] = f"{ACQUISITION_ROOT}/second-scan.json"
    second_core = {
        key: value for key, value in second.items() if key != "itemId"
    }
    second["itemId"] = "transport-datum-scan/" + _digest(second_core)[:16]
    core = {key: value for key, value in plan.items() if key != "planDigest"}
    core["items"].append(second)
    core["summary"]["itemCount"] = 2
    core["summary"]["scanRequiredCount"] = 2
    plan = {**core, "planDigest": _digest(core)}
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    first_scan = tmp_path / ACQUISITION_ROOT / "scan.json"
    first_scan.write_text(json.dumps(scan), encoding="utf-8")
    materialize_next_transport_datum_review(tmp_path, plan_path=plan_path)
    status = inspect_transport_datum_port_acquisition(tmp_path, plan_path=plan_path)

    assert status["summary"]["stateCounts"] == {
        "engineering_confirmation_required": 1,
        "bounded_leaf_scan_required": 1,
    }
    assert status["nextAction"]["action"] == "run_bounded_leaf_scan"
    assert status["nextAction"]["moduleDefinitionId"] == "project99::SS00"
