from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


STATUS_RANK = {
    "not_required": 0,
    "available": 1,
    "partial": 2,
    "missing": 3,
}

EVIDENCE_DEFINITIONS = [
    ("moduleIdentity", "Major assemblies are mapped to process capabilities."),
    ("moduleCadPaths", "Source CAD paths for the selected module scope are resolvable."),
    ("baseOperationFace", "The operator-facing side of the frame is identified."),
    ("baseTopInstallationSurface", "The frame installation plane and normal are identified."),
    ("transportInstallationFrame", "The transport-to-frame XYZ datum is calibrated."),
    ("transportWorkPositions", "Carrier buffer and dispensing work positions are identified."),
    ("barcodeFaceAndSide", "Barcode target face and transport side are identified."),
    ("scannerWorkingDistanceAndAxis", "Scanner optical origin, axis and usable distance are calibrated."),
    ("ccdWorkingGeometry", "Product CCD optical origin, axis, distance and FOV are calibrated."),
    ("dualValveReach", "The common reachable envelope of the two valve tips is calibrated."),
    ("serviceFunctionPoints", "Calibration, cleaning, weighing and drain service points are identified."),
    ("operationSideCapacity", "Operator-side residual and maintenance space is estimated."),
    ("moduleOccupancy", "Rigid-module occupancy is represented by conservative or multi-box geometry."),
    ("staticCollisionPolicy", "Every relevant module pair has a collision-check class."),
    ("allowedContactsAndSafeStates", "Installation contacts and accepted prototype overlaps are explicitly listed."),
    ("glueSupplyFunctionalInterface", "Glue outlet, hose direction and maintenance access are identified."),
    ("solveScopeCoverage", "All intended top-level instances are represented or explicitly excluded."),
]

COMMON_REQUIRED = {
    "moduleIdentity",
    "moduleCadPaths",
    "baseOperationFace",
    "baseTopInstallationSurface",
    "transportInstallationFrame",
    "transportWorkPositions",
    "operationSideCapacity",
    "moduleOccupancy",
    "staticCollisionPolicy",
}

ALIASES = {
    "calibrationServicePoint": "serviceFunctionPoints",
    "combinedServiceFunctionPoints": "serviceFunctionPoints",
    "calibrationAndWeighingPoints": "serviceFunctionPoints",
    "cleaningServicePoint": "serviceFunctionPoints",
    "drainServicePoints": "serviceFunctionPoints",
    "glueSupplyIdentity": "glueSupplyFunctionalInterface",
    "secondGlueSupplyInstance": "solveScopeCoverage",
}

SERVICE_CAPABILITIES = {
    "calibration",
    "cleaning",
    "weighing",
    "glue_drain",
    "glue_hardness_test",
}

ACTION_BY_EVIDENCE = {
    "moduleIdentity": "confirm major-assembly identities and capability roles",
    "moduleCadPaths": "resolve independently loadable CAD paths for every selected module",
    "baseOperationFace": "capture or infer the frame operation face",
    "baseTopInstallationSurface": "recover the frame installation plane and normal",
    "transportInstallationFrame": "extract the frame-to-transport datum from mates or CAD geometry",
    "transportWorkPositions": "locate buffer and dispensing carrier stations",
    "barcodeFaceAndSide": "identify the barcode target face and transport side",
    "scannerWorkingDistanceAndAxis": "recover scanner optical origin, axis and distance",
    "ccdWorkingGeometry": "recover CCD optical origin, axis, distance and FOV",
    "dualValveReach": "estimate the project-specific common valve-tip reach",
    "serviceFunctionPoints": "locate calibration, cleaning, weighing and drain targets",
    "operationSideCapacity": "estimate operator-side residual and maintenance space",
    "moduleOccupancy": "capture leaf geometry and build multi-box occupancy",
    "staticCollisionPolicy": "classify every relevant module pair",
}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _authority(item: dict[str, Any]) -> str:
    explicit = str(item.get("authority") or "").strip()
    if explicit:
        return explicit
    acquisition = str(item.get("acquisition") or "").lower()
    if "vendor" in acquisition or "厂商" in acquisition:
        return "vendor-confirmed"
    if acquisition == "filesystem":
        return "filesystem"
    if "mate" in acquisition or "配合" in acquisition:
        return "cad-mate-derived"
    if "prototype" in acquisition or "原型" in acquisition:
        return "prototype-calibrated"
    if "ppt" in acquisition:
        return "ppt-cad-inferred"
    if acquisition:
        return "project-artifact"
    return "not-captured"


