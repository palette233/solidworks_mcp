import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from demo_backend.scanner_point_pair_binding import (
    build_scanner_point_pair_report,
    derive_scanner_cross_track_translation_candidate,
    evaluate_scanner_point_pair_in_saved_context,
)


ROOT = Path(__file__).resolve().parents[3]
RULE = ROOT / "data/assembly_stations/scanner-a180-a800-a600-point-pair-v1.json"
MEASUREMENT = ROOT / "demo/layout_previews/project02_scanner_barcode_points.json"
STATE = ROOT / "demo/cross_project_substitution/wastecup-project05-to-project02-v1/support-position-chain-v3/read-only-chain-verification.json"


def _read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _args():
    state = _read(STATE)
    return {
        "rule": _read(RULE),
        "measurement": _read(MEASUREMENT),
        "saved_state": state,
        "state_path": str(STATE),
        "state_sha256": _sha(STATE),
        "assembly_sha256": state["assemblySha256"],
    }


def _apply_common_world_transform(transform, common):
    """Compose a saved row-vector rigid transform with one world transform."""

    result = [0.0] * 16
    for row in range(3):
        for column in range(3):
            result[3 * row + column] = sum(
                transform[3 * row + index] * common[3 * index + column]
                for index in range(3)
            )
    for column in range(3):
        result[9 + column] = (
            sum(
                transform[9 + index] * common[3 * index + column]
                for index in range(3)
            )
            + common[9 + column]
        )
    result[12:16] = [1.0, 0.0, 0.0, 0.0]
    return result


def test_real_project02_saved_context_binds_exact_transport_and_reports_mismatch():
    report = build_scanner_point_pair_report(
        rule_path=RULE, measurement_path=MEASUREMENT, state_path=STATE
    )
    assert report["targetAssociationBound"] is True
    assert report["instances"] == {
        "scanner": "FL9A24D062A180.001-1",
        "transport": "FL9A24D062A800.001-1",
        "targetBase": "FL9A24D062A600.001-1",
    }
    assert report["geometry"]["requiredWorkingDistanceMeters"] == pytest.approx(
        0.1205750000042018
    )
    assert report["geometry"]["crossTrackErrorMeters"] == pytest.approx(
        0.04015440188733746
    )
    assert report["processProxyValidationPassed"] is False
    assert report["blockingReasonCodes"] == [
        "OPTICAL_AXIS_MISSES_CURRENT_BARCODE_TARGET_PROXY"
    ]
    assert report["mechanicalPlacementChanged"] is False
    assert report["cadExecuted"] is False
    assert report["measuredScanSuccess"] is False


def test_common_rigid_motion_preserves_current_point_pair_metrics():
    baseline = evaluate_scanner_point_pair_in_saved_context(**_args())
    changed = _args()
    state = copy.deepcopy(changed["saved_state"])
    rigid = [0, 1, 0, -1, 0, 0, 0, 0, 1, 0.5, 0.6, 0.7, 1, 0, 0, 0]
    for row in state["observed"]["components"]:
        if any(token in row["name"] for token in ("A180", "A800", "A600")):
            row["transform"] = _apply_common_world_transform(row["transform"], rigid)
    changed["saved_state"] = state
    result = evaluate_scanner_point_pair_in_saved_context(**changed)
    assert result["geometry"]["requiredWorkingDistanceMeters"] == pytest.approx(
        baseline["geometry"]["requiredWorkingDistanceMeters"]
    )
    assert result["geometry"]["crossTrackErrorMeters"] == pytest.approx(
        baseline["geometry"]["crossTrackErrorMeters"]
    )


