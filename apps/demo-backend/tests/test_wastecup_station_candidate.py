import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

import pytest

from demo_backend.saved_output_station_inspection import (
    authenticate_saved_output_station_inspection_binding,
    build_saved_output_station_inspection_plan,
)
from demo_backend.wastecup_station_candidate import (
    build_wastecup_station_candidate,
    build_wastecup_station_candidate_batch,
)


ROOT = Path(__file__).resolve().parents[3]
MAPPING_CONFIG = ROOT / "data/assembly_stations/a300-cross-base-cup-mapping-v1.json"
MAPPING_REPORT = ROOT / (
    "demo/station_gap_batch_20261028/coverage-v12/"
    "wastecup-function-mapping-v1/report.json"
)
INSPECTION_BATCH = ROOT / (
    "demo/station_gap_batch_20261028/wastecup-base-pose-rechecks-v1/"
    "batch-report.json"
)
CASES = [
    {
        "source": "project02::A300",
        "target": "project01::JJ00",
        "base": "JJ00",
        "token": "A300",
        "request": ROOT / (
            "demo/station_gap_batch_20261028/wastecup-base-pose-rechecks-v1/"
            "p02-a300--p01-jj00/request.json"
        ),
        "expected": {
            "longitudinal": 0.5200824749305753,
            "lateral": 1.211000000000025,
            "supportGap": 0.0,
        },
    },
    {
        "source": "project02::A300",
        "target": "project03::AA00",
        "base": "AA00",
        "token": "A300",
        "request": ROOT / (
            "demo/station_gap_batch_20261028/wastecup-base-pose-rechecks-v1/"
            "p02-a300--p03-aa00/request.json"
        ),
        "expected": {
            "longitudinal": 1.3962609640453295,
            "lateral": 1.0122967191213309,
            "supportGap": 0.0,
        },
    },
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


@pytest.fixture
def evidence_dir():
    path = ROOT / ".codex-artifacts" / "pytest-wastecup-candidate" / uuid.uuid4().hex
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _materialize_state(case: dict, evidence_dir: Path, *, target_fixed=False):
    evidence_dir.mkdir(parents=True, exist_ok=True)
    original = json.loads(case["request"].read_text(encoding="utf-8"))
    cad_path = ROOT / original["cadResult"]["path"]
    cad = json.loads(cad_path.read_text(encoding="utf-8"))
    graph_path = Path(cad["executionEffectiveGraphPath"])
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    base_graph = next(
        row for row in graph["Modules"] if row["ModuleToken"] == case["base"]
    )
    state_path = evidence_dir / "reopened-state.json"
    process_path = evidence_dir / "inspection-process.json"
    request_path = evidence_dir / "request.json"
    original["outputStatePath"] = str(state_path)
    original["processReportPath"] = str(process_path)
    original["requestDigest"] = _digest(original)
    request_path.write_text(json.dumps(original, indent=2), encoding="utf-8")
    state = {
        "schemaVersion": "p000-support-position-readonly-state/v1",
        "success": True,
        "assemblyPath": cad["outputAssemblyPath"],
        "assemblySha256": cad["outputAssemblySha256"],
        "checks": {
            "expectedTopLevelComponentCount": True,
            "onlyBaseFixed": True,
            "threeActiveMates": True,
            "matesHaveNoErrors": True,
            "outputFileUnchanged": True,
        },
        "observed": {
            "readOnly": True,
            "components": [
                {
                    "name": f"FL_TEST_{case['base']}.001-1",
                    "sourcePath": f"FL_TEST_{case['base']}.001.SLDASM",
                    "isFixed": True,
                    "constrainedStatus": 3,
                    "transform": base_graph["SourceTransform"],
                },
                {
                    "name": cad["toolResult"]["InsertedComponentName"],
                    "sourcePath": cad["toolResult"]["TargetModuleSourcePath"],
                    "isFixed": target_fixed,
                    "constrainedStatus": 3,
                    "transform": cad["toolResult"]["ReopenedTargetRootTransform"],
                },
            ],
        },
    }
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return request_path, state_path


@pytest.mark.parametrize("case", CASES)
def test_selected_mapping_becomes_review_only_distance_candidate(case, evidence_dir):
    request, state = _materialize_state(case, evidence_dir)
    result = build_wastecup_station_candidate(
        ROOT,
        mapping_config_path=MAPPING_CONFIG,
        mapping_report_path=MAPPING_REPORT,
        inspection_request_path=request,
        saved_state_path=state,
        source_module_definition_id=case["source"],
        target_base_definition_id=case["target"],
    )
    assert result["schemaVersion"] == "wastecup-station-candidate/v1"
    assert result["status"] == "review_candidate_requires_fresh_nonprototype_cad"
    assert result["cadLaunchAllowed"] is False
    assert result["freshNonPrototypeCadRequired"] is True
    assert result["sourceWorldPoseCopied"] is False
    assert result["prototypeExecutionPoseUsed"] is False
    assert result["functionalMappingCheck"][
        "allTargetPointsInsideMeasuredOpenings"
    ] is True
    assert result["distanceFlipDimensions"] == {
        "longitudinal": False,
        "lateral": False,
        "supportGap": False,
    }
    assert result["positionParametersMeters"] == pytest.approx(case["expected"])
    assert len(result["candidateDigest"]) == 64


def test_completed_inspection_binding_is_reusable_but_cannot_be_replanned(evidence_dir):
    request, _ = _materialize_state(CASES[0], evidence_dir)
    binding = authenticate_saved_output_station_inspection_binding(ROOT, request)
    assert binding["readOnly"] is True
    with pytest.raises(FileExistsError, match="already exists"):
        build_saved_output_station_inspection_plan(ROOT, request)


def test_fixed_target_and_changed_mapping_report_fail_closed(evidence_dir):
    request, state = _materialize_state(CASES[0], evidence_dir, target_fixed=True)
    with pytest.raises(ValueError, match="only the target base may be fixed"):
        build_wastecup_station_candidate(
            ROOT,
            mapping_config_path=MAPPING_CONFIG,
            mapping_report_path=MAPPING_REPORT,
            inspection_request_path=request,
            saved_state_path=state,
            source_module_definition_id=CASES[0]["source"],
            target_base_definition_id=CASES[0]["target"],
        )

    request, state = _materialize_state(CASES[0], evidence_dir / "stale")
    stale = evidence_dir / "stale-report.json"
    report = json.loads(MAPPING_REPORT.read_text(encoding="utf-8"))
    report["candidates"][0]["mappingDecision"]["selected"]["screening"][
        "commonPlanarTranslationBaseLocalMeters"
    ][0] += 0.001
    stale.write_text(json.dumps(report, indent=2), encoding="utf-8")
    with pytest.raises(ValueError, match="stale or changed"):
        build_wastecup_station_candidate(
            ROOT,
            mapping_config_path=MAPPING_CONFIG,
            mapping_report_path=stale,
            inspection_request_path=request,
            saved_state_path=state,
            source_module_definition_id=CASES[0]["source"],
            target_base_definition_id=CASES[0]["target"],
        )


def test_real_batch_waits_for_two_readonly_states_without_launching_cad():
    result = build_wastecup_station_candidate_batch(
        ROOT,
        mapping_config_path=MAPPING_CONFIG,
        mapping_report_path=MAPPING_REPORT,
        inspection_batch_path=INSPECTION_BATCH,
    )
    assert result["summary"] == {
        "pairCount": 2,
        "pendingSavedOutputInspectionCount": 2,
        "candidateReadyCount": 0,
    }
    assert result["cadStarted"] is False
    assert result["relationPublished"] is False
    unsigned = dict(result)
    digest = unsigned.pop("candidateDigest")
    assert digest == hashlib.sha256(
        json.dumps(
            unsigned,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    assert all(
        row["status"] == "pending_saved_output_inspection"
        and row["candidatePayload"] is None
        and "verify_datum_chain_live_state.py"
        in " ".join(row["readOnlyInspectionCommand"])
        for row in result["rows"]
    )


def test_materialized_batch_digest_covers_exact_written_payload(evidence_dir):
    output = evidence_dir / "batch"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/build_wastecup_station_candidate_batch.py"),
            "--mapping-config",
            str(MAPPING_CONFIG),
            "--mapping-report",
            str(MAPPING_REPORT),
            "--inspection-batch",
            str(INSPECTION_BATCH),
            "--output-dir",
            str(output),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads((output / "batch-report.json").read_text(encoding="utf-8"))
    stored = payload.pop("candidateDigest")
    actual = hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    assert stored == actual