def _required_ids(capabilities: set[str]) -> set[str]:
    required = set(COMMON_REQUIRED)
    if "scanner" in capabilities:
        required.update({"barcodeFaceAndSide", "scannerWorkingDistanceAndAxis"})
    if "ccd_product" in capabilities:
        required.add("ccdWorkingGeometry")
    if capabilities.intersection({"gantry", "dispense_head"}):
        required.add("dualValveReach")
    if capabilities.intersection(SERVICE_CAPABILITIES):
        required.add("serviceFunctionPoints")
    return required


def _worst_status(statuses: Iterable[str]) -> str:
    values = [value if value in STATUS_RANK else "missing" for value in statuses]
    return max(values, key=lambda value: STATUS_RANK[value]) if values else "missing"


def _normalize_evidence(
    *,
    project_id: str,
    package: dict[str, Any] | None,
    capabilities: set[str],
    manifest_modules: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for raw in (package or {}).get("requiredEvidence") or []:
        canonical_id = ALIASES.get(str(raw.get("id")), str(raw.get("id")))
        grouped.setdefault(canonical_id, []).append(raw)

    required = _required_ids(capabilities)
    normalized = []
    for evidence_id, description in EVIDENCE_DEFINITIONS:
        items = grouped.get(evidence_id, [])
        is_required = evidence_id in required
        if evidence_id == "ccdWorkingGeometry" and "ccd_product" not in capabilities:
            status = "not_required"
            authorities = ["not-required-by-design"]
        elif items:
            status = _worst_status(str(item.get("status") or "missing") for item in items)
            authorities = sorted({_authority(item) for item in items})
        elif evidence_id == "allowedContactsAndSafeStates":
            collision = grouped.get("staticCollisionPolicy", [])
            status = "partial" if collision else "missing"
            authorities = ["derived-from-collision-policy" if collision else "not-captured"]
        elif evidence_id == "glueSupplyFunctionalInterface":
            status = "partial" if "glue_supply" in capabilities else "not_required"
            authorities = ["module-identity-only" if status == "partial" else "not-required-by-design"]
        elif evidence_id == "solveScopeCoverage":
            package_ready = bool((package or {}).get("top3SolveReady"))
            status = "available" if package_ready else "missing"
            authorities = ["parameter-package"]
        elif evidence_id == "moduleIdentity" and manifest_modules:
            identified = all(
                module.get("cadId") and module.get("capabilities")
                for module in manifest_modules
            )
            status = "available" if identified else "partial"
            authorities = ["multi-project-module-manifest"]
        elif evidence_id == "moduleCadPaths" and manifest_modules:
            # The manifest identifies CAD IDs and the prototype root, but it does
            # not prove that every independently replayable subassembly resolves.
            status = "partial"
            authorities = ["prototype-root-and-cad-ids-only"]
        else:
            status = "missing" if is_required else "not_required"
            authorities = ["not-captured" if is_required else "not-required-by-design"]

        if evidence_id == "solveScopeCoverage" and project_id == "02":
            # The current nine-object solve intentionally includes one T401 instance,
            # while the prototype mate-graph scope records two concrete instances.
            status = "partial"
            authorities = ["current-nine-object-scope"]

        coarse_usable = status == "available" or (
            not is_required and status in {"partial", "not_required"}
        )
        normalized.append(
            {
                "id": evidence_id,
                "description": description,
                "status": status,
                "authorities": authorities,
                "coarseLayoutRequired": is_required,
                "coarseLayoutUsable": coarse_usable,
                "productionConfirmed": any(
                    authority == "vendor-confirmed" for authority in authorities
                ),
            }
        )
    return normalized


def build_calibration_portfolio(
    workspace: Path,
    *,
    manifest_path: Path | None = None,
    project_ids: Iterable[str] = ("01", "02", "03", "05", "06"),
) -> dict[str, Any]:
    """Normalize project-scoped calibration evidence without copying coordinates."""

    workspace = workspace.resolve()
    manifest_path = manifest_path or workspace / "demo/multi_project_module_manifest_v1.json"
    manifest = _load(manifest_path)
    manifest_by_id = {
        str(project.get("projectId")): project for project in manifest.get("projects") or []
    }
    projects = []
    for project_id in project_ids:
        project_id = str(project_id).zfill(2)
        manifest_project = manifest_by_id.get(project_id)
        if manifest_project is None:
            raise ValueError(f"Project{project_id} is absent from the module manifest")
        package_path = workspace / f"demo/project{project_id}_parameter_package.json"
        package = _load(package_path) if package_path.is_file() else None
        modules = list(manifest_project.get("modules") or [])
        capabilities = {
            str(capability)
            for module in modules
            for capability in (module.get("capabilities") or [])
        }
        evidence = _normalize_evidence(
            project_id=project_id,
            package=package,
            capabilities=capabilities,
            manifest_modules=modules,
        )
        required_blockers = [
            item["id"]
            for item in evidence
            if item["coarseLayoutRequired"] and not item["coarseLayoutUsable"]
        ]
        package_ready = bool(package and package.get("top3SolveReady") is True)
        top3_ready = package_ready and not required_blockers
        optional_debt = [
            item["id"]
            for item in evidence
            if not item["coarseLayoutRequired"] and item["status"] in {"partial", "missing"}
        ]
        projects.append(
            {
                "projectId": project_id,
                "family": manifest_project.get("family"),
                "sourceAssemblyPath": manifest_project.get("sourceAssemblyPath"),
                "manifestModuleTypeCount": len(modules),
                "capabilities": sorted(capabilities),
                "parameterPackagePath": str(package_path) if package else None,
                "parameterPackageStatus": (package or {}).get("status", "NOT_CREATED"),
                "parameterPackageReady": package_ready,
                "top3SolveReady": top3_ready,
                "productionReady": False,
                "coarseLayoutBlockers": required_blockers,
                "nextCalibrationActions": [
                    ACTION_BY_EVIDENCE[evidence_id]
                    for evidence_id in required_blockers
                    if evidence_id in ACTION_BY_EVIDENCE
                ],
                "optionalEngineeringDebt": optional_debt,
                "evidence": evidence,
            }
        )

    matrix = []
    for evidence_id, _description in EVIDENCE_DEFINITIONS:
        row: dict[str, Any] = {"evidenceId": evidence_id}
        for project in projects:
            item = next(value for value in project["evidence"] if value["id"] == evidence_id)
            row[f"project{project['projectId']}"] = item["status"]
        matrix.append(row)

    ready = [project["projectId"] for project in projects if project["top3SolveReady"]]
    blocked = [project["projectId"] for project in projects if not project["top3SolveReady"]]
    return {
        "schemaVersion": "multi-project-calibration-readiness/v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "principle": (
            "Constraint types and solving order are portable; all geometric values, "
            "faces, points, ranges, occupancy and allowed contacts remain project-scoped."
        ),
        "authorityOrder": [
            "vendor-confirmed",
            "cad-mate-or-geometry-derived",
            "ppt-cad-inferred",
            "prototype-calibrated",
            "temporary-estimate",
        ],
        "projects": projects,
        "matrix": matrix,
        "summary": {
            "projectCount": len(projects),
            "top3ReadyProjects": ready,
            "blockedProjects": blocked,
            "productionReadyProjects": [],
            "importantLimit": (
                "Top-3 readiness certifies coarse static layout input completeness only; "
                "it does not certify motion, hose/cable, ergonomics or production parameters."
            ),
        },
    }
