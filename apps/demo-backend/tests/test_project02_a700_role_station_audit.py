from pathlib import Path

from demo_backend.project02_a700_role_station_audit import (
    build_project02_a700_role_station_audit,
)


ROOT = Path(__file__).resolve().parents[3]


def test_n000_a600_is_blocked_at_a700_role_station_until_endpoints_exist():
    report = build_project02_a700_role_station_audit(ROOT)

    assert report["status"] == "blocked_before_cad_missing_role_station_endpoint_bundle"
    assert report["classification"] == "REVIEW_REQUIRED"
    assert report["replacementEnvelopeFitsRoleStation"] is True
    assert report["cadLaunchAllowed"] is False
    assert report["forbiddenFallback"] == {
        "longitudinalMeters": 0.465,
        "lateralMeters": 0.7125,
        "reason": "previous recipe placed N000 directly over the A800 transport region",
    }
    assert {row["code"] for row in report["blockers"]} == {
        "A700_A600_NATIVE_ENDPOINT_BUNDLE_NOT_CAPTURED",
        "ROLE_STATION_TRANSPORT_BOUNDARY_REQUIRES_EXACT_FOOTPRINT_PLACEMENT",
    }
    interval = report["allowedReplacementDatumIntervalMeters"]
    assert interval["minX"] <= interval["maxX"]
    assert interval["minY"] <= interval["maxY"]
