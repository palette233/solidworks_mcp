from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT01_GROUPS = [
    {
        "id": "frame-context",
        "placementMode": "fixed-context",
        "primaryCadId": "FL9C24N074JJ00.001",
        "memberCadIds": ["FL9C24N074JJ00.001", "FL9C24N074HL00.001"],
        "reason": "Frame/enclosure and lower return transport define installation context rather than free process objects.",
    },
    {
        "id": "transport-process-group",
        "placementMode": "frame-anchored-primary",
        "primaryCadId": "FL9C24N074SS00.001",
        "memberCadIds": ["FL9C24N074SS00.001"],
        "reason": "Upper transport is fixed to JJ00 by one coincident plane and two concentric locating holes.",
    },
    {
        "id": "flip-positioning-module",
        "placementMode": "frame-anchored-process-dependent",
        "primaryCadId": "FL9C24N074FF00.001",
        "memberCadIds": ["FL9C24N074FF00.001"],
        "reason": "FF00 is independently fixed to JJ00; its process relation to SS00 must not be modeled as a direct rigid mate.",
    },
    {
        "id": "gantry-motion-group",
        "placementMode": "coverage-solved-rigid-group",
        "primaryCadId": "FL9C24N074LM00.001",
        "memberCadIds": ["FL9C24N074LM00.001", "FL9C24N074ZZ00.001"],
        "reason": "The gantry base is placed as one layout object while the dual-valve Z/head assembly defines its internal reach.",
    },
    {
        "id": "combined-service-module",
        "placementMode": "independent-rigid-multifunction",
        "primaryCadId": "FL9C24N074GN00.001",
        "memberCadIds": ["FL9C24N074GN00.001"],
        "reason": "Cleaning, weighing, drain and hardness-test functions require separate ports but share one rigid assembly placement.",
    },
    {
        "id": "calibration-module",
        "placementMode": "independent-rigid",
        "primaryCadId": "FL9C24N074BD00.001",
        "memberCadIds": ["FL9C24N074BD00.001"],
        "reason": "Calibration is an independent service module.",
    },
    {
        "id": "scanner-module",
        "placementMode": "transport-dependent-rigid",
        "primaryCadId": "FL9C24N074SM00.001",
        "memberCadIds": ["FL9C24N074SM00.001"],
        "reason": "Scanner placement is derived after transport and barcode-side evidence.",
    },
    {
        "id": "glue-supply-module",
        "placementMode": "service-side-rigid",
        "primaryCadId": "FL9C24N074GJ00.001",
        "memberCadIds": ["FL9C24N074GJ00.001"],
        "reason": "Glue supply must preserve hose/service access but is not a valve-reach target.",
    },
]


PROJECT01_REQUIRED_EVIDENCE = [
    ("moduleIdentity", "available", "manifest-and-folder-names"),
    ("moduleCadPaths", "available", "filesystem"),
    ("baseOperationFace", "missing", "SolidWorks face capture or mate-derived frame"),
    ("baseTopInstallationSurface", "missing", "SolidWorks face/mate extraction"),
    ("transportInstallationFrame", "missing", "JJ00-SS00 mate graph and datum measurement"),
    ("transportWorkPositions", "missing", "SS00/FF00 station geometry and PPT workflow"),
    ("barcodeFaceAndSide", "missing", "carrier barcode leaf and SM00 optical-axis audit"),
    ("scannerWorkingDistanceAndAxis", "missing", "SM00 scanner leaf/axis evidence"),
    ("dualValveReach", "missing", "LM00/ZZ00 axis-limit geometry or prototype baseline"),
    ("calibrationServicePoint", "missing", "BD00 calibration target geometry"),
    ("combinedServiceFunctionPoints", "missing", "GN00 cleaning/weighing/drain/hardness subtrees"),
    ("operationSideCapacity", "missing", "frame operation face plus residual-space audit"),
    ("moduleOccupancy", "missing", "top-level and subtree leaf envelopes"),
    ("staticCollisionPolicy", "partial", "classify ordinary, structural and nested module pairs"),
]


