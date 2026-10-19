from __future__ import annotations

from copy import deepcopy

from demo_backend.global_manifest_job_user_summary import (
    build_global_manifest_job_user_summary,
    render_global_manifest_job_user_summary_markdown,
    write_global_manifest_job_user_summary,
)


def _job() -> dict:
    return {
        "schemaVersion": "ordered-assembly-job/v2",
        "jobId": "job-cross-project",
        "status": "succeeded",
        "assemblyStatus": "assembled",
        "collisionStatus": "not_evaluated",
        "startedAt": "2026-10-12T01:00:00Z",
        "completedAt": "2026-10-12T01:02:00Z",
        "plan": {
            "contextId": "project01-jj00-project03-ae00-transport-v1",
            "relationReleaseBinding": {
                "releaseId": "release-v43",
                "catalogDigest": "catalog-digest",
                "authorizedDrivingTemplateIds": ["template/cross-project/transport"],
            },
            "releaseAuthority": {"status": "verified"},
            "commandAudit": {
                "payload": {
                    "commandCount": 2,
                    "mappedCommandCount": 2,
                    "commands": [
                        {
                            "requirement": "先添加Project01 JJ00箱体作为基座。",
                            "moduleInstances": [
                                {
                                    "instanceId": "jj00-1",
                                    "displayName": "箱体",
                                }
                            ],
                            "connections": [],
                        },
                        {
                            "requirement": "安装Project03 AE00传输模组。",
                            "moduleInstances": [
                                {
                                    "instanceId": "ae00-1",
                                    "displayName": "传输模组",
                                }
                            ],
                            "connections": [
                                {
                                    "connectionId": "connection-001",
                                    "globalTemplateId": "template/cross-project/transport",
                                    "purpose": "installation",
                                    "instanceAId": "ae00-1",
                                    "instanceBId": "jj00-1",
                                    "portA": {
                                        "globalPortId": "module::port/ae00-frame-installation"
                                    },
                                    "portB": {
                                        "globalPortId": "module::port/jj00-transport-installation"
                                    },
                                    "singleTemplateExpectedResidualDof": 0,
                                    "cadPacketId": "packet-001",
                                }
                            ],
                        },
                    ],
                }
            },
        },
        "steps": [
            {
                "stepId": "packet-001",
                "moduleToken": "AE00",
                "operation": "INSERT_AND_CONNECT",
                "status": "succeeded",
                "attempts": [{"durationSeconds": 122.1}],
                "checkpoint": {
                    "assemblyPath": "D:/demo/result.SLDASM",
                    "timingBreakdown": {
                        "baseWrapperCacheStatus": "hit",
                        "estimatedPreparationSecondsAvoided": 152.3,
                    },
                },
            }
        ],
    }


def _cad_result() -> dict:
    return {
        "success": True,
        "durationSeconds": 101.3,
        "toolResult": {
            "Success": True,
            "RequestedMateCount": 3,
            "CreatedMateCount": 3,
            "TargetFullyConstrained": True,
            "TargetConstraintStateAccepted": True,
            "MateSolveClean": True,
            "Reopened": True,
            "ReopenedMateParametersMatch": True,
        },
    }


def test_builds_compact_passed_summary_with_explicit_collision_boundary():
    summary = build_global_manifest_job_user_summary(
        _job(),
        cad_results_by_step={"packet-001": _cad_result()},
        preflight={"naturalLanguageCompilation": {"totalSeconds": 0.128}},
    )

    assert summary["status"] == "passed"
    assert summary["naturalLanguageCommands"] == [
        "先添加Project01 JJ00箱体作为基座。",
        "安装Project03 AE00传输模组。",
    ]
    assert len(summary["moduleInstances"]) == 2
    assert summary["connections"][0]["sourcePortId"].endswith(
        "ae00-frame-installation"
    )
    assert summary["connections"][0]["targetPortId"].endswith(
        "jj00-transport-installation"
    )
    assert summary["cadSteps"][0]["createdMateCount"] == 3
    assert summary["cadSteps"][0]["cadPassed"] is True
    assert summary["resultAssemblyPath"] == "D:/demo/result.SLDASM"
    assert summary["timingSeconds"]["jobExecution"] == 120.0
    assert summary["collisionStatus"] == "not_evaluated"
    assert summary["claims"]["collisionOrBrepPassed"] is False

    markdown = render_global_manifest_job_user_summary_markdown(summary)
    assert "先添加Project01 JJ00箱体作为基座" in markdown
    assert "ae00-frame-installation" in markdown
    assert "not_evaluated" in markdown
    assert "不包含实体干涉或B-rep通过声明" in markdown


def test_incomplete_mate_creation_cannot_be_reported_as_passed():
    cad_result = deepcopy(_cad_result())
    cad_result["toolResult"]["CreatedMateCount"] = 2

    summary = build_global_manifest_job_user_summary(
        _job(), cad_results_by_step={"packet-001": cad_result}
    )

    assert summary["status"] == "not_passed"
    assert summary["cadSteps"][0]["cadPassed"] is False
    assert summary["claims"]["cadLifecyclePassed"] is False
    assert summary["userFailureExplanation"]["reasonCode"] == (
        "CAD_EXECUTION_FAILED"
    )

    markdown = render_global_manifest_job_user_summary_markdown(summary)
    assert "未通过原因" in markdown
    assert "CAD_EXECUTION_FAILED" in markdown


def test_writer_materializes_json_and_markdown(tmp_path):
    cad_path = tmp_path / "cad-result.json"
    import json

    cad_path.write_text(json.dumps(_cad_result()), encoding="utf-8")
    job = _job()
    job["steps"][0]["checkpoint"]["cadActionEvidencePaths"] = [str(cad_path)]

    written = write_global_manifest_job_user_summary(job, tmp_path)

    assert written["status"] == "passed"
    assert (tmp_path / "user-summary.json").is_file()
    assert (tmp_path / "user-summary.md").is_file()
