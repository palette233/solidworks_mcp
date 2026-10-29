import copy
import hashlib
import json
from pathlib import Path

import pytest

from demo_backend.scanner_transport_binding_queue import (
    apply_scanner_saved_context_inventory,
    SELECTION_SCHEMA,
    apply_scanner_current_context_evaluations,
    build_scanner_transport_binding_review_queue,
    compile_scanner_transport_binding_selections,
)


ROOT = Path(__file__).resolve().parents[3]
GAP = ROOT / "demo/station_gap_batch_20261028/coverage-v6/gap-batch-v13/gap-queue.json"
COVERAGE = ROOT / "demo/station_gap_batch_20261028/coverage-v6/coverage.json"
MEASUREMENTS = ROOT / "data/assembly_stations/measurement-reuse-index-v5.json"
LATEST_GAP = ROOT / "demo/station_gap_batch_20261028/coverage-v13/gap-batch-v27/gap-queue.json"
LATEST_COVERAGE = ROOT / "demo/station_gap_batch_20261028/coverage-v13/coverage.json"
CURRENT_CONTEXT = ROOT / "demo/station_gap_batch_20261028/coverage-v13/scanner-a180-a800-a600-current-context-v2.json"


def _read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _digest(value):
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _queue():
    return build_scanner_transport_binding_review_queue(
        _read(GAP), _read(COVERAGE), _read(MEASUREMENTS)
    )


def _inventory(queue, *, exact_key=None):
    rows = []
    for candidate in queue["candidates"]:
        key = (
            candidate["sourceModuleDefinitionId"],
            candidate["transportModuleDefinitionId"],
            candidate["targetBaseDefinitionId"],
        )
        exact = key == exact_key
        rows.append(
            {
                "sourceModuleDefinitionId": key[0],
                "transportModuleDefinitionId": key[1],
                "targetBaseDefinitionId": key[2],
                "status": (
                    "exact_saved_context_available"
                    if exact
                    else "new_cumulative_chain_context_required"
                ),
                "savedContexts": (
                    [
                        {
                            "statePath": "demo/state.json",
                            "stateSha256": "a" * 64,
                        }
                    ]
                    if exact
                    else []
                ),
            }
        )
    core = {
        "schemaVersion": "scanner-saved-context-inventory/v1",
        "reviewQueue": {"queueDigest": queue["queueDigest"]},
        "summary": {},
        "candidates": rows,
    }
    return {**core, "inventoryDigest": _digest(core)}


def test_saved_context_inventory_refines_next_action_without_cad_authority():
    queue = _queue()
    first = queue["candidates"][0]
    exact_key = (
        first["sourceModuleDefinitionId"],
        first["transportModuleDefinitionId"],
        first["targetBaseDefinitionId"],
    )
    result = apply_scanner_saved_context_inventory(
        queue, _inventory(queue, exact_key=exact_key)
    )

    assert result["summary"]["exactSavedContextAvailableCount"] == 1
    assert result["summary"]["newCumulativeChainContextRequiredCount"] == 13
    exact = next(
        row
        for row in result["candidates"]
        if row["sourceModuleDefinitionId"] == exact_key[0]
        and row["targetBaseDefinitionId"] == exact_key[2]
    )
    assert (
        exact["status"]
        == "exact_saved_context_available_requires_geometry_evaluation"
    )
    assert exact["cadLaunchAllowed"] is False


def test_saved_context_inventory_preserves_stronger_geometry_result():
    queue = _queue()
    first = queue["candidates"][0]
    first["status"] = "current_context_point_pair_geometry_mismatch"
    first["currentContextEvaluation"] = {"processProxyValidationPassed": False}
    first["candidateDigest"] = _digest(
        {key: value for key, value in first.items() if key != "candidateDigest"}
    )
    queue_core = {key: value for key, value in queue.items() if key != "queueDigest"}
    queue["queueDigest"] = _digest(queue_core)
    result = apply_scanner_saved_context_inventory(queue, _inventory(queue))

    preserved = result["candidates"][0]
    assert preserved["status"] == "current_context_point_pair_geometry_mismatch"
    assert "savedContextInventory" not in preserved


def test_all_current_scanner_gaps_get_one_exact_validated_transport_context():
    result = _queue()
    assert result["summary"] == {
        "scannerGapCount": 14,
        "candidateCount": 14,
        "blockedGapCount": 0,
        "confirmedSelectionCount": 0,
    }
    assert result["cadStarted"] is False
    assert all(row["selectionTemplate"]["confirmed"] is False
               for row in result["candidates"])
    assert all(row["cadLaunchAllowed"] is False
               for row in result["candidates"])
    a600 = [row for row in result["candidates"]
            if row["targetBaseDefinitionId"] == "project02::A600"]
    assert {row["transportModuleDefinitionId"] for row in a600} == {
        "project02::A800"
    }
    aa00 = [row for row in result["candidates"]
            if row["targetBaseDefinitionId"] == "project03::AA00"]
    assert {row["transportModuleDefinitionId"] for row in aa00} == {
        "project01::SS00"
    }


