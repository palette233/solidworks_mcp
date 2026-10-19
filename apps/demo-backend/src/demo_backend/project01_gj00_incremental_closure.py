"""Close Project01 GJ00 rigid installation while preserving hose debt."""
from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Any
TOKENS=("JJ00","HL00","SS00","FF00","SM00","GN00","BD00","GJ00")
def _sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def _v(d:dict[str,Any],k:str,x:Any=None)->Any:return d.get(k,d.get(k[0].lower()+k[1:],x))
def _t(s:str)->str:
 r=[x for x in TOKENS if x in str(s).upper()]
 if len(r)!=1:raise ValueError(f"Unknown token {s!r}")
 return r[0]
def build_project01_gj00_incremental_closure(*,source_graph:dict[str,Any],insert_result:dict[str,Any],poses:dict[str,Any],screening:dict[str,Any],assembly_path:Path)->dict[str,Any]:
 a=assembly_path.resolve();src={str(x["ModuleToken"]):x for x in source_graph.get("Modules") or [] if str(x.get("ModuleToken") or "") in TOKENS};obs={_t(str(x.get("HierarchyPath") or x.get("Name") or "")):x for x in poses.get("components") or []}
 if set(src)!=set(TOKENS) or set(obs)!=set(TOKENS):raise ValueError("Unexpected GJ00 checkpoint module set")
 pr=[]
 for token in TOKENS:
  e=[float(v) for v in src[token]["SourceTransform"]];o=[float(v) for v in obs[token]["Transform"]];err=max(abs(x-y) for x,y in zip(e,o,strict=True));p=Path(str(obs[token]["Path"]));pr.append({"moduleToken":token,"maximumTransformElementError":err,"sourceFilePath":str(p.resolve()),"sourceFileSha256":_sha(p),"sourcePoseEquivalent":err<=1e-12})
 pairs=[]
 for row in screening.get("broadPhase") or []:
  pair=[_t(x) for x in row["pair"]];sep=row.get("requiresExactLeafBrep") is not True;decision="accepted-by-strict-world-aabb-separation" if sep else "accepted-as-unchanged-prior-context" if "GJ00" not in pair else "accepted-static-glue-supply-context-by-source-pose-equivalence";pairs.append({"pair":pair,"broadPhaseStatus":row["broadPhaseStatus"],"decision":decision,"accepted":True})
 tool=insert_result.get("toolResult") or {};insert_ok=bool(insert_result.get("success") and _v(tool,"IndependentComponentInserted") is True and int(_v(tool,"CreatedMateCount",-1))==3 and _v(tool,"ReopenedMateParametersMatch") is True and _v(tool,"TargetFullyConstrained") is True and _v(tool,"MateSolveClean") is True);pose_ok=len(pr)==8 and all(x["sourcePoseEquivalent"] for x in pr);collision_ok=len(pairs)==28 and int(screening.get("aabbProvenPairCount") or 0)==13 and int(screening.get("exactCandidatePairCount") or 0)==15;passed=insert_ok and pose_ok and collision_ok
 timing={"gj00IncrementalInsertSeconds":float(insert_result.get("durationSeconds") or 0),"poseCaptureSeconds":float(poses.get("durationSeconds") or 0),"broadPhaseCaptureSeconds":float((screening.get("timing") or {}).get("totalDurationSeconds") or 0)};timing["totalMeasuredSeconds"]=sum(timing.values())
 return {"schemaVersion":"project01-gj00-incremental-closure/v1","projectId":"project01","status":"PROJECT01_GJ00_STATIC_RIGID_DEMO_CLOSED_HOSE_BLOCKED" if passed else "PROJECT01_GJ00_BLOCKED","success":passed,"staticCheckpointPassed":passed,"productionReady":False,"absoluteZeroInterferenceClaimed":False,"assemblyPath":str(a),"assemblySha256":_sha(a),"componentCount":len(obs),"drivingMateCount":int(_v(tool,"CreatedMateCount",0)),"incrementalInsertGate":{"passed":insert_ok},"poseAudit":{"passed":pose_ok,"maximumTransformElementError":max(x["maximumTransformElementError"] for x in pr),"modules":pr},"collisionGate":{"passed":collision_ok,"pairCount":len(pairs),"aabbSeparatedPairCount":sum(x["decision"]=="accepted-by-strict-world-aabb-separation" for x in pairs),"pairs":pairs},"hoseMaintenanceGate":{"passed":False,"blockers":["Hose centerlines and minimum bend radii are not registered.","Continuous hose sweep and maintenance removal path are not validated."]},"timingSeconds":timing,"limitations":["The 220 mm installation interface is prototype-derived.","Rigid GJ00 placement does not prove flexible hose feasibility.","Static source-pose equivalence proves no new penetration, not absolute zero contact."],"nextStep":"Build LM00/ZZ00 final gantry increment; keep hose production release blocked." if passed else "Repair GJ00 before continuing."}
