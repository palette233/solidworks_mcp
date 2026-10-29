import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from demo_backend.flexible_calibration_slot_selection import (
    build_g000_flexible_slot_candidate_catalog,
)
from demo_backend.hybrid_plane_axis_slot_selection import (
    build_f000_hybrid_axis_slot_catalog,
)
from demo_backend.mechanical_interface_contracts import MechanicalInterfaceContractError
from demo_backend.parameterized_datum_engineering_review import (
    build_parameterized_datum_engineering_review,
)
from demo_backend.parameterized_datum_geometry_decisions import (
    REQUEST_SCHEMA,
    build_geometry_decision_request_template,
    compile_geometry_decision_requests,
    geometry_decision_evidence_maps,
)
from demo_backend.parameterized_datum_validation_queue import (
    build_parameterized_datum_validation_queue,
)
from demo_backend.two_axis_slot_selection import (
    build_two_axis_slot_candidate_catalog,
)


ROOT = Path(__file__).resolve().parents[3]
HISTORICAL_REVIEW = (
    ROOT
    / "demo/cross_project_substitution/parameterized-datum-placement-v1"
    / "engineering-decision-review-20261026-v22/engineering-review.json"
)
PRE_NATIVE_STATION_REVIEW = (
    ROOT
    / "demo/cross_project_substitution/parameterized-datum-placement-v1"
    / "engineering-decision-review-20261026-v39/engineering-review.json"
)
V50_REVIEW = (
    ROOT
    / "demo/cross_project_substitution/parameterized-datum-placement-v1"
    / "engineering-decision-review-20261026-v50/engineering-review.json"
)


def _historical_review():
    return json.loads(HISTORICAL_REVIEW.read_text(encoding="utf-8-sig"))


def _pre_native_station_review():
    return json.loads(
        PRE_NATIVE_STATION_REVIEW.read_text(encoding="utf-8-sig")
    )


def _v50_review():
    return json.loads(V50_REVIEW.read_text(encoding="utf-8-sig"))


def _request(decision, **updates):
    row = {
        "moduleDefinitionId": decision["moduleDefinitionId"],
        "slotDefinitionId": decision["slotDefinitionId"],
        "decisionKind": decision["decisionKind"],
        "action": None,
        "confirmed": True,
        "source": "mechanical-engineer-review",
        "confirmedBy": "test-engineer",
        "confirmedAt": "2026-10-26T12:00:00+08:00",
        "sourceDecisionDigest": decision["decisionDigest"],
    }
    row.update(updates)
    return row


def _requests(review, rows):
    return {
        "schemaVersion": REQUEST_SCHEMA,
        "sourceReviewDigest": review["reviewDigest"],
        "requests": rows,
    }


def _decision(review, kind, module, slot):
    return next(
        row
        for row in review["decisions"]
        if row["decisionKind"] == kind
        and row["moduleDefinitionId"] == module
        and row["slotDefinitionId"] == slot
    )


def _evidence_map(document):
    return {
        (row["moduleDefinitionId"], row["slotDefinitionId"]): {
            key: value
            for key, value in row.items()
            if key not in {"moduleDefinitionId", "slotDefinitionId"}
        }
        for row in document["pairs"]
    }


def test_template_covers_all_current_geometry_decisions_without_confirmation():
    review = _v50_review()
    template = build_geometry_decision_request_template(review)
    expected = (
        review["axisDecisionCount"]
        + review["axisPairDecisionCount"]
        + review["flexibleSlotDecisionCount"]
    )
    assert template["requestCount"] == expected
    assert len(template["requests"]) == expected
    assert all(row["confirmed"] is False for row in template["requests"])
    kinds = [row["decisionKind"] for row in template["requests"]]
    assert kinds.count("axis_selection") == review["axisDecisionCount"]
    assert kinds.count("axis_pair_selection") == 4
    assert kinds.count("flexible_slot_selection") == 3
    a600 = next(
        row
        for row in template["requests"]
        if row["moduleDefinitionId"] == "project05::F000"
        and row["slotDefinitionId"] == "project02::A600"
    )
    assert a600["action"] == "accept_recommendation"
    assert a600["recommendationAvailable"] is True


def test_accept_axis_recommendation_promotes_only_exact_pair():
    review = _historical_review()
    decision = _decision(
        review, "axis_selection", "project05::F000", "project01::JJ00"
    )
    bundle = compile_geometry_decision_requests(
        ROOT,
        review,
        _requests(review, [_request(decision, action="accept_recommendation")]),
    )
    assert bundle["confirmedDecisionCount"] == 1
    assert bundle["confirmedAxisSelectionCount"] == 1
    record = bundle["axisSelections"]["pairs"][0]
    assert record["selectedAxisEndpointId"] == decision["recommendedAxisEndpointId"]
    queue = build_parameterized_datum_validation_queue(
        ROOT,
        explicit_axis_selections=_evidence_map(bundle["axisSelections"]),
    )
    pair = next(
        row
        for row in queue["pairs"]
        if row["moduleDefinitionId"] == "project05::F000"
        and row["slotDefinitionId"] == "project01::JJ00"
    )
    assert pair["state"] == "released"
    assert queue["summary"]["confirmedExplicitAxisSelectionCount"] == 1


