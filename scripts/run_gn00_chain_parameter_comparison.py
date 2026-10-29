"""Validate the 354 -> 364 mm GN00 parameter edit on a four-module checkpoint.

This deliberately executes the existing CAD runner and read-only verifier;
there is no alternate assembly implementation here. Existing failed evidence
is preserved, and successful artifacts can only be reused after hash checks.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))
from demo_backend.datum_chain_verification import compare_cad_states

DEFAULT_EXPERIMENT = ROOT / "demo/cross_project_substitution/six-role-gn00-datum-20261024-v1"
OLD_PREFIX = "MCP_GRAPH_MCP_IFACE_F6B58DD2_"
NEW_PREFIX = "MCP_GRAPH_MCP_IFACE_149A9DB3_"
NAME_MAP = {OLD_PREFIX + suffix: NEW_PREFIX + suffix for suffix in ("LONGITUDINAL", "LATERAL", "SUPPORT")}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()


def write_new(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def resolve_stage(closure_path):
    closure = read(closure_path)
    if (closure.get("status") != "passed" or not closure.get("checks")
            or not all(value is True for value in closure["checks"].values())
            or closure.get("closureDigest") != digest({key: value for key, value in closure.items() if key != "closureDigest"})):
        raise ValueError("Stage closure is not passed or its digest changed")
    output = Path(closure["finalAssemblyPath"])
    envelope_path = Path(closure["executionEnvelopePath"])
    if sha(output) != closure["finalAssemblySha256"] or sha(envelope_path) != closure["executionEnvelopeSha256"]:
        raise ValueError("Stage output or execution envelope changed")
    envelope = read(envelope_path)
    cad_path = Path(envelope["cadResultPath"])
    cad = read(cad_path)
    if (envelope.get("success") is not True or cad.get("success") is not True
            or Path(cad["outputAssemblyPath"]).resolve() != output.resolve()
            or cad.get("outputAssemblySha256") != closure["finalAssemblySha256"]):
        raise ValueError("Stage CAD result does not identify its committed assembly")
    return output, cad_path, closure


def verify_insert_result(path, source, graph, output):
    cad = read(path)
    tool = cad.get("toolResult") or {}
    checks = {
        "success": cad.get("success") is True and tool.get("Success") is True,
        "sourcePath": Path(cad.get("sourceAssemblyPath", "")).resolve() == source.resolve(),
        "sourceUnchanged": cad.get("sourceAssemblyUnchanged") is True
            and cad.get("sourceAssemblySha256Before") == cad.get("sourceAssemblySha256After") == sha(source),
        "graphBound": cad.get("effectiveGraphSha256") == sha(graph),
        "outputBound": Path(cad.get("outputAssemblyPath", "")).resolve() == output.resolve()
            and cad.get("outputAssemblySha256") == sha(output),
        "threeMates": tool.get("RequestedMateCount") == tool.get("CreatedMateCount") == 3,
        "targetUnanchored": tool.get("TargetCaseAnchored") is False
            and tool.get("RequestedTargetLeafPoseAnchorCount") == tool.get("AppliedTargetLeafPoseAnchorCount") == 0,
        "fullyConstrained": tool.get("TargetFullyConstrained") is True and tool.get("TargetConstraintStateAccepted") is True,
        "savedReopened": tool.get("Reopened") is True and tool.get("ReopenedMateParametersMatch") is True,
        "mateSolveClean": tool.get("MateSolveClean") is True,
        "cleanSession": cad.get("outputClosedAfterVerification") is True and cad.get("targetSourceSessionClean") is True,
    }
    if not all(checks.values()):
        raise ValueError("Existing CAD evidence is failed or stale: " + str(checks))
    return cad


def verify_readonly_report(path, output, source):
    state = read(path)
    if (state.get("success") is not True or state.get("assemblySha256") != sha(output)
            or Path(state.get("assemblyPath", "")).resolve() != output.resolve()
            or state.get("sourceCheckpointSha256Before") != state.get("sourceCheckpointSha256After")
            or state.get("sourceCheckpointSha256Before") != sha(source)
            or len(state.get("observed", {}).get("components", [])) != 5
            or len(state.get("sourceObserved", {}).get("components", [])) != 4):
        raise ValueError("Read-only report is failed, stale, or not the expected 4 -> 5 module append")
    source_state = {"success": True, "observed": state["sourceObserved"]}
    preservation = compare_cad_states(source_state, state, base_token="AA00", added_token="GN00")
    if not preservation["success"]:
        raise ValueError("Original four components or nine mates were changed: " + str(preservation["checks"]))
    if (len(state["sourceObserved"]["allTopLevelMates"]) != 9
            or len(state["observed"]["allTopLevelMates"]) != 12):
        raise ValueError("Expected nine unchanged mates plus exactly three new mates")
    return state, preservation


def run_phase(name, command, directory, phases, timeout):
    path = directory / f"{name}.execution.json"
    if path.exists():
        raise FileExistsError(f"Preserving prior invocation evidence: {path}")
    started_at, clock = datetime.now(timezone.utc).isoformat(), perf_counter()
    try:
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=timeout)
        record = {"phase": name, "startedAtUtc": started_at,
                  "finishedAtUtc": datetime.now(timezone.utc).isoformat(), "durationSeconds": perf_counter() - clock,
                  "command": command, "returnCode": completed.returncode,
                  "stdout": completed.stdout.decode("utf-8", errors="replace"),
                  "stderr": completed.stderr.decode("utf-8", errors="replace")}
    except subprocess.TimeoutExpired as exc:
        record = {"phase": name, "startedAtUtc": started_at,
                  "finishedAtUtc": datetime.now(timezone.utc).isoformat(), "durationSeconds": perf_counter() - clock,
                  "command": command, "returnCode": None, "error": str(exc)}
    write_new(path, record)
    phases.append({key: value for key, value in record.items() if key not in ("stdout", "stderr", "command")})
    if record["returnCode"] != 0:
        raise RuntimeError(f"{name} failed; preserved diagnostics at {path}")


def execute(experiment, output_dir, timeout, direct_stdio):
    source, _, source_closure = resolve_stage(experiment / "standard-v2/s03-bd00/stage-closure.json")
    default_output, default_cad, default_closure = resolve_stage(experiment / "standard-v2/s04-gn00/stage-closure.json")
    graph = experiment / "parameter-change/effective-mate-graph.json"
    payload = read(graph)
    expected = {name.removeprefix("MCP_GRAPH_") for name in NAME_MAP.values()}
    mates = {row["MateName"]: row for row in payload["Mates"]}
    if (set(mates) != expected or mates[NEW_PREFIX.removeprefix("MCP_GRAPH_") + "LONGITUDINAL"]["Distance"] != .364
            or payload.get("EditPolicy", {}).get("initialPlacementMode") != "deterministic"
            or payload.get("EditPolicy", {}).get("fixedModuleTokens") != ["AA00"]
            or payload.get("CaseAnchor") or payload.get("TargetLeafPoseAnchors")):
        raise ValueError("Not the expected unanchored 364 mm GN00 candidate graph")
    output_dir.mkdir(parents=True, exist_ok=True)
    output, cad_path = output_dir / "gn00-364mm-five-modules.SLDASM", output_dir / "cad-result.json"
    comparison_path = output_dir / "comparison.json"
    before_path, after_path = output_dir / "default-five-readonly.json", output_dir / "changed-five-readonly.json"
    if comparison_path.exists():
        old = read(comparison_path)
        if old.get("success") is not True:
            raise FileExistsError("Previous failure is preserved; select a new --output-dir for a new attempt")
        if any(old.get(key) != sha(path) for key, path in (
            ("sourceCheckpointSha256", source), ("defaultAssemblySha256", default_output),
            ("outputAssemblySha256", output), ("effectiveGraphSha256", graph),
        )):
            raise ValueError("Previously successful comparison artifact binding changed")
        verify_insert_result(cad_path, source, graph, output)
        before, _ = verify_readonly_report(before_path, default_output, source)
        after, _ = verify_readonly_report(after_path, output, source)
        rechecked = compare_cad_states(before, after, base_token="AA00", moved_token="GN00",
            expected_displacement_meters=[.010, 0., 0.], mate_name_map=NAME_MAP,
            expected_parameter_changes={OLD_PREFIX + "LONGITUDINAL": (.354, .364)})
        if not rechecked["success"]:
            raise ValueError("Previously successful comparison no longer validates")
        return old
    phases, clock = [], perf_counter()
    report = {"schemaVersion": "gn00-cumulative-parameter-comparison/v1", "success": False,
              "startedAtUtc": datetime.now(timezone.utc).isoformat(), "phases": phases,
              "sourceCheckpointPath": str(source), "sourceCheckpointSha256": sha(source),
              "defaultAssemblyPath": str(default_output), "defaultAssemblySha256": sha(default_output),
              "outputAssemblyPath": str(output), "effectiveGraphPath": str(graph), "effectiveGraphSha256": sha(graph),
              "expectedDisplacementMeters": [.010, 0., 0.],
              "baseToken": "AA00", "movedToken": "GN00",
              "sourceClosureDigest": source_closure["closureDigest"], "defaultClosureDigest": default_closure["closureDigest"],
              "collisionOrBrep": "not_evaluated", "actualFasteningMethod": "not_verified"}
    try:
        if cad_path.exists() or output.exists():
            cad = verify_insert_result(cad_path, source, graph, output)
            phases.append({"phase": "cad-insert", "reusedValidatedEvidence": True, "durationSeconds": 0})
        else:
            command = [sys.executable, str(ROOT / "scripts/run_context_mate_graph_insert.py"),
                "--source", str(source), "--effective", str(graph), "--output", str(output),
                "--target", "GN00", "--expected-source-sha256", sha(source),
                "--expected-effective-sha256", sha(graph), "--result", str(cad_path), "--timeout", str(timeout)]
            if direct_stdio:
                command.append("--direct-stdio")
            run_phase("cad-insert", command, output_dir, phases, timeout + 60)
            cad = verify_insert_result(cad_path, source, graph, output)
        states, preservations = [], []
        for name, cad_result, path, assembly in (
            ("default-readonly", default_cad, before_path, default_output),
            ("changed-readonly", cad_path, after_path, output),
        ):
            if not path.exists():
                run_phase(name, [sys.executable, str(ROOT / "scripts/verify_datum_chain_live_state.py"),
                    "--cad-result", str(cad_result), "--report", str(path), "--count", "5",
                    "--source", str(source), "--base", "AA00"], output_dir, phases, 360)
            else:
                phases.append({"phase": name, "reusedValidatedEvidence": True, "durationSeconds": 0})
            state, preservation = verify_readonly_report(path, assembly, source)
            states.append(state)
            preservations.append(preservation)
        comparison = compare_cad_states(*states, base_token="AA00", moved_token="GN00",
            expected_displacement_meters=[.010, 0., 0.], mate_name_map=NAME_MAP,
            expected_parameter_changes={OLD_PREFIX + "LONGITUDINAL": (.354, .364)})
        report.update(comparison)
        report.update({"schemaVersion": "gn00-cumulative-parameter-comparison/v1",
                       "sourcePreservation": preservations, "readOnlyReportPaths": [str(before_path), str(after_path)],
                       "cadDurationSeconds": cad["durationSeconds"],
                       "cadPhaseSeconds": cad["toolResult"].get("PhaseDurationsSeconds"),
                       "outputAssemblySha256": sha(output)})
    except Exception as exc:
        report["success"], report["error"] = False, f"{type(exc).__name__}: {exc}"
    report["finishedAtUtc"], report["durationSeconds"] = datetime.now(timezone.utc).isoformat(), perf_counter() - clock
    write_new(comparison_path, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-root", type=Path, default=DEFAULT_EXPERIMENT)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--timeout", type=float, default=600.)
    parser.add_argument("--direct-stdio", action="store_true")
    args = parser.parse_args()
    experiment = args.experiment_root.resolve()
    report = execute(experiment, (args.output_dir or experiment / "parameter-change").resolve(), args.timeout, args.direct_stdio)
    print(json.dumps({"success": report["success"], "durationSeconds": report.get("durationSeconds"),
                      "checks": report.get("checks"), "error": report.get("error")}, ensure_ascii=False, indent=2))
    return 0 if report["success"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
