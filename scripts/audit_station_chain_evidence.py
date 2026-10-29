"""Read-only audit of committed chains using the existing CAD and station verifiers.

Never starts CAD. Missing checkpoints are failures, not instructions to rerun.
"""
import argparse
from pathlib import Path
from time import perf_counter

import run_natural_language_staged_chain as cli
from demo_backend.functional_chain_closure import build_functional_chain_closure


def audit_chain(directory):
    directory = Path(directory).resolve()
    clock = perf_counter()
    chain = cli.read(directory / "chain.json")
    compilation = cli.read(directory / "compilation.json")
    if cli.sha(directory / "chain.json") != compilation["chainSha256"]:
        raise ValueError("Compiled chain changed")
    stages, proof, roles = [], [], {"Base"}
    for number, stage in enumerate(chain["stages"], 2):
        stage_id = stage["stageId"]
        # Prevent verify_stage_checkpoint's missing-report path from opening CAD.
        index_path = directory / stage_id / "station-postcheck.json"
        if not index_path.is_file():
            raise ValueError("Missing committed station report: " + stage_id)
        closure = cli.read(directory / stage_id / "stage-closure.json")
        if cli.sha(closure["finalAssemblyPath"]) != closure["finalAssemblySha256"]:
            raise ValueError("Saved assembly changed: " + stage_id)
        index = cli.verify_stage_checkpoint(directory, stage_id, closure, expected_count=number)
        state = cli.read(index["savedStatePath"])
        if len(state["observed"]["components"]) != number:
            raise ValueError("Unexpected cumulative component count: " + stage_id)
        plan_path = directory / "station-preparation" / stage_id / "station-plan.json"
        plan = cli.read(plan_path)
        roles.add(plan["ruleBinding"]["rule"]["role"])
        envelope = cli.read(closure["executionEnvelopePath"])
        proof.append({"stageId": stage_id, "cadResultPath": envelope["cadResultPath"],
                      "afterStatePath": index["savedStatePath"]})
        stages.append({"stageId": stage_id, "source": plan["sourceModuleDefinitionId"],
                       "base": plan["targetBaseDefinitionId"],
                       "parametersMeters": plan.get("effectivePositionParametersMeters"),
                       "relationExecutionMode": stage["relationExecutionMode"],
                       "assemblyPath": closure["finalAssemblyPath"],
                       "assemblySha256": closure["finalAssemblySha256"],
                       "savedStatePath": index["savedStatePath"],
                       "savedStateSha256": index["savedStateSha256"],
                       "openWarnings": state["observed"].get("openWarnings"),
                       "cadPassed": True, "proxyGeometryPassed": True, "functionalPassed": None})
    continuity = build_functional_chain_closure(cli.ROOT, stages=proof, required_roles=[])
    if continuity.get("cadPassed") is not True:
        raise ValueError("CAD continuity failed: " + str(continuity))
    return {"chainId": chain["chainId"], "directory": str(directory), "roles": sorted(roles),
            "stages": stages, "cadContinuity": continuity, "durationSeconds": perf_counter()-clock,
            "passed": True, "newCadExecuted": False, "functionalPassed": None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directories", nargs="+", type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    if args.report.exists():
        raise FileExistsError(args.report)
    started, clock, results = cli.now(), perf_counter(), []
    for path in args.directories:
        try:
            results.append(audit_chain(path))
        except (ValueError, OSError, KeyError, TypeError) as exc:
            results.append({"directory": str(path.resolve()), "passed": False,
                            "error": str(exc), "newCadExecuted": False})
    report = {"schemaVersion": "station-chain-evidence-audit/v1", "startedAtUtc": started,
              "finishedAtUtc": cli.now(), "durationSeconds": perf_counter()-clock,
              "chains": results, "passed": all(r["passed"] for r in results),
              "newCadExecuted": False, "functionalPassed": None,
              "collisionOrBrep": "not_evaluated", "actualFastening": "not_verified"}
    cli.write_new(args.report, report)
    print({"passed": report["passed"], "chains": len(results), "seconds": report["durationSeconds"]})
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
