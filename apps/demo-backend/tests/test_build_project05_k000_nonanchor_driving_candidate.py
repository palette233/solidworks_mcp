import importlib.util
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[3]
SCRIPT = WORKSPACE / "scripts/build_project05_k000_nonanchor_driving_candidate.py"


def _module():
    spec = importlib.util.spec_from_file_location("project05_k000_candidate", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_k000_candidate_uses_nonanchor_three_relation_checkpoint(tmp_path):
    module = _module()
    package = WORKSPACE / ".tmp" / tmp_path.name / "K000"
    candidate, assessment = module.build_k000_package(package)

    assert assessment["checkpointPassed"] is True
    template = candidate["connectionTemplates"][0]
    assert template["templateId"] == "K000_to_A000_nonanchor_driving_v1"
    assert [row["mateName"] for row in template["mateSteps"]] == [
        "重合4",
        "平行2",
        "同心5",
    ]
    assert template["constraintEffect"]["expectedResidualDof"] == 0
    assert candidate["drivingScope"]["caseAnchorAllowed"] is False


def test_k000_candidate_merges_with_six_existing_project05_templates(tmp_path):
    module = _module()
    package = WORKSPACE / ".tmp" / tmp_path.name / "K000"
    module.build_k000_package(package)
    catalog = module.build_combined_catalog(package)

    expected = {
        "D000_to_A000_scoped_driving_v2",
        "F000_to_A000_nonanchor_driving_v1",
        "G000_to_A000_nonanchor_driving_v1",
        "K000_to_A000_nonanchor_driving_v1",
        "M000_to_A000_nonanchor_driving_v1",
        "N000_to_A000_nonanchor_driving_v2",
        "P000_to_A000_nonanchor_driving_v2",
    }
    observed = {
        row.get("legacyTemplateId")
        for row in catalog["connectionTemplates"]
        if row.get("legacyTemplateId") in expected
    }
    assert observed == expected
