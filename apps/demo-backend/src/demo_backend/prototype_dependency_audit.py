from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .parameter_authority_registry import (
    ParameterAuthorityRegistryError,
    audit_parameter_authorities,
)
from .project_assembly_profile import load_project_assembly_profile


DEPENDENCY_AUDIT_SCHEMA = "prototype-dependency-audit/v1"
PRODUCTION_ACCEPTED_CONFIDENCE = {"vendor-confirmed", "engineer-confirmed"}


def audit_project_profile_dependencies(
    project_id: str,
    *,
    workspace: Path | None = None,
) -> dict[str, Any]:
    profile = load_project_assembly_profile(project_id)
    workspace = (workspace or Path(__file__).resolve().parents[4]).resolve()
    parameter_audit = None
    parameter_modules: dict[str, dict[str, Any]] = {}
    try:
        parameter_audit = audit_parameter_authorities(workspace, project_id)
        parameter_modules = {
            str(row["moduleToken"]): row for row in parameter_audit["modules"]
        }
    except ParameterAuthorityRegistryError:
        # Profiles created before the parameter-authority workflow retain the
        # conservative module-level confidence behavior.
        parameter_audit = None
    modules = []
    counts: Counter[str] = Counter()
    production_blockers = []
    for token, row in profile["modules"].items():
        confidence = str(row["sourceConfidence"])
        counts[confidence] += 1
        limitations = [str(value) for value in (row.get("assemblyPolicy") or {}).get("engineeringLimitations") or []]
        parameter_module = parameter_modules.get(token)
        accepted = (
            bool(parameter_module["productionAuthorityAccepted"])
            if parameter_module is not None
            else confidence in PRODUCTION_ACCEPTED_CONFIDENCE
        )
        modules.append(
            {
                "moduleToken": token,
                "moduleLabel": row["label"],
                "sourceConfidence": confidence,
                "staticDemoAccepted": confidence != "temporary-estimate",
                "productionAuthorityAccepted": accepted,
                "parameterAuthorityRequirementIds": (
                    parameter_module.get("requirementIds", [])
                    if parameter_module is not None
                    else []
                ),
                "pendingParameterAuthorityRequirementIds": (
                    parameter_module.get("pendingRequirementIds", [])
                    if parameter_module is not None
                    else []
                ),
                "engineeringLimitations": limitations,
            }
        )
        if not accepted:
            production_blockers.append(
                {
                    "moduleToken": token,
                    "sourceConfidence": confidence,
                    "requiredReplacement": (
                        "用厂商安装/光学/行程数据或机械工程师签认值替换，并重新运行静态与动态门禁。"
                    ),
                    "pendingParameterAuthorityRequirementIds": (
                        parameter_module.get("pendingRequirementIds", [])
                        if parameter_module is not None
                        else []
                    ),
                }
            )

    release = profile.get("releaseBoundary") or {}
    return {
        "schemaVersion": DEPENDENCY_AUDIT_SCHEMA,
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "projectId": profile["projectId"],
        "projectProfile": {
            "profileVersion": profile["profileVersion"],
            "profileDigest": profile["profileDigest"],
            "profilePath": profile["profilePath"],
        },
        "countsBySourceConfidence": dict(sorted(counts.items())),
        "modules": modules,
        "prototypeDependentModuleCount": sum(
            1 for row in modules if row["sourceConfidence"] == "inferred-from-prototype"
        ),
        "productionAuthorityAcceptedModuleCount": sum(
            1 for row in modules if row["productionAuthorityAccepted"]
        ),
        "staticDemoProfileAccepted": all(row["staticDemoAccepted"] for row in modules),
        "productionProfileAccepted": not production_blockers,
        "productionBlockers": production_blockers,
        "parameterAuthorityAudit": (
            {
                "registry": parameter_audit["registry"],
                "requirementCount": parameter_audit["requirementCount"],
                "productionAcceptedRequirementCount": parameter_audit[
                    "productionAcceptedRequirementCount"
                ],
                "staticDemoParameterEvidenceAccepted": parameter_audit[
                    "staticDemoParameterEvidenceAccepted"
                ],
                "productionParameterAuthorityAccepted": parameter_audit[
                    "productionParameterAuthorityAccepted"
                ],
                "productionBlockers": parameter_audit["productionBlockers"],
            }
            if parameter_audit is not None
            else None
        ),
        "productionDynamicRequirements": [
            str(value) for value in release.get("productionDynamicRequires") or []
        ],
    }
