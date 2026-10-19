"""Record the explicit Project05 glue-supply scope decision."""

from __future__ import annotations

from typing import Any


def build_project05_glue_supply_scope(manifest: dict[str, Any]) -> dict[str, Any]:
    project = next(
        (item for item in manifest.get("projects") or [] if str(item.get("projectId")) == "05"),
        None,
    )
    if project is None:
        raise ValueError("Project05 is absent from the module manifest")
    glue_rows = [
        item
        for item in project.get("modules") or []
        if "glue_supply" in (item.get("capabilities") or [])
    ]
    if len(glue_rows) != 1 or glue_rows[0].get("cadId"):
        raise ValueError("Project05 glue-supply manifest row must be one unresolved optional capability")
    return {
        "schemaVersion": "project05-glue-supply-scope/v1",
        "projectId": "project05",
        "status": "PROJECT05_GLUE_SUPPLY_EXTERNAL_CONTEXT_DECISION_RECORDED",
        "coarseLayoutUsable": True,
        "engineeringConfirmed": False,
        "manifestEvidence": glue_rows[0],
        "scopeDecision": {
            "partOfNineObjectTop3Solve": False,
            "classification": "fixed-external-utility-context",
            "reason": "PPT requires glue supply, but no independent numbered major top-level assembly is mapped in Project05",
            "mustBeAddedBeforeFullMachineProductionRelease": True,
        },
        "requiredLaterEvidence": [
            "identify the physical glue-supply parent component or external skid",
            "register hose connection port, minimum bend radius and maintenance route",
            "run static and swept collision checks for the complete hose route",
        ],
        "releaseDecision": {
            "coarseNineObjectLayoutMayProceed": True,
            "fullMachineProductionReleaseMayProceed": False,
        },
    }
