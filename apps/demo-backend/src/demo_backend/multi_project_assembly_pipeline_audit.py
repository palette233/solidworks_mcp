from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .ordered_assembly_planner import preview_ordered_assembly
from .assembly_release_contract import build_assembly_release_contract
from .project_assembly_profile import (
    ProjectAssemblyProfileError,
    load_project_assembly_profile,
)


SCHEMA = "multi-project-assembly-pipeline-audit/v1"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def audit_multi_project_assembly_pipeline(workspace: Path) -> dict[str, Any]:
    workspace = workspace.resolve()
    calibration_path = workspace / "demo/layout_previews/multi_project_calibration_readiness.json"
    if not calibration_path.is_file():
        raise FileNotFoundError(f"Missing multi-project calibration portfolio: {calibration_path}")
    portfolio = _load(calibration_path)
    profile_directory = workspace / "apps/demo-backend/src/demo_backend/project_profiles"
    projects = []
    for raw in portfolio.get("projects") or []:
        short_id = str(raw.get("projectId") or "")
        project_id = f"project{short_id}"
        profile_path = profile_directory / f"{project_id}.json"
        profile_exists = profile_path.is_file()
        profile = None
        profile_valid = False
        profile_error = None
        plan_preview_ready = False
        plan_missing_implementation_count = None
        if profile_exists:
            try:
                profile = load_project_assembly_profile(project_id)
                profile_valid = True
                sequence = profile["validatedSequence"][1:]
                command = f"项目{short_id}：" + "，".join(
                    ("先添加" if index == 0 else "再添加") + token
                    for index, token in enumerate(sequence)
                ) + "。"
                preview = preview_ordered_assembly(project_id, command)
                plan_preview_ready = preview["plan"]["summary"]["orderValid"] is True
                plan_missing_implementation_count = preview["plan"]["summary"][
                    "missingImplementationCount"
                ]
            except (ProjectAssemblyProfileError, ValueError) as exc:
                profile_error = str(exc)
        expected_closure = None
        closure_exists = False
        closure_document = None
        closure_success = False
        macro_static_passed = False
        full_geometry_closed = False
        if profile:
            artifact = (profile.get("artifacts") or {}).get("fullMachineClosure")
            if artifact:
                expected_closure = (workspace / str(artifact)).resolve()
                closure_exists = expected_closure.is_file()
                if closure_exists:
                    closure_document = _load(expected_closure)
                    release = closure_document.get("releaseDecision") or {}
                    legacy_static_release = (
                        release.get("staticTenObjectDemoReleaseAllowed") is True
                    )
                    closure_success = (
                        closure_document.get("success") is True
                        or legacy_static_release
                    )
                    macro_static_passed = (
                        closure_document.get("macroStaticPassed") is True
                        or closure_success
                    )
                    full_geometry_closed = (
                        closure_document.get("fullGeometryClosed") is True
                        or closure_success
                    )
        layout_ready = raw.get("top3SolveReady") is True
        ordered_pipeline_ready = (
            layout_ready
            and profile_valid
            and plan_preview_ready
            and plan_missing_implementation_count == 0
            and closure_exists
            and closure_success
        )
        blockers = []
        release_contract = (
            build_assembly_release_contract(workspace, project_id)
            if profile_valid
            else None
        )
        if not layout_ready:
            blockers.extend(str(value) for value in raw.get("coarseLayoutBlockers") or [])
        if not profile_exists:
            blockers.append("versionedProjectAssemblyProfile")
        if profile_exists and not profile_valid:
            blockers.append("invalidProjectAssemblyProfile")
        if profile_valid and not plan_preview_ready:
            blockers.append("orderedAssemblyPlanPreview")
        if profile_valid and plan_missing_implementation_count:
            blockers.append("projectSpecificCadActionsAndStepEvidence")
        if profile_valid and not closure_exists:
            blockers.append("fullMachineStaticClosure")
        if profile_valid and closure_exists and not closure_success:
            blockers.append("fullMachineClosureBlocked")
        projects.append(
            {
                "projectId": project_id,
                "family": raw.get("family"),
                "coarseLayoutTop3Ready": layout_ready,
                "versionedAssemblyProfileExists": profile_exists,
                "versionedAssemblyProfileValid": profile_valid,
                "profileError": profile_error,
                "profilePath": str(profile_path),
                "orderedPlanPreviewReady": plan_preview_ready,
                "missingCadImplementationStepCount": plan_missing_implementation_count,
                "fullMachineClosureExists": closure_exists,
                "fullMachineClosurePath": str(expected_closure) if expected_closure else None,
                "fullMachineClosureSuccess": closure_success,
                "macroStaticPassed": macro_static_passed,
                "fullGeometryClosed": full_geometry_closed,
                "closureBlockers": (
                    list(
                        closure_document.get("blockers")
                        or closure_document.get("productionBlockers")
                        or []
                    )
                    if closure_document
                    else []
                ),
                "naturalLanguageOrderedCadPipelineReady": ordered_pipeline_ready,
                "releaseContract": release_contract,
                "staticDemoReady": bool(
                    release_contract
                    and release_contract["release"]["staticDemoAllowed"]
                ),
                "liveCadReady": bool(
                    release_contract and release_contract["release"]["liveCadAllowed"]
                ),
                "dynamicEvidenceConfigured": bool(
                    release_contract and release_contract["dynamic"]["configured"]
                ),
                "dynamicEvidenceStatus": (
                    release_contract["dynamic"]["status"] if release_contract else None
                ),
                "productionReady": bool(
                    release_contract
                    and release_contract["release"]["productionAllowed"]
                ),
                "blockers": blockers,
                "nextStage": (
                    "complete-project-specific-calibration"
                    if not layout_ready
                    else "create-project-profile-and-plan-preview"
                    if not profile_valid or not plan_preview_ready
                    else "restore-flexible-subassembly-state-and-run-conditional-brep"
                    if macro_static_passed and not full_geometry_closed
                    else "implement-project-cad-actions-and-step-evidence"
                    if plan_missing_implementation_count
                    else "replace-prototype-estimates-and-close-dynamics"
                    if ordered_pipeline_ready and not (
                        closure_document and closure_document.get("productionReady") is True
                    )
                    else "execute-and-audit-ordered-cad-chain"
                    if ordered_pipeline_ready
                    else "execute-and-close-ordered-cad-chain"
                ),
            }
        )
    return {
        "schemaVersion": SCHEMA,
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sourcePortfolioPath": str(calibration_path),
        "projects": projects,
        "summary": {
            "projectCount": len(projects),
            "coarseLayoutReadyProjects": [
                row["projectId"] for row in projects if row["coarseLayoutTop3Ready"]
            ],
            "orderedCadPipelineReadyProjects": [
                row["projectId"]
                for row in projects
                if row["naturalLanguageOrderedCadPipelineReady"]
            ],
            "productionReadyProjects": [
                row["projectId"] for row in projects if row["productionReady"]
            ],
        },
    }
