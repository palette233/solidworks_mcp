"""Append one explicitly experimental datum candidate using existing CAD tools.

This is not a release-authority bypass for normal jobs: it writes a separate
experiment, never promotes a template, and keeps functional acceptance unknown.
The source checkpoint is immutable; a failed attempt keeps its own diagnostics.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
IDENTITY = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def validate_graph(graph, base, target):
    policy = graph.get("EditPolicy") or {}
    anchor_policy = graph.get("BaseGraphPolicy") or {}
    if (policy.get("initialPlacementMode") != "deterministic"
            or policy.get("baseModuleToken") != base
            or policy.get("fixedModuleTokens") != [base]
            or policy.get("caseAnchoredModuleTokens") or policy.get("targetLeafPoseAnchors")
            or policy.get("fixCaseAnchorBeforeMates") is not False
            or graph.get("CaseAnchor") is not None or graph.get("TargetLeafPoseAnchors")
            or any(anchor_policy.get(key) is not False for key in
                   ("caseAnchorAllowed", "prototypeTopLevelTargetPoseAllowed", "targetLeafPoseAnchorsAllowed"))):
        raise ValueError("Experiment requires deterministic placement, one fixed base and no anchors")
    if type(policy.get("initialPlacementVariant")) is not int or policy["initialPlacementVariant"] < 0:
        raise ValueError("A nonnegative deterministic initial placement variant is required")
    modules = graph.get("Modules") or []
    if len(modules) != 2 or {m["ModuleToken"] for m in modules} != {base, target}:
        raise ValueError("Expected an explicit two-module candidate graph")
    moving = next(m for m in modules if m["ModuleToken"] == target)
    if type(moving.get("SolvingState")) is not int or moving["SolvingState"] != 0:
        raise ValueError("This experiment supports rigid external modules only")
    transform = moving.get("SourceTransform")
    if (not isinstance(transform, list) or len(transform) != 16
            or any(type(value) not in (int, float) or not math.isfinite(value) or abs(value - expected) > 1e-10
                   for value, expected in zip(transform, IDENTITY))):
        raise ValueError("Target source transform must be an identity placeholder, not a source pose")
    mates = graph.get("Mates") or []
    if len(mates) != 3 or any(m.get("IsSuppressed", False) for m in mates):
        raise ValueError("Expected three active datum mates")
    if any(set(m.get("ModuleTokens", [])) != {base, target} for m in mates):
        raise ValueError("Every driving mate must connect the selected target to this base")
    mate_types = [(m.get("MateType"), m.get("MateTypeName")) for m in mates]
    if (mate_types.count((0, "swMateCOINCIDENT")) != 1 or mate_types.count((5, "swMateDISTANCE")) != 2
            or any(type(m.get("MateType")) is not int for m in mates)):
        raise ValueError("Expected one coincident support and two distance datum mates")
    by_token = {module["ModuleToken"]: module for module in modules}
    normals = {base: [], target: []}
    if len({mate.get("MateName") for mate in mates}) != 3 or any(not mate.get("MateName") for mate in mates):
        raise ValueError("Datum mate names must be present and unique")
    for mate in mates:
        if type(mate.get("Alignment")) is not int or mate["Alignment"] not in (0, 1):
            raise ValueError("Datum alignment must be explicit")
        if mate["MateType"] == 5:
            value = mate.get("Distance")
            flip = (mate.get("AdvancedOptions") or {}).get("DistanceFlipDimension", False)
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0 or type(flip) is not bool:
                raise ValueError("Datum distance/flip must be finite nonnegative metres and a boolean")
        endpoints = mate.get("Endpoints") or []
        if len(endpoints) != 2 or {ep.get("ModuleToken") for ep in endpoints} != {base, target}:
            raise ValueError("Driving endpoint identities do not bind this pair")
        for endpoint in endpoints:
            token = endpoint["ModuleToken"]
            module = by_token[token]
            normal = endpoint.get("FaceNormalWorld")
            if (endpoint.get("GeometryType") != "Face" or endpoint.get("SurfaceType") not in (None, "Plane")
                    or endpoint.get("ModuleHierarchyPath") != module.get("HierarchyPath")
                    or not endpoint.get("RelativeLeafHierarchyPath") or not endpoint.get("LeafComponentPath")
                    or not endpoint.get("SourceAssemblyPersistentReferenceBase64")
                    or not isinstance(normal, list) or len(normal) != 3
                    or any(type(value) not in (int, float) or not math.isfinite(value) for value in normal)
                    or abs(sum(value * value for value in normal) - 1) > 1e-7):
                raise ValueError("Every datum needs an identified real planar leaf face and unit normal")
            normals[token].append(normal)
    for frame in normals.values():
        if any(abs(sum(a * b for a, b in zip(frame[i], frame[j]))) > 1e-7 for i in range(3) for j in range(i)):
            raise ValueError("Three datum normals must be orthogonal within each module")


def validate_cad_result(cad, *, source, graph, output, source_sha, graph_sha, target, variant):
    tool = cad.get("toolResult") or {}
    required = ("Success", "IndependentComponentInserted", "Reopened", "ReopenedMateParametersMatch",
                "TargetFullyConstrained", "MateSolveClean", "ComponentSemanticsMatch")
    diagnostics = tool.get("Diagnostics") or []
    if (cad.get("success") is not True or not all(tool.get(key) is True for key in required)
            or tool.get("TargetModuleToken") != target or tool.get("TargetCaseAnchored") is not False
            or tool.get("RequestedTargetLeafPoseAnchorCount") != 0 or tool.get("AppliedTargetLeafPoseAnchorCount") != 0
            or tool.get("CreatedMateCount") != 3 or tool.get("RequestedMateCount") != 3
            or not any(isinstance(row, str) and row.startswith(f"Deterministic non-source placement variant={variant},") for row in diagnostics)):
        raise ValueError("CAD did not prove independent nonprototype, unanchored three-datum save/reopen")
    if (Path(cad.get("sourceAssemblyPath", "")).resolve() != source
            or cad.get("sourceAssemblySha256Before") != source_sha or cad.get("sourceAssemblySha256After") != source_sha
            or Path(cad.get("executionEffectiveGraphPath", "")).resolve() != graph
            or cad.get("executionEffectiveGraphSha256") != graph_sha
            or Path(cad.get("outputAssemblyPath", "")).resolve() != output
            or cad.get("outputAssemblySha256") != sha(output)):
        raise ValueError("Actual CAD source/graph/output differs from the explicitly confirmed experiment")


def validate_state(state, *, source, output, source_sha, source_count, base, target, graph):
    if (state.get("success") is not True or state.get("observed", {}).get("readOnly") is not True
            or not state.get("checks") or not all(value is True for value in state["checks"].values())
            or Path(state.get("assemblyPath", "")).resolve() != output or state.get("assemblySha256") != sha(output)
            or Path(state.get("sourceCheckpointPath", "")).resolve() != source
            or state.get("sourceCheckpointSha256Before") != source_sha or state.get("sourceCheckpointSha256After") != source_sha
            or state.get("sourceObserved", {}).get("readOnly") is not True):
        raise ValueError("Actual readonly source/output evidence is missing or inconsistent")
    before = state["sourceObserved"].get("components") or []
    after = state["observed"].get("components") or []
    if len(before) != source_count or len(after) != source_count + 1:
        raise ValueError("Actual source/output component counts differ from the append request")
    modules = {row["ModuleToken"]: row for row in graph["Modules"]}
    def matches(rows, token):
        return [row for row in rows if Path(row.get("sourcePath", "")).resolve() == Path(modules[token]["Path"]).resolve()]
    if len(matches(before, base)) != 1 or matches(before, target) or any(len(matches(after, token)) != 1 for token in (base, target)):
        raise ValueError("Actual source must contain the exact base and no preexisting target; output must contain both")


def run_phase(name, command, directory, report, timeout):
    started, clock = datetime.now(timezone.utc).isoformat(), perf_counter()
    row = {"name": name, "startedAtUtc": started, "command": command}
    try:
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=timeout)
        row.update(returnCode=completed.returncode,
                   stdout=completed.stdout.decode("utf-8", errors="replace"),
                   stderr=completed.stderr.decode("utf-8", errors="replace"))
    except subprocess.TimeoutExpired as exc:
        def decoded(value):
            return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value or ""
        row.update(returnCode=None, error=str(exc), timeout=True, stdout=decoded(exc.stdout), stderr=decoded(exc.stderr))
    except OSError as exc:
        row.update(returnCode=None, error=str(exc), launchFailed=True)
    row.update(finishedAtUtc=datetime.now(timezone.utc).isoformat(), durationSeconds=perf_counter()-clock)
    with (directory / f"{name}.execution.json").open("x", encoding="utf-8") as stream:
        json.dump(row, stream, ensure_ascii=False, indent=2)
    report["phases"].append({k: v for k, v in row.items() if k not in {"command", "stdout", "stderr"}})
    print(json.dumps(report["phases"][-1], ensure_ascii=False), flush=True)
    if row["returnCode"] != 0:
        raise RuntimeError(f"{name} failed; inspect its execution.json; source checkpoint was not replaced")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for flag in ("source", "graph", "output-dir"):
        p.add_argument("--"+flag, type=Path, required=True)
    p.add_argument("--expected-source-sha256", required=True)
    p.add_argument("--expected-graph-sha256", required=True)
    p.add_argument("--target", required=True)
    p.add_argument("--base", default="AA00")
    p.add_argument("--source-count", type=int, required=True)
    p.add_argument("--allow-demo-estimate", action="store_true")
    p.add_argument("--timeout", type=float, default=360)
    a = p.parse_args()
    if not a.allow_demo_estimate:
        p.error("Explicit --allow-demo-estimate is required; this does not publish or approve engineering feasibility")
    if a.source_count < 1 or not math.isfinite(a.timeout) or a.timeout <= 0:
        raise ValueError("Positive source count and timeout required")
    source, graph, directory = a.source.resolve(), a.graph.resolve(), a.output_dir.resolve()
    if sha(source) != a.expected_source_sha256 or sha(graph) != a.expected_graph_sha256:
        raise ValueError("Confirmed source or candidate graph changed")
    graph_payload = read(graph)
    validate_graph(graph_payload, a.base, a.target)
    directory.mkdir(parents=True, exist_ok=False)
    output, cad, state = directory / "assembly.SLDASM", directory / "cad-result.json", directory / "reopened-state.json"
    clock = perf_counter()
    report = {"schemaVersion": "target-station-candidate-append/v1", "success": False,
              "startedAtUtc": datetime.now(timezone.utc).isoformat(), "phases": [],
              "sourceAssemblyPath": str(source), "sourceAssemblySha256": a.expected_source_sha256,
              "graphPath": str(graph), "graphSha256": a.expected_graph_sha256,
              "outputAssemblyPath": str(output), "cadResultPath": str(cad), "statePath": str(state),
              "target": a.target, "expectedComponentCount": a.source_count+1,
              "functionalAcceptance": None, "published": False, "demoEstimateExplicitlyAuthorized": True,
              "collisionOrBrep": "not_evaluated", "actualFastening": "not_verified"}
    try:
        if sha(source) != a.expected_source_sha256 or sha(graph) != a.expected_graph_sha256:
            raise ValueError("Confirmed inputs changed before CAD launch")
        run_phase("cad-append", [sys.executable, "-X", "utf8", str(ROOT/"scripts/run_context_mate_graph_insert.py"),
            "--source", str(source), "--effective", str(graph), "--output", str(output), "--target", a.target,
            "--expected-source-sha256", a.expected_source_sha256, "--expected-effective-sha256", a.expected_graph_sha256,
            "--result", str(cad), "--direct-stdio", "--timeout", str(a.timeout)], directory, report, a.timeout+45)
        validate_cad_result(read(cad), source=source, graph=graph, output=output,
            source_sha=a.expected_source_sha256, graph_sha=a.expected_graph_sha256, target=a.target,
            variant=graph_payload["EditPolicy"]["initialPlacementVariant"])
        if sha(source) != a.expected_source_sha256 or sha(graph) != a.expected_graph_sha256:
            raise ValueError("Confirmed inputs changed before readonly reopen")
        run_phase("reopen-and-preserve", [sys.executable, "-X", "utf8", str(ROOT/"scripts/verify_datum_chain_live_state.py"),
            "--cad-result", str(cad), "--report", str(state), "--count", str(a.source_count+1),
            "--source", str(source), "--base", a.base], directory, report, 360)
        validate_state(read(state), source=source, output=output, source_sha=a.expected_source_sha256,
                       source_count=a.source_count, base=a.base, target=a.target, graph=graph_payload)
        if a.source_count > 1:
            preservation = read(state.with_suffix(".preservation.json"))
            if preservation.get("success") is not True or not preservation.get("checks") or not all(value is True for value in preservation["checks"].values()):
                raise ValueError("Cumulative source pose/mate preservation was not verified")
        report.update(success=True, outputAssemblySha256=sha(output), cadResultSha256=sha(cad), stateSha256=sha(state))
    except Exception as exc:
        report["error"] = str(exc)
    def unchanged(path, expected):
        try:
            return sha(path) == expected
        except OSError as exc:
            report.setdefault("finalEvidenceErrors", []).append({"path": str(path), "error": str(exc)})
            return False
    report.update(finishedAtUtc=datetime.now(timezone.utc).isoformat(), durationSeconds=perf_counter()-clock,
                  sourceUnchanged=unchanged(source, a.expected_source_sha256),
                  graphUnchanged=unchanged(graph, a.expected_graph_sha256))
    report["success"] = report["success"] and report["sourceUnchanged"] and report["graphUnchanged"]
    with (directory/"append-summary.json").open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False), flush=True)
    return 0 if report["success"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
