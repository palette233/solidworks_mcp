"""Read-only runtime closure of existing incremental CAD and functional reports.

Each stage binds its actual predecessor/output, not a historical preflight
checkpoint. This module neither runs CAD nor changes execution or release gates.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any

from .datum_chain_verification import _rigid
from .scanner_target_association import preflight_scanner_target_for_cumulative_chain


SCHEMA = "functional-chain-runtime-closure/v1"


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _path(value):
    return str(value or "").replace("\\", "/").casefold()


def _near(a, b, tolerance=1e-8):
    return isinstance(a, list) and isinstance(b, list) and len(a) == len(b) and all(
        type(x) in (int, float) and type(y) in (int, float) and math.isfinite(x) and math.isfinite(y)
        and abs(x-y) <= tolerance for x, y in zip(a, b, strict=True))


def _tri(values):
    return False if any(v is False for v in values) else True if values and all(v is True for v in values) else None


def _dimension_same(a, b):
    return a is None and b is None or type(a) in (int, float) and type(b) in (int, float) and math.isfinite(a) and math.isfinite(b) and abs(a-b) <= 1e-8


def audit_nonprototype_insertion(cad_result: dict, effective_graph: dict) -> dict:
    """Consume actual run_context output fields, not requested variant metadata.

The runner records deterministic variant/seed in Diagnostics but does not emit
numeric pre-mate coordinates. The distinction is retained in the result.
"""
    tool = cad_result.get("toolResult") or {}
    diagnostic = next((row for row in tool.get("Diagnostics") or [] if isinstance(row, str)
                       and re.search(r"Deterministic non-source placement variant=\d+, seed=\d+;", row)), None)
    match = re.search(r"variant=(\d+), seed=(\d+);", diagnostic) if diagnostic else None
    checks = {
        "independentInserted": tool.get("IndependentComponentInserted") is True,
        "noCaseAnchor": tool.get("TargetCaseAnchored") is False and not effective_graph.get("CaseAnchor"),
        "noLeafAnchors": tool.get("RequestedTargetLeafPoseAnchorCount") == 0
        and type(tool.get("RequestedTargetLeafPoseAnchorCount")) is int
        and tool.get("AppliedTargetLeafPoseAnchorCount") == 0
        and type(tool.get("AppliedTargetLeafPoseAnchorCount")) is int
        and not effective_graph.get("TargetLeafPoseAnchors"),
        "deterministicNonSourceInsertionObserved": match is not None,
    }
    return {"passed": all(checks.values()), "checks": checks,
            "runtimeDiagnostic": diagnostic, "initialPlacementVariant": int(match[1]) if match else None,
            "initialPlacementSeed": int(match[2]) if match else None,
            "numericInitialPoseObserved": False,
            "evidenceGrade": "actual_runner_diagnostic_and_anchor_audit_not_numeric_initial_pose"}


def compare_append_observations(before: dict, after: dict, *, tool_result: dict) -> dict:
    """Compare observed instance identities, world poses and all existing mates."""
    checks = {}
    component_maps = []
    for label, state in (("before", before), ("after", after)):
        rows = (state.get("observed") or {}).get("components") or []
        ids = [(r.get("name"), _path(r.get("sourcePath"))) for r in rows]
        checks[f"{label}ComponentIdentityUnique"] = bool(rows) and all(a and b for a, b in ids) and len(set(ids)) == len(ids)
        checks[f"{label}RigidPosesAvailable"] = bool(rows) and all(_rigid(r.get("transform")) for r in rows)
        component_maps.append(dict(zip(ids, rows)))
    left, right = component_maps
    added = (tool_result.get("InsertedComponentName"), _path(tool_result.get("TargetModuleSourcePath")))
    checks["exactlyRequestedInstanceAdded"] = set(right) - set(left) == {added} and set(left) <= set(right)
    checks["existingWorldPosesPreserved"] = all(key in right and _near(row.get("transform"), right[key].get("transform"))
                                               for key, row in left.items())
    semantic_keys = ("configuration", "solvingState", "constrainedStatus", "isFixed")
    checks["existingComponentSemanticsPreserved"] = all(key in right and all(
        field in row and field in right[key] and row[field] == right[key][field] for field in semantic_keys)
        for key, row in left.items())
    target = right.get(added) or {}
    checks["newTargetNotFixed"] = target.get("isFixed") is False
    checks["newTargetPoseMatchesReopen"] = _near(target.get("transform"), tool_result.get("ReopenedTargetRootTransform"))
    checks["newTargetFullyConstrained"] = target.get("constrainedStatus") == 3
    mate_maps = []
    for label, state in (("before", before), ("after", after)):
        rows = (state.get("observed") or {}).get("allTopLevelMates")
        checks[f"{label}MateInventoryAvailable"] = isinstance(rows, list)
        rows = rows if isinstance(rows, list) else []
        names = [r.get("name") for r in rows]
        checks[f"{label}MateNamesUnique"] = all(names) and len(set(names)) == len(names)
        checks[f"{label}MatesActiveClean"] = all(r.get("isSuppressed") is False and type(r.get("errorCode")) is int
                                                  and r["errorCode"] == 0 for r in rows)
        mate_maps.append(dict(zip(names, rows)))
    old, new = mate_maps
    checks["existingMatesPreserved"] = all(name in new and all(
        key in row and key in new[name] and row[key] == new[name][key]
        for key in ("mateType", "alignment", "isSuppressed", "errorCode"))
        and "dimensionSystemValue" in row and "dimensionSystemValue" in new[name]
        and _dimension_same(row["dimensionSystemValue"], new[name]["dimensionSystemValue"])
        for name, row in old.items())
    expected_names = [r.get("ObservedMateName") for r in tool_result.get("MateVerifications") or []]
    checks["addedMateNamesMatchReopenedVerification"] = (bool(expected_names) and all(expected_names)
        and set(new) - set(old) == set(expected_names) and len(expected_names) == len(set(expected_names)))
    return {"passed": all(checks.values()), "checks": checks,
            "preservedComponentCount": len(left), "preservedMateCount": len(old),
            "newMateCount": len(set(new)-set(old)),
            "boundary": "Observed rigid world poses/configuration and exported mate fields only; not B-rep or dynamic motion."}


def build_functional_chain_closure(
    workspace: Path, *, stages: list[dict], functional_reports: list[dict] | None = None,
    required_roles: list[str] | None = None,
) -> dict:
    """Summarize actual runs without authorizing execution or publication.

    stage: stageId, cadResultPath, afterStatePath; optional beforeStatePath.
    Without a separate before file, use the same read-only report's explicitly
    hash-bound sourceObserved/sourceCheckpoint fields.
