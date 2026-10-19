"""Finalize the Project03 AJ00 glue-supply incremental checkpoint."""
from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Any

TOKENS=("FL9A24D063AA00","FL9A24D063AF00","FL9A24D063AE00","FL9A24D063AD00","FL9A24D063AI00","FL9A24D063AG00","FL9A24D063AH00","FL9A24D063AJ00")
def _get(d:dict[str,Any],n:str,x:Any=None)->Any:return d.get(n,d.get(n[0].lower()+n[1:],x))
def _token(s:str)->str:
 m=[t for t in TOKENS if t in str(s).upper()]
 if len(m)!=1:raise ValueError(f"Cannot identify one Project03 module in {s!r}.")
 return m[0]
def build_project03_aj00_incremental_closure(*,source_graph:dict[str,Any],insert_result:dict[str,Any],poses:dict[str,Any],screening:dict[str,Any],occupancy:dict[str,Any],assembly_path:Path)->dict[str,Any]:
 assembly_path=assembly_path.resolve()
 if not assembly_path.is_file():raise FileNotFoundError(assembly_path)
 source={str(r["ModuleToken"]):r for r in source_graph.get("Modules") or [] if str(r.get("ModuleToken") or "") in TOKENS}
 observed={_token(r.get("Name") or r.get("HierarchyPath") or ""):r for r in poses.get("components") or []}
 if set(source)!=set(TOKENS) or set(observed)!=set(TOKENS):raise ValueError("Expected exactly the eight modules through AJ00.")
 pose_rows=[]
 for token in TOKENS:
  err=max((abs(float(a)-float(b)) for a,b in zip(source[token]["SourceTransform"],observed[token]["Transform"])),default=0.0)
  pose_rows.append({"moduleToken":token,"maximumTransformElementError":err,"sourcePoseEquivalent":err<=1e-12})
 pose_ok=all(r["sourcePoseEquivalent"] for r in pose_rows)
 tool=insert_result.get("toolResult") or {}
 insert_ok=bool(insert_result.get("success") and _get(tool,"IndependentComponentInserted") is True and _get(tool,"TargetCaseAnchored") is False and int(_get(tool,"CreatedMateCount",-1))==3 and _get(tool,"ReopenedMateParametersMatch") is True and _get(tool,"TargetFullyConstrained") is True and _get(tool,"MateSolveClean") is True)
 supply=[r for r in occupancy.get("layoutObjects") or [] if r.get("primaryCode")=="AJ00"]
 maintenance_static_ok=bool(pose_ok and len(supply)==1 and int(supply[0].get("occupancyBoxCount") or 0)==1)
 pairs=[]
 for row in screening.get("broadPhase") or []:
  decision="accepted-by-identical-source-files-and-relative-pose" if row.get("requiresExactLeafBrep") is True else "accepted-by-strict-world-aabb-separation"
  pairs.append({"pair":sorted((_token(row["pair"][0]),_token(row["pair"][1]))),"decision":decision,"accepted":True})
 collision_ok=bool(len(pairs)==28 and int(screening.get("aabbProvenPairCount") or 0)==15 and int(screening.get("exactCandidatePairCount") or 0)==13 and pose_ok)
 success=insert_ok and pose_ok and maintenance_static_ok and collision_ok
 timing={"incrementalInsertSeconds":float(insert_result.get("durationSeconds") or 0),"poseCaptureSeconds":float(poses.get("durationSeconds") or 0),"broadPhaseCaptureSeconds":float((screening.get("timing") or {}).get("totalDurationSeconds") or 0)};timing["totalMeasuredSeconds"]=sum(timing.values())
 return {"schemaVersion":"project03-aj00-incremental-closure/v1","projectId":"project03","status":"PROJECT03_AJ00_STATIC_INCREMENT_CLOSED" if success else "PROJECT03_AJ00_INCREMENT_BLOCKED","success":success,"staticDemoCheckpointPassed":success,"productionReady":False,"zeroInterferenceClaimed":False,"noNewInterferenceOverPrototype":collision_ok,"assemblyPath":str(assembly_path),"assemblySha256":hashlib.sha256(assembly_path.read_bytes()).hexdigest(),"componentCount":len(observed),"installationGate":{"passed":insert_ok,"drivingMateCount":int(_get(tool,"CreatedMateCount",0)),"residualAnchorApplied":False},"poseAudit":{"passed":pose_ok,"maximumTransformElementError":max(r["maximumTransformElementError"] for r in pose_rows),"modules":pose_rows},"maintenanceGate":{"passedForStaticDemo":maintenance_static_ok,"productionReady":False,"staticOccupancyBoxCount":1 if supply else 0,"hoseContinuousSweepAvailable":False,"maintenanceEnvelopeEngineeringConfirmed":False},"collisionGate":{"passed":collision_ok,"pairCount":len(pairs),"aabbSeparatedPairCount":sum("strict-world-aabb" in r["decision"] for r in pairs),"sourcePoseEquivalentCandidatePairCount":sum("source-files-and-relative-pose" in r["decision"] for r in pairs),"pairs":pairs},"timingSeconds":timing,"blockers":["AJ00当前只有保守顶层AABB，没有软管连续扫掠体。","供胶维护空间和管路最小弯曲半径未工程确认。","13个AABB候选只由原型相对位姿等价证明无新增干涉。"],"nextStep":"将AJ00登记为第六个静态CAD动作，随后建立AB00/AC00龙门双对象最终增量。" if success else "暂停龙门步骤；先修复AJ00门禁。"}
