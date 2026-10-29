import copy
import hashlib
import json
from pathlib import Path

import pytest

from demo_backend.saved_output_station_inspection import (
    authenticate_saved_output_station_inspection_binding,
    build_saved_output_station_inspection_plan,
)


ROOT = Path(__file__).resolve().parents[3]
REQUEST = ROOT / (
    "data/assembly_stations/"
    "a300-a000-saved-output-inspection-request-v1.json"
)
NEW_REQUESTS = [
    (
        ROOT / "demo/station_gap_batch_20261028/coverage-v13/"
        "gn00-jj00-native-postcheck-v1/request.json",
        "JJ00",
        "GN00",
    ),
    (
        ROOT / "demo/station_gap_batch_20261028/coverage-v13/"
        "a300-base-pose-inspection-v1/jj00/request.json",
        "JJ00",
        "A300",
    ),
    (
        ROOT / "demo/station_gap_batch_20261028/coverage-v13/"
        "a300-base-pose-inspection-v1/aa00/request.json",
        "AA00",
        "A300",
    ),
]
TRANSPORT_RECHECK_BATCH = ROOT / (
    "demo/station_gap_batch_20261028/transport-rechecks-v1/batch-report.json"
)
WASTECUP_BASE_POSE_BATCH = ROOT / (
    "demo/station_gap_batch_20261028/wastecup-base-pose-rechecks-v1/"
    "batch-report.json"
)
LATEST_RECHECK_BATCHES = [
    (
        ROOT / "demo/station_gap_batch_20261028/"
        "wastecup-saved-output-rechecks-v4/batch-report.json",
        4,
    ),
    (
        ROOT / "demo/station_gap_batch_20261028/"
        "cleaning-saved-output-rechecks-v4/batch-report.json",
        3,
    ),
    (
        ROOT / "demo/station_gap_batch_20261028/"
        "transport-saved-output-rechecks-v4/batch-report.json",
        8,
    ),
]


def _digest(payload: dict) -> str:
    unsigned = dict(payload)
    unsigned.pop("requestDigest", None)
    return hashlib.sha256(
        json.dumps(
            unsigned,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def test_real_a300_a000_request_plans_readonly_without_rerunning_cad():
    plan = build_saved_output_station_inspection_plan(ROOT, REQUEST)
    assert plan["baseToken"] == "A000"
    assert plan["targetToken"] == "A300"
    assert plan["expectedTopLevelComponentCount"] == 2
    assert plan["readOnly"] is True
    assert plan["cadStarted"] is False
    assert plan["recreatesMatesOrComponents"] is False
    assert "verify_datum_chain_live_state.py" in " ".join(plan["command"])


@pytest.mark.parametrize("request_path,base,target", NEW_REQUESTS)
def test_new_saved_outputs_are_authenticated_as_readonly_requests(
    request_path: Path, base: str, target: str
):
    plan = build_saved_output_station_inspection_plan(ROOT, request_path)
    assert plan["baseToken"] == base
    assert plan["targetToken"] == target
    assert plan["expectedTopLevelComponentCount"] == 2
    assert plan["readOnly"] is True
    assert plan["recreatesMatesOrComponents"] is False


def test_changed_request_and_wrong_target_fail_closed(tmp_path: Path):
    payload = json.loads(REQUEST.read_text(encoding="utf-8"))
    payload["targetToken"] = "P000"
    changed = tmp_path / "changed.json"
    changed.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="digest mismatch"):
        build_saved_output_station_inspection_plan(ROOT, changed)

    payload["requestDigest"] = _digest(payload)
    changed.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="target differs"):
        build_saved_output_station_inspection_plan(ROOT, changed)


def test_existing_evidence_is_never_overwritten(tmp_path: Path):
    payload = copy.deepcopy(json.loads(REQUEST.read_text(encoding="utf-8")))
    state = tmp_path / "state.json"
    state.write_text("{}", encoding="utf-8")
    payload["outputStatePath"] = str(state)
    payload["processReportPath"] = str(tmp_path / "process.json")
    payload["requestDigest"] = _digest(payload)
    request = tmp_path / "request.json"
    request.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(FileExistsError, match="already exists"):
        build_saved_output_station_inspection_plan(ROOT, request)


def test_exact_reference_resolution_is_authenticated_and_passed_to_verifier(
    tmp_path: Path,
):
    payload = copy.deepcopy(json.loads(REQUEST.read_text(encoding="utf-8")))
    resolved = tmp_path / "example.SLDPRT"
    resolved.write_bytes(b"exact-reference")
    payload["referenceResolution"] = {
        "policy": "transient-exact-file-parent-search/v1",
        "mappings": [
            {
                "savedPath": r"D:\\old\\example.SLDPRT",
                "resolvedPath": str(resolved),
                "sha256": hashlib.sha256(resolved.read_bytes()).hexdigest(),
            }
        ],
    }
    payload["outputStatePath"] = str(tmp_path / "state.json")
    payload["processReportPath"] = str(tmp_path / "process.json")
    payload["requestDigest"] = _digest(payload)
    request = tmp_path / "request.json"
    request.write_text(json.dumps(payload), encoding="utf-8")

    plan = build_saved_output_station_inspection_plan(ROOT, request)

    assert plan["referenceSearchFolders"] == [str(tmp_path.resolve())]
    assert plan["referenceResolutionMappings"][0]["resolvedPath"] == str(
        resolved.resolve()
    )
    assert "--reference-search-folder" in plan["command"]


