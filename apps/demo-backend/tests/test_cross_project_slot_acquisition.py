import json
from pathlib import Path

import pytest

from demo_backend.cross_project_slot_acquisition import (
    build_calibration_slot_acquisition_request,
    build_slot_port_candidate,
    screen_slot_capture,
    select_operation_side_candidate,
)


ROOT = Path(__file__).resolve().parents[3]


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _request():
    return build_calibration_slot_acquisition_request(
        _read(
            ROOT
            / "demo/global_assembly_catalog/releases/"
            "relation-v39-project03-ab00-complete-driving-20261012/"
            "global_module_catalog.json"
        ),
        geometry_capture=_read(
            ROOT
            / "demo/layout_previews/"
            "project02_a600_installation_geometry_capture.json"
        ),
        installation_surface=_read(
            ROOT
            / "demo/layout_previews/project02_a600_installation_surface.json"
        ),
        installation_frame=_read(
            ROOT / "demo/layout_previews/project02_a600_installation_frame.json"
        ),
    )


def test_a600_calibration_slot_request_is_precise_and_fail_closed():
    request = _request()

    assert request["status"] == "geometry_capture_required"
    assert request["sourceModule"]["moduleToken"] == "AH00"
    assert request["targetBase"]["moduleToken"] == "A600"
    assert request["targetBase"]["cadPath"].endswith(
        "FL9A24D062A600.001.SLDASM"
    )
    assert request["requiredInterface"]["locatingPairSpacingMeters"] == 0.05
    assert request["requiredInterface"]["spacingToleranceMeters"] == 0.0005
    assert request["executionPolicy"] == {
        "cadExecutionAllowed": False,
        "failClosedReason": "TARGET_SLOT_GEOMETRY_NOT_REGISTERED",
        "adapterGeometryInvented": False,
        "unregisteredSlotInferred": False,
        "collisionOrBrepRequiredAtThisStage": False,
    }


def test_a600_request_reuses_native_leaf_as_targeted_scan_scope_only():
    request = _request()
    plan = request["targetedCapturePlan"]

    assert plan["primaryLeafHierarchyPath"].endswith(
        "24D062-FL5B24D062A600001.01-1-1"
    )
    assert plan["priorityBodyIndicesFromNativeSlot"] == [12]
    assert plan["fullAssemblyBlindScanRequired"] is False
    assert plan["fallbackMode"] == "three-user-selected-faces"
    native = request["nativeTargetReference"]
    assert native["moduleToken"] == "A500"
    assert native["topologyConclusion"] == (
        "native_slot_not_equivalent_to_two_hole_pattern"
    )
    assert {"mount_plane", "width_side_a", "width_side_b", "offset_plane"} == set(
        native["nativeEndpointRoles"]
    )


def test_existing_a600_assets_are_not_misrepresented_as_hole_evidence():
    request = _request()
    assessment = request["existingEvidenceAssessment"]

    assert assessment["geometryCapture"]["bodyCount"] == 708
    assert assessment["geometryCapture"]["sufficientForHoleTopology"] is False
    assert assessment["installationSurface"]["usableForCoarseLayout"] is True
    assert assessment["installationSurface"]["sufficientForHoleTopology"] is False
    assert assessment["installationFrame"]["sufficientForHoleTopology"] is False
    assert assessment["nativeSlot"]["sufficientForRequiredInterface"] is False


def test_existing_bounded_a500_catalog_does_not_invent_a_two_hole_slot():
    screening = screen_slot_capture(
        _request(),
        _read(
            ROOT
            / "demo/semantic_ports/project02_A500_full_installation_v2/"
            "face_endpoint_catalog.json"
        ),
    )

    assert screening["status"] == "no_matching_geometry_in_supplied_catalog"
    assert screening["cylindricalEndpointCount"] == 0
    assert screening["candidateCount"] == 0
    assert screening["decision"]["semanticPortPublished"] is False
    assert screening["decision"]["cadExecutionAllowed"] is False


