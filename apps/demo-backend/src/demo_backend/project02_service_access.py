from __future__ import annotations
from typing import Any


SERVICE_COMPONENTS = {
    "FL9A24D062A500.001-1": "A500",
    "FL9A24D062A700.001-1": "A700",
    "FL9A24D062A300.001-1": "A300",
}


def build_project02_service_access_audit(
    request: dict[str, Any], preview: dict[str, Any]
) -> dict[str, Any]:
    semantics = request.get("moduleSemantics") or {}
    modules = {
        module.get("componentName"): module for module in preview.get("modules") or []
    }
    diagnostics = {
        item.get("id"): item for item in preview.get("diagnostics") or []
    }

    rows: list[dict[str, Any]] = []
    all_defined = True
    all_passed = True
    for component, code in SERVICE_COMPONENTS.items():
        parameters = ((semantics.get(component) or {}).get("parameters") or {})
        requested = parameters.get("protectedSpaceBoxesLocal") or []
        rendered = (modules.get(component) or {}).get("protectedSpaces") or []
        checks = []
        for space in requested:
            prefix = f"protected-space-{component}-{space['id']}-"
            expected_partners = list(space.get("hardClearanceWith") or [])
            partner_checks = []
            for partner in expected_partners:
                diagnostic = diagnostics.get(prefix + partner)
                passed = bool(diagnostic and diagnostic.get("success") is True)
                partner_checks.append({"component": partner, "passed": passed})
                all_passed = all_passed and passed
            checks.append(
                {
                    "id": space["id"],
                    "purpose": space.get("purpose"),
                    "partnerChecks": partner_checks,
                    "passed": bool(partner_checks) and all(
                        item["passed"] for item in partner_checks
                    ),
                }
            )
        defined = bool(
            parameters.get("serviceAccessLaneRequired")
            and requested
            and len(rendered) == len(requested)
        )
        all_defined = all_defined and defined
        rows.append(
            {
                "moduleCode": code,
                "componentName": component,
                "defined": defined,
                "protectedSpaceCount": len(requested),
                "evidenceStatus": parameters.get("serviceAccessLaneEvidenceStatus"),
                "checks": checks,
                "passed": defined and all(item["passed"] for item in checks),
            }
        )

    success = bool(preview.get("metrics", {}).get("hardFeasible")) and all_defined and all_passed
    return {
        "schemaVersion": "project02-service-access-audit/v1",
        "success": success,
        "status": (
            "COARSE_SERVICE_ACCESS_CLEAR_ENGINEERING_CONFIRMATION_PENDING"
            if success
            else "SERVICE_ACCESS_CONSTRAINT_FAILED"
        ),
        "projectId": "project02",
        "modules": rows,
        "protectedSpaceConstraintCount": sum(
            len(check["partnerChecks"])
            for row in rows
            for check in row["checks"]
        ),
        "usableForCoarseLayout": success,
        "engineeringConfirmed": False,
        "authoritativeForFinalMaintenance": False,
        "remainingInput": (
            "Confirm the real operator/tool maintenance envelopes and split the "
            "combined A700 cleaning (A710/A720) and weighing (A730) access needs."
        ),
    }
