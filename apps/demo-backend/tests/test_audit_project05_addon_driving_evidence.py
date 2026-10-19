import importlib.util
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[3]
SCRIPT = WORKSPACE / "scripts/audit_project05_addon_driving_evidence.py"


def _module():
    spec = importlib.util.spec_from_file_location("project05_addon_audit", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_project05_addon_audit_fails_closed_until_nonanchor_candidates_are_promoted():
    module = _module()
    catalog = module._read(module.DEFAULT_CATALOG)
    evidence = sorted(
        {
            *module.DEFAULT_EVIDENCE_ROOT.glob(
                "project05-job-*/packet-runs/packet-*/cad-result.json"
            ),
            *(
                path
                for directory in module.DEFAULT_CHECKPOINT_ROOT.glob(
                    "project05-*-checkpoint-v1"
                )
                for path in directory.glob("*.result.json")
            ),
        }
    )
    report = module.build_audit(catalog, evidence)
    by_token = {row["moduleToken"]: row for row in report["targets"]}

    assert report["status"] == "blocked"
    assert report["releaseCandidateCount"] == 0
    assert set(by_token) == {"M000", "F000", "P000", "G000"}
    assert by_token["F000"]["state"] == (
        "semantic_upgrade_required_with_nonanchor_checkpoint"
    )
    assert "TEMPLATE_NOT_DECLARED_CLOSED_WITHOUT_CASE_ANCHOR" in by_token["F000"][
        "blockers"
    ]
    assert "NONPROTOTYPE_INITIAL_POSE_CHECKPOINT_MISSING" not in by_token["F000"][
        "blockers"
    ]
    assert by_token["M000"]["state"] == (
        "semantic_upgrade_required_with_nonanchor_checkpoint"
    )
    assert "NONPROTOTYPE_INITIAL_POSE_CHECKPOINT_MISSING" not in by_token["M000"][
        "blockers"
    ]
    assert by_token["G000"]["state"] == (
        "semantic_upgrade_required_with_nonanchor_checkpoint"
    )
    assert "NONPROTOTYPE_INITIAL_POSE_CHECKPOINT_MISSING" not in by_token["G000"][
        "blockers"
    ]
    selected = by_token["G000"]["evidence"][0]["assessment"]
    assert selected["checkpointPassed"] is True
    assert selected["constraintStateObservation"][
        "acceptedFlexibleInternalState"
    ] is True
    # P000 now has real four-relation evidence, but this audit deliberately
    # targets the historical two-relation source template.  The evidence must
    # therefore be visible yet rejected as incompatible, not reported absent.
    assert by_token["P000"]["state"] == "cad_evidence_blocked"
    assert by_token["P000"]["evidence"]
    assert "TWO_MATE_BUNDLE_REQUIRES_INDEPENDENT_DOF_PROOF" in by_token["P000"][
        "blockers"
    ]
    assert "RIGID_BODY_DOF_NOT_CLOSED" in by_token["P000"]["blockers"]
    assert by_token["P000"]["dofAnalysis"]["constraintRank"] == 4
    assert by_token["P000"]["dofAnalysis"]["residualDof"] == 2
    assert len(by_token["P000"]["dofAnalysis"]["residualDofBasis"]) == 2
