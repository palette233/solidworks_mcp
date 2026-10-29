"""Summarize the measured GN00 mixed-interface experiment; never launch CAD."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
import math
import ntpath
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / "apps/demo-backend/src"))
from demo_backend.datum_chain_verification import compare_cad_states
from demo_backend.multi_release_cad_chain import (
    build_multi_release_stage_closure, validate_multi_release_cad_chain,
)
from demo_backend.semantic_assembly_jobs import DurableAssemblyJobStore

EXPERIMENT=ROOT / "demo/cross_project_substitution/six-role-gn00-datum-20261024-v1"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path,value):
    if Path(path).exists():
        if read(path) != value:
            raise ValueError(f"拒绝覆盖已有不同证据：{path}")
        return
    with Path(path).open("x",encoding="utf-8") as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False)
        stream.write("\n")


def report_generation_time(path):
    """Reverification retains the immutable report's original creation time."""
    if not Path(path).exists():
        return datetime.now(timezone.utc).isoformat()
    previous=read(path)
    if previous.get("schemaVersion")!="gn00-six-role-datum-experiment/v1":
        raise ValueError("已有汇总报告类型不匹配。")
    value=previous.get("generatedAtUtc")
    if not isinstance(value,str) or datetime.fromisoformat(value.replace("Z","+00:00")).tzinfo is None:
        raise ValueError("已有汇总报告时间戳无效。")
    return value


def stage_attempt_timings(job):
    steps=job.get("steps") or []
    if job.get("status")!="succeeded" or len(steps)!=1 or steps[0].get("status")!="succeeded":
        raise ValueError("阶段计时需要成功的单包任务。")
    attempts=steps[0].get("attempts") or []
    if not attempts or len(attempts)!=steps[0].get("attemptCount") or any(
        type(a.get("durationSeconds")) not in (int,float)
        or not math.isfinite(a["durationSeconds"]) or a["durationSeconds"]<0
        or not a.get("completedAt") for a in attempts
    ):
        raise ValueError("阶段尝试计时缺失或无效。")
    return {"attempts":attempts,"lastSuccessfulAttemptSeconds":attempts[-1]["durationSeconds"],
            "failedAttemptSeconds":sum(a["durationSeconds"] for a in attempts[:-1])}


def chain_timing_summary(stages,run_attempts):
    if not run_attempts:
        raise ValueError("缺少run调用计时。")
    start=datetime.fromisoformat(run_attempts[0]["startedAtUtc"].replace("Z","+00:00"))
    end=datetime.fromisoformat(run_attempts[-1]["finishedAtUtc"].replace("Z","+00:00"))
    if start.tzinfo is None or end.tzinfo is None or end<start:
        raise ValueError("run首尾时间无效。")
    durations=[a.get("durationSeconds") for a in run_attempts]
    if any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in durations):
        raise ValueError("run调用耗时缺失或无效。")
    return {"totalRunInvocationSeconds":sum(durations),"wallSpanSeconds":(end-start).total_seconds(),
            "successfulStepSeconds":sum(s["lastSuccessfulAttemptSeconds"] for s in stages),
            "failedAttemptSeconds":sum(s["failedAttemptSeconds"] for s in stages),
            "timingDefinitions":{
                "totalRunInvocationSeconds":"各run/resume调用耗时之和，含执行与编排开销，不含调用间诊断等待。",
                "wallSpanSeconds":"首run开始至末run结束的墙钟跨度，包含中间诊断、修复和等待。",
                "successfulStepSeconds":"每个单包任务最后成功尝试的durationSeconds之和，不含之前失败重试。",
                "failedAttemptSeconds":"各任务最后成功尝试之前的attempt耗时之和，包含CAD失败与注入失败。",
                "jobExecutionSeconds":"阶段任务累计执行耗时，可包含失败和成功尝试及执行开销，不等同于成功单包时间。",
                "nestedCadTimings":"cadAdapterSeconds和cadPhaseSeconds属于成功尝试内部时间，不应与上述总量相加。",
            }}


def target_alias_matches(alias,tool):
    """Legacy scanner graphs use the full file token instead of its short alias."""
    actual=str(tool.get("TargetModuleToken") or "").upper()
    alias=str(alias).upper()
    source=ntpath.basename(str(tool.get("TargetModuleSourcePath") or "")).upper()
    return actual==alias or (actual.endswith(alias) and source==f"{actual}.001.SLDASM")


