"""Formal closure for Project03 runtime top-level pose detachment."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


def _get(mapping: dict[str, Any], key: str, default: Any = None) -> Any:
    if key in mapping:
        return mapping[key]
    wanted = key.casefold()
    for observed, value in mapping.items():
        if str(observed).casefold() == wanted:
            return value
    return default


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _cad_gate(result: dict[str, Any], expected_mates: int) -> dict[str, Any]:
    tool = result.get("toolResult") or {}
    output = Path(str(_get(tool, "OutputAssemblyPath") or ""))
    translation = float(_get(tool, "CaseAnchorTranslationErrorMeters", 1.0) or 0.0)
    rotation = float(_get(tool, "CaseAnchorRotationError", 1.0) or 0.0)
    checks = {
        "actionSucceeded": result.get("success") is True and _get(tool, "Success") is True,
        "independentComponentInserted": _get(tool, "IndependentComponentInserted") is True,
        "caseAnchorApplied": _get(tool, "TargetCaseAnchored") is True,
        "caseAnchorPoseMatch": _get(tool, "CaseAnchorPoseMatch") is True,
        "caseAnchorTranslationWithinTolerance": translation <= 1e-7,
        "caseAnchorRotationWithinTolerance": rotation <= 1e-7,
        "createdMateCountMatches": int(_get(tool, "CreatedMateCount", -1)) == expected_mates,
        "reopened": _get(tool, "Reopened") is True,
        "mateParametersMatch": _get(tool, "ReopenedMateParametersMatch") is True,
        "fullyConstrained": _get(tool, "TargetFullyConstrained") is True,
        "constraintStateAccepted": _get(tool, "TargetConstraintStateAccepted") is True,
        "mateSolveClean": _get(tool, "MateSolveClean") is True,
        "componentSemanticsMatch": _get(tool, "ComponentSemanticsMatch") is True,
        "outputExists": output.is_file(),
    }
    validations = list(_get(tool, "ValidationResults", []) or [])
    checks["validationRelationsPassed"] = all(
        _get(item, "Passed") is True for item in validations
    )
    return {
        "success": all(checks.values()),
        "checks": checks,
        "durationSeconds": float(result.get("durationSeconds") or 0.0),
        "assemblyPath": str(output),
        "assemblySha256": _sha256(output) if output.is_file() else None,
        "caseAnchorTranslationErrorMeters": translation,
        "caseAnchorRotationError": rotation,
        "validationResults": validations,
    }


def build_project03_deprototype_closure(
    compile_ablation: dict[str, Any],
    calibrated_parameters_path: Path,
    ag00_result: dict[str, Any],
    ab00_result: dict[str, Any],
) -> dict[str, Any]:
    compile_gate = bool(
        compile_ablation.get("success") is True
        and compile_ablation.get("status")
        == "PASSED_RUNTIME_TOP_LEVEL_POSE_DETACHMENT"
        and int(compile_ablation.get("moduleCount") or 0) == 2
        and all(
            row.get("compiledTransformStableUnderSourcePosePerturbation") is True
            and row.get("runtimePrototypeTopLevelPoseReadRequired") is False
            for row in compile_ablation.get("modules") or []
        )
    )
    parameter_gate = calibrated_parameters_path.is_file()
    ag_gate = _cad_gate(ag00_result, 2)
    ab_gate = _cad_gate(ab00_result, 1)
    ab_validations = ab_gate["validationResults"]
    distance_gate = bool(
        len(ab_validations) == 1
        and _get(ab_validations[0], "RelationTypeName") == "swMateDISTANCE"
        and abs(float(_get(ab_validations[0], "ExpectedDistanceMeters", 0.0)) - 0.04)
        <= 1e-12
        and _get(ab_validations[0], "Passed") is True
    )
    success = compile_gate and parameter_gate and ag_gate["success"] and ab_gate["success"] and distance_gate
    return {
        "schemaVersion": "project03-deprototype-closure/v1",
        "projectId": "project03",
        "success": success,
        "status": (
            "PROJECT03_RUNTIME_POSE_DEPENDENCY_REDUCED_CAD_VALIDATED"
            if success
            else "PROJECT03_RUNTIME_POSE_DEPENDENCY_REDUCTION_BLOCKED"
        ),
        "compileAblationGate": compile_gate,
        "calibratedParameterGate": {
            "passed": parameter_gate,
            "path": str(calibrated_parameters_path),
            "sha256": (
                _sha256(calibrated_parameters_path) if parameter_gate else None
            ),
        },
        "cadGates": {"AG00": ag_gate, "AB00": ab_gate},
        "ab00DistanceValidationGate": distance_gate,
        "totalCadActionDurationSeconds": round(
            ag_gate["durationSeconds"] + ab_gate["durationSeconds"], 6
        ),
        "runtimePrototypeTopLevelPoseReadRequired": False if success else None,
        "productionReady": False,
        "remainingPrototypeDerivedParameters": [
            "AG00 anti-rotation residual orientation in the calibrated parameter set",
            "AB00 unsupported Width1 replacement pose in the calibrated parameter set",
            "AC00 hybrid static snapshot geometry and internal state",
            "prototype-derived process envelopes and optical proxies",
        ],
        "nextGate": "Replace temporary calibrated values with explicit engineering datums and rerun the affected CAD and collision gates.",
    }
