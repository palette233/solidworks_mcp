import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

import demo_backend.parameterized_datum_validation_queue as queue_module

from demo_backend.parameterized_datum_validation_queue import (
    _position_parameter_fallback_pairs,
    build_parameterized_datum_validation_queue,
    build_successor_parameterized_datum_validation_queue,
)
from demo_backend.mechanical_interface_contracts import MechanicalInterfaceContractError
from demo_backend.hybrid_plane_axis_slot_selection import (
    build_f000_hybrid_axis_slot_catalog,
    rank_f000_hybrid_axis_candidates,
)
from demo_backend.two_axis_slot_selection import (
    build_two_axis_slot_candidate_catalog,
)
from demo_backend.flexible_calibration_slot_selection import (
    build_g000_flexible_slot_candidate_catalog,
)
from demo_backend.parameterized_datum_placement import (
    load_parameterized_datum_placement_catalog,
)


ROOT = Path(__file__).resolve().parents[3]


def test_position_fallback_pair_is_distinct_from_negative_native_axis_audit():
    catalog = {
        "compatibilityMatrix": [
            {
                "moduleDefinitionId": "project01::SS00",
                "slotDefinitionId": "project02::A600",
                "blockers": [{"code": "POSITION_PARAMETERS_MISSING"}],
            },
            {
                "moduleDefinitionId": "project03::AE00",
                "slotDefinitionId": "project02::A600",
                "blockers": [{"code": "MODULE_POSITION_PRESET_MISSING"}],
            },
            {
                "moduleDefinitionId": "project01::BD00",
                "slotDefinitionId": "project05::A000",
                "blockers": [{"code": "LOCATING_FEATURE_SPACING_MISMATCH"}],
            },
        ]
    }
    assert _position_parameter_fallback_pairs(catalog) == {
        ("project01::SS00", "project02::A600"),
        ("project03::AE00", "project02::A600"),
    }


def test_confirmed_transport_plane_fallback_supersedes_only_missing_native_axis_pair(
    monkeypatch,
):
    catalog = copy.deepcopy(load_parameterized_datum_placement_catalog(ROOT))
    # The production catalog may already contain the reviewed SS00 fallback.
    # Remove it so this unit test can add one isolated synthetic copy without
    # making the result depend on the current publication history.
    catalog["contracts"] = [
        row
        for row in catalog["contracts"]
        if not (
            row.get("moduleDefinitionId") == "project01::SS00"
            and row.get("side") == "moving_module"
        )
    ]
    catalog["compatibilityMatrix"] = [
        row
        for row in catalog["compatibilityMatrix"]
        if row.get("moduleDefinitionId") != "project01::SS00"
    ]
    source_contract = next(
        row
        for row in catalog["contracts"]
        if row.get("moduleDefinitionId") == "project02::A800"
        and row.get("side") == "moving_module"
    )
    fallback_contract = copy.deepcopy(source_contract)
    fallback_contract["contractId"] = "contract/project01-ss00-parameterized-test"
    fallback_contract["moduleDefinitionId"] = "project01::SS00"
    fallback_contract["moduleToken"] = "SS00"
    fallback_contract["sourcePortId"] = "SS00.parameterized_datum_installation.v1"
    catalog["contracts"].append(fallback_contract)
    source_match = next(
        row
        for row in catalog["compatibilityMatrix"]
        if row.get("slotDefinitionId") == "project02::A600"
        and {blocker.get("code") for blocker in row.get("blockers") or []}
        in ({"POSITION_PARAMETERS_MISSING"}, {"MODULE_POSITION_PRESET_MISSING"})
    )
    fallback_match = copy.deepcopy(source_match)
    fallback_match["moduleDefinitionId"] = "project01::SS00"
    fallback_match["moduleContractId"] = fallback_contract["contractId"]
    fallback_match["blockers"] = [{"code": "POSITION_PARAMETERS_MISSING"}]
    catalog["compatibilityMatrix"].append(fallback_match)
    monkeypatch.setattr(
        queue_module,
        "load_parameterized_datum_placement_catalog",
        lambda workspace: copy.deepcopy(catalog),
    )
    # Keep the synthetic fallback independent from the immutable production
    # release that may already exist for this exact pair.
    discover_releases = queue_module.discover_global_relation_release_pairs
    monkeypatch.setattr(
        queue_module,
        "discover_global_relation_release_pairs",
        lambda *args, **kwargs: {
            pair: evidence
            for pair, evidence in discover_releases(*args, **kwargs).items()
            if pair != ("project01::SS00", "project02::A600")
        },
    )

    queue = build_parameterized_datum_validation_queue(ROOT)
    row = next(
        item
        for item in queue["pairs"]
        if item["moduleDefinitionId"] == "project01::SS00"
        and item["slotDefinitionId"] == "project02::A600"
    )

    assert row["state"] == "explicit_position_parameters_required"
    assert row["interfaceFamily"] == "support_plane_two_offset_position/v1"
    # The existing A000 native two-axis path still has priority.  Once the
    # exact pair has acquired immutable CAD evidence it is released instead of
    # remaining an engineering decision.
    native = next(
        item
        for item in queue["pairs"]
        if item["moduleDefinitionId"] == "project01::SS00"
        and item["slotDefinitionId"] == "project05::A000"
    )
    assert native["state"] in {
        "explicit_axis_pair_selection_required",
        "released",
    }


