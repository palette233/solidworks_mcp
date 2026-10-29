#!/usr/bin/env python3
"""Re-evaluate one station rule against existing immutable CAD evidence.

This recovery is for evaluator improvements that make an old derived report
stale while the underlying saved CAD, mate graph and source files remain
unchanged.  It never runs CAD and never overwrites the original registry or
evidence.  A fresh candidate plan is built with the current evaluator, then
the normal current-state postcheck and registry validator must both pass.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.station_rule_planner import plan_station_chain, verify_station_stage  # noqa: E402
from demo_backend.station_rule_registry import (  # noqa: E402
    read,
    sha,
    validate_rule,
    workspace_file,
)


def _write_new(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def _selection(definition_id: str) -> dict:
    project, token = definition_id.split("::", 1)
    if not project or not token:
        raise ValueError("station rule identity must be project::token")
    return {"projectId": project, "moduleToken": token, "confirmed": True}


def recover(
    *,
    registry_path: Path,
    rule_id: str,
    cad_result_path: Path,
    saved_state_path: Path,
    output_directory: Path,
    output_registry_path: Path,
) -> dict:
    started = time.perf_counter()
    registry_path = registry_path.resolve()
    cad_result_path = cad_result_path.resolve()
    saved_state_path = saved_state_path.resolve()
    output_directory = output_directory.resolve()
    output_registry_path = output_registry_path.resolve()
    for path in (output_directory, output_registry_path):
        if path.exists():
            raise FileExistsError(path)
    original = read(registry_path)
    matches = [row for row in original.get("rules") or [] if row.get("ruleId") == rule_id]
    if len(matches) != 1:
        raise ValueError("station rule does not resolve uniquely")
    old_rule = matches[0]
    old_validation = deepcopy(old_rule.get("validation") or {})
    if old_validation.get("status") not in {"experimental_cad_verified", "released_demo"}:
        raise ValueError("only a previously validated station rule may be recovered")
    candidate_rule = deepcopy(old_rule)
    candidate_rule["validation"] = {"status": "candidate"}
    candidate_registry = deepcopy(original)
    candidate_registry["rules"] = [
        candidate_rule if row.get("ruleId") == rule_id else row
        for row in original["rules"]
    ]
    candidate_registry_path = output_directory / "candidate-registry.json"
    _write_new(candidate_registry_path, candidate_registry)
    request = {
        "chainId": f"recover-{rule_id}",
        "baseRequirement": "重新验证既有目标工位证据，不运行CAD。",
        "baseSelection": _selection(old_rule["targetBaseDefinitionId"]),
        "stationRegistryPath": str(candidate_registry_path.relative_to(ROOT)).replace("\\", "/"),
        "allowPrototypeEstimate": True,
        "placementValidationMode": "target_role_station",
        "steps": [
            {
                "stageId": "recover-station",
                "moduleRole": old_rule["role"],
                "requirement": "使用当前规则重新计算派生几何并核对既有保存实体。",
                "moduleSelection": _selection(old_rule["sourceModuleDefinitionId"]),
                "allowDatumFallback": True,
            }
        ],
    }
    plan_report = plan_station_chain(ROOT, request, prepare_candidates=True)
    if plan_report.get("planningComplete") is not True:
        raise ValueError(
            "current evaluator cannot rebuild station plan: "
            + str(plan_report.get("stages"))
        )
    plan = plan_report["stages"][0]["plan"]
    plan_path = output_directory / "current-evaluator-plan.json"
    _write_new(plan_path, plan)
    postcheck = verify_station_stage(
        ROOT,
        plan,
        cad_result_path=cad_result_path,
        saved_state_path=saved_state_path,
    )
    if (
        postcheck.get("cadPassed") is not True
        or postcheck.get("targetStationValidated") is not True
    ):
        raise ValueError("existing CAD does not pass the current station postcheck")
    postcheck_path = output_directory / "current-evaluator-postcheck.json"
    _write_new(postcheck_path, postcheck)
    recovered_rule = deepcopy(candidate_rule)
    recovered_validation = {
        "status": old_validation["status"],
        "profile": old_validation.get("profile", "declared_demo_geometry"),
        "kind": "station_plan_current_postcheck",
        "configurationSha256": sha(
            workspace_file(ROOT, recovered_rule["evaluator"]["inputPath"])
        ),
        "planPath": str(plan_path.relative_to(ROOT)).replace("\\", "/"),
        "cadResultPath": str(cad_result_path.relative_to(ROOT)).replace("\\", "/"),
        "savedStatePath": str(saved_state_path.relative_to(ROOT)).replace("\\", "/"),
    }
    if old_validation.get("releaseManifestPath"):
        recovered_validation["releaseManifestPath"] = old_validation[
            "releaseManifestPath"
        ]
    recovered_rule["validation"] = recovered_validation
    scope = read(workspace_file(ROOT, original["scopePath"]))
    review = validate_rule(ROOT, recovered_rule, scope)
    if review.get("validatedStationRule") is not True or review.get(
        "blockingReasonCodes"
    ):
        raise ValueError("recovered station rule failed registry validation: " + str(review))
    recovered_registry = deepcopy(original)
    recovered_registry["rules"] = [
        recovered_rule if row.get("ruleId") == rule_id else row
        for row in original["rules"]
    ]
    _write_new(output_registry_path, recovered_registry)
    report = {
        "schemaVersion": "station-rule-postcheck-recovery/v1",
        "ruleId": rule_id,
        "sourceRegistryPath": str(registry_path),
        "sourceRegistrySha256": sha(registry_path),
        "candidateRegistryPath": str(candidate_registry_path),
        "candidateRegistrySha256": sha(candidate_registry_path),
        "currentEvaluatorPlanPath": str(plan_path),
        "currentEvaluatorPlanSha256": sha(plan_path),
        "postcheckPath": str(postcheck_path),
        "postcheckSha256": sha(postcheck_path),
        "cadResultPath": str(cad_result_path),
        "cadResultSha256": sha(cad_result_path),
        "savedStatePath": str(saved_state_path),
        "savedStateSha256": sha(saved_state_path),
        "outputRegistryPath": str(output_registry_path),
        "outputRegistrySha256": sha(output_registry_path),
        "stationValidated": True,
        "newCadExecuted": False,
        "historicalEvidenceOverwritten": False,
        "durationSeconds": time.perf_counter() - started,
        "boundary": (
            "Current evaluator rechecked existing immutable CAD and saved state. "
            "No new CAD, fastening, collision/B-rep or process validation occurred."
        ),
    }
    _write_new(output_directory / "recovery-report.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--rule-id", required=True)
    parser.add_argument("--cad-result", required=True, type=Path)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--output-directory", required=True, type=Path)
    parser.add_argument("--output-registry", required=True, type=Path)
    args = parser.parse_args()
    report = recover(
        registry_path=args.registry,
        rule_id=args.rule_id,
        cad_result_path=args.cad_result,
        saved_state_path=args.state,
        output_directory=args.output_directory,
        output_registry_path=args.output_registry,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
