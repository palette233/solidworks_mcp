from __future__ import annotations

from demo_backend.project05_dual_valve_reach import infer_project05_dual_valve_reach


def test_named_axes_and_dual_cup_pitch_form_common_reach() -> None:
    poses = {"components": [{
        "Name": "FL9C254098B000.001-1",
        "BoundingBoxWorld": [-0.5, 0, -0.7, 0.9, 1.0, 0.7],
    }]}
    geometry = {"installationFrame": {
        "originWorldMeters": [0, 0, 0],
        "flowAxisWorld": [0, 0, 1],
        "transverseAxisWorld": [1, 0, 0],
        "upAxisWorld": [0, 1, 0],
    }}
    work = {"workPositions": [
        {"stableId": "work-1", "installationFramePointMeters": {"u": -0.2, "v": 0.1, "normal": 0.2}},
        {"stableId": "work-2", "installationFramePointMeters": {"u": 0.2, "v": 0.2, "normal": 0.2}},
    ]}
    service = {"servicePorts": [
        {"id": "drain-1", "capability": "glue_drain", "installationFrameMeters": {"u": -0.065, "v": 0.1, "normal": 0.2}},
        {"id": "drain-2", "capability": "glue_drain", "installationFrameMeters": {"u": 0.065, "v": 0.1, "normal": 0.2}},
        {"id": "clean", "capability": "cleaning", "installationFrameMeters": {"u": 0.0, "v": 0.2, "normal": 0.2}},
    ]}

    result = infer_project05_dual_valve_reach(
        poses,
        geometry,
        work,
        service,
        ["axis_TC-D01-T7512A-950L-HA.SLDASM", "rail_TC-SLM-800L-TL10.SLDPRT"],
    )
    assert result["axisEvidence"]["flowAxisNominalLengthMeters"] == 0.95
    assert result["dualValvePitch"]["meters"] == 0.13
    assert result["commonPlanarReachInstallationMeters"]["maxU"] - result["commonPlanarReachInstallationMeters"]["minU"] == 0.82
    assert result["allTargetsInsideCommonPlanarReach"] is True
    assert result["coarseLayoutUsable"] is True
    assert result["engineeringConfirmed"] is False
