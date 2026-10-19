from pathlib import Path

from scripts.build_project02_t401_driving_candidates import (
    SPECS,
    build_candidate,
    build_catalog,
)


def test_t401_candidates_are_nonanchor_driving_and_occurrence_specific(tmp_path: Path):
    for name, spec in SPECS.items():
        candidate, assessment = build_candidate(name, tmp_path / name)
        assert assessment["checkpointPassed"] is True
        assert candidate["drivingScope"]["caseAnchorAllowed"] is False
        assert candidate["drivingScope"]["occurrenceRole"] == name
        assert len(candidate["connectionTemplates"]) == 1
        template = candidate["connectionTemplates"][0]
        assert template["constraintEffect"]["expectedResidualDof"] == 0
        assert template["constraintEffect"]["parameterAuthority"] == "prototype_estimate"
        assert len(template["mateSteps"]) == 3
        tokens = {row["moduleToken"] for row in candidate["ports"]}
        assert tokens == {"T401", spec["context"]}


def test_combined_catalog_contains_two_distinct_t401_templates(tmp_path: Path):
    for name in SPECS:
        build_candidate(name, tmp_path / name)
    catalog = build_catalog(tmp_path)
    templates = [
        row
        for row in catalog["connectionTemplates"]
        if str(row.get("legacyTemplateId") or "").startswith("T401_")
        and str(row.get("legacyTemplateId") or "").endswith("_nonanchor_driving_v1")
    ]
    assert {row["legacyTemplateId"] for row in templates} == {
        "T401_1_to_A600_nonanchor_driving_v1",
        "T401_2_to_A200_nonanchor_driving_v1",
    }
    assert len({row["globalTemplateId"] for row in templates}) == 2
