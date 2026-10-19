from pathlib import Path

from demo_backend.cross_project_scanner_transport_process_validation import (
    build_scanner_transport_process_validation,
)


IDENTITY = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]


def _build(tmp_path: Path, *, target=(0.0, 0.1, 0.0), with_range=False):
    assembly = tmp_path / "result.SLDASM"
    assembly.write_bytes(b"assembly")
    graph = {"Modules": [{"ModuleToken": "SS00", "SourceTransform": IDENTITY}]}
    return build_scanner_transport_process_validation(
        optical_validation={
            "scannerModel": "KEYENCE SR-X100",
            "modeledWorkingDistanceMeters": 0.1,
            "opticalDirectionWorld": [0, 1, 0],
            "targetProxyWorldMeters": list(target),
        },
        project01_scanner_geometry={
            "schemaVersion": "project01-scanner-geometry/v1",
            "productScanInterface": {
                "targetProxyInstallationFrameMeters": {
                    "u": 0.5,
                    "v": 0.0,
                    "normal": 0.08,
                }
            },
        },
        project01_first_stage_geometry={
            "schemaVersion": "project01-first-stage-geometry/v1",
            "transportInstallationInterface": {
                "originWorldMeters": [0, 0, 0],
                "flowAxisWorld": [1, 0, 0],
                "transverseAxisWorld": [0, 0, 1],
                "upAxisWorld": [0, 1, 0],
            },
            "topLevelOccupancy": {
                "ss00WorldBoundsMeters": [-1, -0.1, -0.1, 1, 0.2, 0.1]
            },
        },
        project01_source_graph=graph,
        final_ss00_graph=graph,
        final_assembly_path=assembly,
        working_distance_evidence=(
            {
                "minimumMeters": 0.07,
                "maximumMeters": 1.0,
                "authority": "KEYENCE official SR-X100 specifications",
                "sourceUrl": "https://www.keyence.com.cn/example",
            }
            if with_range
            else None
        ),
    )


def test_moving_lane_is_compared_at_current_scanner_station(tmp_path):
    report = _build(tmp_path)
    checks = report["readOnlyChecks"]
    assert checks["scannerStationFlowCoordinateMeters"] == 0.0
    assert checks["barcodeLaneTargetAtScannerStationMeters"][0] == 0.0
    assert checks["requiredWorkingDistanceMeters"] == 0.08
    assert checks["crossTrackErrorMeters"] == 0.0
    assert report["coarseProcessGeometryPassed"] is True


def test_coarse_match_does_not_claim_full_working_distance_pass(tmp_path):
    report = _build(tmp_path)
    assert report["status"] == (
        "coarse_geometry_compatible_working_distance_unconfirmed"
    )
    assert report["staticDemoProcessValidationPassed"] is False
    assert report["engineeringProcessValidationPassed"] is False
    assert report["productionReady"] is False
    assert report["readOnlyChecks"]["workingDistanceCompatibilityPassed"] is None


def test_official_range_closes_static_demo_but_not_engineering_release(tmp_path):
    report = _build(tmp_path, with_range=True)
    assert report["status"] == "static_demo_passed_barcode_surface_proxy"
    assert report["readOnlyChecks"]["workingDistanceCompatibilityPassed"] is True
    assert report["staticDemoProcessValidationPassed"] is True
    assert report["engineeringProcessValidationPassed"] is False
    assert report["productionReady"] is False


def test_cross_track_mismatch_fails_closed(tmp_path):
    report = _build(tmp_path, target=(0.0, 0.1, 0.02))
    assert report["coarseProcessGeometryPassed"] is False
    assert report["status"] == "blocked_cross_project_optical_geometry_mismatch"


def test_digest_is_deterministic(tmp_path):
    assert _build(tmp_path)["validationDigest"] == _build(tmp_path)["validationDigest"]
