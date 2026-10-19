"""Close Project01 BD00 static mechanical and calibration-target checkpoint."""
from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Any
TOKENS=("JJ00","HL00","SS00","FF00","SM00","GN00","BD00")
def _sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def _v(d:dict[str,Any],k:str,x:Any=None)->Any:return d.get(k,d.get(k[0].lower()+k[1:],x))
def _t(s:str)->str:
 r=[x for x in TOKENS if x in str(s).upper()]
 if len(r)!=1:raise ValueError(f"Unknown token {s!r}")
 return r[0]
def build_project01_bd00_incremental_closure(*,source_graph:dict[str,Any],insert_result:dict[str,Any],poses:dict[str,Any],screening:dict[str,Any],service_points:dict[str,Any],assembly_path:Path)->dict[str,Any]:
 a=assembly_path.resolve();src={str(x["ModuleToken"]):x for x in source_graph.get("Modules") or [] if str(x.get("ModuleToken") or "") in TOKENS};obs={_t(str(x.get("HierarchyPath") or x.get("Name") or "")):x for x in poses.get("components") or []}
 if set(src)!=set(TOKENS) or set(obs)!=set(TOKENS):raise ValueError("Unexpected BD00 checkpoint module set")
 pr=[]
 for token in TOKENS:
  e=[float(v) for v in src[token]["SourceTransform"]];o=[float(v) for v in obs[token]["Transform"]];err=max(abs(x-y) for x,y in zip(e,o,strict=True));p=Path(str(obs[token]["Path"]));pr.append({"moduleToken":token,"maximumTransformElementError":err,"sourceFilePath":str(p.resolve()),"sourceFileSha256":_sha(p),"sourcePoseEquivalent":err<=1e-12})
 pairs=[]
 for row in screening.get("broadPhase") or []:
  pair=[_t(x) for x in row["pair"]];sep=row.get("requiresExactLeafBrep") is not True
  decision="accepted-by-strict-world-aabb-separation" if sep else "accepted-as-unchanged-prior-context" if "BD00" not in pair else "accepted-static-calibration-context-by-source-pose-equivalence"
  pairs.append({"pair":pair,"broadPhaseStatus":row["broadPhaseStatus"],"decision":decision,"accepted":True})
 tool=insert_result.get("toolResult") or {};insert_ok=bool(insert_result.get("success") and _v(tool,"IndependentComponentInserted") is True and int(_v(tool,"CreatedMateCount",-1))==3 and _v(tool,"ReopenedMateParametersMatch") is True and _v(tool,"TargetFullyConstrained") is True and _v(tool,"MateSolveClean") is True)
 pose_ok=len(pr)==7 and all(x["sourcePoseEquivalent"] for x in pr);collision_ok=len(pairs)==21 and int(screening.get("aabbProvenPairCount") or 0)==7 and int(screening.get("exactCandidatePairCount") or 0)==14
 targets=[x for x in service_points.get("servicePorts") or [] if x.get("id")=="calibration-prism-target"]
 target_ok=bool(service_points.get("coarseLayoutUsable") is True and len(targets)==1 and targets[0].get("capability")=="calibration" and targets[0].get("sourceSubassembly")=="FL9C24N074BD00.001-1" and (service_points.get("captureCoverage") or {}).get("bd00",{}).get("coverageComplete") is True)
 passed=insert_ok and pose_ok and collision_ok and target_ok;timing={"bd00IncrementalInsertSeconds":float(insert_result.get("durationSeconds") or 0),"poseCaptureSeconds":float(poses.get("durationSeconds") or 0),"broadPhaseCaptureSeconds":float((screening.get("timing") or {}).get("totalDurationSeconds") or 0)};timing["totalMeasuredSeconds"]=sum(timing.values())
 return {"schemaVersion":"project01-bd00-incremental-closure/v1","projectId":"project01","status":"PROJECT01_BD00_STATIC_CALIBRATION_DEMO_CLOSED" if passed else "PROJECT01_BD00_BLOCKED","success":passed,"staticCheckpointPassed":passed,"productionReady":False,"absoluteZeroInterferenceClaimed":False,"assemblyPath":str(a),"assemblySha256":_sha(a),"componentCount":len(obs),"drivingMateCount":int(_v(tool,"CreatedMateCount",0)),"incrementalInsertGate":{"passed":insert_ok},"poseAudit":{"passed":pose_ok,"maximumTransformElementError":max(x["maximumTransformElementError"] for x in pr),"modules":pr},"collisionGate":{"passed":collision_ok,"pairCount":len(pairs),"aabbSeparatedPairCount":sum(x["decision"]=="accepted-by-strict-world-aabb-separation" for x in pairs),"pairs":pairs},"calibrationTargetGate":{"staticDemoPassed":target_ok,"engineeringConfirmed":targets[0].get("engineeringConfirmed") is True if targets else False,"target":targets[0] if targets else None},"timingSeconds":timing,"limitations":["The 50 mm interface and prism target are prototype-derived.","The prism point is a leaf-envelope proxy, not an authored calibration datum.","Needle insertion depth, camera calibration accuracy and vendor tolerance are unverified."],"nextStep":"Build GJ00 supply-module increment while keeping production calibration blocked." if passed else "Repair BD00 before continuing."}
