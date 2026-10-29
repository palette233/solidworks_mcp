import copy
from pathlib import Path

import pytest

from demo_backend.transport_datum_port_acquisition import (
    CONFIRMED_PORT_SCHEMA,
    PLAN_SCHEMA,
    REVIEW_SCHEMA,
    TransportDatumPortAcquisitionError,
    audit_existing_transport_seed_evidence,
    build_transport_datum_port_acquisition_plan,
    confirm_transport_datum_port_candidate,
    load_confirmed_transport_datum_source_specs,
    review_transport_datum_leaf_scan,
)


ROOT = Path(__file__).resolve().parents[3]


def _row(endpoint_id, normal, area, face_index, *, persistent=True):
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
            "FaceArea": area,
            "FaceCenterLocal": [float(face_index), 0.0, 0.0],
            "FaceNormalLocal": normal,
            "SourceAssemblyPersistentReferenceBase64": (
                f"persistent-{face_index}" if persistent else None
            ),
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


def _item():
    return {
        "moduleDefinitionId": "project01::SS00",
        "moduleToken": "SS00",
        "sourceReleaseId": "relation-source",
        "sourceAssemblyPath": "C:/cad/source.SLDASM",
        "seedCatalogPath": "seed.json",
        "scanOutputPath": "scan.json",
        "existingSupportEndpointId": "face:ss00:support",
        "staticMountLeafSelector": "SS00-1/static-leaf-1",
    }


def test_committed_sources_build_exact_two_item_scan_plan():
    plan = build_transport_datum_port_acquisition_plan(ROOT)
    assert plan["schemaVersion"] == PLAN_SCHEMA
    assert plan["summary"] == {
        "itemCount": 2,
        "scanRequiredCount": 2,
        "confirmedPortCount": 0,
    }
    assert [row["moduleDefinitionId"] for row in plan["items"]] == [
        "project01::SS00",
        "project03::AE00",
    ]
    assert all(row["cadExecutionAuthorized"] is False for row in plan["items"])
    assert all(row["scanPolicy"]["siblingLeafTraversalAllowed"] is False for row in plan["items"])
    assert plan["safetyBoundary"]["native58mmCompatibilityClaimed"] is False


def test_historical_seed_catalogs_do_not_replace_bounded_leaf_scan():
    audit = audit_existing_transport_seed_evidence(ROOT)
    assert audit["summary"] == {
        "itemCount": 2,
        "reusableWithoutRescanCount": 0,
        "boundedLeafScanRequiredCount": 2,
    }
    assert [row["sameLeafEndpointCount"] for row in audit["items"]] == [3, 3]
    assert [row["sameLeafPersistentPlaneCount"] for row in audit["items"]] == [
        1,
        1,
    ]
    assert all(row["boundedLeafScanStillRequired"] for row in audit["items"])
    assert audit["executionBoundary"]["cadExecutionAuthorized"] is False


def test_review_enumerates_real_orthogonal_triplet_but_does_not_select_it():
    support = _row("face:ss00:support", [0.0, 0.0, 1.0], 0.02, 0)
    first = _row("face:ss00:x", [1.0, 0.0, 0.0], 0.01, 1)
    second = _row("face:ss00:y", [0.0, 1.0, 0.0], 0.008, 2)
    parallel = _row("face:ss00:z2", [0.0, 0.0, -1.0], 0.03, 3)
    seed = _catalog([support])
    scan = _catalog([support, first, second, parallel], leaf_scoped=True)

    review = review_transport_datum_leaf_scan(_item(), seed, scan)

    assert review["schemaVersion"] == REVIEW_SCHEMA
    assert review["status"] == "candidate_triplets_require_engineering_confirmation"
    assert review["candidateCount"] == 1
    assert review["engineeringDecision"] == {
        "confirmed": False,
        "selectedCandidateId": None,
        "longitudinalEndpointId": None,
        "lateralEndpointId": None,
        "confirmationSource": None,
    }
    assert review["executionBoundary"]["cadExecutionAuthorized"] is False
    assert review["executionBoundary"]["native58mmMechanicalCompatibilityClaimed"] is False


def test_review_rejects_sibling_leaf_and_missing_persistent_reference():
    support = _row("face:ss00:support", [0.0, 0.0, 1.0], 0.02, 0)
    missing_ref = _row(
        "face:ss00:x", [1.0, 0.0, 0.0], 0.01, 1, persistent=False
    )
    sibling = _row("face:ss00:y", [0.0, 1.0, 0.0], 0.01, 2)
    sibling["Endpoint"]["LeafHierarchyPath"] = "SS00-1/sibling-leaf-1"
    review = review_transport_datum_leaf_scan(
        _item(),
        _catalog([support]),
        _catalog([support, missing_ref, sibling], leaf_scoped=True),
    )
    assert review["status"] == "no_mutually_orthogonal_plane_triplet_found"
    assert review["candidateCount"] == 0


def test_review_rejects_non_leaf_scoped_catalog():
    support = _row("face:ss00:support", [0.0, 0.0, 1.0], 0.02, 0)
    with pytest.raises(
        TransportDatumPortAcquisitionError, match="not leaf_scoped"
    ):
        review_transport_datum_leaf_scan(
            _item(), _catalog([support]), _catalog([support])
        )


