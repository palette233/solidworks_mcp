import json
from pathlib import Path

import pytest

from demo_backend.cross_project_scanner_alternate_route import (
    CrossProjectScannerAlternateRouteError,
    build_scanner_alternate_route_evaluation,
)


ROOT = Path(__file__).resolve().parents[3]
CASE = (
    ROOT
    / "demo/cross_project_substitution/scanner-slot-discovery-v1/"
    "project01_JJ00_project03_AI00"
)


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _build(**kwargs) -> dict:
    return build_scanner_alternate_route_evaluation(
        discovery=_json(CASE / "scanner_slot_discovery.json"),
        endpoint_recovery=_json(CASE / "endpoint_recovery_evidence.json"),
        source_face_catalog=_json(
            ROOT
            / "demo/semantic_ports/project03_AI00_third_increment_v1/"
            "face_endpoint_catalog.json"
        ),
        target_face_catalog=_json(
            CASE / "jj00-scanner-support-leaf-face-catalog.json"
        ),
        source_graph=_json(
            ROOT
            / "demo/global_assembly_contexts/manifest_jobs/"
            "project-global-job-f0aa2d732403/packet-runs/packet-003-attempt-01/"
            "execution-effective-mate-graph.json"
        ),
        prior_process_evidence=_json(
            ROOT
            / "demo/cross_project_substitution/cumulative-project03-v2/"
            "scanner-transport-process-validation.json"
        ),
        source_support_endpoint_id="face:fl9a24d063ai00:916bba1ff4ce84b0",
        source_hole_endpoint_ids=[
            "face:fl9a24d063ai00:90a1d02db6e9d829",
            "face:fl9a24d063ai00:aa9f3e759104cfd0",
        ],
        **kwargs,
    )


def test_real_alternate_route_solves_mechanical_pose_but_rejects_process_proxy():
    report = _build()

    assert report["schemaVersion"] == (
        "cross-project-scanner-alternate-route-evaluation/v1"
    )
    assert report["candidatePoseTransformSolved"] is True
    assert report["processProxyValidationPassed"] is False
    assert report["status"] == "blocked_process_proxy_mismatch"
    assert report["cadLaunchAllowed"] is False
    assert report["semanticPortPublished"] is False
    assert report["evaluatedPoseCount"] >= 12


def test_real_alternate_route_residuals_are_not_confused_with_hole_depth():
    report = _build()
    selected = report["selectedCandidate"]

    assert selected["mechanicalChecks"]["passed"] is True
    assert selected["mechanicalChecks"]["supportPlaneResidualMeters"] < 1e-9
    assert max(
        selected["mechanicalChecks"]["locatingAxisPerpendicularResidualMeters"]
    ) < 1e-9
    assert selected["processProxyChecks"]["crossTrackErrorMeters"] > 0.04
    assert selected["processProxyChecks"]["crossTrackPassed"] is False


def test_candidate_output_is_deterministic():
    assert _build()["evaluationDigest"] == _build()["evaluationDigest"]


def test_legacy_unbound_calculation_is_not_associated_or_cad_evidence():
    report = _build()
    assert report["processCandidateReady"] is False
    assert report["targetAssociationCheck"]["blockingReasonCodes"] == ["SCANNER_TARGET_ASSOCIATION_REQUIRED"]
    assert report["calculationEvidence"]["performed"] is True
    assert report["cadEvidence"]["performed"] is False
    assert report["cadEvidence"]["savedReopened"] is None
    assert report["measuredScanSuccess"] is False


@pytest.mark.parametrize("value", [0, -0.001, 0.05, float("nan"), float("inf"), True])
def test_cross_track_acceptance_cannot_be_relaxed_or_invalid(value):
    with pytest.raises(CrossProjectScannerAlternateRouteError, match="tolerance"):
        _build(cross_track_tolerance_meters=value)


def test_mechanical_acceptance_cannot_be_relaxed():
    with pytest.raises(CrossProjectScannerAlternateRouteError, match="tolerance"):
        _build(mechanical_residual_tolerance_meters=0.01)
