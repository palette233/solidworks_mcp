"""Exercise generated station candidates through the ordinary planning entry; no CAD."""
import argparse
from pathlib import Path
from time import perf_counter
import run_natural_language_staged_chain as cli


def verify_batch(directory):
    directory = Path(directory).resolve()
    report_path = directory / "planning-verification.json"
    if report_path.exists():
        raise FileExistsError(report_path)
    started, clock, results = cli.now(), perf_counter(), []
    queue = cli.read(directory / "gap-queue.json")
    for row in queue["queue"]:
        if row["status"] != "generated_installation_rule_candidate":
            continue
        source_project, source_token = row["sourceModuleDefinitionId"].split("::")
        base_project, base_token = row["targetBaseDefinitionId"].split("::")
        request = {"chainId": row["ruleId"], "stationRegistryPath": str(directory / "station-rules.json"),
                   "allowPrototypeEstimate": True, "placementValidationMode": "target_role_station",
                   "baseRequirement": "建立已确认基座。",
                   "baseSelection": {"projectId": base_project, "moduleToken": base_token, "confirmed": True},
                   "steps": [{"stageId": "install", "requirement": "按已登记目标工位安装已确认模组。",
                              "stationRuleId": row["ruleId"], "moduleSelection": {
                                  "projectId": source_project, "moduleToken": source_token, "confirmed": True}}]}
        request_path = directory / (row["ruleId"] + "-request.json")
        cli.write_new(request_path, request)
        plan = cli.plan_stations(request_path, directory / (row["ruleId"] + "-planning"))
        results.append({"ruleId": row["ruleId"], "planningComplete": plan["planningComplete"],
                        "blockingStages": [{"stageId": s["stageId"], "reasons": s["blockingReasonCodes"]}
                                           for s in plan["stages"] if not s["planned"]]})
    report = {"startedAtUtc": started, "finishedAtUtc": cli.now(), "durationSeconds": perf_counter()-clock,
              "candidates": results, "passed": bool(results) and all(r["planningComplete"] for r in results),
              "cadExecuted": False, "stationCadValidated": False}
    cli.write_new(report_path, report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    result = verify_batch(args.directory)
    print(result)
    raise SystemExit(0 if result["passed"] else 2)