def test_latest_exact_instance_gap_category_builds_same_fail_closed_review_queue():
    result = build_scanner_transport_binding_review_queue(
        _read(LATEST_GAP), _read(LATEST_COVERAGE), _read(MEASUREMENTS)
    )
    assert result["summary"] == {
        "scannerGapCount": 14,
        "candidateCount": 14,
        "blockedGapCount": 0,
        "confirmedSelectionCount": 0,
    }
    assert result["status"] == "ready_for_chain_instance_selection"
    assert result["cadStarted"] is False
    assert all(
        row["status"] == "ready_for_exact_chain_instance_selection"
        and row["cadLaunchAllowed"] is False
        and row["prototypePoseAllowedAsCadExecutionAuthority"] is False
        for row in result["candidates"]
    )


def test_missing_validated_transport_or_source_measurement_fails_closed():
    coverage = _read(COVERAGE)
    changed = copy.deepcopy(coverage)
    for row in changed["pairs"]:
        if row.get("role") == "Transport" and row.get("targetBaseDefinitionId") == "project02::A600":
            row["validatedStationRule"] = False
    result = build_scanner_transport_binding_review_queue(
        _read(GAP), changed, _read(MEASUREMENTS)
    )
    assert result["summary"]["candidateCount"] == 10
    assert result["summary"]["blockedGapCount"] == 4
    assert all("VALIDATED_TRANSPORT_STATION_MISSING" in row["blockingReasonCodes"]
               for row in result["blocked"])


def test_explicit_unique_instance_selection_compiles_without_cad():
    queue = _queue()
    candidate = next(
        row for row in queue["candidates"]
        if row["sourceModuleDefinitionId"] == "project01::SM00"
        and row["targetBaseDefinitionId"] == "project02::A600"
    )
    selections = {
        "schemaVersion": SELECTION_SCHEMA,
        "sourceQueueDigest": queue["queueDigest"],
        "selections": [{
            "candidateDigest": candidate["candidateDigest"],
            "confirmed": True,
            "scannerInstanceId": "SM00-1",
            "transportInstanceId": "A800-1",
            "targetBaseInstanceId": "A600-1",
            "confirmedBy": "test-engineer",
            "confirmedAt": "2026-10-28T20:00:00+08:00",
        }],
    }
    result = compile_scanner_transport_binding_selections(queue, selections)
    assert result["decisionCount"] == 1
    assert result["cadStarted"] is False
    decision = result["decisions"][0]
    assert decision["transportModuleDefinitionId"] == "project02::A800"
    assert decision["transportInstanceId"] == "A800-1"
    assert decision["status"] == "ready_for_saved_context_scanner_target_materialization"


def test_selection_rejects_unconfirmed_duplicate_instances_or_stale_queue():
    queue = _queue()
    candidate = queue["candidates"][0]
    base = {
        "schemaVersion": SELECTION_SCHEMA,
        "sourceQueueDigest": queue["queueDigest"],
        "selections": [{
            "candidateDigest": candidate["candidateDigest"],
            "confirmed": False,
            "scannerInstanceId": "scanner-1",
            "transportInstanceId": "transport-1",
            "targetBaseInstanceId": "base-1",
            "confirmedBy": "test-engineer",
            "confirmedAt": "2026-10-28T20:00:00+08:00",
        }],
    }
    with pytest.raises(ValueError, match="not confirmed"):
        compile_scanner_transport_binding_selections(queue, base)
    duplicate = copy.deepcopy(base)
    duplicate["selections"][0]["confirmed"] = True
    duplicate["selections"][0]["transportInstanceId"] = "scanner-1"
    with pytest.raises(ValueError, match="must be unique"):
        compile_scanner_transport_binding_selections(queue, duplicate)
    stale = copy.deepcopy(queue)
    stale["candidates"][0]["status"] = "tampered"
    confirmed = copy.deepcopy(base)
    confirmed["selections"][0]["confirmed"] = True
    with pytest.raises(ValueError, match="queue digest mismatch"):
        compile_scanner_transport_binding_selections(stale, confirmed)


def test_current_context_evaluation_refines_only_the_exact_scanner_pair():
    queue = build_scanner_transport_binding_review_queue(
        _read(LATEST_GAP), _read(LATEST_COVERAGE), _read(MEASUREMENTS)
    )
    evaluation = _read(CURRENT_CONTEXT)
    result = apply_scanner_current_context_evaluations(
        queue,
        [evaluation],
        evidence=[{"path": "evaluation.json", "sha256": "1" * 64}],
    )
    assert result["summary"]["currentContextEvaluationCount"] == 1
    assert result["summary"]["currentContextGeometryMismatchCount"] == 1
    changed = [
        row
        for row in result["candidates"]
        if row["status"] == "current_context_point_pair_geometry_mismatch"
    ]
    assert len(changed) == 1
    assert changed[0]["sourceModuleDefinitionId"] == "project02::A180"
    assert changed[0]["transportModuleDefinitionId"] == "project02::A800"
    assert changed[0]["targetBaseDefinitionId"] == "project02::A600"
    assert changed[0]["cadLaunchAllowed"] is False
    assert changed[0]["currentContextEvaluation"][
        "processProxyValidationPassed"
    ] is False
    assert sum(
        row["status"] == "ready_for_exact_chain_instance_selection"
        for row in result["candidates"]
    ) == 13

    tampered = copy.deepcopy(evaluation)
    tampered["geometry"]["crossTrackErrorMeters"] = 0
    with pytest.raises(ValueError, match="digest mismatch"):
        apply_scanner_current_context_evaluations(
            queue,
            [tampered],
            evidence=[{"path": "evaluation.json", "sha256": "1" * 64}],
        )