def test_explicit_axis_pair_and_flexible_slot_compile_to_queue_candidates():
    review = _v50_review()
    axis_pair_decision = _decision(
        review, "axis_pair_selection", "project01::BD00", "project05::A000"
    )
    pair_catalog = build_two_axis_slot_candidate_catalog(ROOT)
    family = next(
        row
        for row in pair_catalog["families"]
        if "project01::BD00" in row["moduleDefinitionIds"]
    )
    candidate_pair_id = family["axisPairCandidates"][0]["candidatePairId"]
    flexible_decision = _decision(
        review, "flexible_slot_selection", "project05::G000", "project03::AA00"
    )
    flexible_catalog = build_g000_flexible_slot_candidate_catalog(ROOT)
    flexible_base = next(
        row
        for row in flexible_catalog["baseSlots"]
        if row["slotDefinitionId"] == "project03::AA00"
    )
    axis_id = flexible_base["axisCandidates"][0]["endpointId"]
    bundle = compile_geometry_decision_requests(
        ROOT,
        review,
        _requests(
            review,
            [
                _request(
                    axis_pair_decision,
                    action="select_axis_pair",
                    selectedCandidatePairId=candidate_pair_id,
                ),
                _request(
                    flexible_decision,
                    action="select_flexible_slot",
                    selectedAxisEndpointId=axis_id,
                    longitudinalOffsetMeters=0.42,
                ),
            ],
        ),
    )
    maps = geometry_decision_evidence_maps(bundle)
    queue = build_parameterized_datum_validation_queue(
        ROOT,
        explicit_axis_pair_selections=maps["axisPairSelections"],
        explicit_flexible_slot_selections=maps["flexibleSlotSelections"],
    )
    states = {
        (row["moduleDefinitionId"], row["slotDefinitionId"]): row["state"]
        for row in queue["pairs"]
    }
    assert states[("project01::BD00", "project05::A000")] in {
        "ready_for_nonprototype_cad_validation",
        "released",
    }
    # The exact G000→AA00 pair has since completed non-prototype CAD validation
    # and immutable publication; replaying historical selection evidence must
    # reuse the release instead of generating a duplicate candidate.
    assert states[("project05::G000", "project03::AA00")] == "released"


def test_accept_flexible_slot_recommendation_promotes_only_exact_pair():
    review = _v50_review()
    decision = _decision(
        review, "flexible_slot_selection", "project05::G000", "project01::JJ00"
    )
    bundle = compile_geometry_decision_requests(
        ROOT,
        review,
        _requests(review, [_request(decision, action="accept_recommendation")]),
    )
    assert bundle["confirmedDecisionCount"] == 1
    assert bundle["confirmedFlexibleSlotSelectionCount"] == 1
    record = bundle["flexibleSlotSelections"]["pairs"][0]
    assert record["selectedAxisEndpointId"] == decision[
        "recommendedAxisEndpointId"
    ]
    assert record["longitudinalOffsetMeters"] == pytest.approx(0.482)
    assert record["evidenceBasis"] == (
        "accepted_native_semantic_station_recommendation"
    )
    maps = geometry_decision_evidence_maps(bundle)
    queue = build_parameterized_datum_validation_queue(
        ROOT,
        explicit_flexible_slot_selections=maps["flexibleSlotSelections"],
    )
    pair = next(
        row
        for row in queue["pairs"]
        if row["moduleDefinitionId"] == "project05::G000"
        and row["slotDefinitionId"] == "project01::JJ00"
    )
    assert pair["state"] == "released"


def test_accept_axis_pair_recommendation_promotes_only_exact_pair():
    review = _v50_review()
    decision = _decision(
        review, "axis_pair_selection", "project01::SS00", "project05::A000"
    )
    bundle = compile_geometry_decision_requests(
        ROOT,
        review,
        _requests(review, [_request(decision, action="accept_recommendation")]),
    )
    assert bundle["confirmedDecisionCount"] == 1
    assert bundle["confirmedAxisPairSelectionCount"] == 1
    record = bundle["axisPairSelections"]["pairs"][0]
    assert record["selectedCandidatePairId"] == decision[
        "recommendedCandidatePairId"
    ]
    assert record["evidenceBasis"] == (
        "accepted_native_primary_secondary_station_recommendation"
    )
    maps = geometry_decision_evidence_maps(bundle)
    queue = build_parameterized_datum_validation_queue(
        ROOT,
        explicit_axis_pair_selections=maps["axisPairSelections"],
    )
    pair = next(
        row
        for row in queue["pairs"]
        if row["moduleDefinitionId"] == "project01::SS00"
        and row["slotDefinitionId"] == "project05::A000"
    )
    assert pair["state"] == "released"


