from __future__ import annotations
from pathlib import Path
from demo_backend.project01_final_static_snapshot_work_packet import build_project01_final_static_snapshot_work_packet


def test_builds_nine_top_level_nodes_representing_ten_functional_objects(tmp_path: Path) -> None:
    snapshot=tmp_path/"snapshot.SLDASM";snapshot.write_bytes(b"cad")
    prior={"SchemaVersion":"editable-module-mate-graph/v1","SourceAssemblyPath":"source","ModuleCount":8,"InterModuleMateCount":1,"Modules":[{"ModuleToken":f"M{i}","Path":str(tmp_path/f"M{i}.SLDASM"),"HierarchyPath":f"M{i}-1","SourceTransform":[1,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0]} for i in range(8)],"Mates":[{}],"MateBundles":[],"MateBundleCount":0,"EditPolicy":{}}
    comparison={"stable":True,"comparedCount":2,"maximumTransformElementError":1e-9}
    result=build_project01_final_static_snapshot_work_packet(prior,snapshot,{"success":True},comparison,comparison)
    assert result["effectiveGraph"]["ModuleCount"]==9
    assert result["effectiveGraph"]["Mates"]==[]
    assert result["summary"]["finalFunctionalObjectCount"]==10
    assert result["summary"]["productionReady"] is False
    audit=result["effectiveGraph"]["SemanticAssemblyPlanAudit"]["finalStaticSnapshot"]
    assert audit["representedFunctionalModuleTokens"]==["LM00","ZZ00"]
    assert audit["staticGeometryPreserved"] is True
    assert audit["independentMotionGraphReconstructed"] is False
