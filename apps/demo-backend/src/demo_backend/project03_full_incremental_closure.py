"""Summarize the complete Project03 ten-object incremental static CAD chain."""
from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Any

TOKENS=("FL9A24D063AA00","FL9A24D063AF00","FL9A24D063AE00","FL9A24D063AD00","FL9A24D063AI00","FL9A24D063AG00","FL9A24D063AH00","FL9A24D063AJ00","FL9A24D063AB00","FL9A24D063AC00")
def _get(d:dict[str,Any],n:str,x:Any=None)->Any:return d.get(n,d.get(n[0].lower()+n[1:],x))
def _token(s:str)->str:
 m=[t for t in TOKENS if t in str(s).upper()]
 if len(m)!=1:raise ValueError(f"Cannot identify one Project03 module in {s!r}.")
 return m[0]
def build_project03_full_incremental_closure(*,source_graph:dict[str,Any],prior_closures:list[dict[str,Any]],failed_ab00_result:dict[str,Any],ab00_result:dict[str,Any],ac00_result:dict[str,Any],poses:dict[str,Any],screening:dict[str,Any],valve_reach:dict[str,Any],assembly_path:Path)->dict[str,Any]:
 assembly_path=assembly_path.resolve()
 if not assembly_path.is_file():raise FileNotFoundError(assembly_path)
 prior_ok=len(prior_closures)==6 and all(r.get("success") is True for r in prior_closures)
 source={str(r["ModuleToken"]):r for r in source_graph.get("Modules") or [] if str(r.get("ModuleToken") or "") in TOKENS};observed={_token(r.get("Name") or r.get("HierarchyPath") or ""):r for r in poses.get("components") or []}
 if set(source)!=set(TOKENS) or set(observed)!=set(TOKENS):raise ValueError("Expected the complete ten-object Project03 set.")
 pose_rows=[]
 for token in TOKENS:
  err=max((abs(float(a)-float(b)) for a,b in zip(source[token]["SourceTransform"],observed[token]["Transform"])),default=0.0);pose_rows.append({"moduleToken":token,"maximumTransformElementError":err,"sourcePoseEquivalent":err<=1e-12})
 pose_ok=all(r["sourcePoseEquivalent"] for r in pose_rows)
 failed_tool=failed_ab00_result.get("toolResult") or {};ab=_get(ab00_result,"toolResult",{}) or {};ac=_get(ac00_result,"toolResult",{}) or {};vals=list(_get(ab,"ValidationResults",[]) or [])
 ab_failure_captured=bool(failed_ab00_result.get("success") is False and int(_get(failed_tool,"CreatedMateCount",-1))==2 and _get(failed_tool,"ReopenedMateParametersMatch") is False)
 ab_ok=bool(ab00_result.get("success") and _get(ab,"TargetCaseAnchored") is True and _get(ab,"CaseAnchorPoseMatch") is True and int(_get(ab,"CreatedMateCount",-1))==1 and _get(ab,"ReopenedMateParametersMatch") is True and _get(ab,"TargetFullyConstrained") is True and _get(ab,"MateSolveClean") is True and len(vals)==1 and _get(vals[0],"Passed") is True and abs(float(_get(vals[0],"ExpectedDistanceMeters",0))-.04)<=1e-12)
 ac_ok=bool(ac00_result.get("success") and _get(ac,"TargetCaseAnchored") is False and int(_get(ac,"CreatedMateCount",-1))==3 and _get(ac,"ReopenedMateParametersMatch") is True and _get(ac,"TargetFullyConstrained") is True and _get(ac,"MateSolveClean") is True)
 reach_checks=list(valve_reach.get("requiredTargetChecks") or []);reach_ok=bool(valve_reach.get("coarseLayoutUsable") is True and int(valve_reach.get("requiredTargetCount") or 0)==9 and len(reach_checks)==9 and valve_reach.get("allRequiredTargetsInsideCommonReach") is True and all(r.get("insideCommonReach") is True for r in reach_checks));reach_production=bool(reach_ok and valve_reach.get("engineeringConfirmed") is True and valve_reach.get("vendorConfirmed") is True)
 pairs=[]
 for row in screening.get("broadPhase") or []:
  decision="accepted-by-identical-source-files-and-relative-pose" if row.get("requiresExactLeafBrep") is True else "accepted-by-strict-world-aabb-separation";pairs.append({"pair":sorted((_token(row["pair"][0]),_token(row["pair"][1]))),"decision":decision,"accepted":True})
 collision_ok=bool(len(pairs)==45 and int(screening.get("aabbProvenPairCount") or 0)==22 and int(screening.get("exactCandidatePairCount") or 0)==23 and pose_ok)
 success=prior_ok and ab_failure_captured and ab_ok and ac_ok and pose_ok and reach_ok and collision_ok
 action_seconds=[]
 for r in prior_closures:
  t=r.get("timingSeconds") or {};action_seconds.append(float(t.get("ae00IncrementalInsertSeconds") or t.get("ad00IncrementalInsert") or t.get("successfulIncrementalInsertSeconds") or t.get("anchoredIncrementalInsertSeconds") or t.get("incrementalInsertSeconds") or 0))
 action_seconds.extend([float(ab00_result.get("durationSeconds") or 0),float(ac00_result.get("durationSeconds") or 0)])
 return {"schemaVersion":"project03-full-incremental-static-closure/v1","projectId":"project03","status":"PROJECT03_FULL_INCREMENTAL_STATIC_DEMO_CLOSED" if success else "PROJECT03_FULL_INCREMENTAL_STATIC_DEMO_BLOCKED","success":success,"staticDemoPassed":success,"productionReady":False,"zeroInterferenceClaimed":False,"noNewInterferenceOverPrototype":collision_ok,"assemblyPath":str(assembly_path),"assemblySha256":hashlib.sha256(assembly_path.read_bytes()).hexdigest(),"semanticStageCount":7,"cadActionCount":8,"componentCount":len(observed),"priorCheckpointGate":{"passed":prior_ok,"checkpointCount":len(prior_closures)},"finalGantryGate":{"passed":ab_failure_captured and ab_ok and ac_ok,"ab00FailedAttemptCaptured":ab_failure_captured,"ab00":{"drivingMateCount":int(_get(ab,"CreatedMateCount",0)),"validationRelationCount":len(vals),"caseAnchored":True,"unsupportedWidthMatePending":True},"ac00":{"drivingMateCount":int(_get(ac,"CreatedMateCount",0)),"caseAnchored":False,"omittedRedundantCoincident":"重合29"}},"poseAudit":{"passed":pose_ok,"maximumTransformElementError":max(r["maximumTransformElementError"] for r in pose_rows),"modules":pose_rows},"reachGate":{"passedForStaticDemo":reach_ok,"productionReady":reach_production,"requiredTargetCount":len(reach_checks),"allInsideCommonReach":all(r.get("insideCommonReach") is True for r in reach_checks),"minimumBoundaryMarginMeters":valve_reach.get("minimumTargetBoundaryMarginMeters"),"checks":reach_checks},"collisionGate":{"passed":collision_ok,"pairCount":len(pairs),"aabbSeparatedPairCount":sum("strict-world-aabb" in r["decision"] for r in pairs),"sourcePoseEquivalentCandidatePairCount":sum("source-files-and-relative-pose" in r["decision"] for r in pairs),"pairs":pairs},"timingSeconds":{"successfulCadActionsSeconds":sum(action_seconds),"finalPoseCaptureSeconds":float(poses.get("durationSeconds") or 0),"finalBroadPhaseSeconds":float((screening.get("timing") or {}).get("totalDurationSeconds") or 0),"failedAb00IterationSeconds":float(failed_ab00_result.get("durationSeconds") or 0)},"productionBlockers":["AG00 remains dependent on a prototype residual orientation anchor.","AB00 remains dependent on a prototype residual pose anchor because Width1 is unsupported.","AD00 25-degree sweep and AG00 service-tool sweeps are not closed.","Dual-valve 900/1100 mm envelopes and 9-target reach are prototype estimates, not vendor travel limits.","Scanner working distance, calibration action, hose sweep and maintenance clearances remain unconfirmed.","23 broad-phase candidates are accepted only by exact source-pose equivalence; absolute zero interference is not claimed."],"nextStep":"Use this artifact as the complete static Demo checkpoint. Replace residual anchors and inferred process envelopes with engineering-authoritative datums before production or cross-project release."}
