import importlib.util
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[3]
SCRIPT = WORKSPACE / "scripts/build_project05_nonanchor_driving_candidate.py"


def _module():
    spec = importlib.util.spec_from_file_location("project05_nonanchor_candidate", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_f000_checkpoint_can_promote_a_closed_nonanchor_candidate(tmp_path):
    module = _module()
    package = WORKSPACE / ".tmp" / tmp_path.name / "F000"
    candidate, assessment = module.build_candidate(
        "F000", module.SUPPORTED["F000"], package
    )

    template = candidate["connectionTemplates"][0]
    assert assessment["checkpointPassed"] is True
    assert template["templateId"] == "F000_to_A000_nonanchor_driving_v1"
    assert template["constraintEffect"]["fullyLocatesAddedComponent"] is True
    assert template["constraintEffect"]["expectedResidualDof"] == 0
    assert candidate["drivingScope"]["caseAnchorAllowed"] is False
    assert candidate["effectiveMateGraphPath"].endswith(
        "/F000/assembly_plan_effective.json"
    )


def test_f000_and_m000_candidates_can_share_one_catalog(tmp_path):
    module = _module()
    root = WORKSPACE / ".tmp" / tmp_path.name / "multi"
    rows = []
    for target in ("F000", "M000"):
        candidate, assessment = module.build_candidate(
            target, module.SUPPORTED[target], root / target
        )
        rows.append(candidate)
        assert assessment["checkpointPassed"] is True

    catalog = module.build_global_module_catalog(
        WORKSPACE,
        additional_semantic_catalog_paths=[
            module.D000_CANDIDATE_SEMANTIC,
            root / "F000" / "semantic_port_catalog.json",
            root / "M000" / "semantic_port_catalog.json",
        ],
    )
    module.validate_global_module_catalog(catalog)

    assert {
        row["connectionTemplates"][0]["templateId"] for row in rows
    } == {
        "F000_to_A000_nonanchor_driving_v1",
        "M000_to_A000_nonanchor_driving_v1",
    }
    assert all(
        row["connectionTemplates"][0]["constraintEffect"][
            "expectedResidualDof"
        ]
        == 0
        for row in rows
    )
    candidate_ids = {
        row.get("legacyTemplateId") for row in catalog["connectionTemplates"]
    }
    assert "F000_to_A000_nonanchor_driving_v1" in candidate_ids
    assert "M000_to_A000_nonanchor_driving_v1" in candidate_ids