def _redigest(queue: dict) -> dict:
    value = copy.deepcopy(queue)
    value.pop("queueDigest", None)
    value["queueDigest"] = hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return value


def test_queue_separates_released_ready_and_capture_gap_states():
    queue = build_parameterized_datum_validation_queue(ROOT)
    summary = queue["summary"]
    assert summary["listedPairCount"] == len(queue["pairs"])
    assert summary["releasedPairCount"] == sum(
        row["state"] == "released" for row in queue["pairs"]
    )
    assert summary["readyForCadValidationCount"] == sum(
        row["state"] == "ready_for_nonprototype_cad_validation"
        for row in queue["pairs"]
    )
    assert summary["blockedBeforeCadCount"] == 1
    assert summary["captureGapCount"] == 0
    released = {
        (row["moduleDefinitionId"], row["slotDefinitionId"])
        for row in queue["pairs"]
        if row["state"] == "released"
    }
    assert {
        ("project01::GN00", "project02::A600"),
        ("project01::SS00", "project02::A600"),
        ("project02::A800", "project02::A600"),
        ("project02::A800", "project05::A000"),
        ("project05::F000", "project01::JJ00"),
    }.issubset(released)
    blocked = [
        row
        for row in queue["pairs"]
        if row["state"] == "blocked_before_cad"
    ]
    assert [
        (row["moduleDefinitionId"], row["slotDefinitionId"])
        for row in blocked
    ] == [("project05::N000", "project02::A600")]
    assert blocked[0]["blocker"]["code"] == "TRANSPORT_OCCUPANCY_REGION_OVERLAP"
    assert all(
        row["readyForCadValidation"] is True
        and row["readyForReleasedCadExecution"] is False
        and row["physicalFasteningVerified"] is False
        for row in queue["pairs"]
        if row["state"] == "ready_for_nonprototype_cad_validation"
    )
    parameter_required = {
        (row["moduleDefinitionId"], row["slotDefinitionId"])
        for row in queue["pairs"]
        if row["state"] == "explicit_position_parameters_required"
    }
    assert not parameter_required
    assert {
        ("project02::A300", "project01::JJ00"),
        ("project02::A500", "project01::JJ00"),
        ("project02::A500", "project03::AA00"),
        ("project02::A500", "project05::A000"),
        ("project05::P000", "project01::JJ00"),
    } <= released
    axis_required = {
        (row["moduleDefinitionId"], row["slotDefinitionId"])
        for row in queue["pairs"]
        if row["state"] == "explicit_axis_selection_required"
    }
    assert not axis_required
    assert ("project05::F000", "project02::A600") in released
    assert ("project05::F000", "project01::JJ00") not in axis_required
    axis_pair_required = {
        (row["moduleDefinitionId"], row["slotDefinitionId"])
        for row in queue["pairs"]
        if row["state"] == "explicit_axis_pair_selection_required"
    }
    axis_pair_scope = {
        ("project01::BD00", "project05::A000"),
        ("project03::AH00", "project05::A000"),
        ("project01::SS00", "project05::A000"),
        ("project03::AE00", "project05::A000"),
    }
    # All four reviewed A000 pairs now have immutable non-prototype CAD
    # releases.  Release discovery must not depend on replaying the historical
    # confirmation packet.
    assert not axis_pair_required
    assert axis_pair_scope <= released
    unavailable_axis_pairs = {
        (row["moduleDefinitionId"], row["slotDefinitionId"])
        for row in queue["pairs"]
        if row["state"] == "axis_pair_not_found_in_authoritative_catalog"
    }
    assert unavailable_axis_pairs == set()
    flexible_slot_required = {
        (row["moduleDefinitionId"], row["slotDefinitionId"])
        for row in queue["pairs"]
        if row["state"] == "explicit_flexible_slot_selection_required"
    }
    # All three reviewed G000 flexible-slot pairs now have immutable releases;
    # no historical confirmation packet is required to retire the decision.
    assert not flexible_slot_required
    assert ("project05::G000", "project03::AA00") in released
    assert queue["captureGaps"] == []