PROJECT03_GROUPS = [
    {
        "id": "frame-context",
        "placementMode": "fixed-context",
        "primaryCadId": "FL9A24D063AA00.001",
        "memberCadIds": ["FL9A24D063AA00.001", "FL9A24D063AF00.001"],
        "reason": "Frame/enclosure and lower return transport define the Project03 installation context.",
    },
    {
        "id": "transport-process-group",
        "placementMode": "frame-anchored-primary",
        "primaryCadId": "FL9A24D063AE00.001",
        "memberCadIds": ["FL9A24D063AE00.001"],
        "reason": "Upper transport must be recovered from the Project03 frame/transport mate interface.",
    },
    {
        "id": "flip-positioning-module",
        "placementMode": "frame-anchored-process-dependent",
        "primaryCadId": "FL9A24D063AD00.001",
        "memberCadIds": ["FL9A24D063AD00.001"],
        "reason": "Lift, clamp and rotation stations are placed after transport while preserving their own frame interface.",
    },
    {
        "id": "gantry-motion-group",
        "placementMode": "coverage-solved-rigid-group",
        "primaryCadId": "FL9A24D063AB00.001",
        "memberCadIds": ["FL9A24D063AB00.001", "FL9A24D063AC00.001"],
        "reason": "AB00 gantry and AC00 dual-valve Z/head assembly form one layout coverage group.",
    },
    {
        "id": "combined-service-module",
        "placementMode": "independent-rigid-multifunction",
        "primaryCadId": "FL9A24D063AG00.001",
        "memberCadIds": ["FL9A24D063AG00.001"],
        "reason": "Cleaning, weighing, drain and hardness-test ports share one Project03 rigid assembly.",
    },
    {
        "id": "calibration-module",
        "placementMode": "independent-rigid",
        "primaryCadId": "FL9A24D063AH00.001",
        "memberCadIds": ["FL9A24D063AH00.001"],
        "reason": "AH00 is the independent needle-calibration module; its camera is not a product CCD.",
    },
    {
        "id": "scanner-module",
        "placementMode": "transport-dependent-rigid",
        "primaryCadId": "FL9A24D063AI00.001",
        "memberCadIds": ["FL9A24D063AI00.001"],
        "reason": "Scanner placement depends on the Project03 barcode side, optical axis and transport station.",
    },
    {
        "id": "glue-supply-module",
        "placementMode": "service-side-rigid",
        "primaryCadId": "FL9A24D063AJ00.001",
        "memberCadIds": ["FL9A24D063AJ00.001"],
        "reason": "Glue supply is placed for hose routing and maintenance rather than valve-head reach.",
    },
]


PROJECT03_REQUIRED_EVIDENCE = [
    ("moduleIdentity", "available", "03-PPT plus offline assembly thumbnails"),
    ("moduleCadPaths", "available", "filesystem"),
    ("baseOperationFace", "missing", "AA00 face/mate evidence"),
    ("baseTopInstallationSurface", "missing", "AA00 frame mate extraction"),
    ("transportInstallationFrame", "missing", "AA00-AE00 mate graph and datum measurement"),
    ("transportWorkPositions", "missing", "AE00/AD00 station geometry and 03-PPT workflow"),
    ("barcodeFaceAndSide", "missing", "carrier/product barcode leaf and AI00 optical-axis audit"),
    ("scannerWorkingDistanceAndAxis", "missing", "AI00 scanner head and beam/axis evidence"),
    ("dualValveReach", "missing", "AB00/AC00 axis geometry and dual-head offset"),
    ("calibrationServicePoint", "missing", "AH00 prism/calibration target geometry"),
    ("combinedServiceFunctionPoints", "missing", "AG00 cleaning/weighing/drain/hardness subtrees"),
    ("operationSideCapacity", "missing", "AA00 operation face and residual-space audit"),
    ("moduleOccupancy", "missing", "top-level and subtree leaf envelopes"),
    ("staticCollisionPolicy", "partial", "classify ordinary, structural and nested Project03 pairs"),
]


def load_project03_migration_readiness(workspace: Path) -> dict[str, Any]:
    artifact_path = workspace / "demo/layout_previews/project03_migration_readiness.json"
    if artifact_path.is_file():
        return json.loads(artifact_path.read_text(encoding="utf-8-sig"))
    return build_project03_migration_skeleton(workspace)


