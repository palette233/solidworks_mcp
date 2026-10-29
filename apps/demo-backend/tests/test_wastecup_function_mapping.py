from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile

import pytest

from demo_backend.wastecup_function_mapping import (
    build_wastecup_function_mapping_report,
)


ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "data/assembly_stations/a300-cross-base-cup-mapping-v1.json"


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_real_a300_cross_base_mappings_are_unique_and_reversed() -> None:
    report = build_wastecup_function_mapping_report(ROOT, read(CONFIG))
    assert report["schemaVersion"] == "station-candidate-extension-report/v1"
    assert report["summary"] == {"candidateCount": 2, "mappingSelectedCount": 2}
    for row in report["candidates"]:
        assert row["cadLaunchAllowed"] is False
        assert row["readyForCadValidation"] is False
        assert row["status"] == (
            "wastecup_mapping_selected_requires_saved_base_pose_and_station_candidate"
        )
        decision = row["mappingDecision"]
        assert decision["passingCandidateCount"] == 1
        assert decision["selected"]["screening"]["passed"] is True
        assert decision["selected"]["screening"][
            "maximumPlanarMappingResidualMeters"
        ] == pytest.approx(0.02)
        mapping = decision["selected"]["mappingByLeaf"]
        assert mapping["C000437564-1"].endswith("-2")
        assert mapping["C000437564-2"].endswith("-1")


def test_mapping_report_rejects_duplicate_pair() -> None:
    config = read(CONFIG)
    config["entries"].append(copy.deepcopy(config["entries"][0]))
    with pytest.raises(ValueError, match="duplicate wastecup"):
        build_wastecup_function_mapping_report(ROOT, config)


def test_mapping_report_rejects_cad_identity_mismatch() -> None:
    config = read(CONFIG)
    config["entries"] = [copy.deepcopy(config["entries"][0])]
    source = ROOT / config["entries"][0]["pairCadResultPath"]
    payload = read(source)
    payload["toolResult"]["TargetModuleToken"] = "WRONG"
    # Evidence consumers intentionally reject files outside the workspace.
    # Keep the tampered fixture inside a transient workspace directory so the
    # test reaches the identity gate without weakening that containment rule.
    with tempfile.TemporaryDirectory(dir=ROOT) as directory:
        changed = Path(directory) / "cad-result.json"
        changed.write_text(json.dumps(payload), encoding="utf-8")
        config["entries"][0]["pairCadResultPath"] = str(changed)
        with pytest.raises(ValueError, match="CAD target identity"):
            build_wastecup_function_mapping_report(ROOT, config)
