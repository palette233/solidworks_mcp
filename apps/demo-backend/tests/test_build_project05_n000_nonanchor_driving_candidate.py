import importlib.util
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[3]
SCRIPT = WORKSPACE / "scripts/build_project05_n000_nonanchor_driving_candidate.py"


def _module():
    spec = importlib.util.spec_from_file_location("project05_n000_candidate", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_n000_candidate_is_nonanchor_four_relation_bundle(tmp_path):
    module = _module()
    package = WORKSPACE / ".tmp" / tmp_path.name / "N000"
    candidate, assessment = module.write_candidate_package(package)

    assert assessment["checkpointPassed"] is True
    template = candidate["connectionTemplates"][0]
    assert template["templateId"] == "N000_to_A000_nonanchor_driving_v2"
    assert [row["mateName"] for row in template["mateSteps"]] == [
        "重合42",
        "平行13",
        "槽口4",
        "N000_LOCATING_DISTANCE_X",
    ]
    assert template["mateSteps"][2]["advancedOptions"]["SlotConstraint"] == 0
    assert template["constraintEffect"]["expectedResidualDof"] == 0
    assert template["constraintEffect"]["parameterAuthority"] == "prototype_estimate"
    assert candidate["drivingScope"]["caseAnchorAllowed"] is False
    assert candidate["effectiveMateGraphPath"].endswith("/N000/assembly_plan_effective.json")
    assert candidate["readOnlySourceRelations"] == []


def test_n000_candidate_merges_with_five_existing_project05_templates(tmp_path):
    module = _module()
    package = WORKSPACE / ".tmp" / tmp_path.name / "N000"
    module.write_candidate_package(package)
    catalog = module.build_global_module_catalog(
        WORKSPACE,
        additional_semantic_catalog_paths=[
            module.D000_CANDIDATE,
            *(module.EXISTING_CANDIDATES / token / "semantic_port_catalog.json" for token in ("F000", "M000", "G000")),
            module.P000_CANDIDATE,
            package / "semantic_port_catalog.json",
        ],
    )
    module.validate_global_module_catalog(catalog)
    matches = [
        row for row in catalog["connectionTemplates"]
        if row.get("legacyTemplateId") == "N000_to_A000_nonanchor_driving_v2"
    ]
    assert len(matches) == 1
    assert len(matches[0]["mateSteps"]) == 4