def build_project03_migration_skeleton(
    workspace: Path,
    *,
    manifest_path: Path | None = None,
    source_root_override: Path | None = None,
) -> dict[str, Any]:
    """Build the Project03 evidence gate without inheriting Project01/02 coordinates."""

    manifest_path = manifest_path or workspace / "demo/multi_project_module_manifest_v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    project = next(
        (item for item in manifest.get("projects") or [] if str(item.get("projectId")) == "03"),
        None,
    )
    if project is None:
        raise ValueError("Project03 is absent from the multi-project module manifest")

    source_assembly = Path(project["sourceAssemblyPath"])
    source_root = source_root_override or source_assembly.parent
    assembly_index: dict[str, list[Path]] = {}
    if source_root.is_dir():
        for path in source_root.rglob("*.SLDASM"):
            if not path.name.startswith("~$"):
                assembly_index.setdefault(path.name.upper(), []).append(path)

    modules = []
    capabilities: set[str] = set()
    for item in project.get("modules") or []:
        cad_id = str(item.get("cadId") or "")
        expected_name = f"{cad_id}.SLDASM".upper()
        candidates = assembly_index.get(expected_name) or []
        resolved_path = min(candidates, key=lambda path: len(str(path))) if candidates else None
        item_capabilities = [str(value) for value in item.get("capabilities") or []]
        capabilities.update(item_capabilities)
        modules.append(
            {
                "cadId": cad_id,
                "capabilities": item_capabilities,
                "confidence": item.get("confidence"),
                "expectedFileName": f"{cad_id}.SLDASM",
                "resolvedCadPath": str(resolved_path) if resolved_path else None,
                "cadFileExists": bool(resolved_path and resolved_path.is_file()),
                "cadFileBytes": resolved_path.stat().st_size if resolved_path else None,
            }
        )

    module_by_id = {item["cadId"]: item for item in modules}
    groups = []
    for configured in PROJECT03_GROUPS:
        group = dict(configured)
        group["membersResolved"] = all(
            module_by_id.get(cad_id, {}).get("cadFileExists") is True
            for cad_id in configured["memberCadIds"]
        )
        groups.append(group)

    first_stage_path = workspace / "demo/layout_previews/project03_first_stage_geometry.json"
    first_stage = None
    if first_stage_path.is_file():
        candidate = json.loads(first_stage_path.read_text(encoding="utf-8-sig"))
        if candidate.get("status") == "PROJECT03_FIRST_STAGE_GEOMETRY_CAPTURED":
            first_stage = candidate

    first_stage_statuses = {
        "baseOperationFace": "partial",
        "baseTopInstallationSurface": "available",
        "transportInstallationFrame": "available",
        "operationSideCapacity": "partial",
        "moduleOccupancy": "partial",
    }
    evidence = []
    for item_id, status, acquisition in PROJECT03_REQUIRED_EVIDENCE:
        if first_stage is not None and item_id in first_stage_statuses:
            status = first_stage_statuses[item_id]
            acquisition = f"Project03 first-stage CAD evidence: {acquisition}"
        evidence.append({"id": item_id, "status": status, "acquisition": acquisition})

    work_positions_path = workspace / "demo/layout_previews/project03_work_positions.json"
    work_positions = None
    if work_positions_path.is_file():
        candidate = json.loads(work_positions_path.read_text(encoding="utf-8-sig"))
        if (
            candidate.get("status") == "PROJECT03_TWO_WORK_POSITIONS_INFERRED"
            and candidate.get("coarseLayoutUsable") is True
        ):
            work_positions = candidate
            for item in evidence:
                if item["id"] == "transportWorkPositions":
                    item["status"] = "available"
                    item["acquisition"] = (
                        "two repeated AD10/AD20 lift-rotation subtrees bracketed by three AE90 transport structures"
                    )
    scanner_geometry_path = workspace / "demo/layout_previews/project03_scanner_geometry.json"
    scanner_geometry = None
    if scanner_geometry_path.is_file():
        candidate = json.loads(scanner_geometry_path.read_text(encoding="utf-8-sig"))
        if (
            candidate.get("status") == "PROJECT03_SCANNER_GEOMETRY_PARTIALLY_INFERRED"
            and candidate.get("coarseLayoutUsable") is True
        ):
            scanner_geometry = candidate
            evidence_updates = {
                "barcodeFaceAndSide": (
                    "partial",
                    "one explicit SR-X100 product-barcode beam is recovered; PPT/CAD carrier-barcode versus RFID identity-head discrepancy remains open",
                ),
                "scannerWorkingDistanceAndAxis": (
                    "available",
                    "AI00 explicit SR-X100 beam body gives +worldY optical axis and 100 mm Project03 CAD baseline",
                ),
            }
            for item in evidence:
                update = evidence_updates.get(item["id"])
                if update:
                    item["status"], item["acquisition"] = update
    service_points_path = workspace / "demo/layout_previews/project03_service_points.json"
    service_points = None
    if service_points_path.is_file():
        candidate = json.loads(service_points_path.read_text(encoding="utf-8-sig"))
        if (
            candidate.get("status") == "PROJECT03_SERVICE_POINTS_INFERRED"
            and candidate.get("coarseLayoutUsable") is True
        ):
            service_points = candidate
            evidence_updates = {
                "calibrationServicePoint": (
                    "available",
                    "AH10 explicit 30 mm prism top-center prototype target",
                ),
                "combinedServiceFunctionPoints": (
                    "available",
                    "AG12/AG13 two cleaning positions, AG20 weighing cup, AG30 hardness plate and AG40 dual drain cups",
                ),
            }
            for item in evidence:
                update = evidence_updates.get(item["id"])
                if update:
                    item["status"], item["acquisition"] = update
    valve_reach_path = workspace / "demo/layout_previews/project03_dual_valve_reach.json"
    valve_reach = None
    if valve_reach_path.is_file():
        candidate = json.loads(valve_reach_path.read_text(encoding="utf-8-sig"))
        if (
            candidate.get("status") == "PROJECT03_DUAL_VALVE_REACH_INFERRED"
            and candidate.get("coarseLayoutUsable") is True
            and candidate.get("allRequiredTargetsInsideCommonReach") is True
        ):
            valve_reach = candidate
            for item in evidence:
                if item["id"] == "dualValveReach":
                    item["status"] = "available"
                    item["acquisition"] = (
                        "AB00 900/1100 mm CAD scale envelopes plus AC00 two-valve 130 mm offset prototype baseline"
                    )
    occupancy_path = workspace / "demo/layout_previews/project03_module_occupancy.json"
    occupancy = None
    occupancy_summary = None
    if occupancy_path.is_file():
        occupancy = json.loads(occupancy_path.read_text(encoding="utf-8-sig"))
        occupancy_summary = {
            key: occupancy.get(key)
            for key in (
                "schemaVersion",
                "projectId",
                "status",
                "engineeringConfirmed",
                "prototypeBaselineAcceptedForCoarseLayout",
                "operationSideBaseline",
                "coverage",
                "staticCollisionPolicy",
                "prototypePairDiagnostics",
                "remainingProductionGates",
            )
        }
        occupancy_summary["layoutObjects"] = [
            {
                "id": item.get("id"),
                "memberCodes": item.get("memberCodes"),
                "primaryCode": item.get("primaryCode"),
                "occupancyBoxCount": item.get("occupancyBoxCount"),
                "leafBodyOccupancyBoxCount": item.get("leafBodyOccupancyBoxCount"),
            }
            for item in occupancy.get("layoutObjects") or []
        ]
        if occupancy.get("status") == "PROJECT03_OCCUPANCY_AND_COLLISION_POLICY_READY":
            evidence_updates = {
                "baseOperationFace": (
                    "available",
                    "prototype +worldX/+installationV operation-side baseline accepted for coarse layout; exact AA00 face remains engineering debt",
                ),
                "operationSideCapacity": (
                    "available",
                    "AA00 envelope plus AG00/AH00/AJ00 prototype service-side occupancy accepted as a coarse capacity baseline",
                ),
                "moduleOccupancy": (
                    "available",
                    "seven structural modules use Project03 leaf-subtree unions; AJ00 uses a conservative top-level box; AA00/AF00 remain fixed context",
                ),
                "staticCollisionPolicy": (
                    "available",
                    "all 28 layout-object pairs are partitioned into strict multi-AABB, conditional B-rep, or installation-contact classes",
                ),
            }
            for item in evidence:
                update = evidence_updates.get(item["id"])
                if update:
                    item["status"], item["acquisition"] = update
            if scanner_geometry is not None:
                for item in evidence:
                    if item["id"] == "barcodeFaceAndSide":
                        item["status"] = "available"
                        item["acquisition"] = (
                            "the explicit Project03 SR-X100 beam and prototype carrier station are accepted for coarse scanner placement; "
                            "carrier-barcode versus RFID identity remains non-blocking engineering debt"
                        )
    missing = [item["id"] for item in evidence if item["status"] == "missing"]
    partial = [item["id"] for item in evidence if item["status"] == "partial"]
    all_module_paths_resolved = bool(modules) and all(item["cadFileExists"] for item in modules)
    top3_ready = not missing and not partial and all_module_paths_resolved
    evidence_status = {item["id"]: item["status"] for item in evidence}
    next_extraction_order = []
    if evidence_status.get("scannerWorkingDistanceAndAxis") != "available":
        next_extraction_order.append("AI00 optical axis and barcode side")
    elif evidence_status.get("barcodeFaceAndSide") != "available":
        next_extraction_order.append("resolve AI00 carrier barcode/RFID evidence")
    if (
        evidence_status.get("combinedServiceFunctionPoints") != "available"
        or evidence_status.get("calibrationServicePoint") != "available"
    ):
        next_extraction_order.append("AG00 function ports and AH00 calibration point")
    if evidence_status.get("dualValveReach") != "available":
        next_extraction_order.append("AB00/AC00 dual-valve common reach")
    if (
        evidence_status.get("moduleOccupancy") != "available"
        or evidence_status.get("staticCollisionPolicy") != "available"
    ):
        next_extraction_order.append("module/subtree occupancy and collision-pair classification")
    if (
        evidence_status.get("baseOperationFace") != "available"
        or evidence_status.get("operationSideCapacity") != "available"
    ):
        next_extraction_order.append("exact AA00 operation-face and capacity confirmation")
    return {
        "schemaVersion": "project-migration-parameter-skeleton/v1",
        "projectId": "project03",
        "family": project.get("family"),
        "sourceAssemblyPath": str(source_assembly),
        "sourceAssemblyExists": source_assembly.is_file(),
        "pptPath": project.get("pptPath"),
        "pptExists": Path(str(project.get("pptPath"))).is_file(),
        "moduleCount": len(modules),
        "resolvedModuleCadCount": sum(item["cadFileExists"] for item in modules),
        "allModuleCadPathsResolved": all_module_paths_resolved,
        "modules": modules,
        "capabilityCoverage": sorted(capabilities),
        "notPresentByDesign": [
            {
                "capability": "ccd_product",
                "reason": "Project03 PPT/CAD identify no independent product-positioning CCD; AH00 vision belongs to calibration.",
            }
        ],
        "layoutObjectGroups": groups,
        "proposedTopLevelSolveObjects": [
            group["primaryCadId"] for group in groups if group["placementMode"] != "fixed-context"
        ],
        "requiredEvidence": evidence,
        "missingRequiredEvidence": missing,
        "partialEvidence": partial,
        "top3SolveReady": top3_ready,
        "status": (
            "PROJECT03_TOP3_INPUT_READY"
            if top3_ready
            else "PROJECT03_FIRST_STAGE_GEOMETRY_READY_FURTHER_EXTRACTION_REQUIRED"
            if first_stage is not None
            else "PROJECT03_PARAMETER_SKELETON_READY_GEOMETRY_CAPTURE_REQUIRED"
        ),
        "firstStageGeometryPath": str(first_stage_path) if first_stage is not None else None,
        "firstStageGeometry": first_stage,
        "workPositionsPath": str(work_positions_path) if work_positions is not None else None,
        "workPositions": work_positions,
        "scannerGeometryPath": str(scanner_geometry_path) if scanner_geometry is not None else None,
        "scannerGeometry": scanner_geometry,
        "servicePointsPath": str(service_points_path) if service_points is not None else None,
        "servicePoints": service_points,
        "dualValveReachPath": str(valve_reach_path) if valve_reach is not None else None,
        "dualValveReach": valve_reach,
        "moduleOccupancyPath": str(occupancy_path) if occupancy is not None else None,
        "moduleOccupancy": occupancy_summary,
        "project01NumericParametersInherited": False,
        "project02NumericParametersInherited": False,
        "engineeringConfirmationDebt": [
            "Confirm the exact AA00 operation face and maintenance envelope.",
            "Confirm whether the separate AI00 thin identity head reads a carrier barcode or RFID; no second SR-X100 beam was inferred.",
            "Replace any prototype-derived scanner and dual-valve spans when vendor limits arrive.",
            "Run B-rep only after a Project03 Top-3 candidate is visually selected.",
        ],
        "forbiddenInheritedCaseConstants": [
            "Project01 JJ00/SS00 installation coordinates, 200 mm scanner beam and 770 x 1100 mm reach",
            "Project01 process-contact allowlist",
            "Project02 A600/A800 installation coordinates and A100 reach rectangles",
            "Project02 A180/A200/A300/A500/A700 service and optical coordinates",
        ],
        "portableRulesSelected": [
            "base -> transport -> positioning/scanner -> service functions -> gantry coverage order",
            "one rigid CAD module may expose multiple function-specific ports",
            "strict inflated AABB for ordinary pairs and conditional B-rep for structural/nested pairs",
            "selected-candidate-only Replay and exact interference validation",
        ],
        "nextExtractionOrder": next_extraction_order,
    }