def test_changed_or_mismatched_reference_resolution_fails_closed(tmp_path: Path):
    payload = copy.deepcopy(json.loads(REQUEST.read_text(encoding="utf-8")))
    resolved = tmp_path / "different.SLDPRT"
    resolved.write_bytes(b"reference")
    payload["referenceResolution"] = {
        "policy": "transient-exact-file-parent-search/v1",
        "mappings": [
            {
                "savedPath": r"D:\\old\\expected.SLDPRT",
                "resolvedPath": str(resolved),
                "sha256": hashlib.sha256(resolved.read_bytes()).hexdigest(),
            }
        ],
    }
    payload["outputStatePath"] = str(tmp_path / "state.json")
    payload["processReportPath"] = str(tmp_path / "process.json")
    payload["requestDigest"] = _digest(payload)
    request = tmp_path / "request.json"
    request.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="filename differs"):
        build_saved_output_station_inspection_plan(ROOT, request)


def test_transport_recheck_batch_authenticates_eight_historical_outputs():
    batch = json.loads(TRANSPORT_RECHECK_BATCH.read_text(encoding="utf-8"))
    assert batch["candidateCount"] == 9
    assert batch["readyReadOnlyInspectionCount"] == 8
    assert batch["freshCadStillRequiredCount"] == 1
    assert batch["cadStarted"] is False
    pairs = set()
    for row in batch["ready"]:
        request = ROOT / row["requestPath"]
        plan = build_saved_output_station_inspection_plan(ROOT, request)
        station_plan = ROOT / row["stationPlanPath"]
        assert plan["readOnly"] is True
        assert plan["cadStarted"] is False
        assert plan["recreatesMatesOrComponents"] is False
        assert hashlib.sha256(station_plan.read_bytes()).hexdigest() == row[
            "stationPlanSha256"
        ]
        pairs.add((row["sourceModuleDefinitionId"], row["targetBaseDefinitionId"]))
    assert len(pairs) == 8
    assert batch["freshCadRequired"] == [{
        "sourceModuleDefinitionId": "project03::AE00",
        "targetBaseDefinitionId": "project03::AA00",
        "gapCategory": "native_transport_station_nonprototype_cad_validation_required",
        "nextAction": "execute_fresh_nonprototype_cad_queue",
    }]


def test_wastecup_mapping_batch_prepares_two_saved_base_pose_inspections():
    batch = json.loads(WASTECUP_BASE_POSE_BATCH.read_text(encoding="utf-8"))
    assert batch["role"] == "WasteCup"
    assert batch["requestCount"] == 2
    assert batch["cadStarted"] is False
    assert {
        (row["sourceModuleDefinitionId"], row["targetBaseDefinitionId"])
        for row in batch["requests"]
    } == {
        ("project02::A300", "project01::JJ00"),
        ("project02::A300", "project03::AA00"),
    }
    for row in batch["requests"]:
        plan = build_saved_output_station_inspection_plan(
            ROOT, ROOT / row["requestPath"]
        )
        assert plan["readOnly"] is True
        assert plan["cadStarted"] is False
        assert plan["recreatesMatesOrComponents"] is False


def test_latest_gap_v52_saved_output_queue_authenticates_all_fifteen_requests():
    identities = set()
    total = 0
    for report_path, expected_count in LATEST_RECHECK_BATCHES:
        batch = json.loads(report_path.read_text(encoding="utf-8"))
        assert batch["requestCount"] == expected_count
        assert batch["cadStarted"] is False
        assert "gap-batch-v52" in batch["sourceGapReport"]["path"]
        for row in batch["requests"]:
            identity = (
                row["sourceModuleDefinitionId"],
                row["targetBaseDefinitionId"],
            )
            assert identity not in identities
            identities.add(identity)
            request_path = ROOT / row["requestPath"]
            request_payload = json.loads(request_path.read_text(encoding="utf-8"))
            state = ROOT / request_payload["outputStatePath"]
            process = ROOT / request_payload["processReportPath"]
            plan = (
                authenticate_saved_output_station_inspection_binding(
                    ROOT, request_path
                )
                if state.exists() or process.exists()
                else build_saved_output_station_inspection_plan(ROOT, request_path)
            )
            assert plan["readOnly"] is True
            assert plan["cadStarted"] is False
            assert plan["recreatesMatesOrComponents"] is False
            total += 1
    assert total == 15
