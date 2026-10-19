import importlib.util
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[3]
SCRIPT = WORKSPACE / "scripts/build_project05_p000_nonanchor_driving_candidate.py"


def _module():
    spec = importlib.util.spec_from_file_location("project05_p000_candidate", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_p000_candidate_uses_free_slot_and_explicit_prototype_estimate(tmp_path):
    module = _module()
    package = WORKSPACE / ".tmp" / tmp_path.name / "P000"
    candidate, assessment = module.write_candidate_package(package)

    assert assessment["checkpointPassed"] is True
    template = candidate["connectionTemplates"][0]
    assert template["templateId"] == "P000_to_A000_nonanchor_driving_v2"
    assert [row["mateName"] for row in template["mateSteps"]] == [
        "重合43",
        "平行14",
        "槽口6",
        "P000_LOCATING_DISTANCE_X",
    ]
    assert template["mateSteps"][2]["advancedOptions"]["SlotConstraint"] == 0
    assert template["constraintEffect"]["expectedResidualDof"] == 0
    assert template["constraintEffect"]["parameterAuthority"] == "prototype_estimate"
    assert candidate["drivingScope"]["caseAnchorAllowed"] is False
    assert candidate["drivingScope"]["productionReady"] is False
    assert candidate["effectiveMateGraphPath"].endswith(
        "/P000/assembly_plan_effective.json"
    )


def test_p000_candidate_is_portable_in_combined_project05_catalog(tmp_path):
    module = _module()
    package = WORKSPACE / ".tmp" / tmp_path.name / "P000"
    module.write_candidate_package(package)
    catalog = module.build_global_module_catalog(
        WORKSPACE,
        additional_semantic_catalog_paths=[
            module.D000_CANDIDATE,
            *(
                module.EXISTING_CANDIDATES / token / "semantic_port_catalog.json"
                for token in ("F000", "M000", "G000")
            ),
            package / "semantic_port_catalog.json",
        ],
    )
    module.validate_global_module_catalog(catalog)
    matches = [
        row
        for row in catalog["connectionTemplates"]
        if row.get("legacyTemplateId") == "P000_to_A000_nonanchor_driving_v2"
    ]
    assert len(matches) == 1
    template = matches[0]
    assert len(template["mateSteps"]) == 4
    compatibility = [
        row
        for row in catalog["compatibility"]
        if row.get("globalTemplateId") == template["globalTemplateId"]
    ]
    assert compatibility
    assert all(row["portableForTemplate"] is True for row in compatibility)