def test_confirmation_binds_selected_endpoints_without_cad_authorization():
    support = _row("face:ss00:support", [0.0, 0.0, 1.0], 0.02, 0)
    scan = _catalog(
        [
            support,
            _row("face:ss00:x", [1.0, 0.0, 0.0], 0.01, 1),
            _row("face:ss00:y", [0.0, 1.0, 0.0], 0.008, 2),
        ],
        leaf_scoped=True,
    )
    review = review_transport_datum_leaf_scan(
        _item(), _catalog([support]), scan
    )
    candidate_id = review["candidates"][0]["candidateId"]
    confirmed = confirm_transport_datum_port_candidate(
        review,
        selected_candidate_id=candidate_id,
        longitudinal_endpoint_id="face:ss00:x",
        lateral_endpoint_id="face:ss00:y",
        confirmation_source="mechanical-review-20261026",
    )
    assert confirmed["schemaVersion"] == CONFIRMED_PORT_SCHEMA
    assert [
        binding["role"] for binding in confirmed["port"]["endpointBindings"]
    ] == ["support_datum", "longitudinal_datum", "lateral_datum"]
    assert confirmed["authorization"]["readyForParameterizedCatalogRegistration"] is True
    assert confirmed["authorization"]["readyForReleasedCadExecution"] is False
    assert confirmed["authorization"]["requiresExplicitPositionParameters"] is True


def test_confirmation_rejects_unknown_candidate_and_blank_source():
    review = {
        "schemaVersion": REVIEW_SCHEMA,
        "moduleDefinitionId": "project01::SS00",
        "moduleToken": "SS00",
        "reviewDigest": "digest",
        "candidates": [],
    }
    with pytest.raises(TransportDatumPortAcquisitionError, match="absent"):
        confirm_transport_datum_port_candidate(
            review,
            selected_candidate_id="missing",
            longitudinal_endpoint_id="x",
            lateral_endpoint_id="y",
            confirmation_source="review",
        )
    with pytest.raises(TransportDatumPortAcquisitionError, match="required"):
        confirm_transport_datum_port_candidate(
            {**review, "candidates": [{"candidateId": "c"}]},
            selected_candidate_id="c",
            longitudinal_endpoint_id="x",
            lateral_endpoint_id="y",
            confirmation_source=" ",
        )


def test_scan_source_and_requested_leaf_are_bound():
    support = _row("face:ss00:support", [0.0, 0.0, 1.0], 0.02, 0)
    seed = _catalog([support])
    scan = _catalog([support], leaf_scoped=True)
    altered = copy.deepcopy(scan)
    altered["RequestedLeafSelectors"] = ["SS00-1/other-leaf"]
    with pytest.raises(TransportDatumPortAcquisitionError, match="planned"):
        review_transport_datum_leaf_scan(_item(), seed, altered)


def test_confirmed_port_loader_reauthenticates_scan_and_geometry(tmp_path):
    support = _row("face:ss00:support", [0.0, 0.0, 1.0], 0.02, 0)
    scan = _catalog(
        [
            support,
            _row("face:ss00:x", [1.0, 0.0, 0.0], 0.01, 1),
            _row("face:ss00:y", [0.0, 1.0, 0.0], 0.008, 2),
        ],
        leaf_scoped=True,
    )
    scan_path = tmp_path / "scan.json"
    scan_path.write_text(__import__("json").dumps(scan), encoding="utf-8")
    item = {**_item(), "scanOutputPath": "scan.json"}
    review = review_transport_datum_leaf_scan(item, _catalog([support]), scan)
    confirmed = confirm_transport_datum_port_candidate(
        review,
        selected_candidate_id=review["candidates"][0]["candidateId"],
        longitudinal_endpoint_id="face:ss00:x",
        lateral_endpoint_id="face:ss00:y",
        confirmation_source="mechanical-review",
    )
    directory = (
        tmp_path
        / "demo/cross_project_substitution/transport-three-plane-port-acquisition-v1/confirmed-ports"
    )
    directory.mkdir(parents=True)
    (directory / "ss00.json").write_text(
        __import__("json").dumps(confirmed), encoding="utf-8"
    )

    specs = load_confirmed_transport_datum_source_specs(tmp_path)

    assert specs["project01::SS00"]["role"] == "Transport"
    assert specs["project01::SS00"]["catalog"] == "scan.json"
    assert specs["project01::SS00"]["endpoints"] == (
        "face:ss00:support",
        "face:ss00:x",
        "face:ss00:y",
    )


def test_confirmed_port_loader_rejects_stale_scan(tmp_path):
    directory = (
        tmp_path
        / "demo/cross_project_substitution/transport-three-plane-port-acquisition-v1/confirmed-ports"
    )
    directory.mkdir(parents=True)
    document = {
        "schemaVersion": CONFIRMED_PORT_SCHEMA,
        "moduleDefinitionId": "project01::SS00",
        "moduleToken": "SS00",
        "sourceReleaseId": "relation-source",
        "scanCatalogPath": "scan.json",
        "scanCatalogDigest": "stale",
        "port": {"endpointBindings": []},
    }
    from demo_backend.transport_datum_port_acquisition import _digest

    document["confirmationDigest"] = _digest(document)
    (directory / "ss00.json").write_text(
        __import__("json").dumps(document), encoding="utf-8"
    )
    (tmp_path / "scan.json").write_text("{}", encoding="utf-8")

    with pytest.raises(TransportDatumPortAcquisitionError, match="digest mismatch"):
        load_confirmed_transport_datum_source_specs(tmp_path)
