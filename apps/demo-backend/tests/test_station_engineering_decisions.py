import copy
import json
from pathlib import Path

import pytest

from demo_backend.station_engineering_decisions import (
    build_station_engineering_decision_summary,
    validate_station_engineering_decision_summary,
)


ROOT = Path(__file__).resolve().parents[3]
GAP = ROOT / (
    "demo/station_gap_batch_20261028/coverage-v23/"
    "gap-batch-v52/gap-queue.json"
)


def test_v52_engineering_decisions_are_consolidated_without_cad_authority():
    report = build_station_engineering_decision_summary(ROOT, GAP)
    validate_station_engineering_decision_summary(report)
    assert report["decisionPairCount"] == 27
    assert report["topicCount"] == 9
    assert report["status"] == "engineering_confirmation_required"
    assert report["confirmed"] is False
    assert report["cadLaunchAllowed"] is False
    assert sum(topic["pairCount"] for topic in report["topics"]) == 27
    assert all(topic["confirmed"] is False for topic in report["topics"])
    assert all(topic["cadLaunchAllowed"] is False for topic in report["topics"])


def test_scanner_candidates_preserve_catalog_references():
    report = build_station_engineering_decision_summary(ROOT, GAP)
    topic = next(
        row
        for row in report["topics"]
        if row["gapCategory"]
        == "scanner_role_selection_from_candidate_catalog_required"
    )
    assert topic["pairCount"] == 7
    references = [
        reference
        for pair in topic["exactPairs"]
        for reference in pair["evidenceReferences"]
    ]
    assert any(
        reference.get("sourceOpticalCandidateCatalogPath")
        == "data/assembly_stations/scanner-source-candidates-f000-v1.json"
        for reference in references
    )
    assert any(
        reference.get("transportBarcodeTargetCandidateCatalogPath")
        == "data/assembly_stations/scanner-target-candidates-d000-v1.json"
        for reference in references
    )


def test_summary_digest_and_unknown_category_fail_closed(tmp_path: Path):
    report = build_station_engineering_decision_summary(ROOT, GAP)
    changed = copy.deepcopy(report)
    changed["decisionPairCount"] += 1
    with pytest.raises(ValueError, match="digest mismatch"):
        validate_station_engineering_decision_summary(changed)

    gap = json.loads(GAP.read_text(encoding="utf-8-sig"))
    row = next(item for item in gap["queue"] if item["workClass"] == "engineering_decision")
    row["gapCategory"] = "unknown_engineering_choice"
    path = tmp_path / "gap.json"
    path.write_text(json.dumps(gap), encoding="utf-8")
    with pytest.raises(ValueError, match="no guidance"):
        build_station_engineering_decision_summary(tmp_path, path)
