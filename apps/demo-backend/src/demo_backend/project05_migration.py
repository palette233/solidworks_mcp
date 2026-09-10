"""Project05 case-isolated module grouping and evidence readiness gate."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT05_GROUPS = [
    {
        "id": "frame-context",
        "placementMode": "fixed-context",
        "primaryCadId": "FL9C254098A000.001",
        "memberCadIds": ["FL9C254098A000.001", "FL9C254098E000.001"],
        "reason": "The enclosure/frame and lower return conveyor define the fixed installation context.",
    },
    {
        "id": "transport-process-group",
        "placementMode": "frame-anchored-primary",
        "primaryCadId": "FL9C254098D000.001",
        "memberCadIds": ["FL9C254098D000.001"],
        "reason": "The upper conveyor is positioned first from the supplier frame interface.",
    },
    {
        "id": "lift-positioning-module",
        "placementMode": "transport-dependent-rigid",
        "primaryCadId": "FL9C254098K000.001",
        "memberCadIds": ["FL9C254098K000.001"],
        "reason": "The two positioning stations are derived after the transport work path.",
    },
    {
        "id": "gantry-motion-group",
        "placementMode": "coverage-solved-rigid-group",
        "primaryCadId": "FL9C254098B000.001",
        "memberCadIds": ["FL9C254098B000.001", "FL9C254098Z000.001"],
        "reason": "The XYZ gantry and dual-valve Z/head assembly form one coverage object.",
    },
    {
        "id": "scanner-module",
        "placementMode": "transport-dependent-rigid",
        "primaryCadId": "FL9C254098F000.001",
        "memberCadIds": ["FL9C254098F000.001"],
        "reason": "Scanner placement depends on the barcode side and carrier stop on D000.",
    },
    {
        "id": "calibration-weighing-module",
        "placementMode": "independent-rigid-multifunction",
        "primaryCadId": "FL9C254098G000.001",
        "memberCadIds": ["FL9C254098G000.001"],
        "reason": "Calibration and weighing expose separate service points on one rigid module.",
    },
    {
        "id": "product-ccd-module",
        "placementMode": "transport-dependent-optical",
        "primaryCadId": "FL9C254098M000.001",
        "memberCadIds": ["FL9C254098M000.001"],
        "reason": "Product CCD alignment is tied to the transport work positions and product datum.",
    },
    {
        "id": "cleaning-module",
        "placementMode": "independent-rigid",
        "primaryCadId": "FL9C251093N000.001",
        "memberCadIds": ["FL9C251093N000.001"],
        "reason": "The reused-number N000 assembly is the independent automatic needle cleaner.",
    },
    {
        "id": "drain-module",
        "placementMode": "independent-rigid",
        "primaryCadId": "FL9C254098P000.001",
        "memberCadIds": ["FL9C254098P000.001"],
        "reason": "The dual drain cups are an independent valve-reach target.",
    },
]


PROJECT05_REQUIRED_EVIDENCE = [
    ("moduleIdentity", "available", "05-PPT plus named CAD module directories"),
    ("moduleCadPaths", "available", "filesystem"),
    ("baseOperationFace", "missing", "A000 face or service-side mate evidence"),
    ("baseTopInstallationSurface", "missing", "A000 frame mate extraction"),
    ("transportInstallationFrame", "missing", "A000-D000 mate graph and supplier datum"),
    ("transportWorkPositions", "missing", "D000/K000 repeated station geometry and workflow"),
    ("barcodeFaceAndSide", "missing", "carrier/product barcode and F000 optical audit"),
    ("scannerWorkingDistanceAndAxis", "missing", "F000 scanner head/beam geometry"),
    ("ccdWorkingGeometry", "missing", "M000 optical axis, work distance and product datum"),
    ("dualValveReach", "missing", "B000/Z000 axis geometry and dual-head offset"),
    ("calibrationAndWeighingPoints", "missing", "G000 function subtrees"),
    ("cleaningServicePoint", "missing", "N000 cleaning target"),
    ("drainServicePoints", "missing", "P000 cup centers"),
    ("operationSideCapacity", "missing", "A000 operation side and residual-space audit"),
    ("moduleOccupancy", "missing", "top-level and process-subtree envelopes"),
    ("staticCollisionPolicy", "partial", "ordinary, optical, nested and installation pair classification"),
    ("glueSupplyIdentity", "partial", "PPT requires glue supply but no independent numbered major assembly is mapped"),
]


def _manifest_project(manifest: dict[str, Any]) -> dict[str, Any]:
    project = next(
        (item for item in manifest.get("projects") or [] if str(item.get("projectId")) == "05"),
        None,
    )
    if project is None:
        raise ValueError("Project05 is absent from the multi-project module manifest")
    return project


def build_project05_migration_skeleton(
    workspace: Path,
    *,
    manifest_path: Path | None = None,
    source_root_override: Path | None = None,
) -> dict[str, Any]:
    """Build the Project05 gate without inheriting Project01/02/03 coordinates."""

    manifest_path = manifest_path or workspace / "demo/multi_project_module_manifest_v1.json"
    project = _manifest_project(json.loads(manifest_path.read_text(encoding="utf-8-sig")))
    source_assembly = Path(project["sourceAssemblyPath"])
    source_root = source_root_override or source_assembly.parent
    assembly_index: dict[str, list[Path]] = {}
    if source_root.is_dir():
        for path in source_root.rglob("*.SLDASM"):
            if not path.name.startswith("~$"):
                assembly_index.setdefault(path.name.upper(), []).append(path)

    modules: list[dict[str, Any]] = []
    unresolved_optional_capabilities: list[str] = []
    capability_coverage: set[str] = set()
    for item in project.get("modules") or []:
        capabilities = [str(value) for value in item.get("capabilities") or []]
        capability_coverage.update(capabilities)
        cad_id = str(item.get("cadId") or "")
        if not cad_id:
            unresolved_optional_capabilities.extend(capabilities)
            continue
        expected_name = f"{cad_id}.SLDASM".upper()
        candidates = assembly_index.get(expected_name) or []
        resolved = min(candidates, key=lambda path: len(str(path))) if candidates else None
        modules.append({
            "cadId": cad_id,
            "capabilities": capabilities,
            "confidence": item.get("confidence"),
            "expectedFileName": f"{cad_id}.SLDASM",
            "resolvedCadPath": str(resolved) if resolved else None,
            "cadFileExists": bool(resolved and resolved.is_file()),
            "cadFileBytes": resolved.stat().st_size if resolved else None,
            "notes": item.get("notes"),
        })

    module_by_id = {item["cadId"]: item for item in modules}
    groups = []
    for configured in PROJECT05_GROUPS:
        group = dict(configured)
        group["membersResolved"] = all(
            module_by_id.get(cad_id, {}).get("cadFileExists") is True
            for cad_id in group["memberCadIds"]
        )
        groups.append(group)

    evidence = [
        {"id": item_id, "status": status, "acquisition": acquisition}
        for item_id, status, acquisition in PROJECT05_REQUIRED_EVIDENCE
    ]
    first_stage_path = workspace / "demo/layout_previews/project05_first_stage_geometry.json"
    process_path = workspace / "demo/layout_previews/project05_process_semantics.json"
    work_positions_path = workspace / "demo/layout_previews/project05_work_positions.json"
    occupancy_path = workspace / "demo/layout_previews/project05_module_occupancy.json"
    first_stage = None
    process_semantics = None
    work_positions = None
    occupancy = None
    if first_stage_path.is_file():
        candidate = json.loads(first_stage_path.read_text(encoding="utf-8-sig"))
        if candidate.get("status") == "PROJECT05_FIRST_STAGE_GEOMETRY_CAPTURED":
            first_stage = candidate
            evidence_updates = {
                "baseOperationFace": ("partial", "prototype +worldX service-side inference; exact A000 face not captured"),
                "baseTopInstallationSurface": ("available", "A000-D000 coincident contact plane"),
                "transportInstallationFrame": ("available", "A000-D000 coincident + 312 mm distance + centered width mate bundle"),
                "operationSideCapacity": ("partial", "top-level prototype service cluster only; maintenance envelope pending"),
                "moduleOccupancy": ("partial", "13 top-level poses captured; process-subtree multi-box occupancy pending"),
            }
            for item in evidence:
                update = evidence_updates.get(item["id"])
                if update:
                    item["status"], item["acquisition"] = update
    if work_positions_path.is_file():
        candidate = json.loads(work_positions_path.read_text(encoding="utf-8-sig"))
        if candidate.get("status") == "PROJECT05_TWO_WORK_POSITIONS_INFERRED" and candidate.get("coarseLayoutUsable"):
            work_positions = candidate
            for item in evidence:
                if item["id"] == "transportWorkPositions":
                    item["status"] = "available"
                    item["acquisition"] = "complete K000 @root leaf capture; two explicit KA00/header dispensing-position subtrees"
    if occupancy_path.is_file():
        candidate = json.loads(occupancy_path.read_text(encoding="utf-8-sig"))
        policy = candidate.get("staticCollisionPolicy") or {}
        if policy.get("pairPolicyComplete") is True:
            occupancy = candidate
            for item in evidence:
                if item["id"] == "staticCollisionPolicy":
                    item["status"] = "available"
                    item["acquisition"] = "all 36 Project05 layout-object pairs classified"
                elif item["id"] == "moduleOccupancy":
                    item["status"] = "available" if candidate.get("solverOccupancyReady") else "partial"
                    item["acquisition"] = (
                        "all required modules have complete leaf occupancy"
                        if candidate.get("solverOccupancyReady")
                        else "K000 leaf multi-box complete; remaining modules use conservative top-level placeholders"
                    )
    if process_path.is_file():
        candidate = json.loads(process_path.read_text(encoding="utf-8-sig"))
        if candidate.get("status") == "PROJECT05_PROCESS_SEMANTICS_CAPTURED_CAD_COORDINATES_REQUIRED":
            process_semantics = candidate
            evidence_updates = {
                "transportWorkPositions": ("partial", "05-PPT confirms two lift work positions plus buffer; D000/K000 CAD coordinates pending"),
                "barcodeFaceAndSide": ("partial", "05-PPT confirms carrier plus four product barcodes at buffer; label locations are tentative"),
                "ccdWorkingGeometry": ("partial", "05-PPT provides 19x14.25 mm FOV and 110+/-2 mm distance; CAD optical origin/axis pending"),
            }
            for item in evidence:
                update = evidence_updates.get(item["id"])
                # PPT semantics enrich unknown/partial evidence, but must never
                # downgrade a complete CAD-derived measurement to "partial".
                if update and item["status"] != "available":
                    item["status"], item["acquisition"] = update
    missing = [item["id"] for item in evidence if item["status"] == "missing"]
    partial = [item["id"] for item in evidence if item["status"] == "partial"]
    all_paths_resolved = bool(modules) and all(item["cadFileExists"] for item in modules)
    top3_ready = all_paths_resolved and not missing and not partial
    if top3_ready:
        status = "PROJECT05_TOP3_INPUT_READY"
    elif first_stage:
        status = "PROJECT05_FIRST_STAGE_GEOMETRY_CAPTURED_MORE_EVIDENCE_REQUIRED"
    else:
        status = "PROJECT05_PARAMETER_SKELETON_READY_GEOMETRY_CAPTURE_REQUIRED"

    next_extraction_order = []
    if not first_stage:
        next_extraction_order.extend([
            "capture Project05 top-level poses and module-level mate graph",
            "recover A000-D000 installation frame",
        ])
    if "transportWorkPositions" in missing or "transportWorkPositions" in partial:
        next_extraction_order.append("recover D000/K000 work positions")
    if any(item in missing for item in ("barcodeFaceAndSide", "scannerWorkingDistanceAndAxis", "ccdWorkingGeometry")):
        next_extraction_order.append("recover F000 scan axis and M000 CCD work geometry")
    if any(item in missing for item in ("calibrationAndWeighingPoints", "cleaningServicePoint", "drainServicePoints")):
        next_extraction_order.append("recover G000/N000/P000 service points")
    if "dualValveReach" in missing:
        next_extraction_order.append("infer B000/Z000 dual-valve common reach")
    if any(item in partial for item in ("moduleOccupancy", "staticCollisionPolicy")):
        next_extraction_order.append("build multi-box occupancy and classify all object pairs")
    return {
        "schemaVersion": "project-migration-parameter-skeleton/v1",
        "projectId": "project05",
        "family": project.get("family"),
        "sourceAssemblyPath": str(source_assembly),
        "sourceAssemblyExists": source_assembly.is_file(),
        "pptPath": project.get("pptPath"),
        "pptExists": Path(str(project.get("pptPath"))).is_file(),
        "moduleCount": len(modules),
        "resolvedModuleCadCount": sum(item["cadFileExists"] for item in modules),
        "allModuleCadPathsResolved": all_paths_resolved,
        "modules": modules,
        "capabilityCoverage": sorted(capability_coverage),
        "unresolvedOptionalCapabilities": sorted(set(unresolved_optional_capabilities)),
        "layoutObjectGroups": groups,
        "proposedTopLevelSolveObjects": [
            group["primaryCadId"] for group in groups if group["placementMode"] != "fixed-context"
        ],
        "requiredEvidence": evidence,
        "firstStageGeometryPath": str(first_stage_path) if first_stage else None,
        "firstStageGeometry": first_stage,
        "processSemanticsPath": str(process_path) if process_semantics else None,
        "processSemantics": process_semantics,
        "workPositionsPath": str(work_positions_path) if work_positions else None,
        "workPositions": work_positions,
        "occupancyPath": str(occupancy_path) if occupancy else None,
        "occupancy": occupancy,
        "missingRequiredEvidence": missing,
        "partialEvidence": partial,
        "top3SolveReady": top3_ready,
        "status": status,
        "otherProjectNumericParametersInherited": False,
        "engineeringConfirmationDebt": [
            "Locate the glue-supply parent component or explicitly approve it as fixed external context.",
            "Confirm G000 calibration/weighing ports and the reused FL9C251093N000 cleaner identity.",
            "Replace prototype-derived scanner, CCD and dual-valve ranges when vendor data arrives.",
            "Run B-rep only after one Project05 Top-3 candidate is selected.",
        ],
        "forbiddenInheritedCaseConstants": [
            "Project01/03 tunnel installation coordinates, scanner ranges and combined-service ports",
            "Project02 A600/A800 installation frame, A180/A200 optical geometry and A100 reach",
            "Any Project01/02/03 allowed-contact list",
        ],
        "portableRulesSelected": [
            "frame -> transport -> lift/work positions -> scanner and product CCD -> service modules -> gantry coverage",
            "capability-specific service points are attached to rigid CAD modules",
            "strict inflated multi-AABB for ordinary pairs and conditional B-rep for optical/structural/nested pairs",
            "Replay and exact interference validation only after one candidate is selected",
        ],
        "nextExtractionOrder": next_extraction_order,
    }


def load_project05_migration_readiness(workspace: Path) -> dict[str, Any]:
    artifact = workspace / "demo/layout_previews/project05_migration_readiness.json"
    if artifact.is_file():
        return json.loads(artifact.read_text(encoding="utf-8-sig"))
    return build_project05_migration_skeleton(workspace)
