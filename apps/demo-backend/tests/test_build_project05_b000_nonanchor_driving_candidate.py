import importlib.util
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[3]
SCRIPT = WORKSPACE / "scripts/build_project05_b000_nonanchor_driving_candidate.py"


def _module():
    spec = importlib.util.spec_from_file_location("project05_b000_candidate", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_b000_candidate_preserves_flexible_internal_state(tmp_path):
    module = _module()
    package = WORKSPACE / ".tmp" / tmp_path.name / "B000"
    candidate, assessment = module.build_b000_package(package)

    assert assessment["checkpointPassed"] is True
    assert assessment["constraintStateObservation"]["targetFullyConstrained"] is True
    assert assessment["semanticChecks"]["componentSemanticsMatch"] is True
    template = candidate["connectionTemplates"][0]
    assert template["templateId"] == "B000_to_A000_nonanchor_driving_v1"
    assert [row["mateName"] for row in template["mateSteps"]] == [
        "重合37",
        "同心1",
        "平行1",
    ]
    assert template["constraintEffect"]["expectedResidualDof"] == 0
    assert template["constraintEffect"]["internalFlexibilityPreserved"] is True
    assert candidate["drivingScope"]["caseAnchorAllowed"] is False


def test_b000_candidate_merges_all_eight_project05_addons(tmp_path):
    module = _module()
    package = WORKSPACE / ".tmp" / tmp_path.name / "B000"
    module.build_b000_package(package)
    catalog = module.build_combined_catalog(package)

    expected = {
        "B000_to_A000_nonanchor_driving_v1",
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
