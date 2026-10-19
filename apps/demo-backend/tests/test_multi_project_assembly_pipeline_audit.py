from __future__ import annotations

from pathlib import Path

from demo_backend.multi_project_assembly_pipeline_audit import audit_multi_project_assembly_pipeline


WORKSPACE = Path(__file__).resolve().parents[3]


def test_multi_project_audit_separates_layout_from_ordered_cad_readiness() -> None:
    audit = audit_multi_project_assembly_pipeline(WORKSPACE)
    rows = {row["projectId"]: row for row in audit["projects"]}

    assert audit["summary"]["coarseLayoutReadyProjects"] == [
        "project01",
        "project02",
        "project03",
        "project05",
    ]
    assert audit["summary"]["orderedCadPipelineReadyProjects"] == [
        "project01",
        "project02",
        "project03",
        "project05",
    ]
    assert rows["project01"]["versionedAssemblyProfileExists"] is True
    assert rows["project01"]["versionedAssemblyProfileValid"] is True
    assert rows["project01"]["orderedPlanPreviewReady"] is True
    assert rows["project01"]["missingCadImplementationStepCount"] == 0
    assert rows["project01"]["fullMachineClosureSuccess"] is True
    assert rows["project01"]["naturalLanguageOrderedCadPipelineReady"] is True
    assert rows["project01"]["productionReady"] is False
    assert rows["project01"]["closureBlockers"]
    assert rows["project03"]["macroStaticPassed"] is True
    assert rows["project03"]["missingCadImplementationStepCount"] == 0
    assert rows["project03"]["fullGeometryClosed"] is True
    assert rows["project03"]["fullMachineClosureSuccess"] is True
    assert rows["project03"]["naturalLanguageOrderedCadPipelineReady"] is True
    assert rows["project03"]["staticDemoReady"] is True
    assert rows["project03"]["liveCadReady"] is True
    assert rows["project03"]["dynamicEvidenceConfigured"] is True
    assert rows["project03"]["dynamicEvidenceStatus"].startswith("FAILED_PROJECT03_AD20")
    assert rows["project03"]["nextStage"] == "replace-prototype-estimates-and-close-dynamics"
    assert rows["project05"]["versionedAssemblyProfileExists"] is True
    assert rows["project05"]["versionedAssemblyProfileValid"] is True
    assert rows["project05"]["orderedPlanPreviewReady"] is True
    assert rows["project05"]["coarseLayoutTop3Ready"] is True
    assert rows["project05"]["missingCadImplementationStepCount"] == 0
    assert rows["project05"]["fullMachineClosureSuccess"] is True
    assert rows["project05"]["naturalLanguageOrderedCadPipelineReady"] is True
    assert rows["project05"]["dynamicEvidenceConfigured"] is False
    assert rows["project05"]["blockers"] == []
    assert rows["project05"]["nextStage"] == "replace-prototype-estimates-and-close-dynamics"
    assert rows["project06"]["naturalLanguageOrderedCadPipelineReady"] is False
