from __future__ import annotations

from demo_backend.project05_operation_side import infer_project05_operation_side


def test_service_cluster_is_checked_against_operation_side_strip() -> None:
    poses = {"components": [
        {"Name": "A000", "BoundingBoxWorld": [-1, 0, -1, 1, 1, 1]},
        {"Name": "D000", "BoundingBoxWorld": [-0.2, 0, -0.8, 0.2, 0.3, 0.8]},
        {"Name": "G000", "BoundingBoxWorld": [0.4, 0.3, -0.3, 0.6, 0.6, -0.1]},
        {"Name": "N000", "BoundingBoxWorld": [0.4, 0.3, 0.0, 0.6, 0.6, 0.2]},
        {"Name": "P000", "BoundingBoxWorld": [0.4, 0.3, 0.3, 0.6, 0.6, 0.5]},
    ]}
    geometry = {"installationFrame": {
        "originWorldMeters": [0, 0, 0],
        "flowAxisWorld": [0, 0, 1],
        "transverseAxisWorld": [1, 0, 0],
        "upAxisWorld": [0, 1, 0],
    }}
    result = infer_project05_operation_side(poses, geometry)
    assert result["operationSide"]["sign"] == "+v"
    assert result["allPrototypeServiceModulesInsideStrip"] is True
    assert result["coarseLayoutUsable"] is True
    assert result["engineeringConfirmed"] is False
