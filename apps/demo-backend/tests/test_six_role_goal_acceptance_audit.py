from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from demo_backend.six_role_goal_acceptance_audit import (
    build_six_role_goal_acceptance_audit,
)


def _write(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _request(chain_id: str, order: list[str], *, plus10: bool = False) -> dict:
    roles = {
        "s01-transport": ("Transport", "project01", "SS00"),
        "s02-scanner": ("Scanner", "project03", "AI00"),
        "s03-calibration": ("Calibration", "project01", "BD00"),
        "s04-cleaning": ("CleaningWeighing", "project01", "GN00"),
        "s05-cup": ("WasteCup", "project05", "P000"),
    }
    steps = []
    for stage_id in order:
        role, project, token = roles[stage_id]
        row = {
            "stageId": stage_id,
            "moduleRole": role,
            "moduleSelection": {
                "projectId": project,
                "moduleToken": token,
                "confirmed": True,
            },
        }
        if role in {"Scanner", "CleaningWeighing", "WasteCup"}:
            row["allowPrototypeEstimate"] = True
        if plus10 and stage_id == "s04-cleaning":
            row["positionParametersMeters"] = {
                "longitudinal": 0.366,
                "lateral": 0.231,
                "supportGap": 0.0,
            }
        steps.append(row)
    return {
        "chainId": chain_id,
        "baseSelection": {
            "projectId": "project03",
            "moduleToken": "AA00",
            "confirmed": True,
        },
        "steps": steps,
    }


def _fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    coverage = _write(
        tmp_path / "coverage.json",
        {
            "schemaVersion": "six-role-station-coverage/v1",
            "summary": {
                "exactPairCount": 68,
                "roleCounts": {
                    "Transport": 4,
                    "Scanner": 4,
                    "Calibration": 4,
                    "CleaningWeighing": 3,
                    "WasteCup": 2,
                },
                "crossProjectPairCount": 51,
                "configuredStationRulePairCount": 33,
                "validatedStationRulePairCount": 17,
            },
            "pairs": [{} for _ in range(68)],
        },
    )
    gap = _write(
        tmp_path / "gap.json",
        {
            "schemaVersion": "station-gap-batch-preparation/v1",
            "summary": {
                "pendingPairCount": 1,
                "workClassCounts": {"engineering_decision": 1},
                "pairClassCounts": {"cross_project_pair": 1},
            },
            "queue": [{}],
            "sourceFiles": [{"path": str(coverage), "sha256": _sha(coverage)}],
        },
    )
    phases = [
        {
            "phaseId": phase_id,
            "totalCount": total,
            "completedCount": 0,
            "status": "ready",
        }
        for phase_id, total in {
            "saved_output_readonly_postchecks": 15,
            "fresh_nonprototype_cad_validations": 2,
            "scanner_current_context_chains": 6,
            "new_six_role_cumulative_chain": 3,
        }.items()
    ]
    closure = _write(
        tmp_path / "closure.json",
        {"status": "ready_for_next_serial_action", "nextAction": {}, "phases": phases},
    )
    chain_specs = [
        (
            "station-aa00-six-role-current-v1",
            [
                "s01-transport",
                "s02-scanner",
                "s03-calibration",
                "s04-cleaning",
                "s05-cup",
            ],
            False,
        ),
        (
            "station-aa00-six-role-reordered-current-v1",
            [
                "s03-calibration",
                "s01-transport",
                "s04-cleaning",
                "s05-cup",
                "s02-scanner",
            ],
            False,
        ),
        (
            "station-aa00-six-role-plus10mm-current-v2",
            [
                "s01-transport",
                "s02-scanner",
                "s03-calibration",
                "s04-cleaning",
                "s05-cup",
            ],
            True,
        ),
    ]
    batch_rows = []
    for index, (chain_id, order, plus10) in enumerate(chain_specs, start=1):
        source = _write(
            tmp_path / f"source-{index}.json", _request(chain_id, order, plus10=plus10)
        )
        generated = _write(tmp_path / f"generated-{index}.json", {"chainId": f"{chain_id}-g"})
        compiled_root = tmp_path / f"chain-{index}" / "compiled"
        chain = _write(
            compiled_root / "chain.json",
            {
                "stages": [{"stageId": stage_id} for stage_id in order],
            },
        )
        for stage_id in order:
            longitudinal = 0.356
            explicit = False
            if plus10 and stage_id == "s04-cleaning":
                longitudinal = 0.366
                explicit = True
            _write(
                compiled_root / "station-preparation" / stage_id / "station-plan.json",
                {
                    "sourceWorldPoseCopied": False,
                    "effectivePositionParametersMeters": {
                        "longitudinal": longitudinal,
                        "lateral": 0.231,
                        "supportGap": 0.0,
                    },
                    "explicitPositionOverride": explicit,
                    "timing": {"durationSeconds": 0.1},
                },
            )
        compilation = _write(
            compiled_root / "compilation.json",
            {
                "chainId": f"{chain_id}-g",
                "chainPath": str(chain),
                "chainSha256": _sha(chain),
                "status": "ready_not_started",
                "cadStarted": False,
                "targetStationPreflightPassed": True,
            },
        )
        batch_rows.append(
            {
                "sourceRequestPath": str(source),
                "sourceRequestSha256": _sha(source),
                "generatedRequestPath": str(generated),
                "generatedRequestSha256": _sha(generated),
                "sourceChainId": chain_id,
                "generatedChainId": f"{chain_id}-g",
                "compilationPath": str(compilation),
                "compilationSha256": _sha(compilation),
                "targetStationPreflightPassed": True,
                "status": "ready_not_started",
                "cadStarted": False,
                "durationSeconds": 1.0,
            }
        )
    batch = _write(
        tmp_path / "batch.json",
        {
            "schemaVersion": "staged-chain-registry-recompilation-batch/v1",
            "chainCount": 3,
            "readyCount": 3,
            "chains": batch_rows,
            "durationSeconds": 3.0,
            "cadStarted": False,
        },
    )
    failure = _write(
        tmp_path / "failure.json",
        {"nextAction": {"chainId": "station-aa00-six-role-current-v1-g"}},
    )
    monkeypatch.setattr(
        "demo_backend.six_role_goal_acceptance_audit.build_staged_chain_execution_batch_status",
        lambda *_: {
            "status": "ready_for_next_chain_action",
            "completedChainCount": 0,
            "runtimeStateCounts": {"ready_not_started": 3},
            "chains": [
                {
                    "chainId": row["generatedChainId"],
                    "outputRoot": str(Path(row["compilationPath"]).parent.relative_to(tmp_path)),
                    "runtimeState": "ready_not_started",
                    "latestAttemptPath": None,
                }
                for row in batch_rows
            ],
        },
    )
    return {
        "coverage": coverage,
        "gap": gap,
        "closure": closure,
        "batch": batch,
        "failure": failure,
    }


def test_current_ready_state_is_incomplete_not_complete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _fixture(tmp_path, monkeypatch)
    report = build_six_role_goal_acceptance_audit(tmp_path, **{
        "coverage_path": paths["coverage"],
        "gap_queue_path": paths["gap"],
        "closure_program_status_path": paths["closure"],
        "acceptance_batch_report_path": paths["batch"],
        "failure_plan_path": paths["failure"],
    })
    assert report["status"] == "incomplete"
    assert report["goalComplete"] is False
    by_id = {row["checkId"]: row for row in report["checks"]}
    assert by_id["coverage_catalog_integrity"]["status"] == "passed"
    assert by_id["acceptance_batch_integrity"]["status"] == "passed"
    assert by_id["ordered_closure_program_complete"]["status"] == "incomplete"
    assert by_id["three_acceptance_chains_completed"]["status"] == "incomplete"


def test_position_variant_is_verified_from_compiled_plans(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _fixture(tmp_path, monkeypatch)
    report = build_six_role_goal_acceptance_audit(
        tmp_path,
        paths["coverage"],
        paths["gap"],
        paths["closure"],
        paths["batch"],
        paths["failure"],
    )
    by_id = {row["checkId"]: row for row in report["checks"]}
    check = by_id["position_variant_is_exactly_plus_10mm"]
    assert check["status"] == "passed"
    assert check["details"]["deltaMeters"]["longitudinal"] == pytest.approx(0.01)


def test_gap_report_digest_drift_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _fixture(tmp_path, monkeypatch)
    paths["coverage"].write_text("{}", encoding="utf-8")
    report = build_six_role_goal_acceptance_audit(
        tmp_path,
        paths["coverage"],
        paths["gap"],
        paths["closure"],
        paths["batch"],
        paths["failure"],
    )
    by_id = {row["checkId"]: row for row in report["checks"]}
    assert by_id["coverage_catalog_integrity"]["status"] == "failed"
    assert by_id["gap_report_binds_current_coverage"]["status"] == "failed"
    assert report["goalComplete"] is False


def test_out_of_scope_prototype_authority_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _fixture(tmp_path, monkeypatch)
    batch = json.loads(paths["batch"].read_text(encoding="utf-8"))
    source_path = Path(batch["chains"][0]["sourceRequestPath"])
    request = json.loads(source_path.read_text(encoding="utf-8"))
    request["steps"][0]["allowPrototypeEstimate"] = True
    _write(source_path, request)
    batch["chains"][0]["sourceRequestSha256"] = _sha(source_path)
    _write(paths["batch"], batch)
    report = build_six_role_goal_acceptance_audit(
        tmp_path,
        paths["coverage"],
        paths["gap"],
        paths["closure"],
        paths["batch"],
        paths["failure"],
    )
    by_id = {row["checkId"]: row for row in report["checks"]}
    assert by_id["three_chain_intents_and_scoped_authority"]["status"] == "failed"


def test_complete_current_evidence_is_the_only_path_to_goal_complete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _fixture(tmp_path, monkeypatch)
    closure = json.loads(paths["closure"].read_text(encoding="utf-8"))
    for phase in closure["phases"]:
        phase["completedCount"] = phase["totalCount"]
        phase["status"] = "complete"
    closure["status"] = "complete"
    closure["nextAction"] = None
    _write(paths["closure"], closure)

    batch = json.loads(paths["batch"].read_text(encoding="utf-8"))
    runtime_rows = []
    for chain_index, row in enumerate(batch["chains"], start=1):
        output_root = Path(row["compilationPath"]).parent
        chain = json.loads((output_root / "chain.json").read_text(encoding="utf-8"))
        for stage_index, stage in enumerate(chain["stages"], start=1):
            stage_id = stage["stageId"]
            stage_root = output_root / stage_id
            assembly = stage_root / "assembly.SLDASM"
            assembly.parent.mkdir(parents=True, exist_ok=True)
            assembly.write_bytes(f"assembly-{chain_index}-{stage_index}".encode())
            reopened = _write(
                stage_root / "reopened-state.json",
                {
                    "success": True,
                    "durationSeconds": 2.0,
                    "observed": {
                        "components": [
                            {"name": f"component-{index}", "isFixed": index == 0}
                            for index in range(6)
                        ]
                    },
                },
            )
            postcheck = _write(
                stage_root / "postcheck.json",
                {
                    "targetStationValidated": True,
                    "timing": {"durationSeconds": 0.2},
                },
            )
            _write(
                stage_root / "stage-closure.json",
                {
                    "status": "passed",
                    "executionDurationSeconds": 3.0,
                    "finalAssemblyPath": str(assembly),
                    "finalAssemblySha256": _sha(assembly),
                },
            )
            _write(
                stage_root / "station-postcheck.json",
                {
                    "targetStationValidated": True,
                    "savedStatePath": str(reopened),
                    "savedStateSha256": _sha(reopened),
                    "postcheckPath": str(postcheck),
                },
            )
        attempts = output_root / "run-attempts"
        if chain_index == 1:
            _write(
                attempts / "attempt-001.json",
                {
                    "success": False,
                    "targetStationValidated": False,
                    "injectedFailureBeforeStage": "s02-scanner",
                    "stages": [
                        {
                            "stageId": "s01-transport",
                            "status": "succeeded",
                            "jobId": "transport-job",
                        },
                        {"stageId": "s02-scanner", "status": "failed"},
                    ],
                },
            )
            latest = _write(
                attempts / "attempt-002.json",
                {
                    "success": True,
                    "targetStationValidated": True,
                    "injectedFailureBeforeStage": None,
                    "stages": [
                        {
                            "stageId": "s01-transport",
                            "status": "reused_committed_checkpoint",
                            "jobId": "transport-job",
                        }
                    ],
                },
            )
        else:
            latest = _write(
                attempts / "attempt-001.json",
                {
                    "success": True,
                    "targetStationValidated": True,
                    "injectedFailureBeforeStage": None,
                    "stages": [],
                },
            )
        runtime_rows.append(
            {
                "chainId": row["generatedChainId"],
                "outputRoot": str(output_root.relative_to(tmp_path)),
                "runtimeState": "completed_target_station_validated",
                "latestAttemptPath": str(latest.relative_to(tmp_path)),
            }
        )
    monkeypatch.setattr(
        "demo_backend.six_role_goal_acceptance_audit.build_staged_chain_execution_batch_status",
        lambda *_: {
            "status": "complete",
            "completedChainCount": 3,
            "runtimeStateCounts": {"completed_target_station_validated": 3},
            "chains": runtime_rows,
        },
    )
    report = build_six_role_goal_acceptance_audit(
        tmp_path,
        paths["coverage"],
        paths["gap"],
        paths["closure"],
        paths["batch"],
        paths["failure"],
    )
    assert report["status"] == "complete"
    assert report["goalComplete"] is True
    assert report["summary"]["passedCount"] == report["summary"]["checkCount"]
    assert all(row["status"] == "passed" for row in report["checks"])