def test_leaf_capture_screening_finds_parallel_50_mm_pair_but_requires_review():
    request = _request()
    leaf = request["targetedCapturePlan"]["primaryLeafHierarchyPath"]

    def endpoint(endpoint_id, surface, center, axis=None, normal=None):
        if surface == "Cylinder":
            box = [
                center[0] - 0.002,
                center[1] - 0.002,
                center[2] - 0.005,
                center[0] + 0.002,
                center[1] + 0.002,
                center[2] + 0.005,
            ]
        else:
            box = [-0.01, -0.04, center[2], 0.01, 0.04, center[2]]
        return {
            "EndpointId": endpoint_id,
            "GeometryClass": surface,
            "Endpoint": {
                "RelativeLeafHierarchyPath": leaf,
                "SurfaceType": surface,
                "BodyIndex": 0,
                "FaceBoxLocal": box,
                "FaceCenterLocal": center,
                "FaceNormalLocal": normal,
                "CylinderOriginLocal": center if surface == "Cylinder" else None,
                "CylinderAxisLocal": axis,
                "CylinderRadius": 0.002 if surface == "Cylinder" else None,
            },
        }

    catalog = {
        "SchemaVersion": "solidworks-face-endpoint-catalog/v1",
        "CatalogMode": "leaf_scoped",
        "Endpoints": [
            endpoint("plane", "Plane", [0, 0, 0.005], normal=[0, 0, 1]),
            endpoint("hole-a", "Cylinder", [0, -0.025, 0], axis=[0, 0, 1]),
            endpoint("hole-b", "Cylinder", [0, 0.025, 0], axis=[0, 0, -1]),
            endpoint("wrong", "Cylinder", [0.2, 0.2, 0], axis=[1, 0, 0]),
        ],
    }
    screening = screen_slot_capture(request, catalog)

    assert screening["status"] == "candidate_geometry_found_manual_review_required"
    assert screening["candidateCount"] == 1
    assert screening["candidates"][0]["locatingEndpointIds"] == [
        "hole-a",
        "hole-b",
    ]
    assert screening["candidates"][0]["axisSpacingMeters"] == 0.05
    assert screening["decision"]["semanticPortPublished"] is False
    assert screening["decision"]["nextAction"] == (
        "manual-review-and-endpoint-recovery-test"
    )


def test_real_a600_candidates_reduce_to_two_columns_and_operation_side_is_selected():
    request = _request()
    catalog = _read(
        ROOT
        / "demo/cross_project_substitution/alternate-slot-discovery-v1/"
        "project02_A600_calibration_slot_acquisition/"
        "a600-native-service-leaf-face-catalog-v1.json"
    )
    screening = screen_slot_capture(request, catalog)
    selection = select_operation_side_candidate(
        request,
        screening,
        catalog,
        _read(ROOT / "demo/layout_previews/project02_a600_installation_frame.json"),
    )

    assert screening["candidateCount"] == 2
    assert all(row["bodyIndex"] == 72 for row in screening["candidates"])
    assert all(
        row["locatingRadiusMeters"] == pytest.approx(0.0021)
        for row in screening["candidates"]
    )
    assert selection["status"] == "candidate_selected_pending_cad_validation"
    selected = selection["selectedCandidate"]
    alternate = selection["alternateCandidates"][0]
    assert selected["candidateCenterInA600FrameMeters"]["xIntoMachineMeters"] < (
        alternate["candidateCenterInA600FrameMeters"]["xIntoMachineMeters"]
    )
    assert selected["candidateCenterInA600FrameMeters"]["xIntoMachineMeters"] == (
        pytest.approx(0.1613)
    )
    assert selected["locatingEndpointIds"] == [
        "face:fl9a24d062a600.001-1:1e8d1d2e490e3c0a",
        "face:fl9a24d062a600.001-1:adf246feb6c09278",
    ]
    assert selection["decision"]["semanticPortPublished"] is False
    assert selection["decision"]["cadExecutionAllowed"] is False


def test_selected_faces_form_unpublished_port_and_recovery_only_allows_validation():
    request = _request()
    catalog = _read(
        ROOT
        / "demo/cross_project_substitution/alternate-slot-discovery-v1/"
        "project02_A600_calibration_slot_acquisition/"
        "a600-native-service-leaf-face-catalog-v1.json"
    )
    screening = screen_slot_capture(request, catalog)
    selection = select_operation_side_candidate(
        request,
        screening,
        catalog,
        _read(ROOT / "demo/layout_previews/project02_a600_installation_frame.json"),
    )

    pending = build_slot_port_candidate(request, selection, catalog)
    assert pending["status"] == "endpoint_recovery_required"
    assert pending["candidatePort"]["portable"] is False
    assert pending["decision"]["semanticPortPublished"] is False
    assert pending["decision"]["cadExecutionAllowed"] is False
    assert [
        row["role"] for row in pending["candidatePort"]["endpointBindings"]
    ] == ["support_plane", "locating_hole_1", "locating_hole_2"]
    assert all(
        row["hasPersistentReference"]
        for row in pending["candidatePort"]["endpointEvidence"]
    )

    evidence = {
        "schemaVersion": "cross-project-slot-endpoint-recovery/v1",
        "selectionDigest": selection["selectionDigest"],
        "results": [
            {"endpointId": endpoint_id, "success": True}
            for endpoint_id in pending["endpointRecovery"]["requiredEndpointIds"]
        ],
    }
    recovered = build_slot_port_candidate(
        request,
        selection,
        catalog,
        endpoint_recovery_evidence=evidence,
    )
    assert recovered["status"] == "endpoint_recovered_pending_cross_project_cad"
    assert recovered["endpointRecovery"]["allRecovered"] is True
    assert recovered["decision"]["cadExecutionAllowed"] is True
    assert recovered["decision"]["allowedCadScope"] == (
        "candidate-cross-project-validation-only"
    )
    assert recovered["decision"]["semanticPortPublished"] is False