def test_exact_instance_selectors_resolve_duplicates_and_reject_wrong_names():
    args = _args()
    scanner = next(
        row
        for row in args["saved_state"]["observed"]["components"]
        if "A180" in row["name"]
    )
    duplicate = copy.deepcopy(scanner)
    duplicate["name"] = "FL9A24D062A180.001-2"
    args["saved_state"]["observed"]["components"].append(duplicate)
    report = evaluate_scanner_point_pair_in_saved_context(
        **args,
        instance_selectors={
            "scanner": scanner["name"],
            "transport": "FL9A24D062A800.001-1",
            "targetBase": "FL9A24D062A600.001-1",
        },
    )
    assert report["instances"]["scanner"] == scanner["name"]
    with pytest.raises(ValueError, match="exactly one saved component"):
        evaluate_scanner_point_pair_in_saved_context(
            **args,
            instance_selectors={"scanner": "not-the-bound-instance"},
        )


def test_current_mismatch_derives_smallest_review_only_translation_candidate():
    evaluation = build_scanner_point_pair_report(
        rule_path=RULE, measurement_path=MEASUREMENT, state_path=STATE
    )
    candidate = derive_scanner_cross_track_translation_candidate(evaluation)
    assert candidate["status"] == "candidate_requires_mechanical_interface_review"
    assert candidate["recommendedScannerTranslationDeltaWorldMeters"] == pytest.approx(
        [0.00659872799921495, 0.0, 0.03960849378254856], abs=1e-12
    )
    assert candidate[
        "recommendedScannerTranslationDeltaInTargetBaseMeters"
    ] == pytest.approx(candidate["recommendedScannerTranslationDeltaWorldMeters"])
    assert candidate["translationMagnitudeMeters"] == pytest.approx(
        evaluation["geometry"]["crossTrackErrorMeters"]
    )
    assert candidate["predictedCrossTrackErrorMeters"] == pytest.approx(
        0.0, abs=1e-12
    )
    assert candidate["cadLaunchAllowed"] is False
    assert candidate["prototypePoseAllowedAsExecutionAuthority"] is False

    tampered = copy.deepcopy(evaluation)
    tampered["geometry"]["barcodeTargetWorldMeters"][0] += 0.01
    with pytest.raises(ValueError, match="digest mismatch"):
        derive_scanner_cross_track_translation_candidate(tampered)


@pytest.mark.parametrize(
    "change,pattern",
    [
        ("missing_target", "exactly one saved component"),
        ("duplicate_target", "exactly one saved component"),
        ("bad_transform", "proper rigid"),
        ("not_readonly", "read-only"),
        ("wrong_assembly_hash", "assembly digest"),
        ("missing_face_reference", "persistent face reference"),
    ],
)
def test_saved_context_binding_fails_closed(change, pattern):
    args = _args()
    if change == "missing_target":
        args["saved_state"]["observed"]["components"] = [
            row
            for row in args["saved_state"]["observed"]["components"]
            if "A800" not in row["name"]
        ]
    elif change == "duplicate_target":
        target = next(
            row
            for row in args["saved_state"]["observed"]["components"]
            if "A800" in row["name"]
        )
        args["saved_state"]["observed"]["components"].append(copy.deepcopy(target))
    elif change == "bad_transform":
        transform = next(
            row
            for row in args["saved_state"]["observed"]["components"]
            if "A180" in row["name"]
        )["transform"]
        transform[0:3] = [-value for value in transform[0:3]]
    elif change == "not_readonly":
        args["saved_state"]["observed"]["readOnly"] = False
    elif change == "wrong_assembly_hash":
        args["assembly_sha256"] = "0" * 64
    elif change == "missing_face_reference":
        args["measurement"]["entries"]["barcode"]["persistentReferenceBase64"] = None
    with pytest.raises(ValueError, match=pattern):
        evaluate_scanner_point_pair_in_saved_context(**args)


def test_cli_writes_new_evidence_and_refuses_overwrite(tmp_path):
    output = tmp_path / "evaluation.json"
    command = [
        sys.executable,
        str(ROOT / "scripts/build_scanner_point_pair_current_context.py"),
        "--rule",
        str(RULE),
        "--measurement",
        str(MEASUREMENT),
        "--state",
        str(STATE),
        "--output",
        str(output),
    ]
    subprocess.run(command, check=True, capture_output=True)
    assert _read(output)["targetAssociationBound"] is True
    assert subprocess.run(command, capture_output=True).returncode != 0