functional: role, reportPath; Scanner uses associationPath/evaluationPath.
    Scanner/cup reports bind the final saved state. A cleaning CAD measurement
    may precede a later append only when all intervening observations prove
    exact context preservation; propagation is explicitly labeled.
"""
    root = Path(workspace).resolve()
    files, failures, rows, runtime = {}, [], [], []

    def read(value):
        if not isinstance(value, (str, Path)) or not str(value):
            raise ValueError("Missing runtime evidence path")
        path = (root / value).resolve()
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, dict):
            raise ValueError("Evidence must be a JSON object")
        files[str(path)] = _sha(path)
        return path, payload

    def state_bound(value, assembly_path, assembly_sha):
        path, state = read(value)
        if state.get("cadAcceptanceEvaluated") is False:
            raise ValueError("Geometry measurement snapshot is not CAD acceptance evidence")
        if state.get("success") is not True or (state.get("observed") or {}).get("readOnly") is not True:
            raise ValueError("Successful saved read-only state required")
        if not isinstance(state.get("checks"), dict) or not state["checks"] or any(v is not True for v in state["checks"].values()):
            raise ValueError("Read-only state checks missing or failed")
        if _path(Path(state["assemblyPath"]).resolve()) != _path(assembly_path) or state.get("assemblySha256") != assembly_sha:
            raise ValueError("State is not bound to this stage's actual assembly bytes")
        return path, state

    previous = None
    ids = [s.get("stageId") for s in stages]
    if not stages or not all(ids) or len(set(ids)) != len(ids):
        failures.append("STAGE_IDS_EMPTY_OR_DUPLICATE")
    for spec in stages:
        row = {"stageId": spec.get("stageId"), "cadPassed": False, "blockingReasonCodes": []}
        try:
            cad_path, cad = read(spec.get("cadResultPath"))
            graph_path, graph = read(cad.get("executionEffectiveGraphPath") or cad.get("effectiveGraphPath"))
            graph_sha = cad.get("executionEffectiveGraphSha256") or cad.get("effectiveGraphSha256")
            if files[str(graph_path)] != graph_sha:
                raise ValueError("Execution graph hash differs from actual CAD result")
            source, output = (root / cad["sourceAssemblyPath"]).resolve(), (root / cad["outputAssemblyPath"]).resolve()
            source_sha, output_sha = _sha(source), _sha(output)
            files[str(source)], files[str(output)] = source_sha, output_sha
            if source == output or source_sha != cad.get("sourceAssemblySha256Before") or source_sha != cad.get("sourceAssemblySha256After") or output_sha != cad.get("outputAssemblySha256"):
                raise ValueError("Actual stage source/output hashes do not match CAD result")
            if previous and previous != (str(source), source_sha):
                raise ValueError("Stage source is not the actual preceding output")
            after_path, after = state_bound(spec.get("afterStatePath"), output, output_sha)
            before_section = "observed"
            if spec.get("beforeStatePath"):
                before_path, before = state_bound(spec["beforeStatePath"], source, source_sha)
            else:
                if (_path(after.get("sourceCheckpointPath")) != _path(source)
                    or after.get("sourceCheckpointSha256Before") != source_sha
                    or after.get("sourceCheckpointSha256After") != source_sha
                    or (after.get("sourceObserved") or {}).get("readOnly") is not True):
                    raise ValueError("Embedded before-state does not bind the actual source checkpoint")
                before_path, before_section = after_path, "sourceObserved"
                before = {"success": True, "observed": after["sourceObserved"]}
            tool = cad.get("toolResult") or {}
            count = tool.get("RequestedMateCount")
            mate_results, verifications = tool.get("MateResults") or [], tool.get("MateVerifications") or []
            checks = {"runnerSucceeded": cad.get("success") is True and tool.get("Success") is True,
                "sourceUnchanged": cad.get("sourceAssemblyUnchanged") is True,
                "allMatesCreated": type(count) is int and count > 0 and tool.get("CreatedMateCount") == count
                    and len(mate_results) == count and all(r.get("Success") is True for r in mate_results),
                "savedClosedReopened": cad.get("outputClosedAfterVerification") is True and tool.get("Reopened") is True,
                "parametersReopened": tool.get("ReopenedMateParametersMatch") is True and len(verifications) == count
                    and all(all(r.get(k) is True for k in ("Found", "TypeMatches", "AlignmentMatches", "DistanceMatches", "AngleMatches", "AdvancedOptionsMatch")) for r in verifications),
                "targetFullyConstrained": tool.get("TargetFullyConstrained") is True,
                "mateSolveClean": tool.get("MateSolveClean") is True,
                "componentSemanticsMatch": tool.get("ComponentSemanticsMatch") is True}
            insertion = audit_nonprototype_insertion(cad, graph)
            preservation = compare_append_observations(before, after, tool_result=tool)
            checks.update(nonPrototypeInsertionAudited=insertion["passed"], priorContextPreserved=preservation["passed"])
            row.update(cadPassed=all(checks.values()), checks=checks, nonPrototypeAudit=insertion,
                       preservation=preservation, cadResultPath=str(cad_path), cadResultSha256=files[str(cad_path)],
                       executionGraphPath=str(graph_path), executionGraphSha256=graph_sha,
                       sourceAssemblyPath=str(source), sourceAssemblySha256=source_sha,
                       outputAssemblyPath=str(output), outputAssemblySha256=output_sha,
                       beforeStatePath=str(before_path), beforeStateSection=before_section,
                       afterStatePath=str(after_path),
                       afterStateSha256=files[str(after_path)])
            row["blockingReasonCodes"] = [name for name, passed in checks.items() if not passed]
            runtime.append({"row": row, "cad": cad, "state": after, "beforeState": before})
            previous = str(output), output_sha
        except (OSError, ValueError, TypeError, KeyError) as exc:
            row["blockingReasonCodes"].append("RUNTIME_EVIDENCE_BINDING_FAILED:"+str(exc))
            previous = None
            failures.append(f"{spec.get('stageId')}:RUNTIME_EVIDENCE_BINDING_FAILED")
        rows.append(row)

    final = runtime[-1] if runtime and len(runtime) == len(stages) else None
    function_rows = []
    role_specs = functional_reports or []
    roles = required_roles if required_roles is not None else ["Scanner", "CleaningWeighing", "WasteCup"]
    for role in roles:
        item = {"role": role, "bindingVerified": False, "proxyGeometryPassed": None,
                "functionalPassed": None, "status": "unknown", "reasonCodes": []}
        specs = [s for s in role_specs if s.get("role") == role]
        try:
            if final is None or len(specs) != 1:
                raise ValueError("Final runtime state or unique functional report unavailable")
            spec, final_row, state = specs[0], final["row"], final["state"]
            if role == "Scanner":
                _, association = read(spec.get("associationPath"))
                _, evaluation = read(spec.get("evaluationPath"))
                binding = association.get("currentContextEvidence") or {}
                if (_path(binding.get("sourcePath")) != _path(final_row["afterStatePath"])
                    or binding.get("sourceSha256") != final_row["afterStateSha256"]
                    or binding.get("assemblySha256") != final_row["outputAssemblySha256"]):
                    raise ValueError("Scanner association does not bind the final current state")
                planned = []
                for key in ("scanner", "transport", "targetBase"):
                    linked = association[key]
                    observed = [r for r in state["observed"]["components"] if r.get("name") == linked.get("instanceId")]
                    if len(observed) != 1:
                        raise ValueError("Current scanner context instance ambiguous")
                    planned.append({"instanceId": linked["instanceId"], "moduleDefinitionId": linked["moduleDefinitionId"], "transform": observed[0]["transform"]})
                preflight = preflight_scanner_target_for_cumulative_chain(
                    evaluation=evaluation, association=association, planned_components=planned,
                    world_frame_id=final_row["outputAssemblyPath"], allow_prototype_proxy=True)
                if any(code != "SCANNER_TARGET_GEOMETRY_FAILED" for code in preflight["blockingReasonCodes"]):
                    raise ValueError("Current scanner association invalid: "+str(preflight["blockingReasonCodes"]))
                proxy = evaluation.get("processProxyValidationPassed")
                functional = False if proxy is False else None
                item["evidenceGrade"] = "prototype_barcode_lane_proxy"
            else:
                report_path, report = read(spec.get("reportPath"))
                if role in {"Cleaning", "CleaningWeighing"} and report.get("schemaVersion") == "cleaning-service-region-audit/v1":
                    if (report.get("capabilityCoverage") or {}).get("passed") is not True:
                        raise ValueError("Cleaning target service capabilities are incomplete")
                    binding = report.get("cadBinding") or {}
                    matching = [i for i, stage in enumerate(runtime) if
                                binding.get("cadResultSha256") == stage["row"]["cadResultSha256"] and
                                binding.get("outputAssemblySha256") == stage["row"]["outputAssemblySha256"]]
                    if len(matching) != 1 or report.get("evaluationMode") != "saved_cad_reopen_geometry":
                        raise ValueError("Cleaning report is not bound to this actual runtime chain")
                    index = matching[0]
                    if any(stage["row"].get("preservation", {}).get("passed") is not True for stage in runtime[index+1:]):
                        raise ValueError("Cleaning geometry cannot propagate through changed context")
                    item.update(measuredAtStageId=runtime[index]["row"]["stageId"],
                                propagatedThroughPreservedAppends=index != len(runtime)-1,
                                finalAddedModuleInterference="not_evaluated")
                    proxy = report.get("serviceRegionDemoPassed")
                    functional = report.get("serviceRegionEngineeringPassed")
                elif role == "WasteCup" and report.get("schemaVersion") == "cup-saved-cad-projection-verification/v1":
                    state_refs = [r for r in report.get("evidence") or [] if _path(r.get("path")) == _path(final_row["afterStatePath"])]
                    if (len(state_refs) != 1 or state_refs[0].get("sha256") != final_row["afterStateSha256"]
                        or report.get("cadResultSha256") != final_row["cadResultSha256"]
                        or report.get("outputAssemblySha256") != final_row["outputAssemblySha256"]
                        or _path(report.get("outputAssemblyPath")) != _path(final_row["outputAssemblyPath"])):
                        raise ValueError("Saved cup-mouth report does not bind the final CAD/state/output")
                    proxy = report.get("targetCupProjectionPassed")
                    alignment_3d = report.get("threeDimensionalCupMouthAlignmentPassed")
                    if alignment_3d is not None and type(alignment_3d) is not bool:
                        raise ValueError("3D cup-mouth conclusion must be tri-state")
                    # This run specifies planar station alignment/supportGap=0,
                    # not equal cup-mouth height. Record the 3D difference but
                    # do not invent a new height acceptance condition.
                    functional = False if proxy is False else None
                    measurements = (report.get("comparison") or {}).get("measurements") or []
                    item.update(targetCupProjectionPassed=proxy,
                                threeDimensionalCupMouthAlignmentPassed=alignment_3d,
                                cupMouthMeasurements=measurements,
                                actualDischargeValidated=report.get("actualDischargeValidated"),
                                heightAcceptanceCriterionDeclared=False,
                                heightDifferenceRequiresReview=alignment_3d is False,
                                functionalPendingReason="allowed_cup_height_and_actual_discharge_target_not_registered")
                elif role == "WasteCup" and report.get("schemaVersion") == "wastecup-target-station-audit/v1":
                    state_refs = [r for r in report.get("evidence") or [] if _path(r.get("path")) == _path(final_row["afterStatePath"])]
                    if len(state_refs) != 1 or state_refs[0].get("sha256") != final_row["afterStateSha256"]:
                        raise ValueError("WasteCup report does not bind final current state")
                    proxy = report.get("targetDatumPositionVerified")
                    functional = (report.get("measurements") or {}).get("cupMouthPositionVerified")
                else:
                    raise ValueError("Unsupported functional report schema")
                for evidence in report.get("evidence") or []:
                    evidence_path = (root / evidence["path"]).resolve()
                    actual_sha = _sha(evidence_path)
                    files[str(evidence_path)] = actual_sha
                    if actual_sha != evidence.get("sha256"):
                        raise ValueError("Functional source evidence changed")
                if proxy is False:
                    functional = False
                item.update(reportPath=str(report_path), evidenceGrade="measured_prototype_service_or_support_proxy")
            if (proxy is not None and type(proxy) is not bool) or (functional is not None and type(functional) is not bool):
                raise ValueError("Functional conclusions must be tri-state booleans")
            item.update(bindingVerified=True, proxyGeometryPassed=proxy, functionalPassed=functional,
                        status="passed" if functional is True else "failed" if functional is False else "unknown_functional_geometry_only")
        except (OSError, ValueError, TypeError, KeyError) as exc:
            item["reasonCodes"].append("FUNCTIONAL_EVIDENCE_UNAVAILABLE_OR_STALE:"+str(exc))
        function_rows.append(item)
    cad_passed = bool(rows) and all(r["cadPassed"] is True for r in rows) and not failures
    functional_passed = _tri([r["functionalPassed"] for r in function_rows])
    core = {"schemaVersion": SCHEMA, "cadPassed": cad_passed, "functionalPassed": functional_passed,
            "proxyGeometryPassed": _tri([r["proxyGeometryPassed"] for r in function_rows]),
            "status": "cad_failed_or_unverified" if not cad_passed else "cad_passed_functional_failed" if functional_passed is False
                      else "cad_and_declared_functional_checks_passed" if functional_passed is True else "cad_passed_functional_unknown",
            "stages": rows, "functionalReports": function_rows,
            "executedStageCount": len(rows),
            "initialCheckpointComponentCount": len((runtime[0]["beforeState"].get("observed") or {}).get("components") or []) if runtime else None,
            "finalComponentCount": len((final["state"].get("observed") or {}).get("components") or []) if final else None,
            "startedFromReusedCheckpoint": True,
            "completeFromBlankChainClaim": False,
            "unknownFunctionalRoles": [r["role"] for r in function_rows if r["functionalPassed"] is None],
            "blockingReasonCodes": failures,
            "evidence": [{"path": p, "sha256": h} for p, h in sorted(files.items())],
            "newCadExecutedByThisAudit": False, "automaticPublicationAllowed": False,
            "productionReady": False, "collisionOrBrep": "not_evaluated",
            "boundary": "Runtime CAD closure and prototype functional geometry remain distinct. Missing function evidence is unknown, not success. No runner or preflight policy is changed."}
    return {**core, "closureDigest": _digest(core)}
