from demo_backend.installation_datum_discovery import (
    discover_secondary_installation_datums,
)


def _row(endpoint_id, surface, center, direction):
    endpoint = {
        "SurfaceType": surface,
        "FaceCenterWorld": center,
        "FaceIndexInBody": int(endpoint_id.rsplit("-", 1)[-1]),
        "SourceAssemblyPersistentReferenceBase64": "persistent",
    }
    if surface == "Cylinder":
        endpoint.update(
            {
                "CylinderOriginWorld": center,
                "CylinderAxisWorld": direction,
                "CylinderRadius": 0.002,
            }
        )
    else:
        endpoint["FaceNormalWorld"] = direction
    return {
        "EndpointId": endpoint_id,
        "GeometryClass": "Surface" if surface == "Cylinder" else "Plane",
        "Endpoint": endpoint,
    }


def _catalog(rows):
    return {
        "SchemaVersion": "solidworks-face-endpoint-catalog/v1",
        "Endpoints": rows,
    }


def test_single_independent_axis_pair_is_executable_but_not_published():
    moving = _catalog(
        [
            _row("moving-primary-1", "Cylinder", [0, 0, 0], [0, 1, 0]),
            _row("moving-second-2", "Cylinder", [0.03, 0, 0], [0, 1, 0]),
        ]
    )
    target = _catalog(
        [
            _row("target-primary-1", "Cylinder", [0, 0.01, 0], [0, -1, 0]),
            _row("target-second-2", "Cylinder", [0.03, 0.01, 0], [0, 1, 0]),
        ]
    )

    result = discover_secondary_installation_datums(
        moving,
        target,
        primary_moving_endpoint_id="moving-primary-1",
        primary_target_endpoint_id="target-primary-1",
    )

    assert result["status"] == (
        "single_secondary_axis_candidate_pending_cad_validation"
    )
    assert result["secondaryAxisCandidateCount"] == 1
    assert result["preferredCandidate"]["movingEndpointId"] == "moving-second-2"
    assert result["decision"]["cadExecutionAllowed"] is True
    assert result["decision"]["semanticPortPublished"] is False
    assert result["prototypeUse"]["runtimePoseAnchorAllowed"] is False


def test_same_primary_axis_is_rejected_as_duplicate_datum():
    moving = _catalog(
        [
            _row("moving-primary-1", "Cylinder", [0, 0, 0], [0, 1, 0]),
            _row("moving-duplicate-2", "Cylinder", [0, 0.02, 0], [0, 1, 0]),
        ]
    )
    target = _catalog(
        [
            _row("target-primary-1", "Cylinder", [0, 0.01, 0], [0, 1, 0]),
            _row("target-duplicate-2", "Cylinder", [0, 0.03, 0], [0, 1, 0]),
        ]
    )

    result = discover_secondary_installation_datums(
        moving,
        target,
        primary_moving_endpoint_id="moving-primary-1",
        primary_target_endpoint_id="target-primary-1",
    )

    assert result["secondaryAxisCandidateCount"] == 0
    assert result["status"] == "manual_face_selection_required"
    assert result["decision"]["cadExecutionAllowed"] is False


def test_ambiguous_pairs_fail_closed():
    moving = _catalog(
        [
            _row("moving-primary-1", "Cylinder", [0, 0, 0], [0, 1, 0]),
            _row("moving-second-2", "Cylinder", [0.03, 0, 0], [0, 1, 0]),
            _row("moving-third-3", "Cylinder", [-0.03, 0, 0], [0, 1, 0]),
        ]
    )
    target = _catalog(
        [
            _row("target-primary-1", "Cylinder", [0, 0.01, 0], [0, 1, 0]),
            _row("target-second-2", "Cylinder", [0.03, 0.01, 0], [0, 1, 0]),
            _row("target-third-3", "Cylinder", [-0.03, 0.01, 0], [0, 1, 0]),
        ]
    )

    result = discover_secondary_installation_datums(
        moving,
        target,
        primary_moving_endpoint_id="moving-primary-1",
        primary_target_endpoint_id="target-primary-1",
    )

    assert result["secondaryAxisCandidateCount"] == 2
    assert result["status"] == (
        "ambiguous_secondary_axis_candidates_manual_review_required"
    )
    assert result["preferredCandidate"] is None
    assert result["decision"]["cadExecutionAllowed"] is False

