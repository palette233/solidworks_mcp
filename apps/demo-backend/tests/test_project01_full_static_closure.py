from __future__ import annotations
from pathlib import Path
from demo_backend.project01_full_static_closure import build_project01_full_static_closure


def test_static_closure_separates_demo_success_from_dynamic_release(tmp_path: Path) -> None:
    assembly=tmp_path/"final.SLDASM";assembly.write_bytes(b"cad")
    tokens=("JJ00","HL00","SS00","FF00","SM00","GN00","BD00","GJ00")
    identity=[1,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0]
    source={"Modules":[{"ModuleToken":t,"SourceTransform":identity} for t in tokens]}
    poses={"components":[*[{"Name":t,"Transform":identity} for t in tokens],{"Name":"project01_LM00_ZZ00_static_context_v1-1","Transform":identity}]}
    broad={"status":"BROAD_PHASE_COMPLETE","allTopLevelPairCount":36,"aabbProvenPairCount":17,"exactCandidatePairCount":19,"broadPhase":[{}]*36,"timing":{"totalDurationSeconds":1}}
    pairs=[{"acceptance":{"accepted":True,"policy":"zeroInterference"}},{"acceptance":{"accepted":True,"policy":"zeroInterference"}},{"acceptance":{"accepted":True,"policy":"noNewInterferenceOverAcceptedBaseline"}},{"acceptance":{"accepted":True,"policy":"noNewInterferenceOverAcceptedBaseline"}}]
    exact={"requestedPairCount":4,"completedPairCount":4,"acceptedPairCount":4,"hardFailureCount":0,"pairs":pairs,"timing":{"durationSeconds":1}}
    tool_subset={"Reopened":True,"PathsMatch":True,"RootPosesMatch":True,"ReopenedTopLevelComponentCount":2}
    tool_insert={"IndependentComponentInserted":True,"CreatedMateCount":0,"ReopenedMateParametersMatch":True,"TargetFullyConstrained":True}
    reach={"coarseLayoutUsable":True,"allRequiredTargetsInsideCommonReach":True,"requiredTargetCount":8,"requiredTargetChecks":[{"insideCommonReach":True}]*8,"engineeringConfirmed":False,"vendorConfirmed":False}
    result=build_project01_full_static_closure(source_graph=source,prior_closures=[{"success":True}]*6,dynamic_attempts=[{"success":False},{"success":False}],subset_run={"success":True,"toolResult":tool_subset},lm_comparison={"stable":True,"comparedCount":202,"maximumTransformElementError":1e-8},zz_comparison={"stable":True,"comparedCount":156,"maximumTransformElementError":1e-8},insert_run={"success":True,"toolResult":tool_insert},poses=poses,broadphase=broad,exact_batch=exact,valve_reach=reach,assembly_path=assembly)
    assert result["success"] is True
    assert result["staticDemoPassed"] is True
    assert result["productionReady"] is False
    assert result["dynamicSemanticsGate"]["passed"] is False
    assert result["dynamicSemanticsGate"]["failureCaptured"] is True
    assert result["collisionGate"]["prototypeBaselineAcceptedPairCount"]==2
    assert result["absoluteZeroInterferenceClaimed"] is False