def test_axis_without_station_requires_position_and_catalog_endpoint():
    # Preserve the explicit-position compiler branch with the immutable review
    # generated before native role-station evidence was introduced.
    review = _pre_native_station_review()
    decision = _decision(
        review, "axis_selection", "project05::F000", "project02::A600"
    )
    catalog = build_f000_hybrid_axis_slot_catalog(ROOT)
    slot = next(
        row
        for row in catalog["baseSlots"]
        if row["slotDefinitionId"] == "project02::A600"
    )
    endpoint = next(
        row["endpointId"]
        for row in slot["axisCandidates"]
        if row["axisMateAlignmentCompatible"] is True
    )
    base = _request(
        decision,
        action="select_axis",
        selectedAxisEndpointId=endpoint,
    )
    with pytest.raises(MechanicalInterfaceContractError, match="must contain"):
        compile_geometry_decision_requests(
            ROOT, review, _requests(review, [base])
        )
    base["requestedPositionMeters"] = {"longitudinal": 0.2, "lateral": 0.1}
    bundle = compile_geometry_decision_requests(
        ROOT, review, _requests(review, [base])
    )
    assert bundle["axisSelections"]["pairs"][0]["requestedPositionMeters"] == {
        "longitudinal": 0.2,
        "lateral": 0.1,
    }


def test_geometry_requests_fail_closed_on_invalid_or_stale_choices():
    review = _v50_review()
    decision = _decision(
        review, "axis_pair_selection", "project01::BD00", "project05::A000"
    )
    invalid = _request(
        decision,
        action="select_axis_pair",
        selectedCandidatePairId="axis-pair/not-authoritative",
    )
    with pytest.raises(MechanicalInterfaceContractError, match="absent"):
        compile_geometry_decision_requests(
            ROOT, review, _requests(review, [invalid])
        )
    unconfirmed = copy.deepcopy(invalid)
    unconfirmed["confirmed"] = False
    with pytest.raises(MechanicalInterfaceContractError, match="not explicitly"):
        compile_geometry_decision_requests(
            ROOT, review, _requests(review, [unconfirmed])
        )
    catalog = build_two_axis_slot_candidate_catalog(ROOT)
    valid = copy.deepcopy(invalid)
    valid["selectedCandidatePairId"] = next(
        row
        for row in catalog["families"]
        if "project01::BD00" in row["moduleDefinitionIds"]
    )["axisPairCandidates"][0]["candidatePairId"]
    duplicate = copy.deepcopy(valid)
    with pytest.raises(MechanicalInterfaceContractError, match="duplicated"):
        compile_geometry_decision_requests(
            ROOT, review, _requests(review, [valid, duplicate])
        )
    stale = copy.deepcopy(review)
    stale["decisions"][0]["status"] = "tampered"
    with pytest.raises(MechanicalInterfaceContractError, match="review digest mismatch"):
        compile_geometry_decision_requests(
            ROOT, stale, _requests(review, [invalid])
        )


def test_compiled_bundle_rejects_tampering_before_queue_use():
    review = _historical_review()
    decision = _decision(
        review, "axis_selection", "project05::F000", "project01::JJ00"
    )
    bundle = compile_geometry_decision_requests(
        ROOT,
        review,
        _requests(review, [_request(decision, action="accept_recommendation")]),
    )
    maps = geometry_decision_evidence_maps(bundle)
    assert len(maps["axisSelections"]) == 1
    tampered = copy.deepcopy(bundle)
    tampered["axisSelections"]["pairs"][0]["selectedAxisEndpointId"] = (
        "face:tampered"
    )
    with pytest.raises(MechanicalInterfaceContractError, match="digest mismatch"):
        geometry_decision_evidence_maps(tampered)


def test_cli_bundle_drives_validation_queue_without_three_manual_files(tmp_path):
    review = _historical_review()
    decision = _decision(
        review, "axis_selection", "project05::F000", "project01::JJ00"
    )
    requests = _requests(
        review, [_request(decision, action="accept_recommendation")]
    )
    review_path = tmp_path / "review.json"
    request_path = tmp_path / "requests.json"
    evidence_dir = tmp_path / "evidence"
    queue_dir = tmp_path / "queue"
    review_path.write_text(
        json.dumps(review, ensure_ascii=False), encoding="utf-8"
    )
    request_path.write_text(
        json.dumps(requests, ensure_ascii=False), encoding="utf-8"
    )
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/compile_parameterized_datum_geometry_decisions.py"),
            "compile",
            "--review",
            str(review_path),
            "--requests",
            str(request_path),
            "--output",
            str(evidence_dir),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/build_parameterized_datum_validation_queue.py"),
            "--output-dir",
            str(queue_dir),
            "--geometry-decision-bundle",
            str(evidence_dir / "geometry-decision-evidence-bundle.json"),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    queue = json.loads(
        (queue_dir / "validation-queue.json").read_text(encoding="utf-8")
    )
    row = next(
        item
        for item in queue["pairs"]
        if item["moduleDefinitionId"] == "project05::F000"
        and item["slotDefinitionId"] == "project01::JJ00"
    )
    assert row["state"] == "released"
    assert queue["summary"]["confirmedExplicitAxisSelectionCount"] == 1