def test_queue_orders_unreleased_cross_project_candidates_first():
    queue = build_parameterized_datum_validation_queue(ROOT)
    ready = [
        row
        for row in queue["pairs"]
        if row["state"] == "ready_for_nonprototype_cad_validation"
    ]
    first_same_project = next(
        (index for index, row in enumerate(ready) if not row["crossProject"]),
        len(ready),
    )
    assert all(row["crossProject"] for row in ready[:first_same_project])
    assert queue["executionPolicy"]["cadConcurrency"] == 1
    assert queue["executionPolicy"]["continueAfterFailure"] is False


def test_successor_queue_requires_catalog_advance_and_binds_parent_lineage():
    current = build_parameterized_datum_validation_queue(ROOT)
    with pytest.raises(MechanicalInterfaceContractError, match="has not advanced"):
        build_successor_parameterized_datum_validation_queue(ROOT, current)

    prior = copy.deepcopy(current)
    prior["sourceCatalogDigest"] = "0" * 64
    prior = _redigest(prior)
    successor = build_successor_parameterized_datum_validation_queue(ROOT, prior)

    assert successor["sourceCatalogDigest"] == current["sourceCatalogDigest"]
    assert successor["summary"] == current["summary"]
    assert successor["lineage"] == {
        "parentQueueDigest": prior["queueDigest"],
        "parentSourceCatalogDigest": "0" * 64,
        "successorSourceCatalogDigest": current["sourceCatalogDigest"],
        "reason": "canonical_catalog_advanced_after_exact_pair_publication",
        "preservedExplicitPositionEvidenceCount": 0,
        "preservedExplicitAxisSelectionEvidenceCount": 0,
        "preservedExplicitAxisPairSelectionEvidenceCount": 0,
        "preservedExplicitFlexibleSlotSelectionEvidenceCount": 0,
    }


def test_successor_queue_preserves_confirmed_position_decisions():
    pair = ("project02::A180", "project03::AA00")
    evidence = {
        pair: {
            "confirmed": True,
            "source": "engineer_confirmed_demo_station_coordinates",
            "confirmedBy": "test-engineer",
            "confirmedAt": "2026-10-26T00:00:00Z",
            "parametersMeters": {
                "longitudinal": 0.070,
                "lateral": 0.120,
                "supportGap": 0.0,
            },
        }
    }
    prior = build_parameterized_datum_validation_queue(
        ROOT, explicit_position_parameters=evidence
    )
    prior["sourceCatalogDigest"] = "0" * 64
    prior = _redigest(prior)

    successor = build_successor_parameterized_datum_validation_queue(ROOT, prior)
    row = next(
        item
        for item in successor["pairs"]
        if (item["moduleDefinitionId"], item["slotDefinitionId"]) == pair
    )
    assert row["state"] == "ready_for_nonprototype_cad_validation"
    assert row["positionParametersOverride"] == evidence[pair]["parametersMeters"]
    assert successor["lineage"]["preservedExplicitPositionEvidenceCount"] == 1


