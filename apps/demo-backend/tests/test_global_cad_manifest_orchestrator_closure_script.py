import json
from pathlib import Path

from scripts.build_global_cad_manifest_orchestrator_closure import summarize


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_closure_reports_external_placement_and_internal_flexibility(tmp_path: Path):
    job_dir = tmp_path / "job-flex"
    run_dir = job_dir / "run"
    assembly = run_dir / "result.SLDASM"
    assembly.parent.mkdir(parents=True)
    assembly.write_bytes(b"assembly")
    step_evidence = run_dir / "orchestration-step-evidence.json"
    _write(step_evidence, {"schemaVersion": "test"})
    plan = run_dir / "execution-plan.json"
    result = run_dir / "cad-result.json"
    _write(
        plan,
        {
            "effectiveMateGraphExecutionView": {
                "Modules": [
                    {
                        "ModuleToken": "A700",
                        "SolvingStateName": "swComponentFlexibleSolving",
                    }
                ]
            }
        },
    )
    _write(
        result,
        {
            "toolResult": {
                "TargetFullyConstrained": False,
                "TargetConstraintStateAccepted": True,
                "MateSolveClean": True,
                "ComponentSemanticsMatch": True,
            }
        },
    )
    _write(
        job_dir / "job.json",
        {
            "projectId": "project02",
            "status": "succeeded",
            "assemblyStatus": "assembled",
            "collisionStatus": "not_evaluated",
            "plan": {"contextId": "test"},
            "steps": [
                {
                    "stepId": "packet-001",
                    "moduleToken": "A700",
                    "status": "succeeded",
                    "attemptCount": 1,
                    "attempts": [{"durationSeconds": 1.0}],
                    "checkpoint": {
                        "assemblyPath": str(assembly),
                        "evidencePath": str(step_evidence),
                        "cadActionEvidencePaths": [str(plan), str(result)],
                        "collisionStatus": "not_evaluated",
                    },
                }
            ],
            "executionDurationSeconds": 1.0,
            "lastCommittedCheckpoint": {},
        },
    )
    (job_dir / "events.jsonl").write_text(
        json.dumps({"eventType": "job-succeeded"}) + "\n", encoding="utf-8"
    )

    report = summarize(tmp_path, "job-flex")
    semantics = report["steps"][0]["componentSemantics"]
    assert semantics["status"] == "verified"
    assert semantics["externalPlacementStatus"] == "constraint_state_accepted"
    assert semantics["internalFlexibilityDeclared"] is True
    assert semantics["internalFlexibilityPreserved"] is True
    authority = report["parameterAuthority"]
    assert authority["status"] == "registered"
    assert authority["executionGate"] is False
    assert authority["modules"][0]["moduleToken"] == "A700"
    assert authority["modules"][0]["baselineAuthorities"] == [
        "prototype-calibrated"
    ]
