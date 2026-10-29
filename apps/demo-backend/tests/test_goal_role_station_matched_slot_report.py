import hashlib
import json
from pathlib import Path

import pytest

from demo_backend.goal_role_station_matched_slot_report import (
    STATION_CHECKS,
    _positive_case,
    build_goal_report,
    validate_role_station_witness,
    write_goal_artifacts,
)


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_goal_report_binds_required_positive_negative_and_cumulative_evidence() -> None:
    report = build_goal_report(REPO_ROOT)

    assert report["goalStatus"] == "INCOMPLETE"
    assert report["cadEvidenceStatus"] == "PASSED"
    assert report["summary"]["positiveCadClosureCount"] >= 5
    assert len(report["summary"]["positiveRoles"]) >= 3
    assert len(report["summary"]["targetBases"]) >= 3
    assert report["summary"]["cumulativeAssemblyPassCount"] >= 2
    assert report["summary"]["correctlyBlockedNegativeCount"] >= 2
    assert all(report["cadAcceptance"].values())
    assert report["acceptance"]["allPositiveStationChecksPassed"] is False
    assert report["acceptance"]["allPositiveReleasesAvailable"] is False
    assert report["acceptance"]["cumulativeStationContextValidated"] is False
    assert report["summary"]["stationValidatedCount"] == 0
    assert report["summary"]["stationReuseReadyCount"] == 0

    gn00 = next(row for row in report["positiveCases"] if row["caseId"] == "B8-GN00-AA00")
    assert gn00["classification"] == "CAD_POSITIONING_PASS"
    assert gn00["historicalClassification"] == "MATCHED_ALTERNATE_SLOT_PASS"
    assert gn00["cadPositioningPassed"] is True
    assert gn00["stationValidationPassed"] is None
    assert gn00["releaseAvailability"] == "not_available"
    assert gn00["reuseReady"] is False
    assert gn00["layoutGate"]["slotMembership"] is None
    assert gn00["layoutGate"]["transportContext"] is None
    assert gn00["createdMateCount"] == 3
    assert gn00["checks"]["noCaseAnchor"] is True
    assert gn00["checks"]["noLeafPoseAnchors"] is True
    assert gn00["checks"]["saveCloseReopenPassed"] is True

    n000 = next(row for row in report["negativeCases"] if row["caseId"].startswith("A5-"))
    assert n000["classification"] == "REVIEW_REQUIRED"
    assert n000["blockedBeforeCad"] is True
    assert n000["runtimeCandidateReuseBlocked"] is True
    assert n000["forbiddenFallback"]["longitudinalMeters"] == 0.465

    scanner = next(row for row in report["negativeCases"] if row["caseId"].startswith("B9-"))
    assert scanner["classification"] == "GEOMETRIC_MATCH_PASS_PROCESS_PROXY_FAIL"
    assert scanner["realCadExecuted"] is False
    assert scanner["actualBarcodeReadabilityVerified"] is False
    assert scanner["mechanicalChecks"]["passed"] is True
    assert scanner["processProxyChecks"]["passed"] is False


def test_goal_report_writes_unified_artifacts(tmp_path: Path) -> None:
    paths = write_goal_artifacts(REPO_ROOT, tmp_path)

    assert set(paths) == {"summary", "compatibility", "evidence", "timings", "markdown"}
    assert all(path.is_file() for path in paths.values())
    markdown = paths["markdown"].read_text(encoding="utf-8")
    assert "正向真实 CAD 闭环：**7** 项" in markdown
    assert "N000→A600" in markdown
    assert "GN00→AA00" in markdown
    assert "碰撞/B-rep" in markdown
    assert "INCOMPLETE" in markdown
    assert "待补证据：**7**" in markdown
    assert "预设通过值" in markdown
    timing = json.loads(paths["timings"].read_text(encoding="utf-8"))
    assert timing["reportGeneration"]["cadExecutedDuringReport"] is False
    assert timing["reportGeneration"]["durationSeconds"] >= 0


