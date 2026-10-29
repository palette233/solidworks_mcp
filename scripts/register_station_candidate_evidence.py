"""Register one verified candidate in a new station registry, without changing CAD authority."""
import argparse
from copy import deepcopy
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))
from demo_backend.station_rule_registry import read, sha, validate_rule, workspace_file
from demo_backend.station_rule_planner import verify_station_stage
from run_natural_language_staged_chain import write_new


def register(registry_path, plan_path, cad_path, state_path, output):
    if output.exists():
        raise FileExistsError(output)
    registry, plan = read(registry_path), read(plan_path)
    if plan["ruleBinding"]["rule"]["validation"]["status"] != "candidate":
        raise ValueError("Only candidate plans may acquire station evidence")
    scope = read(workspace_file(ROOT, registry["scopePath"]))
    if scope != read(plan["ruleBinding"]["scopePath"]):
        raise ValueError("Scope differs from verified plan")
    result = verify_station_stage(ROOT, plan, cad_result_path=cad_path, saved_state_path=state_path)
    if result.get("cadPassed") is not True or result.get("targetStationValidated") is not True:
        raise ValueError("Current station postcheck did not pass")
    rule = deepcopy(plan["ruleBinding"]["rule"])
    matches = [r for r in registry["rules"] if r["ruleId"] == rule["ruleId"]]
    if len(matches) > 1 or matches and matches[0] != rule:
        raise ValueError("Existing registry rule conflicts with candidate")
    rule["validation"] = {"status": "experimental_cad_verified", "profile": "declared_demo_geometry",
        "kind": "station_plan_current_postcheck", "configurationSha256": sha(workspace_file(ROOT, rule["evaluator"]["inputPath"])),
        "planPath": str(plan_path.resolve()), "cadResultPath": str(cad_path.resolve()), "savedStatePath": str(state_path.resolve())}
    review = validate_rule(ROOT, rule, scope)
    if not review["validatedStationRule"] or review["blockingReasonCodes"]:
        raise ValueError("Registered rule failed evidence validation: " + str(review))
    registry["rules"] = [r for r in registry["rules"] if r["ruleId"] != rule["ruleId"]] + [rule]
    write_new(output, registry)
    return {"ruleId": rule["ruleId"], "stationValidated": True, "newCadExecuted": False,
            "mechanicalReleasePromoted": False, "registry": str(output.resolve())}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("registry", "plan", "cad-result", "state", "output"):
        parser.add_argument("--"+key, required=True, type=Path)
    args = parser.parse_args()
    print(register(args.registry, args.plan, args.cad_result, args.state, args.output))
