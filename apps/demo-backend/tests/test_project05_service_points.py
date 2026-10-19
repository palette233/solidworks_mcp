from __future__ import annotations

from demo_backend.project05_service_points import infer_project05_service_points


def _body(name: str, path: str, bounds: list[float]) -> dict:
    return {
        "Component": {"Name": name, "Path": path, "HierarchyPath": name},
        "BoundingBoxWorld": bounds,
    }


def test_project05_service_points_restore_six_real_cad_proxies() -> None:
    g = {
        "coverageComplete": True,
        "bodies": [
            _body("G/FL5C251093G100013.01-1", r"C:\FL5C251093G100013.01.SLDPRT", [0, 0.1, 0, 0.03, 0.13, 0.002]),
            _body("G/FL00002-00468-1", r"C:\FL00002-00468.SLDPRT", [0.1, 0.02, 0.1, 0.15, 0.08, 0.15]),
        ],
    }
    n = {
        "coverageComplete": True,
        "bodies": [
            _body("N/FL9C251093NB21.001-2/a", r"C:\a.SLDPRT", [0.2, 0.02, 0.1, 0.24, 0.09, 0.14]),
            _body("N/FL9C251093NB21.001-3/b", r"C:\b.SLDPRT", [0.2, 0.02, 0.3, 0.24, 0.09, 0.34]),
        ],
    }
    p = {
        "coverageComplete": True,
        "bodies": [
            _body("FL00002-00549-1", r"C:\FL00002-00549.SLDPRT", [0.3, 0.01, 0.1, 0.36, 0.09, 0.16]),
            _body("FL00002-00549-2", r"C:\FL00002-00549.SLDPRT", [0.3, 0.01, 0.3, 0.36, 0.09, 0.36]),
        ],
    }
    geometry = {
        "installationFrame": {
            "originWorldMeters": [0, 0, 0],
            "flowAxisWorld": [0, 0, 1],
            "transverseAxisWorld": [1, 0, 0],
            "upAxisWorld": [0, 1, 0],
        }
    }

    result = infer_project05_service_points(g, n, p, geometry)
    ports = {item["id"]: item for item in result["servicePorts"]}
    assert len(ports) == 6
    assert ports["calibration-glue-target"]["worldMeters"] == [0.015, 0.115, 0.001]
    assert ports["weighing-cup"]["worldMeters"][1] == 0.08
    assert ports["cleaning-position-1"]["installationFrameMeters"]["u"] == 0.12000000000000001
    assert ports["cleaning-position-2"]["installationFrameMeters"]["u"] == 0.32
    assert ports["glue-drain-cup-1"]["confidence"] == "high"
    assert result["moduleSummary"]["P000"]["targetCount"] == 2
    assert result["coarseLayoutUsable"] is True
    assert result["engineeringConfirmed"] is False