def test_queue_script_materializes_every_ready_candidate(tmp_path: Path):
    expected_ready = build_parameterized_datum_validation_queue(ROOT)["summary"][
        "readyForCadValidationCount"
    ]
    output = tmp_path / "queue"
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/build_parameterized_datum_validation_queue.py"),
            "--output-dir",
            str(output),
            "--materialize-packages",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    queue = json.loads((output / "validation-queue.json").read_text(encoding="utf-8"))
    package_dirs = [path for path in output.iterdir() if path.is_dir()]
    assert len(package_dirs) == queue["summary"]["readyForCadValidationCount"]
    assert queue["summary"]["readyForCadValidationCount"] == expected_ready
    assert all((path / "validation-package.json").is_file() for path in package_dirs)
    assert all((path / "effective-mate-graph.json").is_file() for path in package_dirs)
    assert all(
        (path / "selected-face-endpoint-catalog.json").is_file()
        for path in package_dirs
    )


def test_confirmed_a180_parameters_promote_only_the_exact_pair_to_candidate():
    baseline = build_parameterized_datum_validation_queue(ROOT)["summary"]
    evidence = {
        ("project02::A180", "project03::AA00"): {
            "confirmed": True,
            "source": "engineer_confirmed_demo_station_coordinates",
            "confirmedBy": "test-engineer",
            "confirmedAt": "2026-10-26T00:00:00Z",
            "parametersMeters": {
                "longitudinal": 0.070,
                "lateral": 0.120,
                "supportGap": 0.0,
            },
            "notes": "Test-only coordinates; not a production datum.",
        }
    }
    queue = build_parameterized_datum_validation_queue(
        ROOT, explicit_position_parameters=evidence
    )
    assert queue["summary"]["readyForCadValidationCount"] == (
        baseline["readyForCadValidationCount"] + 1
    )
    assert queue["summary"]["explicitPositionParametersRequiredCount"] == baseline[
        "explicitPositionParametersRequiredCount"
    ]
    assert queue["summary"]["confirmedExplicitPositionParameterCount"] == 1
    assert queue["summary"]["effectiveCompatiblePairCount"] == baseline[
        "effectiveCompatiblePairCount"
    ]
    promoted = next(
        row
        for row in queue["pairs"]
        if row["moduleDefinitionId"] == "project02::A180"
        and row["slotDefinitionId"] == "project03::AA00"
    )
    assert promoted["state"] == "ready_for_nonprototype_cad_validation"
    assert promoted["positionParametersOverride"] == evidence[
        ("project02::A180", "project03::AA00")
    ]["parametersMeters"]
    other = next(
        row
        for row in queue["pairs"]
        if row["moduleDefinitionId"] == "project02::A180"
        and row["slotDefinitionId"] == "project01::JJ00"
    )
    assert other["state"] == "released"


