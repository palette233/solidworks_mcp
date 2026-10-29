from __future__ import annotations

import json
from pathlib import Path

from demo_backend.station_rule_planner import plan_station_chain


ROOT = Path(__file__).resolve().parents[3]


def _request() -> dict:
    return {
        "chainId": "n000-a600-bounded-role-station-test",
        "stationRegistryPath": (
            "data/assembly_stations/station-rules-n000-a600-bounded-v1.json"
        ),
        "baseSelection": {
            "projectId": "project02",
            "moduleToken": "A600",
            "confirmed": True,
        },
        "baseInstanceId": "base",
        "allowPrototypeEstimate": True,
        "steps": [
            {
                "stageId": "s01-cleaning",
                "instanceId": "cleaning",
                "moduleSelection": {
                    "projectId": "project05",
                    "moduleToken": "N000",
                    "confirmed": True,
                },
                "slotSelection": {
                    "projectId": "project02",
                    "moduleToken": "A600",
                    "confirmed": True,
                },
                "allowDatumFallback": True,
            }
        ],
    }


def test_bounded_role_station_plans_complete_nonprototype_package() -> None:
    plan = plan_station_chain(ROOT, _request(), prepare_candidates=True)
    assert plan["planningComplete"] is True
    stage = plan["stages"][0]["plan"]
    assert stage["status"] == "new_datum_candidate_requires_cad_validation_and_release"
    assert stage["requiresFreshCadValidation"] is True
    assert stage["geometry"]["nativeRoleStationContainment"]["passed"] is True
    assert stage["geometry"]["finiteSupportGate"]["passed"] is True
    package = stage["validationPackage"]
    assert package["prototypeTopLevelTargetPoseUsed"] is False
    assert package["caseAnchorUsed"] is False
    assert package["targetLeafPoseAnchorsUsed"] is False
    assert package["boundedRoleStationCandidate"]["candidateDigest"] == stage[
        "geometry"
    ]["candidateDigest"]


def test_bounded_role_station_registry_is_json() -> None:
    path = ROOT / "data/assembly_stations/station-rules-n000-a600-bounded-v1.json"
    assert json.loads(path.read_text(encoding="utf-8"))["rules"][0]["ruleId"] == (
        "cleaning-n000-a600-bounded-role-station-v1"
    )