def verified_cad(path):
    """Bind the adapter result to its current output and executed mate graph."""
    cad=read(path)
    if cad.get("success") is not True or cad.get("toolResult",{}).get("Success") is not True:
        raise ValueError("CAD结果未通过。")
    graph_path=Path(cad["executionEffectiveGraphPath"])
    if sha(graph_path)!=cad.get("executionEffectiveGraphSha256"):
        raise ValueError("CAD执行图摘要不匹配。")
    if sha(cad["outputAssemblyPath"])!=cad.get("outputAssemblySha256"):
        raise ValueError("CAD输出实体摘要不匹配。")
    return cad,read(graph_path)


def verified_state(path,cad):
    state=read(path)
    if (state.get("success") is not True or state.get("observed",{}).get("readOnly") is not True
            or not state.get("checks") or not all(value is True for value in state["checks"].values())
            or Path(state["assemblyPath"]).resolve()!=Path(cad["outputAssemblyPath"]).resolve()
            or state.get("assemblySha256")!=cad["outputAssemblySha256"]
            or sha(state["assemblyPath"])!=state["assemblySha256"]):
        raise ValueError("只读状态未绑定当前CAD实体或检查未通过。")
    return state


def verified_closure(root,chain,stage):
    path=root / stage["stageId"] / "stage-closure.json"
    closure=read(path)
    rebuilt=build_multi_release_stage_closure(
        ROOT,chain,stage_id=stage["stageId"],
        store=DurableAssemblyJobStore(root / "jobs"),job_id=closure["jobId"],
    )
    if rebuilt!=closure:
        raise ValueError("阶段闭合证据或发布绑定发生变化。")
    return closure


def compare_initial_variants():
    baseline=ROOT / "demo/cross_project_substitution/parameterized-datum-placement-v1/validation-gn00-aa00-v1/cad-result.json"
    root=EXPERIMENT / "initial-variant2"
    cad_a,graph_a=verified_cad(baseline)
    cad_b,graph_b=verified_cad(root / "cad-result.json")
    policies=[graph["EditPolicy"] for graph in (graph_a,graph_b)]
    if (any(p.get("initialPlacementMode")!="deterministic" for p in policies)
            or [p.get("initialPlacementVariant") for p in policies]!=[1,2]
            or graph_a.get("Mates")!=graph_b.get("Mates")
            or Path(cad_a["outputAssemblyPath"]).resolve()==Path(cad_b["outputAssemblyPath"]).resolve()):
        raise ValueError("初始位姿对照必须来自不同初始化变体且使用相同配合束。")
    a=verified_state(root / "default-readonly.json",cad_a)
    b=verified_state(root / "variant2-readonly.json",cad_b)
    result=compare_cad_states(a,b,base_token="AA00")
    result["inputEvidence"]={
        "cadResults":[{"path":str(p),"sha256":sha(p)} for p in (baseline,root / "cad-result.json")],
        "readOnlyReports":[{"path":str(p),"sha256":sha(p)} for p in (root / "default-readonly.json",root / "variant2-readonly.json")],
        "initialPlacementVariants":[1,2],
    }
    return result


