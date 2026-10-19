from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/build_project02_a800_a180_driving_candidates.py"
SPEC = importlib.util.spec_from_file_location(
    "build_project02_a800_a180_driving_candidates", SCRIPT
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_project02_driving_candidates_use_strict_nonanchor_checkpoints(tmp_path) -> None:
    output = ROOT / ".tmp" / tmp_path.name / "project02-a800-a180"
    a800, a800_assessment = MODULE.build_candidate("A800", output / "A800")
    a180, a180_assessment = MODULE.build_candidate("A180", output / "A180")
    a500, a500_assessment = MODULE.build_candidate("A500", output / "A500")
    a700, a700_assessment = MODULE.build_candidate("A700", output / "A700")
    a300, a300_assessment = MODULE.build_candidate("A300", output / "A300")
    a200, a200_assessment = MODULE.build_candidate("A200", output / "A200")
    a100, a100_assessment = MODULE.build_candidate("A100", output / "A100")

    assert a800_assessment["checkpointPassed"] is True
    assert a180_assessment["checkpointPassed"] is True
    assert a500_assessment["checkpointPassed"] is True
    assert a700_assessment["checkpointPassed"] is True
    assert a300_assessment["checkpointPassed"] is True
    assert a200_assessment["checkpointPassed"] is True
    assert a100_assessment["checkpointPassed"] is True
    for candidate in (a800, a180, a500, a700, a300, a200, a100):
        template = candidate["connectionTemplates"][0]
        assert template["constraintEffect"]["fullyLocatesAddedComponent"] is True
        assert template["constraintEffect"]["expectedResidualDof"] == 0
        assert candidate["drivingScope"]["caseAnchorAllowed"] is False
        expected_count = 6 if candidate is a700 else 3
        assert len(template["mateSteps"]) == expected_count

    assert [row["mateName"] for row in a800["connectionTemplates"][0]["mateSteps"]] == [
        "重合35",
        "宽度9",
        "A800_LOCATING_DISTANCE_X",
    ]
    assert [row["mateName"] for row in a180["connectionTemplates"][0]["mateSteps"]] == [
        "重合34",
        "距离24",
        "槽口3",
    ]
    assert a180["connectionTemplates"][0]["mateSteps"][2]["advancedOptions"][
        "SlotConstraint"
    ] == 0
    assert [row["mateName"] for row in a500["connectionTemplates"][0]["mateSteps"]] == [
        "重合13",
        "宽度4",
        "距离27",
    ]
    assert {row["moduleToken"] for row in a500["ports"]} == {"A500", "A600"}
    assert [row["mateName"] for row in a700["connectionTemplates"][0]["mateSteps"]] == [
        "平行1",
        "平行2",
        "距离6",
        "重合38",
        "宽度10",
        "距离29",
    ]
    assert a700["connectionTemplates"][0]["constraintEffect"][
        "internalFlexibilityPreserved"
    ] is True
    assert [row["mateName"] for row in a300["connectionTemplates"][0]["mateSteps"]] == [
        "距离19",
        "距离20",
        "重合39",
    ]
    assert [row["mateName"] for row in a200["connectionTemplates"][0]["mateSteps"]] == [
        "重合26",
        "槽口1",
        "槽口2",
    ]
    assert a200["connectionTemplates"][0]["mateSteps"][1]["advancedOptions"][
        "SlotConstraint"
    ] == 1
    assert a200["connectionTemplates"][0]["constraintEffect"][
        "internalFlexibilityPreserved"
    ] is True
    assert [row["mateName"] for row in a100["connectionTemplates"][0]["mateSteps"]] == [
        "重合8",
        "重合9",
        "距离9",
    ]
    assert a100["connectionTemplates"][0]["constraintEffect"][
        "internalFlexibilityPreserved"
    ] is True


def test_project02_candidates_are_portable_in_global_catalog(tmp_path) -> None:
    output = ROOT / ".tmp" / tmp_path.name / "project02-a800-a180"
    MODULE.build_candidate("A800", output / "A800")
    MODULE.build_candidate("A180", output / "A180")
    MODULE.build_candidate("A500", output / "A500")
    MODULE.build_candidate("A700", output / "A700")
    MODULE.build_candidate("A300", output / "A300")
    MODULE.build_candidate("A200", output / "A200")
    MODULE.build_candidate("A100", output / "A100")
    catalog = MODULE.build_catalog(output)

    matches = [
        row
        for row in catalog["connectionTemplates"]
        if row.get("legacyTemplateId")
        in {
            "A800_to_A600_nonanchor_driving_v1",
            "A180_to_A600_nonanchor_driving_v1",
            "A500_to_A600_nonanchor_driving_v1",
            "A700_to_A600_nonanchor_driving_v1",
            "A300_to_A600_nonanchor_driving_v1",
            "A200_to_A600_nonanchor_driving_v1",
            "A100_to_A600_nonanchor_driving_v1",
        }
    ]
    assert len(matches) == 7
    assert sorted(len(row["mateSteps"]) for row in matches) == [3, 3, 3, 3, 3, 3, 6]
    for template in matches:
        compatibility = [
            row
            for row in catalog["compatibility"]
            if row.get("globalTemplateId") == template["globalTemplateId"]
        ]
        assert compatibility
        assert all(row["portableForTemplate"] is True for row in compatibility)