def test_queue_script_materializes_confirmed_position_parameter_candidate(
    tmp_path: Path,
):
    baseline = build_parameterized_datum_validation_queue(ROOT)["summary"]
    parameter_file = tmp_path / "parameters.json"
    parameter_file.write_text(
        json.dumps(
            {
                "schemaVersion": "parameterized-datum-position-parameters/v1",
                "pairs": [
                    {
                        "moduleDefinitionId": "project02::A180",
                        "slotDefinitionId": "project03::AA00",
                        "confirmed": True,
                        "source": "engineer_confirmed_demo_station_coordinates",
                        "confirmedBy": "test-engineer",
                        "confirmedAt": "2026-10-26T00:00:00Z",
                        "parametersMeters": {
                            "longitudinal": 0.070,
                            "lateral": 0.120,
                            "supportGap": 0.0,
                        },
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    output = tmp_path / "queue-with-a180"
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/build_parameterized_datum_validation_queue.py"),
            "--output-dir",
            str(output),
            "--materialize-packages",
            "--explicit-position-parameters",
            str(parameter_file),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    queue = json.loads((output / "validation-queue.json").read_text(encoding="utf-8"))
    assert queue["summary"]["readyForCadValidationCount"] == (
        baseline["readyForCadValidationCount"] + 1
    )
    package = json.loads(
        (
            output / "validation-a180-aa00-v1" / "validation-package.json"
        ).read_text(encoding="utf-8")
    )
    assert package["positionParametersOverride"] == {
        "longitudinal": 0.070,
        "lateral": 0.120,
        "supportGap": 0.0,
    }
    assert package["prototypeTopLevelTargetPoseUsed"] is False


def _confirmed_f000_axis_evidence(slot_definition_id: str) -> dict:
    catalog = build_f000_hybrid_axis_slot_catalog(ROOT)
    ranked = rank_f000_hybrid_axis_candidates(
        catalog,
        slot_definition_id,
        longitudinal_meters=0.078,
        lateral_meters=0.2115,
        limit=1,
    )
    assert len(ranked) == 1
    return {
        "confirmed": True,
        "source": "engineer_reviewed_semantic_position",
        "confirmedBy": "test-engineer",
        "confirmedAt": "2026-10-26T00:00:00Z",
        "selectedAxisEndpointId": ranked[0]["endpointId"],
        "requestedPositionMeters": {
            "longitudinal": 0.078,
            "lateral": 0.2115,
        },
        "notes": "Test-only axis selection; not a fastening approval.",
    }


def test_confirmed_f000_axis_promotes_only_the_exact_pair_to_candidate():
    baseline = build_parameterized_datum_validation_queue(ROOT)["summary"]
    pair = ("project05::F000", "project02::A600")
    evidence = _confirmed_f000_axis_evidence(pair[1])
    queue = build_parameterized_datum_validation_queue(
        ROOT, explicit_axis_selections={pair: evidence}
    )
    assert queue["summary"]["readyForCadValidationCount"] == (
        baseline["readyForCadValidationCount"] + 1
    )
    assert queue["summary"]["explicitAxisSelectionRequiredCount"] == baseline[
        "explicitAxisSelectionRequiredCount"
    ]
    assert queue["summary"]["confirmedExplicitAxisSelectionCount"] == 1
    assert queue["summary"]["effectiveCompatiblePairCount"] == (
        baseline["effectiveCompatiblePairCount"] + 1
    )
    promoted = next(
        row
        for row in queue["pairs"]
        if row["moduleDefinitionId"] == pair[0]
        and row["slotDefinitionId"] == pair[1]
    )
    assert promoted["state"] == "ready_for_nonprototype_cad_validation"
    assert promoted["candidateKind"] == "reviewed_hybrid_plane_axis_datum"
    assert promoted["selectedAxisEndpointId"] == evidence["selectedAxisEndpointId"]
    assert promoted["validationPackageDigest"]


def test_confirmed_f000_axis_reuses_matching_immutable_hybrid_release():
    pair = ("project05::F000", "project01::JJ00")
    evidence = {
        "confirmed": True,
        "source": "engineer_reconfirmed_released_axis",
        "confirmedBy": "test-engineer",
        "confirmedAt": "2026-10-26T00:00:00Z",
        "selectedAxisEndpointId": "face:jj00:02a165b1be818ce3",
        "requestedPositionMeters": {
            "longitudinal": 0.07,
            "lateral": 0.102,
        },
    }
    queue = build_parameterized_datum_validation_queue(
        ROOT, explicit_axis_selections={pair: evidence}
    )
    row = next(
        item
        for item in queue["pairs"]
        if (item["moduleDefinitionId"], item["slotDefinitionId"]) == pair
    )
    assert row["state"] == "released"
    assert row["readyForCadValidation"] is False
    assert row["readyForReleasedCadExecution"] is True
    assert row["selectedAxisEndpointId"] == evidence["selectedAxisEndpointId"]
    assert row["confirmedAxisAlreadyReleased"] is True


def test_queue_script_materializes_confirmed_f000_axis_candidate(tmp_path: Path):
    baseline = build_parameterized_datum_validation_queue(ROOT)["summary"]
    pair = ("project05::F000", "project02::A600")
    evidence = _confirmed_f000_axis_evidence(pair[1])
    selection_file = tmp_path / "axis-selection.json"
    selection_file.write_text(
        json.dumps(
            {
                "schemaVersion": "hybrid-plane-axis-selection-evidence/v1",
                "pairs": [
                    {
                        "moduleDefinitionId": pair[0],
                        "slotDefinitionId": pair[1],
                        **evidence,
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    output = tmp_path / "queue-with-f000-axis"
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/build_parameterized_datum_validation_queue.py"),
            "--output-dir",
            str(output),
            "--materialize-packages",
            "--explicit-axis-selections",
            str(selection_file),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    queue = json.loads((output / "validation-queue.json").read_text(encoding="utf-8"))
    assert queue["summary"]["readyForCadValidationCount"] == (
        baseline["readyForCadValidationCount"] + 1
    )
    package_root = output / "validation-f000-a600-v1"
    package = json.loads(
        (package_root / "validation-package.json").read_text(encoding="utf-8")
    )
    graph = json.loads(
        (package_root / "effective-mate-graph.json").read_text(encoding="utf-8")
    )
    assert package["placementMode"] == "reviewed_hybrid_plane_axis_datum"
    assert package["prototypeTopLevelTargetPoseUsed"] is False
    assert package["hybridAxisSelection"]["selectedAxisEndpointId"] == evidence[
        "selectedAxisEndpointId"
    ]
    assert [row["MateTypeName"] for row in graph["Mates"]] == [
        "swMateCOINCIDENT",
        "swMatePARALLEL",
        "swMateCONCENTRIC",
    ]


def test_confirmed_A000_axis_pair_promotes_only_the_exact_module_pair(monkeypatch):
    catalog = build_two_axis_slot_candidate_catalog(ROOT)
    family = next(
        row for row in catalog["families"] if row["moduleRole"] == "Transport"
    )
    candidate = family["axisPairCandidates"][0]
    pair = ("project01::SS00", "project05::A000")
    discover_releases = queue_module.discover_global_relation_release_pairs
    monkeypatch.setattr(
        queue_module,
        "discover_global_relation_release_pairs",
        lambda *args, **kwargs: {
            released_pair: release
            for released_pair, release in discover_releases(*args, **kwargs).items()
            if released_pair != pair
        },
    )
    evidence = {
        pair: {
            "confirmed": True,
            "source": "test_engineering_review_of_A000_axis_pair",
            "confirmedBy": "test-engineer",
            "confirmedAt": "2026-10-26T00:00:00Z",
            "selectedCandidatePairId": candidate["candidatePairId"],
        }
    }
    queue = build_parameterized_datum_validation_queue(
        ROOT, explicit_axis_pair_selections=evidence
    )
    promoted = next(
        row
        for row in queue["pairs"]
        if (row["moduleDefinitionId"], row["slotDefinitionId"]) == pair
    )
    assert promoted["state"] == "ready_for_nonprototype_cad_validation"
    assert promoted["candidateKind"] == "reviewed_support_plane_two_axis_slot"
    assert promoted["explicitAxisPairSelectionConfirmed"] is True
    assert promoted["selectedCandidatePairId"] == candidate["candidatePairId"]
    assert queue["summary"]["explicitAxisPairSelectionRequiredCount"] == 0
    other = next(
        row
        for row in queue["pairs"]
        if row["moduleDefinitionId"] == "project03::AE00"
        and row["slotDefinitionId"] == "project05::A000"
    )
    assert other["state"] in {
        "explicit_axis_pair_selection_required",
        "released",
    }


def test_queue_script_does_not_rematerialize_released_A000_axis_pair_candidate(
    tmp_path: Path,
):
    catalog = build_two_axis_slot_candidate_catalog(ROOT)
    family = next(
        row for row in catalog["families"] if row["moduleRole"] == "Transport"
    )
    candidate = family["axisPairCandidates"][0]
    selection_file = tmp_path / "axis-pair-selection.json"
    selection_file.write_text(
        json.dumps(
            {
                "schemaVersion": "two-axis-slot-selection-evidence/v1",
                "pairs": [
                    {
                        "moduleDefinitionId": "project01::SS00",
                        "slotDefinitionId": "project05::A000",
                        "confirmed": True,
                        "source": "test_engineering_review_of_A000_axis_pair",
                        "confirmedBy": "test-engineer",
                        "confirmedAt": "2026-10-26T00:00:00Z",
                        "selectedCandidatePairId": candidate[
                            "candidatePairId"
                        ],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    output = tmp_path / "queue-with-A000-axis-pair"
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/build_parameterized_datum_validation_queue.py"),
            "--output-dir",
            str(output),
            "--materialize-packages",
            "--explicit-axis-pair-selections",
            str(selection_file),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    queue = json.loads((output / "validation-queue.json").read_text(encoding="utf-8"))
    row = next(
        item
        for item in queue["pairs"]
        if item["moduleDefinitionId"] == "project01::SS00"
        and item["slotDefinitionId"] == "project05::A000"
    )
    assert row["state"] == "released"
    assert not (output / "validation-ss00-a000-v1").exists()


def _confirmed_g000_flexible_slot_evidence(slot_definition_id: str) -> dict:
    catalog = build_g000_flexible_slot_candidate_catalog(ROOT)
    slot = next(
        row
        for row in catalog["baseSlots"]
        if row["slotDefinitionId"] == slot_definition_id
    )
    endpoint = slot["axisCandidates"][0]["endpointId"]
    return {
        "confirmed": True,
        "source": "test_engineering_review_of_G000_flexible_slot",
        "confirmedBy": "test-engineer",
        "confirmedAt": "2026-10-26T00:00:00Z",
        "selectedAxisEndpointId": endpoint,
        "longitudinalOffsetMeters": 0.321,
    }


def test_confirmed_g000_axis_and_offset_does_not_override_released_exact_pair():
    baseline = build_parameterized_datum_validation_queue(ROOT)["summary"]
    pair = ("project05::G000", "project03::AA00")
    evidence = _confirmed_g000_flexible_slot_evidence(pair[1])
    queue = build_parameterized_datum_validation_queue(
        ROOT, explicit_flexible_slot_selections={pair: evidence}
    )
    promoted = next(
        row
        for row in queue["pairs"]
        if (row["moduleDefinitionId"], row["slotDefinitionId"]) == pair
    )
    assert promoted["state"] == "released"
    assert promoted["candidateKind"] == "reviewed_flexible_calibration_slot"
    assert promoted["explicitFlexibleSlotSelectionConfirmed"] is True
    assert promoted["pairReleaseEvidence"]["source"] == (
        "immutable_global_relation_release"
    )
    assert queue["summary"]["readyForCadValidationCount"] == baseline[
        "readyForCadValidationCount"
    ]
    assert queue["summary"]["releasedPairCount"] == baseline["releasedPairCount"]
    assert queue["summary"]["explicitFlexibleSlotSelectionRequiredCount"] == 0
    assert queue["summary"]["confirmedExplicitFlexibleSlotSelectionCount"] == 1
    other = next(
        row
        for row in queue["pairs"]
        if row["moduleDefinitionId"] == "project05::G000"
        and row["slotDefinitionId"] == "project01::JJ00"
    )
    assert other["state"] == "released"


def test_queue_script_does_not_rematerialize_released_g000_flexible_slot(
    tmp_path: Path,
):
    pair = ("project05::G000", "project03::AA00")
    evidence = _confirmed_g000_flexible_slot_evidence(pair[1])
    selection_file = tmp_path / "flexible-slot-selection.json"
    selection_file.write_text(
        json.dumps(
            {
                "schemaVersion": "flexible-calibration-slot-selection-evidence/v1",
                "pairs": [
                    {
                        "moduleDefinitionId": pair[0],
                        "slotDefinitionId": pair[1],
                        **evidence,
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    output = tmp_path / "queue-with-g000-flexible-slot"
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/build_parameterized_datum_validation_queue.py"),
            "--output-dir",
            str(output),
            "--materialize-packages",
            "--explicit-flexible-slot-selections",
            str(selection_file),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    queue = json.loads((output / "validation-queue.json").read_text(encoding="utf-8"))
    row = next(
        item
        for item in queue["pairs"]
        if (item["moduleDefinitionId"], item["slotDefinitionId"]) == pair
    )
    assert row["state"] == "released"
    assert row["nextAction"] == "reuse_released_pair"
    assert row["pairReleaseEvidence"]["source"] == "immutable_global_relation_release"
    assert not (output / "validation-g000-aa00-v1").exists()


def test_natural_language_delta_replaces_old_pair_release_with_new_candidate():
    baseline = build_parameterized_datum_validation_queue(ROOT)["summary"]
    evidence = {
        ("project01::GN00", "project03::AA00"): {
            "confirmed": True,
            "source": "engineer_confirmed_position_adjustment",
            "confirmedBy": "test-engineer",
            "confirmedAt": "2026-10-26T00:00:00Z",
            "positionInstruction": (
                "沿基座纵向移动10毫米，其余位置参数保持不变。"
            ),
            "currentParametersMeters": {
                "longitudinal": 0.354,
                "lateral": 0.2535,
                "supportGap": 0.0,
            },
        }
    }
    queue = build_parameterized_datum_validation_queue(
        ROOT, explicit_position_parameters=evidence
    )
    row = next(
        item
        for item in queue["pairs"]
        if item["moduleDefinitionId"] == "project01::GN00"
        and item["slotDefinitionId"] == "project03::AA00"
    )
    assert row["state"] == "ready_for_nonprototype_cad_validation"
    assert row["supersedesExistingPairRelease"] is True
    assert row["positionParametersOverride"] == {
        "longitudinal": pytest.approx(0.364),
        "lateral": 0.2535,
        "supportGap": 0.0,
    }
    assert queue["summary"]["releasedPairCount"] == (
        baseline["releasedPairCount"] - 1
    )
    assert queue["summary"]["readyForCadValidationCount"] == (
        baseline["readyForCadValidationCount"] + 1
    )
    assert queue["summary"]["effectiveCompatiblePairCount"] == baseline[
        "effectiveCompatiblePairCount"
    ]


def test_repeated_confirmation_equal_to_release_is_idempotent():
    baseline = build_parameterized_datum_validation_queue(ROOT)["summary"]
    pair = ("project01::GN00", "project02::A600")
    evidence = {
        pair: {
            "confirmed": True,
            "source": "user_reconfirmed_existing_station",
            "confirmedBy": "test-engineer",
            "confirmedAt": "2026-10-26T00:00:00Z",
            "parametersMeters": {
                "longitudinal": 0.354,
                "lateral": 0.2535,
                "supportGap": 0.0,
            },
        }
    }
    queue = build_parameterized_datum_validation_queue(
        ROOT, explicit_position_parameters=evidence
    )
    row = next(
        item
        for item in queue["pairs"]
        if (item["moduleDefinitionId"], item["slotDefinitionId"]) == pair
    )
    assert row["state"] == "released"
    assert row["confirmedParametersAlreadyReleased"] is True
    assert row["readyForCadValidation"] is False
    assert queue["summary"]["releasedPairCount"] == baseline["releasedPairCount"]
    # Idempotently reconfirming GN00 must not alter the independent N000->A600
    # finite-support repeatability candidate currently waiting for CAD.
    assert queue["summary"]["readyForCadValidationCount"] == baseline[
        "readyForCadValidationCount"
    ]


def test_queue_script_compiles_natural_language_delta_into_new_candidate(
    tmp_path: Path,
):
    parameter_file = tmp_path / "position-instruction.json"
    parameter_file.write_text(
        json.dumps(
            {
                "schemaVersion": "parameterized-datum-position-parameters/v1",
                "pairs": [
                    {
                        "moduleDefinitionId": "project01::GN00",
                        "slotDefinitionId": "project03::AA00",
                        "confirmed": True,
                        "source": "engineer_confirmed_position_adjustment",
                        "confirmedBy": "test-engineer",
                        "confirmedAt": "2026-10-26T00:00:00Z",
                        "positionInstruction": (
                            "沿基座纵向移动10毫米，其余位置参数保持不变。"
                        ),
                        "currentParametersMeters": {
                            "longitudinal": 0.354,
                            "lateral": 0.2535,
                            "supportGap": 0.0,
                        },
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    output = tmp_path / "queue-with-position-instruction"
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/build_parameterized_datum_validation_queue.py"),
            "--output-dir",
            str(output),
            "--materialize-packages",
            "--explicit-position-parameters",
            str(parameter_file),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    queue = json.loads((output / "validation-queue.json").read_text(encoding="utf-8"))
    row = next(
        item
        for item in queue["pairs"]
        if item["moduleDefinitionId"] == "project01::GN00"
        and item["slotDefinitionId"] == "project03::AA00"
    )
    assert row["state"] == "ready_for_nonprototype_cad_validation"
    assert row["positionInstructionCompilation"]["parametersMeters"] == {
        "longitudinal": pytest.approx(0.364),
        "lateral": 0.2535,
        "supportGap": 0.0,
    }
    package = json.loads(
        (
            output / "validation-gn00-aa00-v1" / "validation-package.json"
        ).read_text(encoding="utf-8")
    )
    assert package["positionParametersOverride"] == {
        "longitudinal": pytest.approx(0.364),
        "lateral": 0.2535,
        "supportGap": 0.0,
    }
    assert package["prototypeTopLevelTargetPoseUsed"] is False