def compare_parameter_change():
    """Recompute the specific 354→364 mm experiment, never trust a cached pass."""
    root=EXPERIMENT / "standard-v2"
    chain=read(root / "chain.json")
    source_stage=next(s for s in chain["stages"] if s["stageId"]=="s03-bd00")
    default_stage=next(s for s in chain["stages"] if s["stageId"]=="s04-gn00")
    source=verified_closure(root,chain,source_stage)
    default=verified_closure(root,chain,default_stage)
    default_envelope=read(default["executionEnvelopePath"])
    before_cad,before_graph=verified_cad(default_envelope["cadResultPath"])
    edit_root=EXPERIMENT / "parameter-change"
    changed_cad,changed_graph=verified_cad(edit_root / "cad-result.json")
    if (Path(changed_cad["sourceAssemblyPath"]).resolve()!=Path(source["finalAssemblyPath"]).resolve()
            or changed_cad.get("sourceAssemblySha256Before")!=source["finalAssemblySha256"]
            or changed_cad.get("sourceAssemblySha256After")!=source["finalAssemblySha256"]
            or changed_cad.get("sourceAssemblyUnchanged") is not True):
        raise ValueError("参数实验没有使用并保护同一四模组检查点。")
    before=verified_state(edit_root / "default-five-readonly.json",before_cad)
    after=verified_state(edit_root / "changed-five-readonly.json",changed_cad)

    def selected(graph):
        rows={mate["MateName"].rsplit("_",1)[-1]:mate for mate in graph["Mates"]
              if set(mate.get("ModuleTokens") or [])=={"GN00","AA00"}}
        if set(rows)!={"LONGITUDINAL","LATERAL","SUPPORT"}:
            raise ValueError("参数实验缺少唯一GN00三平面配合束。")
        return rows

    old,new=selected(before_graph),selected(changed_graph)
    for role in old:
        if any(old[role].get(k)!=new[role].get(k) for k in ("MateType","Alignment","Endpoints")):
            raise ValueError("参数实验不得替换配合类型、方向或端点。")
        expected=(.354,.364) if role=="LONGITUDINAL" else (.2535,.2535) if role=="LATERAL" else (None,None)
        actual=(old[role].get("Distance"),new[role].get("Distance"))
        if any((v!=e if e is None else type(v) not in (int,float) or not math.isfinite(v) or abs(v-e)>1e-9) for v,e in zip(actual,expected)):
            raise ValueError("参数实验改变了预期之外的距离。")
    rename={"MCP_GRAPH_"+old[r]["MateName"]:"MCP_GRAPH_"+new[r]["MateName"] for r in old}
    expected={"MCP_GRAPH_"+old["LONGITUDINAL"]["MateName"]:[.354,.364]}
    result=compare_cad_states(before,after,base_token="AA00",moved_token="GN00",
        expected_displacement_meters=[.010,0.,0.],mate_name_map=rename,expected_parameter_changes=expected)
    recorded=read(edit_root / "comparison.json")
    if any(recorded.get(key)!=result[key] for key in ("success","checks","changedParameters","mateNameMap","expectedParameterChanges")):
        raise ValueError("参数比较文件与绑定实体的重新计算结果不一致。")
    result["inputEvidence"]={
        "readOnlyReports":[{"path":str(p),"sha256":sha(p)} for p in (edit_root / "default-five-readonly.json",edit_root / "changed-five-readonly.json")],
        "cadResult":{"path":str(edit_root / "cad-result.json"),"sha256":sha(edit_root / "cad-result.json")},
        "sourceClosureDigest":source["closureDigest"],"defaultClosureDigest":default["closureDigest"],
        "recordedComparisonSha256":sha(edit_root / "comparison.json"),
    }
    return result


def case(name):
    root=EXPERIMENT / name
    chain=read(root / "chain.json")
    validate_multi_release_cad_chain(ROOT,chain)
    timings=[]
    for stage in chain["stages"]:
        closure=verified_closure(root,chain,stage)
        envelope=read(closure["executionEnvelopePath"])
        cad,graph=verified_cad(envelope["cadResultPath"])
        tool=cad["toolResult"]
        job=read(root / "jobs" / closure["jobId"] / "job.json")
        if not (closure["status"]=="passed" and closure["finalAssemblySha256"]==cad["outputAssemblySha256"]
                and Path(closure["finalAssemblyPath"]).resolve()==Path(cad["outputAssemblyPath"]).resolve()
                and envelope["executionEffectiveMateGraphSha256"]==cad["executionEffectiveGraphSha256"]
                and target_alias_matches(closure["moduleToken"],tool)):
            raise ValueError("阶段闭合证据没有绑定当前实体。")
        checks={
            "successfulCad":cad.get("success") is True,
            "threeRealMates":tool.get("RequestedMateCount")==tool.get("CreatedMateCount")==3,
            "fullyConstrained":tool.get("TargetFullyConstrained") is True and tool.get("TargetConstraintStateAccepted") is True,
            "saveReopen":tool.get("Reopened") is True and tool.get("ReopenedMateParametersMatch") is True,
            "mateSolveClean":tool.get("MateSolveClean") is True,
            "noPoseAnchors":tool.get("TargetCaseAnchored") is False and tool.get("RequestedTargetLeafPoseAnchorCount")==tool.get("AppliedTargetLeafPoseAnchorCount")==0,
            "deterministicInitialPose":graph.get("EditPolicy",{}).get("initialPlacementMode")=="deterministic",
            "sourcePreserved":envelope.get("sourceAssemblyUnchanged") is True and envelope.get("executionSourceUnchanged") is True,
            "naturalLanguageTraceComplete":job["plan"].get("sourceCommandAudit",{}).get("status")=="complete",
        }
        timings.append({"stageId":stage["stageId"],"moduleToken":closure["moduleToken"],
                        "mode":stage["relationExecutionMode"],"jobId":job["jobId"],"attemptCount":job["steps"][0]["attemptCount"],
                        **stage_attempt_timings(job),
                        "startedAtUtc":cad.get("startedAtUtc"),"finishedAtUtc":cad.get("finishedAtUtc"),
                        "jobExecutionSeconds":job.get("executionDurationSeconds"),"cadAdapterSeconds":cad.get("durationSeconds"),
                        "cadPhaseSeconds":tool.get("PhaseDurationsSeconds"),"baseWrapperCache":envelope.get("baseWrapperCache"),
                        "outputAssemblyPath":closure["finalAssemblyPath"],"outputAssemblySha256":closure["finalAssemblySha256"],
                        "checks":checks})
    state=verified_state(root / "read-only-final.json",cad)
    if state["assemblySha256"]!=timings[-1]["outputAssemblySha256"]:
        raise ValueError("最终只读状态与最后阶段不匹配。")
    attempts=[read(path) for path in sorted((root / "run-attempts").glob("*.json"))]
    result={"name":name,"moduleOrder":["AA00"]+[r["moduleToken"] for r in timings],
            "stages":timings,"runAttempts":attempts,
            **chain_timing_summary(timings,attempts),
            "naturalLanguageCompileSeconds":read(root / "compilation.json")["durationSeconds"],
            "finalAssemblyPath":timings[-1]["outputAssemblyPath"],"finalAssemblySha256":timings[-1]["outputAssemblySha256"],
            "checks":{"fiveSucceededStages":len(timings)==5 and all(all(v is True for v in t["checks"].values()) for t in timings),
                      "expectedModuleTokens":set(r["moduleToken"] for r in timings)=={"SS00","AI00","BD00","GN00","P000"}
                          and all(sum(f"{token.lower()}.001" in ntpath.basename(c["sourcePath"]).lower() for c in state["observed"]["components"])==1
                                  for token in ("AA00","SS00","AI00","BD00","GN00","P000")),
                      "sixModules":len(state["observed"]["components"])==6,
                      "fifteenMates":len(state["observed"]["allTopLevelMates"])==15,"readOnlyPassed":state["success"] is True}}
    return result,state