def _write(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def station_fixture(tmp_path: Path) -> tuple[dict, Path, dict]:
    graph_path = _write(tmp_path / "graph.json", {
        "EditPolicy": {"fixedModuleTokens": ["BASE"], "initialPlacementMode": "deterministic-v1"},
    })
    output = tmp_path / "output.SLDASM"
    output.write_bytes(b"test-output-only")
    tool = {
        "RequestedMateCount": 3, "CreatedMateCount": 3, "Success": True,
        "IndependentComponentInserted": True,
        "Diagnostics": ["Deterministic non-source placement"],
        "TargetCaseAnchored": False, "AppliedTargetLeafPoseAnchorCount": 0,
        "TargetConstraintStateAccepted": True, "TargetFullyConstrained": True,
        "MateSolveClean": True, "Reopened": True, "ReopenedMateParametersMatch": True,
        "TargetModuleToken": "MODULE",
    }
    cad_path = _write(tmp_path / "cad.json", {
        "success": True, "toolResult": tool, "outputClosedAfterVerification": True,
        "sourceAssemblyUnchanged": True, "targetSourceSessionClean": True,
        "effectiveGraphPath": str(graph_path), "outputAssemblyPath": str(output),
        "effectiveGraphSha256": _digest(graph_path), "outputAssemblySha256": _digest(output),
        "durationSeconds": 1.0,
    })
    _write(tmp_path / "release.json", {
        "status": "released_for_demo_relation_execution",
        "validationEvidence": [{"passed": True}],
    })
    evidence_path = _write(tmp_path / "measurement.json", {"testFixtureOnly": True})
    spec = {
        "caseId": "test-module-base", "source": "project01::MODULE", "target": "project03::BASE",
        "role": "CleaningWeighing", "route": "native_role_station", "classification": "HISTORIC_PASS",
        "cad": "cad.json", "release": "release.json",
    }
    witness = {
        "schemaVersion": "role-station-witness/v1", "caseId": spec["caseId"],
        "source": spec["source"], "target": spec["target"],
        "cadResultSha256": _digest(cad_path), "effectiveGraphSha256": _digest(graph_path),
        "checks": {name: {
            "passed": True, "status": "passed", "method": "test_measurement",
            "evidence": [{"path": str(evidence_path), "sha256": _digest(evidence_path)}],
            "observations": {"testFixtureOnly": True},
        } for name in STATION_CHECKS},
    }
    return spec, tmp_path / "station.json", witness


def test_missing_station_witness_never_infers_layout_pass(tmp_path: Path, station_fixture: tuple) -> None:
    spec, _, _ = station_fixture
    row = _positive_case(tmp_path, spec)
    assert row["cadPositioningPassed"] is True
    assert row["stationValidationPassed"] is None
    assert row["reuseReady"] is False
    assert all(row["layoutGate"][key] is None for key in STATION_CHECKS)


def test_bound_complete_station_witness_can_mark_station_reuse_ready(tmp_path: Path, station_fixture: tuple) -> None:
    spec, path, witness = station_fixture
    row = _positive_case(tmp_path, spec, _write(path, witness))
    assert row["stationEvidence"]["bindingVerified"] is True
    assert row["stationValidationPassed"] is True
    assert row["reuseReady"] is True


def test_complete_station_but_missing_release_is_not_reusable(tmp_path: Path, station_fixture: tuple) -> None:
    spec, path, witness = station_fixture
    spec["release"] = None
    row = _positive_case(tmp_path, spec, _write(path, witness))
    assert row["cadPositioningPassed"] is True
    assert row["stationValidationPassed"] is True
    assert row["status"] == "station_validated_unreleased"
    assert row["reuseReady"] is False


def test_missing_release_file_does_not_erase_historical_cad_success(tmp_path: Path, station_fixture: tuple) -> None:
    spec, path, witness = station_fixture
    spec["release"] = "absent-release.json"
    row = _positive_case(tmp_path, spec, _write(path, witness))
    assert row["cadPositioningPassed"] is True
    assert row["releaseAvailability"] == "not_available"
    assert row["reuseReady"] is False


@pytest.mark.parametrize("field", ["caseId", "source", "target", "cadResultSha256", "effectiveGraphSha256"])
def test_wrong_witness_binding_is_rejected(tmp_path: Path, station_fixture: tuple, field: str) -> None:
    spec, path, witness = station_fixture
    witness[field] = "tampered"
    row = _positive_case(tmp_path, spec, _write(path, witness))
    assert row["cadPositioningPassed"] is True
    assert row["stationEvidence"]["status"] == "invalid_evidence"
    assert f"binding_mismatch:{field}" in row["stationEvidence"]["validationErrors"]
    assert row["reuseReady"] is False


def test_station_check_failure_preserves_cad_success(tmp_path: Path, station_fixture: tuple) -> None:
    spec, path, witness = station_fixture
    witness["checks"]["slotMembership"].update(passed=False, status="failed")
    row = _positive_case(tmp_path, spec, _write(path, witness))
    assert row["cadPositioningPassed"] is True
    assert row["stationValidationPassed"] is False
    assert row["layoutGate"]["slotMembership"] is False
    assert row["status"] == "cad_passed_station_failed"


def test_partial_station_measurement_is_not_complete(tmp_path: Path, station_fixture: tuple) -> None:
    spec, path, witness = station_fixture
    witness["checks"]["transportContext"].update(passed=None, status="not_evaluated", evidence=[])
    row = _positive_case(tmp_path, spec, _write(path, witness))
    assert row["stationEvidence"]["status"] == "partially_evaluated"
    assert row["stationValidationPassed"] is None
    assert row["reuseReady"] is False


def test_review_required_measurement_does_not_promote_subcheck_to_failure(tmp_path: Path, station_fixture: tuple) -> None:
    spec, path, witness = station_fixture
    witness["checks"]["supportAndDirectionBound"].update(
        passed=None, status="review_required",
        observations={"fullEnvelopeVsSupportFaceOuterBound": False},
    )
    row = _positive_case(tmp_path, spec, _write(path, witness))
    assert row["stationEvidence"]["bindingVerified"] is True
    assert row["stationValidationPassed"] is None
    assert row["layoutGate"]["supportAndDirectionBound"] is None
    assert row["reuseReady"] is False


@pytest.mark.parametrize("mutation", ["missing_source", "changed_source", "empty_evidence", "missing_check", "wrong_type", "wrong_status"])
def test_invalid_measurement_sources_and_claims_cannot_pass(tmp_path: Path, station_fixture: tuple, mutation: str) -> None:
    spec, path, witness = station_fixture
    check = witness["checks"]["slotMembership"]
    if mutation == "missing_source":
        check["evidence"][0]["path"] = str(tmp_path / "absent.json")
    elif mutation == "changed_source":
        _write(Path(check["evidence"][0]["path"]), {"changed": True})
    elif mutation == "empty_evidence":
        check["evidence"] = []
    elif mutation == "missing_check":
        del witness["checks"]["slotMembership"]
    elif mutation == "wrong_type":
        check["passed"] = 1
    else:
        check["status"] = "not_evaluated"
    row = _positive_case(tmp_path, spec, _write(path, witness))
    assert row["stationEvidence"]["status"] == "invalid_evidence"
    assert row["stationValidationPassed"] is False
    assert row["reuseReady"] is False


def test_report_rejects_unknown_case_witness() -> None:
    with pytest.raises(ValueError, match="unknown station witness cases"):
        build_goal_report(REPO_ROOT, station_witness_paths={"wrong-case": Path("missing.json")})


def test_public_validator_accepts_hash_bound_inputs_outside_workspace(tmp_path: Path, station_fixture: tuple) -> None:
    spec, path, witness = station_fixture
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    result = validate_role_station_witness(
        workspace, case_id=spec["caseId"], source=spec["source"], target=spec["target"],
        cad_result_path=tmp_path / "cad.json", effective_graph_path=tmp_path / "graph.json",
        witness_path=_write(path, witness),
    )
    assert result["passed"] is True
    assert result["readOnly"] is True
    assert result["cadExecutionAuthorized"] is False


@pytest.mark.parametrize("mutation,expected_error", [
    ("wrong_graph_hash", "cad_execution_graph_digest_mismatch"),
    ("missing_graph_hash", "cad_execution_graph_digest_mismatch"),
    ("missing_graph_file", "cad_execution_graph_missing"),
    ("different_execution_graph", "cad_execution_graph_not_witness_graph"),
    ("output_changed", "cad_output_assembly_digest_mismatch"),
    ("missing_output_hash", "cad_output_assembly_digest_mismatch"),
    ("missing_output_file", "cad_output_assembly_missing"),
    ("wrong_witness_output_hash", "binding_mismatch:outputAssemblySha256"),
])
def test_cad_envelope_current_artifacts_must_match(
    tmp_path: Path, station_fixture: tuple, mutation: str, expected_error: str
) -> None:
    spec, path, witness = station_fixture
    cad_path = tmp_path / "cad.json"
    cad = json.loads(cad_path.read_text(encoding="utf-8"))
    if mutation == "wrong_graph_hash":
        cad["effectiveGraphSha256"] = "0" * 64
    elif mutation == "missing_graph_hash":
        del cad["effectiveGraphSha256"]
    elif mutation == "missing_graph_file":
        cad["executionEffectiveGraphPath"] = str(tmp_path / "missing-execution.json")
    elif mutation == "different_execution_graph":
        other_graph = _write(tmp_path / "other-graph.json", {"different": True})
        cad["executionEffectiveGraphPath"] = str(other_graph)
        cad["executionEffectiveGraphSha256"] = _digest(other_graph)
    elif mutation == "output_changed":
        (tmp_path / "output.SLDASM").write_bytes(b"changed-result")
    elif mutation == "missing_output_hash":
        del cad["outputAssemblySha256"]
    elif mutation == "missing_output_file":
        cad["outputAssemblyPath"] = str(tmp_path / "missing.SLDASM")
    else:
        witness["outputAssemblySha256"] = "0" * 64
    _write(cad_path, cad)
    witness["cadResultSha256"] = _digest(cad_path)
    result = validate_role_station_witness(
        tmp_path, case_id=spec["caseId"], source=spec["source"], target=spec["target"],
        cad_result_path=cad_path, effective_graph_path=tmp_path / "graph.json",
        witness_path=_write(path, witness),
    )
    assert result["status"] == "invalid_evidence"
    assert result["passed"] is False
    assert expected_error in result["validationErrors"]
