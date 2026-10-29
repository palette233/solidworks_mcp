"""Compile and run ordered NL steps with separately authorized interface modes.

This is a thin CLI over the existing NL compiler, staged manifests and durable
CAD jobs.  It does not combine datum evidence with direct-installation authority.
CAD starts only with the explicit ``run`` or ``resume`` command.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.global_natural_language_manifest import compile_natural_language_manifest_job
from demo_backend.global_cad_manifest_orchestrator import manifest_cad_step_runner, run_manifest_job
from demo_backend.semantic_assembly_jobs import DurableAssemblyJobStore
from demo_backend.global_relation_catalog_release import load_relation_catalog_release
from demo_backend.global_interface_contract_planner import (
    resolve_preferred_released_interface_authority,
)
from demo_backend.multi_release_cad_chain import (
    build_multi_release_cad_chain, prepare_multi_release_stage_job,
    guard_multi_release_stage_runner, build_multi_release_stage_closure,
)
from demo_backend.target_station_chain_preflight import (
    STRICT, LEGACY, build_target_station_chain_preflight,
    revalidate_target_station_preflight, validate_stage_source_checkpoint,
)
from demo_backend.station_rule_planner import plan_station_chain, verify_station_stage


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def station_preflight_passed(preflight):
    """Report planning readiness separately from post-CAD geometry acceptance."""
    if preflight.get("ruleDriven") is True:
        return (preflight.get("readyForCadCompilation") is True
                and not preflight.get("blockingReasonCodes"))
    return preflight.get("targetStationValidated") is True


def compare_saved_states(request_path, report_path):
    """Compare real saved outputs through the existing state comparator."""
    from demo_backend.datum_chain_verification import compare_cad_states
    started, clock = now(), perf_counter()
    spec = read(request_path)
    states, evidence = [], []
    for key in ("beforeStatePath", "afterStatePath"):
        path = (ROOT / spec[key]).resolve()
        state = read(path)
        assembly = Path(state["assemblyPath"]).resolve()
        if sha(assembly) != state["assemblySha256"] or state.get("cadAcceptanceEvaluated") is False:
            raise ValueError("Saved assembly changed or evidence is measurement-only")
        states.append(state)
        evidence.extend([{"path": str(path), "sha256": sha(path)},
                         {"path": str(assembly), "sha256": sha(assembly)}])
    result = compare_cad_states(*states, base_token=spec["baseToken"],
        moved_token=spec.get("movedToken"), expected_displacement_meters=spec.get("expectedDisplacementMeters"),
        expected_parameter_changes=spec.get("expectedParameterChanges"), mate_name_map=spec.get("mateNameMap"))
    result.update(evidence=evidence, requestPath=str(Path(request_path).resolve()), requestSha256=sha(request_path),
        startedAtUtc=started, finishedAtUtc=now(), durationSeconds=perf_counter()-clock,
        newCadExecuted=False, functionalPassed=None, collisionOrBrep="not_evaluated")
    write_new(report_path, result)
    return result


def resolve_confirmed_selection(selection, catalog):
    if not isinstance(selection, dict) or selection.get("confirmed") is not True:
        raise ValueError("模组选型必须显式确认。")
    rows = [row for row in catalog["moduleDefinitions"] if any(
        alias.get("projectId") == selection.get("projectId") and alias.get("moduleToken") == selection.get("moduleToken")
        for alias in row.get("projectAliases") or [])]
    if len(rows) != 1:
        raise ValueError("已确认选型未唯一对应当前发布目录。")
    return {"moduleDefinitionId": rows[0]["moduleDefinitionId"], "confirmed": True}


def resolve_stage_authority(request, step):
    """Resolve an explicit release or select one from confirmed module/base ids."""

    explicit_release = str(step.get("releaseManifestPath") or "").strip()
    explicit_mode = str(step.get("relationExecutionMode") or "").strip()
    if explicit_release:
        mode = explicit_mode or "direct_installation"
        if mode not in {"direct_installation", "datum_placement_demo"}:
            raise ValueError("不支持的装配模式。")
        return {
            "schemaVersion": "natural-language-stage-authority/v1",
            "status": "explicit_release_authority",
            "ready": True,
            "source": "explicit_request",
            "releaseManifestPath": explicit_release,
            "relationExecutionMode": mode,
        }

    global_catalog = read(ROOT / "demo/global_assembly_catalog/v1/global_module_catalog.json")
    module_selection = resolve_confirmed_selection(step.get("moduleSelection"), global_catalog)
    slot_input = step.get("slotSelection") or request.get("baseSelection")
    slot_selection = resolve_confirmed_selection(slot_input, global_catalog)
    allow_datum = step.get("allowDatumFallback") is True
    authority = resolve_preferred_released_interface_authority(
        ROOT,
        module_selection["moduleDefinitionId"],
        selected_slot_definition_id=slot_selection["moduleDefinitionId"],
        allow_datum_fallback=allow_datum,
    )
    if authority.get("ready") is not True:
        raise ValueError(
            "无法为已确认模组自动选择已发布接口："
            + str(authority.get("status") or "unknown")
        )
    selected_mode = authority["relationExecutionMode"]
    if explicit_mode and explicit_mode != selected_mode:
        raise ValueError(
            f"请求的装配模式{explicit_mode}与已发布接口模式{selected_mode}不一致。"
        )
    return {
        **authority,
        "schemaVersion": "natural-language-stage-authority/v1",
        "source": "confirmed_module_and_slot_planner",
        "confirmedModuleDefinitionId": module_selection["moduleDefinitionId"],
        "confirmedSlotDefinitionId": slot_selection["moduleDefinitionId"],
    }


def plan_stations(request_path: Path, output_root: Path, *, prepare_candidates=False):
    """Data-driven preparation in the normal entry; no CAD or release mutation."""
    output_root.resolve().relative_to(ROOT.resolve())
    if output_root.exists():
        raise FileExistsError(output_root)
    request = read(request_path)
    steps = request.get("steps") or []
    if any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", str(s.get("stageId") or "")) for s in steps):
        raise ValueError("stageId不是安全标识。")
    request_sha = sha(request_path)
    report = plan_station_chain(ROOT, request, prepare_candidates=prepare_candidates)
    if sha(request_path) != request_sha:
        raise ValueError("工位规划期间原请求已修改。")
    report.update(requestPath=str(request_path.resolve()), requestSha256=request_sha,
                  request=request, candidatePreparationRequested=prepare_candidates)
    for row in report["stages"]:
        if not row["planned"]:
            continue
        plan = row["plan"]
        package = plan.get("validationPackage")
        stage_root = output_root / row["stageId"]
        if package is not None:
            # Same artifact layout as the existing validation/publishing tools.
            # This freezes a candidate, not a release or cumulative checkpoint.
            package = dict(package)
            artifacts = {}
            for key, filename in (("effectiveGraph", "effective-mate-graph.json"),
                                  ("selectedEndpointCatalog", "selected-face-endpoint-catalog.json")):
                path = stage_root / filename
                write_new(path, package.pop(key))
                artifacts[key] = {"path": str(path.resolve()), "sha256": sha(path)}
            package["artifacts"] = artifacts
            write_new(stage_root / "validation-package.json", package)
            row["candidatePackagePath"] = str((stage_root / "validation-package.json").resolve())
        write_new(stage_root / "station-plan.json", plan)
    write_new(output_root / "station-planning.json", report)
    return report


def station_authority(request, step, plan):
    if plan.get("requiresFreshCadValidation"):
        raise ValueError("STATION_PARAMETERS_REQUIRE_NEW_CAD_RELEASE")
    authority = plan.get("reusableExecutionAuthority") or (plan.get("geometry") or {}).get("authority")
    if authority is None:
        authority = resolve_stage_authority(request, step)
    authority = {**authority, "source": "registered_station_rule", "ready": True}
    if authority.get("relationExecutionMode") == "datum_placement_demo" and step.get("allowDatumFallback") is not True:
        raise ValueError("STATION_DATUM_AUTHORIZATION_REQUIRED")
    if step.get("releaseManifestPath") and (ROOT / step["releaseManifestPath"]).resolve() != (ROOT / authority["releaseManifestPath"]).resolve():
        raise ValueError("EXPLICIT_RELEASE_DIFFERS_FROM_STATION_RULE")
    if step.get("relationExecutionMode") and step["relationExecutionMode"] != authority["relationExecutionMode"]:
        raise ValueError("EXPLICIT_MODE_DIFFERS_FROM_STATION_RULE")
    return authority


def compile_chain(request_path: Path, output_root: Path):
    started, clock = now(), perf_counter()
    request = read(request_path)
    chain_id = str(request["chainId"])
    steps = request["steps"]
    output_root.resolve().relative_to(ROOT.resolve())
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,119}", chain_id):
        raise ValueError("chainId不是安全标识。")
    if any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", str(s.get("stageId") or "")) for s in steps):
        raise ValueError("stageId不是安全标识。")
    if any(len(f"{chain_id}-{s['stageId']}") > 80 for s in steps):
        raise ValueError("chainId与stageId组合后的contextId不得超过80字符。")
    if not steps or len(steps) > 19:
        raise ValueError("需要1至19个追加步骤。")
    if len({s["stageId"] for s in steps}) != len(steps):
        raise ValueError("stageId必须唯一。")
    if output_root.exists():
        raise FileExistsError(output_root)
    station_plan = None
    if request.get("stationRegistryPath"):
        station_plan = plan_stations(request_path, output_root / "station-preparation", prepare_candidates=True)
        if not station_plan["planningComplete"] or len(station_plan["stages"]) != len(steps):
            report = {"status": "blocked_before_chain_compile", "success": False,
                "blockingReasonCodes": ["TARGET_STATION_PLAN_INCOMPLETE"], "cadStarted": False}
            write_new(output_root / "compilation.json", report)
            return report
    strict = request.get("placementValidationMode", LEGACY) == STRICT
    authorities, bindings = [], []
    for index, step in enumerate(steps):
        try:
            authority = station_authority(request, step, station_plan["stages"][index]["plan"]) if station_plan else resolve_stage_authority(request, step)
        except (OSError, ValueError) as exc:
            if not strict:
                raise
            authority = {"ready": False, "source": "unresolved", "releaseManifestPath": step.get("releaseManifestPath"),
                         "relationExecutionMode": step.get("relationExecutionMode"), "error": str(exc)}
        authorities.append(authority)
        if strict:
            binding = {"stageId": step["stageId"], "releaseManifestPath": authority.get("releaseManifestPath")}
            try:
                catalog, _ = load_relation_catalog_release(ROOT / authority["releaseManifestPath"], workspace_root=ROOT)
                base = step.get("slotSelection") or request.get("baseSelection")
                moving = step.get("moduleSelection")
                binding.update(baseModuleDefinitionId=resolve_confirmed_selection(base, catalog)["moduleDefinitionId"],
                               moduleDefinitionId=resolve_confirmed_selection(moving, catalog)["moduleDefinitionId"],
                               source=f"{moving['projectId']}::{moving['moduleToken']}", target=f"{base['projectId']}::{base['moduleToken']}")
            except (OSError, ValueError, TypeError, KeyError) as exc:
                binding["identityResolutionError"] = str(exc)
            bindings.append(binding)
    if station_plan:
        preflight = {"ruleDriven": True, "placementValidationMode": STRICT,
            "targetStationValidated": False, "readyForCadCompilation": all(a.get("ready") for a in authorities),
            "blockingReasonCodes": [a.get("error") for a in authorities if not a.get("ready")],
            "planDigests": [r["plan"]["planDigest"] for r in station_plan["stages"]],
            "authorities": authorities}
    else:
        preflight = build_target_station_chain_preflight(ROOT, request, stage_bindings=bindings)
    preflight_path = output_root / "target-station-preflight.json"
    write_new(preflight_path, preflight)
    common = {
        "schemaVersion": "natural-language-staged-chain-compilation/v1",
        "chainId": chain_id, "requestPath": str(request_path.resolve()),
        "requestSha256": sha(request_path), "request": request,
        "placementValidationMode": preflight["placementValidationMode"],
        "targetStationValidated": False,
        "targetStationPreflightPassed": station_preflight_passed(preflight),
        "targetStationPreflightPath": str(preflight_path.resolve()),
        "targetStationPreflightSha256": sha(preflight_path),
        "startedAtUtc": started, "cadStarted": False,
        "collisionOrBrep": "not_evaluated", "actualFasteningMethod": "not_verified",
    }
    if preflight["readyForCadCompilation"] is not True:
        report = {**common, "status": "blocked_before_chain_compile", "success": False,
                  "finishedAtUtc": now(), "durationSeconds": perf_counter() - clock,
                  "blockingReasonCodes": preflight["blockingReasonCodes"]}
        write_new(output_root / "compilation.json", report)
        return report
    compiled = []
    for step, authority in zip(steps, authorities, strict=True):
        mode = authority["relationExecutionMode"]
        release_manifest_path = authority["releaseManifestPath"]
        payload = {
            "contextId": f"{chain_id}-{step['stageId']}",
            "displayName": step["requirement"],
            "requirements": [request["baseRequirement"], step["requirement"]],
            "releaseManifestPath": release_manifest_path,
            "relationExecutionMode": mode,
            "enforceMechanicalInterfaceContracts": True,
            "autoOrderByReleasedDependencies": False,
            "overwrite": False,
            "idempotencyKey": f"{chain_id}-{step['stageId']}-nl-compile",
        }
        if "baseSelection" in request or "moduleSelection" in step:
            catalog, _ = load_relation_catalog_release(
                ROOT / release_manifest_path, workspace_root=ROOT
            )
            payload["confirmedModuleSelections"] = [
                resolve_confirmed_selection(
                    step.get("slotSelection") or request.get("baseSelection"), catalog
                ),
                resolve_confirmed_selection(step.get("moduleSelection"), catalog),
            ]
        report = compile_natural_language_manifest_job(ROOT, payload)
        stage_root = output_root / step["stageId"]
        write_new(stage_root / "interface-authority-decision.json", authority)
        write_new(stage_root / "natural-language-request.json", payload)
        write_new(stage_root / "natural-language-compilation.json", report)
        if not report.get("success"):
            raise ValueError(f"自然语言步骤未通过：{step['stageId']}: {report.get('status')}")
        manifest = read(report["manifestPath"])
        if manifest.get("packetCount") != 1:
            raise ValueError("每个自然语言追加步骤必须只产生一个CAD包。")
        compiled.append({
            "stageId": step["stageId"],
            "manifestPath": report["manifestPath"],
            "authoritySource": authority["source"],
            "releaseManifestPath": release_manifest_path,
            "relationExecutionMode": mode,
        })
    chain = build_multi_release_cad_chain(ROOT, chain_id=chain_id, stages=compiled)
    write_new(output_root / "chain.json", chain)
    report = {
        **common,
        "chainPath": str((output_root / "chain.json").resolve()),
        "chainSha256": sha(output_root / "chain.json"),
        "startedAtUtc": started, "finishedAtUtc": now(),
        "durationSeconds": perf_counter() - clock,
        "status": "ready_not_started", "cadStarted": False,
        "implementationBoundary": "One ordered request; separate internal NL contexts preserve per-stage release authority.",
        "collisionOrBrep": "not_evaluated", "actualFasteningMethod": "not_verified",
    }
    write_new(output_root / "compilation.json", report)
    return report


def revalidate_chain_inputs(output_root: Path):
    """Missing preflight is a refusal, never an implicit legacy downgrade."""
    compilation = read(output_root / "compilation.json")
    request_path = Path(compilation["requestPath"])
    if sha(request_path) != compilation.get("requestSha256"):
        raise ValueError("累计链原请求已修改，请以新证据重新编译。")
    request = read(request_path)
    if request != compilation.get("request"):
        raise ValueError("累计链编译记录与原请求不一致。")
    preflight_path = output_root / "target-station-preflight.json"
    if sha(preflight_path) != compilation.get("targetStationPreflightSha256"):
        raise ValueError("工位预检查证据已修改或缺失。")
    preflight = read(preflight_path)
    if preflight.get("ruleDriven"):
        fresh = plan_station_chain(ROOT, request, prepare_candidates=True)
        if not fresh["planningComplete"] or [r["plan"]["planDigest"] for r in fresh["stages"]] != preflight["planDigests"]:
            raise ValueError("工位规则、参数或关联证据已变化。")
        authorities = [station_authority(request, step, row["plan"]) for step, row in zip(request["steps"], fresh["stages"], strict=True)]
        if authorities != preflight["authorities"]:
            raise ValueError("工位执行授权已变化。")
        for row in fresh["stages"]:
            saved = read(output_root / "station-preparation" / row["stageId"] / "station-plan.json")
            from demo_backend.station_rule_planner import plan_digest
            if plan_digest(saved) != row["plan"]["planDigest"]:
                raise ValueError("保存的工位计划已变化。")
    else:
        preflight = revalidate_target_station_preflight(ROOT, request, preflight)
    if sha(output_root / "chain.json") != compilation.get("chainSha256"):
        raise ValueError("累计链内容已修改，请重新编译。")
    return preflight


def station_dependency_states(output_root, plan):
    """Resolve logical dependencies from committed, hash-bound CAD observations."""
    if plan.get("ruleBinding", {}).get("rule", {}).get("evaluator", {}).get("kind") != "scanner_target":
        return {}
    dependency = plan["instanceBinding"]["instances"]["Transport"]
    matches = []
    for path in (output_root / "station-preparation").glob("*/station-plan.json"):
        prior_plan = read(path)
        source = prior_plan["instanceBinding"]["instances"]["source"]
        if source["instanceId"] != dependency["instanceId"]:
            continue
        index = read(output_root / path.parent.name / "station-postcheck.json")
        if (source["moduleDefinitionId"] != dependency["moduleDefinitionId"]
                or index["planSha256"] != sha(path)
                or index["savedStateSha256"] != sha(index["savedStatePath"])):
            raise ValueError("扫描依赖的已提交实例证据已变化。")
        # Recompute the predecessor proof rather than trusting a mutable summary.
        prior_closure = read(output_root / path.parent.name / "stage-closure.json")
        envelope_path = prior_closure["executionEnvelopePath"]
        if sha(envelope_path) != prior_closure["executionEnvelopeSha256"]:
            raise ValueError("扫描依赖的执行证据已变化。")
        cad_path = read(envelope_path)["cadResultPath"]
        if sha(cad_path) != index["cadResultSha256"]:
            raise ValueError("扫描依赖的CAD证据已变化。")
        checked = verify_station_stage(ROOT, prior_plan, cad_result_path=cad_path,
                                       saved_state_path=index["savedStatePath"])
        if not checked.get("targetStationValidated"):
            raise ValueError("扫描依赖的工位验证已失效。")
        matches.append({"savedStatePath": index["savedStatePath"],
                        "savedStateSha256": index["savedStateSha256"],
                        "componentName": checked["sourceInstance"]["name"]})
    if len(matches) != 1:
        raise ValueError("扫描依赖没有唯一的已提交CAD实例。")
    return {dependency["instanceId"]: matches[0]}


def verify_stage_checkpoint(output_root, stage_id, closure, *, expected_count):
    """Reopen a succeeded packet without rerunning insertion, then apply its rule.

    Failed inspections remain immutable attempts; a retry opens a new report.
    Existing successful evidence is recomputed, not trusted by its old label.
    """
    plan_path = output_root / "station-preparation" / stage_id / "station-plan.json"
    plan = read(plan_path)
    dependencies = station_dependency_states(output_root, plan)
    dependency_kwargs = {"dependency_states": dependencies} if dependencies else {}
    envelope_path = Path(closure["executionEnvelopePath"])
    if sha(envelope_path) != closure["executionEnvelopeSha256"]:
        raise ValueError("阶段执行证据已变化。")
    envelope = read(envelope_path)
    cad_path = Path(envelope["cadResultPath"])
    stage_root = output_root / stage_id
    committed = stage_root / "station-postcheck.json"
    if committed.exists():
        old = read(committed)
        if (old["planSha256"] != sha(plan_path) or old["cadResultSha256"] != sha(cad_path)
                or old["savedStateSha256"] != sha(old["savedStatePath"])):
            raise ValueError("已提交工位检查证据已变化。")
        checked = verify_station_stage(ROOT, plan, cad_result_path=cad_path,
                                       saved_state_path=Path(old["savedStatePath"]), **dependency_kwargs)
        if not checked.get("cadPassed") or not checked.get("targetStationValidated"):
            raise ValueError("已提交工位复核不再通过。")
        return old
    attempts = stage_root / "station-check-attempts"
    attempts.mkdir(parents=True, exist_ok=True)
    attempt = attempts / f"attempt-{len(list(attempts.glob('attempt-*')))+1:03}"
    attempt.mkdir()
    state_path = attempt / "reopened-state.json"
    started, clock = now(), perf_counter()
    command = [sys.executable, str(ROOT / "scripts/verify_datum_chain_live_state.py"),
        "--cad-result", str(cad_path), "--report", str(state_path),
        "--count", str(expected_count), "--base", plan["targetBaseDefinitionId"].split("::")[1],
        "--source", envelope["executionSourceAssemblyPath"]]
    completed = subprocess.run(command, capture_output=True, timeout=360)
    write_new(attempt / "inspection-process.json", {
        "startedAtUtc": started, "finishedAtUtc": now(), "durationSeconds": perf_counter()-clock,
        "returnCode": completed.returncode,
        "stdout": completed.stdout.decode("utf-8", errors="replace"),
        "stderr": completed.stderr.decode("utf-8", errors="replace")})
    if completed.returncode:
        raise ValueError("独立重开检查失败；保留已成功CAD包，恢复时只重试复核。")
    try:
        checked = verify_station_stage(ROOT, plan, cad_result_path=cad_path, saved_state_path=state_path,
                                       **dependency_kwargs)
    except (ValueError, OSError, KeyError) as exc:
        write_new(attempt / "postcheck-error.json", {
            "finishedAtUtc": now(), "errorType": type(exc).__name__, "message": str(exc),
            "planPath": str(plan_path.resolve()), "cadResultPath": str(cad_path.resolve()),
            "savedStatePath": str(state_path.resolve()), "checkpointCommitted": False,
            "cadInsertionWillNotBeRepeatedOnResume": True})
        raise
    write_new(attempt / "postcheck.json", checked)
    if not checked.get("cadPassed") or not checked.get("targetStationValidated"):
        raise ValueError("当前工位验证未通过，不能推进下一检查点。")
    result = {"planSha256": sha(plan_path), "cadResultSha256": sha(cad_path),
        "savedStatePath": str(state_path.resolve()), "savedStateSha256": sha(state_path),
        "postcheckPath": str((attempt / "postcheck.json").resolve()),
        "targetStationValidated": True, "functionalPassed": None}
    write_new(committed, result)
    return result


def validate_runtime_source(preflight, stage_id, checkpoint):
    if not preflight.get("ruleDriven"):
        return validate_stage_source_checkpoint(preflight, stage_id, checkpoint)
    # The existing multi-release guard proves predecessor identity. Unlike the
    # legacy preflight, a fresh chain must not equal an old assembly's bytes.
    if checkpoint and checkpoint.get("assemblyPath"):
        if sha(checkpoint["assemblyPath"]) != checkpoint.get("assemblySha256"):
            raise ValueError("当前累计检查点已变化。")


def execute_chain(output_root: Path, *, resume=False, fail_before_stage=None, pause_after_stage=None):
    preflight = revalidate_chain_inputs(output_root)
    chain = read(output_root / "chain.json")
    if pause_after_stage and pause_after_stage not in {s["stageId"] for s in chain["stages"]}:
        raise ValueError("暂停位置不是本链的阶段。")
    store = DurableAssemblyJobStore(output_root / "jobs")
    previous_closure = None
    started, clock, results = now(), perf_counter(), []
    for stage_index, stage in enumerate(chain["stages"]):
        preflight = revalidate_chain_inputs(output_root)
        stage_id = stage["stageId"]
        closure_path = output_root / stage_id / "stage-closure.json"
        prior = read(previous_closure) if previous_closure else {}
        validate_runtime_source(preflight, stage_id, {
            "assemblyPath": prior.get("finalAssemblyPath"), "assemblySha256": prior.get("finalAssemblySha256")
        })
        prepared = prepare_multi_release_stage_job(
            ROOT, chain, stage_id=stage_id, store=store,
            artifacts_root=output_root / "execution", previous_closure_path=previous_closure,
        )
        job_id = prepared["jobId"]
        job = store.load(job_id)
        validate_runtime_source(preflight, stage_id,
            ((job.get("plan") or {}).get("multiReleaseStageBinding") or {}).get("sourceCheckpoint"))
        if closure_path.exists():
            # Revalidate rather than trusting a prior success label.
            rebuilt = build_multi_release_stage_closure(ROOT, chain, stage_id=stage_id, store=store, job_id=job_id)
            old = read(closure_path)
            if old != rebuilt:
                raise ValueError("已提交阶段证据发生变化。")
            if (output_root / "station-preparation" / stage_id / "station-plan.json").exists():
                verify_stage_checkpoint(output_root, stage_id, rebuilt, expected_count=stage_index+2)
            previous_closure = closure_path
            results.append({"stageId": stage_id, "jobId": job_id, "status": "reused_committed_checkpoint"})
            if stage_id == pause_after_stage:
                break
            continue
        if job["status"] in {"failed", "paused"}:
            if not resume:
                raise ValueError(f"已有失败/暂停任务，请使用resume：{job_id}")
            store.prepare_resume(job_id)
        stage_clock = perf_counter()
        runner = manifest_cad_step_runner(
            ROOT, store, timeout_seconds=1200,
            fail_before_packet="packet-001" if stage_id == fail_before_stage else None,
        )
        if preflight["placementValidationMode"] == STRICT:
            cad_runner = runner

            def station_guard(job, step, previous, *, _runner=cad_runner, _stage_id=stage_id):
                current_preflight = revalidate_chain_inputs(output_root)
                validate_runtime_source(current_preflight, _stage_id,
                    ((job.get("plan") or {}).get("multiReleaseStageBinding") or {}).get("sourceCheckpoint"))
                return _runner(job, step, previous)

            runner = station_guard
        guarded = guard_multi_release_stage_runner(ROOT, chain, stage_id=stage_id, store=store, runner=runner)
        # CAD may already be committed while a later read-only station check
        # failed. Never insert the same component again just to retry that check.
        result = job if job["status"] == "succeeded" else run_manifest_job(store, job_id, guarded)
        row = {"stageId": stage_id, "jobId": job_id, "status": result["status"], "durationSeconds": perf_counter() - stage_clock}
        results.append(row)
        print(json.dumps({**row, "event": "cad_job_finished",
            "checkpointCommitted": False,
            "stationPostcheckPending": (output_root / "station-preparation" / stage_id / "station-plan.json").exists(),
        }, ensure_ascii=False), flush=True)
        if result["status"] != "succeeded":
            break
        closure = build_multi_release_stage_closure(ROOT, chain, stage_id=stage_id, store=store, job_id=job_id)
        if (output_root / "station-preparation" / stage_id / "station-plan.json").exists():
            try:
                verify_stage_checkpoint(output_root, stage_id, closure, expected_count=stage_index+2)
            except (ValueError, OSError, KeyError, subprocess.TimeoutExpired) as exc:
                # The underlying CAD job may be successful while this stronger
                # station closure is not. Preserve it for read-only retry, but
                # never advertise a committed checkpoint or run its successor.
                row.update(status="station_postcheck_failed", cadJobStatus=result["status"],
                    checkpointCommitted=False, totalStageDurationSeconds=perf_counter()-stage_clock,
                    errorType=type(exc).__name__, error=str(exc))
                print(json.dumps({**row, "event": "stage_station_postcheck_failed"}, ensure_ascii=False), flush=True)
                break
        write_new(closure_path, closure)
        previous_closure = closure_path
        row["checkpointCommitted"] = True
        row["totalStageDurationSeconds"] = perf_counter() - stage_clock
        print(json.dumps({**row, "event": "stage_checkpoint_committed",
            "stationPostcheckPending": False,
        }, ensure_ascii=False), flush=True)
        if stage_id == pause_after_stage:
            break
    completed_all = len(results)==len(chain["stages"]) and all(r["status"] in {"succeeded", "reused_committed_checkpoint"} for r in results)
    station_passed = completed_all and preflight.get("ruleDriven") is True and all(
        read(output_root / s["stageId"] / "station-postcheck.json").get("targetStationValidated") is True
        for s in chain["stages"])
    report = {
        "schemaVersion": "natural-language-staged-chain-run/v1", "chainId": chain["chainId"],
        "startedAtUtc": started, "finishedAtUtc": now(), "durationSeconds": perf_counter()-clock,
        "stages": results, "success": completed_all,
        "pausedAfterStage": pause_after_stage if not completed_all and results and results[-1]["stageId"] == pause_after_stage and previous_closure and (results[-1].get("checkpointCommitted") or results[-1]["status"] == "reused_committed_checkpoint") else None,
        "lastCommittedClosurePath": str(previous_closure) if previous_closure else None,
        "injectedFailureBeforeStage": fail_before_stage,
        "placementValidationMode": preflight["placementValidationMode"],
        "targetStationPreflightPassed": station_preflight_passed(preflight),
        "targetStationValidated": station_passed,
        "targetStationPostcheckStatus": ("failed_current_state" if any(r["status"] == "station_postcheck_failed" for r in results)
            else "passed_current_state" if station_passed else "incomplete_or_legacy_not_validated"),
        "collisionOrBrep": "not_evaluated", "actualFasteningMethod": "not_verified",
    }
    attempts = output_root / "run-attempts"
    number = len(list(attempts.glob("*.json")))+1
    write_new(attempts / f"attempt-{number:03}.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    compile_parser = sub.add_parser("compile")
    compile_parser.add_argument("request", type=Path)
    compile_parser.add_argument("output_root", type=Path)
    compare_parser = sub.add_parser("compare-states", help="只读比较两个真实保存状态的变序或位置参数变化")
    compare_parser.add_argument("request", type=Path)
    compare_parser.add_argument("report", type=Path)
    station_parser = sub.add_parser("plan-stations", help="推导目标工位参数，可生成未发布候选；不启动CAD")
    station_parser.add_argument("request", type=Path)
    station_parser.add_argument("output_root", type=Path)
    station_parser.add_argument("--prepare-candidates", action="store_true")
    verify_parser = sub.add_parser("verify-station", help="依据实际CAD及独立重开记录重算当前工位几何；不启动CAD")
    verify_parser.add_argument("plan", type=Path)
    verify_parser.add_argument("--cad-result", required=True, type=Path)
    verify_parser.add_argument("--state", required=True, type=Path)
    verify_parser.add_argument("--report", required=True, type=Path)
    for name in ("run", "resume"):
        action = sub.add_parser(name)
        action.add_argument("output_root", type=Path)
        action.add_argument("--inject-failure-before-stage")
        action.add_argument("--pause-after-stage")
    args = parser.parse_args()
    if args.command == "compare-states":
        args.report.resolve().relative_to(ROOT.resolve())
        result = compare_saved_states(args.request, args.report)
        print(json.dumps({"success": result["success"], "checks": result["checks"], "newCadExecuted": False}, ensure_ascii=False))
        return 0 if result["success"] else 2
    if args.command == "verify-station":
        args.report.resolve().relative_to(ROOT.resolve())
        if args.report.exists():
            raise FileExistsError(args.report)
        result = verify_station_stage(ROOT, read(args.plan), cad_result_path=args.cad_result, saved_state_path=args.state)
        write_new(args.report, result)
        print(json.dumps({k: result[k] for k in ("ruleId", "cadPassed", "proxyGeometryPassed", "functionalPassed", "newCadExecutedByThisVerifier")}, ensure_ascii=False))
        return 0 if result["targetStationValidated"] else 2
    if args.command == "plan-stations":
        result = plan_stations(args.request.resolve(), args.output_root.resolve(), prepare_candidates=args.prepare_candidates)
        print(json.dumps({"planningPath": str(args.output_root.resolve() / "station-planning.json"),
            "planningComplete": result["planningComplete"], "plannedStageCount": result["plannedStageCount"],
            "requestedStageCount": result["requestedStageCount"], "durationSeconds": result["durationSeconds"],
            "cadStarted": False, "blockingStages": [{"stageId": r["stageId"], "reasons": r["blockingReasonCodes"]}
                for r in result["stages"] if not r["planned"]]}, ensure_ascii=False, indent=2))
        return 0 if result["planningComplete"] else 2
    if args.command == "compile":
        result = compile_chain(args.request.resolve(), args.output_root.resolve())
    else:
        result = execute_chain(args.output_root.resolve(), resume=args.command == "resume", fail_before_stage=args.inject_failure_before_stage, pause_after_stage=args.pause_after_stage)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 0 if result.get("success", result.get("status") == "ready_not_started") else 2


if __name__ == "__main__":
    raise SystemExit(main())