def main():
    standard,a=case("standard-v2")
    reordered,b=case("reordered-v2")
    comparison=compare_cad_states(a,b,base_token="AA00")
    initial=compare_initial_variants()
    parameter=compare_parameter_change()
    recovery=reordered["runAttempts"]
    checks={"standardChainPassed":all(standard["checks"].values()),"reorderedChainPassed":all(reordered["checks"].values()),
            "orderEquivalent":comparison["success"],"differentInitialPoseEquivalent":initial["success"],
            "parameterChangeVerified":parameter["success"],
            "failureAndResumeRecorded":len(recovery)>=2 and recovery[0]["success"] is False and recovery[-1]["success"] is True,
            "successfulPrefixNotRerun":len(recovery)>=2 and all(r["status"]=="reused_committed_checkpoint" for r in recovery[-1]["stages"][:2]),
            "onlyInjectedStageRetried":all(r["attemptCount"]==(2 if r["moduleToken"]=="SS00" else 1) for r in reordered["stages"])}
    report={"schemaVersion":"gn00-six-role-datum-experiment/v1","success":all(checks.values()),"checks":checks,
            "generatedAtUtc":report_generation_time(EXPERIMENT / "experiment-summary.json"),"cases":[standard,reordered],
            "initialPoseComparison":initial,"orderComparison":comparison,"parameterChange":parameter,
            "collisionOrBrep":"not_evaluated","actualFasteningMethod":"not_verified",
            "limitations":["CLI有序自然语言清单加已确认选型，内部按独立发布分阶段编译；没有声称前端单会话交互已更新。",
                           "两条实测顺序不代表任意排列；位置参数变化为显式CAD候选验证，不静默改写已发布默认参数。",
                           "CAD前注入失败验证检查点恢复，不模拟SolidWorks进程崩溃或掉电。"]}
    if report["success"]:
        for label,result in (("standard",standard),("reordered",reordered)):
            target=EXPERIMENT / f"six-role-gn00-{label}.SLDASM"
            if target.exists():
                if sha(target)!=result["finalAssemblySha256"]:
                    raise ValueError("短路径产物已存在且内容不同。")
            else:
                shutil.copy2(result["finalAssemblyPath"],target)
            result["deliveryAssemblyPath"]=str(target)
            result["deliverySha256Matches"]=sha(target)==result["finalAssemblySha256"]
    # All required inputs are checked before any final evidence is emitted.
    if not report["success"]:
        print(json.dumps({"success":False,"checks":checks},ensure_ascii=False,indent=2))
        return 2
    write(EXPERIMENT / "order-comparison.json",comparison)
    write(EXPERIMENT / "initial-variant2/comparison.json",initial)
    write(EXPERIMENT / "experiment-summary.json",report)
    print(json.dumps({"success":report["success"],"checks":checks,"timings":[{"case":r["name"],"seconds":r["totalRunInvocationSeconds"]} for r in report["cases"]]},ensure_ascii=False,indent=2))
    return 0 if report["success"] else 2


if __name__=="__main__":
    raise SystemExit(main())
