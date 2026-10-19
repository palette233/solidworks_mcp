from __future__ import annotations

from demo_backend.project05_optical_geometry import build_project05_optical_geometry


def _body(path: str, box: list[float]) -> dict:
    return {"Component": {"HierarchyPath": path}, "BoundingBoxWorld": box}


def test_explicit_scan_beams_and_ccd_stack_create_partial_optical_evidence() -> None:
    f000 = {
        "coverageComplete": True,
        "bodies": [
            _body("root/FL5C251093F110002.01-1", [0.0, 1.0, 0.0, 0.17, 1.012, 0.012]),
            _body("root/FL5C251093F100003.01-1", [0.5, 0.8, -0.12, 0.55, 0.808, 0.0]),
        ],
    }
    m000 = {
        "coverageComplete": True,
        "bodies": [
            _body("root/CCD/FL802AD-00111-1", [0.4, 1.16, -0.4, 0.43, 1.22, -0.37]),
            _body("root/CCD/FL801AA-00089-1", [0.39, 0.92, -0.41, 0.44, 1.16, -0.36]),
        ],
    }
    geometry = {"installationFrame": {
        "originWorldMeters": [0.0, 0.656, 0.0],
        "flowAxisWorld": [0.0, 0.0, 1.0],
        "transverseAxisWorld": [1.0, 0.0, 0.0],
        "upAxisWorld": [0.0, 1.0, 0.0],
    }}
    positions = {"workPositions": [
        {"installationFramePointMeters": {"u": 0.0, "v": 0.4, "normal": 0.278}},
        {"installationFramePointMeters": {"u": 0.415, "v": 0.4, "normal": 0.278}},
    ]}

    result = build_project05_optical_geometry(f000, m000, geometry, positions)

    assert result["scanner"]["explicitBeamCount"] == 2
    assert result["scanner"]["beams"][0]["lengthMeters"] == 0.17
    assert result["scanner"]["beams"][1]["lengthMeters"] == 0.12
    assert result["scanner"]["workingDistanceConfirmed"] is False
    assert result["scanner"]["scanStation"]["coarseLayoutUsable"] is True
    assert result["scanner"]["scanStation"]["carrierBeamId"] == "f000-explicit-beam-b"
    assert result["scanner"]["scanStation"]["productBeamId"] == "f000-explicit-beam-a"
    assert result["ccd"]["axisWorld"] == [0.0, -1.0, 0.0]
    assert result["ccd"]["twoWorkPositionCoverageCoarseLayoutUsable"] is True
    assert len(result["ccd"]["workPositionOpticalTargets"]) == 2
    assert result["ccd"]["preciseOpticalOriginConfirmed"] is False
    assert result["releaseDecision"]["coarseOpticalOrientationMayBeUsed"] is True
    assert result["releaseDecision"]["preciseOpticalConstraintMayBeUsed"] is False