def load_project01_migration_readiness(workspace: Path) -> dict[str, Any]:
    """Load the persisted Project01 audit, rebuilding it when no artifact exists yet."""
    artifact_path = workspace / "demo/layout_previews/project01_migration_readiness.json"
    if artifact_path.is_file():
        return json.loads(artifact_path.read_text(encoding="utf-8-sig"))
    return build_project01_migration_skeleton(workspace)


def build_project01_migration_skeleton(
    workspace: Path,
    *,
    manifest_path: Path | None = None,
    source_root_override: Path | None = None,
) -> dict[str, Any]:
    manifest_path = manifest_path or workspace / "demo/multi_project_module_manifest_v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    project = next(
        (item for item in manifest.get("projects") or [] if str(item.get("projectId")) == "01"),
        None,
    )
    if project is None:
        raise ValueError("Project01 is absent from the multi-project module manifest")

    source_assembly = Path(project["sourceAssemblyPath"])
    source_root = source_root_override or source_assembly.parent
    assembly_index: dict[str, list[Path]] = {}
    if source_root.is_dir():
        for path in source_root.rglob("*.SLDASM"):
            if path.name.startswith("~$"):
                continue
            assembly_index.setdefault(path.name.upper(), []).append(path)

    modules = []
    capabilities: set[str] = set()
    for item in project.get("modules") or []:
        cad_id = str(item.get("cadId") or "")
        expected_name = f"{cad_id}.SLDASM".upper()
        candidates = assembly_index.get(expected_name) or []
        resolved_path = min(candidates, key=lambda path: len(str(path))) if candidates else None
        item_capabilities = [str(value) for value in item.get("capabilities") or []]
        capabilities.update(item_capabilities)
        modules.append(
            {
                "cadId": cad_id,
                "capabilities": item_capabilities,
                "confidence": item.get("confidence"),
                "expectedFileName": f"{cad_id}.SLDASM",
                "resolvedCadPath": str(resolved_path) if resolved_path else None,
                "cadFileExists": bool(resolved_path and resolved_path.is_file()),
                "cadFileBytes": resolved_path.stat().st_size if resolved_path else None,
            }
        )

    module_by_id = {item["cadId"]: item for item in modules}
    groups = []
    for configured in PROJECT01_GROUPS:
        group = dict(configured)
        group["membersResolved"] = all(
            module_by_id.get(cad_id, {}).get("cadFileExists") is True
            for cad_id in configured["memberCadIds"]
        )
        groups.append(group)

    evidence = [
        {"id": item_id, "status": status, "acquisition": acquisition}
        for item_id, status, acquisition in PROJECT01_REQUIRED_EVIDENCE
    ]
    first_stage_path = workspace / "demo/layout_previews/project01_first_stage_geometry.json"
    first_stage = None
    if first_stage_path.is_file():
        first_stage = json.loads(first_stage_path.read_text(encoding="utf-8-sig"))
        if first_stage.get("status") == "PROJECT01_FIRST_STAGE_GEOMETRY_CAPTURED":
            evidence_updates = {
                "baseOperationFace": ("partial", "AABB/service-cluster side inference; exact face not selected"),
                "baseTopInstallationSurface": ("available", "JJ00-SS00 coincident mate face"),
                "transportInstallationFrame": ("available", "JJ00-SS00 coincident plane plus two concentric holes"),
                "operationSideCapacity": ("partial", "JJ00 AABB and service-cluster side inference"),
                "moduleOccupancy": ("partial", "top-level world AABBs; subtree multi-box capture pending"),
            }
            for item in evidence:
                update = evidence_updates.get(item["id"])
                if update:
                    item["status"], item["acquisition"] = update
    work_positions_path = workspace / "demo/layout_previews/project01_work_positions.json"
    work_positions = None
    if work_positions_path.is_file():
        work_positions = json.loads(work_positions_path.read_text(encoding="utf-8-sig"))
        if work_positions.get("status") == "PROJECT01_TWO_WORK_POSITIONS_INFERRED":
            for item in evidence:
                if item["id"] == "transportWorkPositions":
                    item["status"] = "available"
                    item["acquisition"] = "two FF10/FF20 SNAP CARRIER subtree envelope centers"
    scanner_geometry_path = workspace / "demo/layout_previews/project01_scanner_geometry.json"
    scanner_geometry = None
    if scanner_geometry_path.is_file():
        scanner_geometry = json.loads(scanner_geometry_path.read_text(encoding="utf-8-sig"))
        if scanner_geometry.get("status") == "PROJECT01_SCANNER_GEOMETRY_INFERRED":
            evidence_updates = {
                "barcodeFaceAndSide": (
                    "available",
                    "carrier SR-X100 explicit CAD beam endpoint and opposing barcode-face normal",
                ),
                "scannerWorkingDistanceAndAxis": (
                    "available",
                    "two SR-X100 explicit CAD beam axes and 200 mm prototype beam baselines",
                ),
            }
            for item in evidence:
                update = evidence_updates.get(item["id"])
                if update:
                    item["status"], item["acquisition"] = update
    service_points_path = workspace / "demo/layout_previews/project01_service_points.json"
    service_points = None
    if service_points_path.is_file():
        service_points = json.loads(service_points_path.read_text(encoding="utf-8-sig"))
        if service_points.get("status") == "PROJECT01_SERVICE_POINTS_INFERRED":
            evidence_updates = {
                "calibrationServicePoint": (
                    "available",
                    "BD00 prism-end target stack top-center prototype proxy",
                ),
                "combinedServiceFunctionPoints": (
                    "available",
                    "GN10 cleaning, GN20 weighing, FJ00 dual drain cups and GN30 hardness-test leaf geometry",
                ),
            }
            for item in evidence:
                update = evidence_updates.get(item["id"])
                if update:
                    item["status"], item["acquisition"] = update
    valve_reach_path = workspace / "demo/layout_previews/project01_dual_valve_reach.json"
    valve_reach = None
    if valve_reach_path.is_file():
        valve_reach = json.loads(valve_reach_path.read_text(encoding="utf-8-sig"))
        if (
            valve_reach.get("status") == "PROJECT01_DUAL_VALVE_REACH_INFERRED"
            and valve_reach.get("allRequiredTargetsInsideCommonReach") is True
        ):
            for item in evidence:
                if item["id"] == "dualValveReach":
                    item["status"] = "available"
                    item["acquisition"] = (
                        "LM00 1.1 m transverse grating scales, 0.9 m flow magnetic scale, "
                        "and ZZ00 dual FL237AA-00012 offset prototype baseline"
                    )
    occupancy_path = workspace / "demo/layout_previews/project01_module_occupancy.json"
    occupancy = None
    occupancy_summary = None
    if occupancy_path.is_file():
        occupancy = json.loads(occupancy_path.read_text(encoding="utf-8-sig"))
        occupancy_summary = {
            key: occupancy.get(key)
            for key in (
                "schemaVersion",
                "projectId",
                "status",
                "engineeringConfirmed",
                "prototypeBaselineAcceptedForCoarseLayout",
                "operationSideBaseline",
                "coverage",
                "staticCollisionPolicy",
                "prototypePairDiagnostics",
                "remainingProductionGates",
            )
        }
        occupancy_summary["layoutObjects"] = [
            {
                "id": item.get("id"),
                "memberCodes": item.get("memberCodes"),
                "primaryCode": item.get("primaryCode"),
                "occupancyBoxCount": item.get("occupancyBoxCount"),
                "leafBodyOccupancyBoxCount": item.get("leafBodyOccupancyBoxCount"),
            }
            for item in occupancy.get("layoutObjects") or []
        ]
        if occupancy.get("status") == "PROJECT01_OCCUPANCY_AND_COLLISION_POLICY_READY":
            evidence_updates = {
                "baseOperationFace": (
                    "available",
                    "prototype +worldX/+installationV operation-side baseline accepted for coarse layout; exact face remains engineering debt",
                ),
                "operationSideCapacity": (
                    "available",
                    "JJ00 envelope and prototype GN00/BD00/GJ00 service-side occupancy baseline",
                ),
                "moduleOccupancy": (
                    "available",
                    "seven structural modules use leaf-subtree union boxes; GJ00 uses conservative top-level box; JJ00/HL00 remain fixed context",
                ),
                "staticCollisionPolicy": (
                    "available",
                    "all layout-object pairs partitioned into strict multi-AABB, conditional B-Rep, or installation-contact classes",
                ),
            }
            for item in evidence:
                update = evidence_updates.get(item["id"])
                if update:
                    item["status"], item["acquisition"] = update
    missing = [item["id"] for item in evidence if item["status"] == "missing"]
    partial = [item["id"] for item in evidence if item["status"] == "partial"]
    evidence_status = {item["id"]: item["status"] for item in evidence}
    next_extraction_order = []
    if evidence_status["baseTopInstallationSurface"] != "available" or evidence_status["transportInstallationFrame"] != "available":
        next_extraction_order.append("JJ00 operation face and top installation surface")
    if evidence_status["transportWorkPositions"] != "available":
        next_extraction_order.append("JJ00-SS00 transport installation frame plus SS00/FF00 work stations")
    if evidence_status["barcodeFaceAndSide"] != "available" or evidence_status["scannerWorkingDistanceAndAxis"] != "available":
        next_extraction_order.append("SM00 optical origin/axis and carrier barcode face")
    if evidence_status["combinedServiceFunctionPoints"] != "available" or evidence_status["calibrationServicePoint"] != "available":
        next_extraction_order.append("GN00 four function ports and BD00 calibration point")
    if evidence_status["dualValveReach"] != "available":
        next_extraction_order.append("LM00/ZZ00 dual-valve reach")
    if evidence_status["baseOperationFace"] != "available":
        next_extraction_order.append("exact JJ00 operation-face confirmation")
    if evidence_status["moduleOccupancy"] != "available" or evidence_status["staticCollisionPolicy"] != "available":
        next_extraction_order.append("module/subtree occupancy and collision-pair classification")
    all_module_paths_resolved = bool(modules) and all(
        item["cadFileExists"] for item in modules
    )
    top3_ready = not missing and not partial and all_module_paths_resolved

    return {
        "schemaVersion": "project-migration-parameter-skeleton/v1",
        "projectId": "project01",
        "family": project.get("family"),
        "sourceAssemblyPath": str(source_assembly),
        "sourceAssemblyExists": source_assembly.is_file(),
        "pptPath": project.get("pptPath"),
        "pptExists": Path(str(project.get("pptPath"))).is_file(),
        "moduleCount": len(modules),
        "resolvedModuleCadCount": sum(item["cadFileExists"] for item in modules),
        "allModuleCadPathsResolved": all_module_paths_resolved,
        "modules": modules,
        "capabilityCoverage": sorted(capabilities),
        "notPresentByDesign": [
            {
                "capability": "ccd_product",
                "reason": "Project01 PPT and CAD identify no independent product-positioning CCD; BD00 vision belongs to calibration.",
            }
        ],
        "layoutObjectGroups": groups,
        "proposedTopLevelSolveObjects": [
            group["primaryCadId"]
            for group in groups
            if group["placementMode"] != "fixed-context"
        ],
        "requiredEvidence": evidence,
        "firstStageGeometryPath": str(first_stage_path) if first_stage else None,
        "firstStageGeometry": first_stage,
        "workPositionsPath": str(work_positions_path) if work_positions else None,
        "workPositions": work_positions,
        "scannerGeometryPath": str(scanner_geometry_path) if scanner_geometry else None,
        "scannerGeometry": scanner_geometry,
        "servicePointsPath": str(service_points_path) if service_points else None,
        "servicePoints": service_points,
        "dualValveReachPath": str(valve_reach_path) if valve_reach else None,
        "dualValveReach": valve_reach,
        "moduleOccupancyPath": str(occupancy_path) if occupancy else None,
        "moduleOccupancy": occupancy_summary,
        "missingRequiredEvidence": missing,
        "partialEvidence": partial,
        "top3SolveReady": top3_ready,
        "status": (
            "PROJECT01_TOP3_INPUT_READY"
            if top3_ready
            else "PROJECT01_PARAMETER_SKELETON_READY_GEOMETRY_CAPTURE_REQUIRED"
        ),
        "project02NumericParametersInherited": False,
        "engineeringConfirmationDebt": [
            "Confirm the exact JJ00 operation face and maintenance envelope before production release.",
            "Replace prototype-derived scanner beam and dual-valve scale spans when vendor limits become available.",
            "Run conditional leaf-level B-Rep checks only after a selected Top-3 solution is replayed.",
        ],
        "forbiddenInheritedProject02Constants": [
            "A600/A800 installation-frame XYZ",
            "A180/A800 barcode and optical points",
            "A100 reach rectangles and 90 mm head spacing",
            "A500/A700/A300 service-point coordinates and protected-space boxes",
            "Project02 relative-anchor windows and allowed-contact pairs",
        ],
        "portableRulesSelected": [
            "base -> transport -> scanner -> service functions -> gantry coverage order",
            "one rigid CAD module may expose multiple function-specific ports",
            "both scan-window endpoints require distance, sight and directed-pointing checks",
            "strict inflated AABB for ordinary pairs and conditional B-rep for structural/nested pairs",
            "CAD evidence reuse only after rigid-pose/source-file equivalence",
        ],
        "nextExtractionOrder": next_extraction_order,
    }
