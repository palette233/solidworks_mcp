"""Compile bounded matched-slot CAD candidates for the active review goal.

This module intentionally does not add another generic interface framework. It
adapts already captured, stable endpoints into one auditable exact-pair graph.
The first supported pair is Project01 GN00 on the reviewed 204 mm Project03
AA00 alternate slot.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from .mechanical_interface_contracts import MechanicalInterfaceContractError


SCHEMA = "goal-matched-alternate-slot-candidate/v1"
IDENTITY = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _endpoint(catalog: dict[str, Any], endpoint_id: str, token: str) -> dict[str, Any]:
    rows = [
        row
        for row in catalog.get("Endpoints") or []
        if row.get("EndpointId") == endpoint_id
    ]
    if len(rows) != 1:
        raise MechanicalInterfaceContractError(
            f"alternate-slot endpoint does not resolve uniquely: {endpoint_id}"
        )
    endpoint = copy.deepcopy(rows[0]["Endpoint"])
    endpoint["ModuleToken"] = token
    endpoint["Index"] = 0
    endpoint["SemanticEndpointIds"] = [endpoint_id]
    return endpoint


def _mate(
    *,
    name: str,
    mate_type: int,
    mate_type_name: str,
    moving: dict[str, Any],
    base: dict[str, Any],
    alignment: int = 1,
) -> dict[str, Any]:
    moving = copy.deepcopy(moving)
    base = copy.deepcopy(base)
    moving["Index"] = 0
    base["Index"] = 1
    return {
        "MateName": name,
        "MateType": mate_type,
        "MateTypeName": mate_type_name,
        "Alignment": alignment,
        "AlignmentName": (
            "swMateAlignALIGNED" if alignment == 0 else "swMateAlignANTI_ALIGNED"
        ),
        "Distance": None,
        "Angle": None,
        "IsSuppressed": False,
        "Endpoints": [moving, base],
        "ModuleTokens": ["GN00", "AA00"],
        "ModuleHierarchyPaths": [
            moving.get("ModuleHierarchyPath"),
            base.get("ModuleHierarchyPath"),
        ],
        "IsBasicTwoFaceRebuildable": True,
        "RebuildRejectionReason": None,
        "MateId": "mate:" + _digest({"name": name, "endpoints": [moving, base]})[:16],
    }


def compile_gn00_aa00_204mm_candidate(workspace: Path) -> dict[str, Any]:
    """Compile the reviewed 204 mm alternate pair without starting CAD."""

    workspace = workspace.resolve()
    package = workspace / (
        "demo/cross_project_substitution/cleaning-weighing-base-only-v1/"
        "project01_GN00_project03_AG00"
    )
    source_graph_path = package / "two-hole-candidate-v1/assembly_plan_effective.nonprototype.json"
    moving_catalog_path = package / "two-hole-candidate-v1/face_endpoint_catalog.json"
    discovery_path = package / "cleaning_weighing_alternate_slot_discovery.json"
    base_catalog_path = workspace / (
        "demo/global_assembly_catalog/coverage-v2/ag00-datum-discovery-v1/"
        "aa00_ag00_mount_leaf_faces.json"
    )
    wrapper_entry_path = workspace / (
        "demo/global_assembly_contexts/base_wrapper_cache/"
        "7d63f8e557c32448109e318405c54fcb38822b7043612411108216f69af810af/"
        "cache-entry.json"
    )
    for path in (
        source_graph_path,
        moving_catalog_path,
        discovery_path,
        base_catalog_path,
        wrapper_entry_path,
    ):
        if not path.is_file():
            raise FileNotFoundError(path)

    source_graph = _read(source_graph_path)
    moving_catalog = _read(moving_catalog_path)
    base_catalog = _read(base_catalog_path)
    discovery = _read(discovery_path)
    preferred = discovery.get("preferredForMechanicalReview") or {}
    locating_ids = list(preferred.get("locatingEndpointIds") or [])
    support_ids = list(preferred.get("supportPlaneEndpointIds") or [])
    if (
        discovery.get("exactSpacingCandidateCount") != 2
        or preferred.get("directSpacingFit") is not True
        or len(locating_ids) != 2
        or len(support_ids) != 2
    ):
        raise MechanicalInterfaceContractError(
            "GN00/AA00 does not have one bounded reviewed 204 mm candidate"
        )

    wrapper_entry = _read(wrapper_entry_path)
    wrapper_path = wrapper_entry_path.parent / str(wrapper_entry.get("assemblyFile") or "")
    if not wrapper_path.is_file() or _sha256(wrapper_path) != wrapper_entry.get("assemblySha256"):
        raise MechanicalInterfaceContractError("AA00 base wrapper evidence changed")

    moving_module = next(
        copy.deepcopy(row)
        for row in source_graph.get("Modules") or []
        if row.get("ModuleToken") == "GN00"
    )
    moving_module["SourceTransform"] = list(IDENTITY)
    base_module = {
        "ModuleToken": "AA00",
        "Name": "FL9A24D063AA00.001-1",
        "Path": str(base_catalog["Endpoints"][0]["ModulePath"]),
        "HierarchyPath": "FL9A24D063AA00.001-1",
        "SourceTransform": list((wrapper_entry.get("inputs") or {})["baseContextTransform"]),
        "IsSuppressed": False,
        "SuppressionState": 2,
        "SuppressionStateName": "swComponentFullyResolved",
        "VisibilityState": 1,
    }

    support_moving = _endpoint(moving_catalog, "face:gn00:d883a7d374868e40", "GN00")
    primary_moving = _endpoint(moving_catalog, "face:gn00:bb97c49f51337da0", "GN00")
    secondary_moving = _endpoint(
        moving_catalog, "face:fl9c24n074gn00.001-1:a10d18a87f322b43", "GN00"
    )
    # The upper face (local z=0.018, downward normal) is the installation
    # support side.  The lower face remains recorded in discovery evidence but
    # is not used as the driving support endpoint.
    support_base = _endpoint(base_catalog, "face:fl9a24d063aa00:0dea78ae25e9aab4", "AA00")
    primary_base = _endpoint(base_catalog, locating_ids[0], "AA00")
    secondary_base = _endpoint(base_catalog, locating_ids[1], "AA00")

    mates = [
        _mate(
            name="MCP_GOAL_GN00_AA00_SUPPORT",
            mate_type=0,
            mate_type_name="swMateCOINCIDENT",
            moving=support_moving,
            base=support_base,
        ),
        _mate(
            name="MCP_GOAL_GN00_AA00_PRIMARY_AXIS",
            mate_type=1,
            mate_type_name="swMateCONCENTRIC",
            moving=primary_moving,
            base=primary_base,
            alignment=0,
        ),
        _mate(
            name="MCP_GOAL_GN00_AA00_SECONDARY_AXIS",
            mate_type=1,
            mate_type_name="swMateCONCENTRIC",
            moving=secondary_moving,
            base=secondary_base,
            alignment=0,
        ),
    ]
    graph = {
        "SchemaVersion": "editable-module-mate-graph/v1",
        "SourceAssemblyPath": str(wrapper_path),
        "ModuleCount": 2,
        "InterModuleMateCount": 3,
        "Modules": [base_module, moving_module],
        "Mates": mates,
        "EditPolicy": {
            "baseModuleToken": "AA00",
            "initialPlacementMode": "deterministic_nonprototype",
            "initialPlacementVariant": 1,
            "sourceGraphImmutable": True,
            "fixedModuleTokens": ["AA00"],
            "targetModuleToken": "GN00",
            "casePoseAnchors": [],
            "targetLeafPoseAnchors": [],
        },
    }
    core = {
        "schemaVersion": SCHEMA,
        "status": "ready_for_nonprototype_cad_validation",
        "classificationBeforeCad": "REVIEWED_MATCHED_ALTERNATE_SLOT_CANDIDATE",
        "moduleDefinitionId": "project01::GN00",
        "slotDefinitionId": "project03::AA00",
        "moduleRole": "CleaningWeighing",
        "sourceAssemblyPath": str(wrapper_path),
        "sourceAssemblySha256": _sha256(wrapper_path),
        "requiredSpacingMeters": 0.204,
        "selectedLocatingEndpointIds": locating_ids,
        "selectedSupportEndpointId": "face:fl9a24d063aa00:0dea78ae25e9aab4",
        "distanceFromNativeRoleStationMeters": preferred.get(
            "distanceFromNativeAg00SlotMeters"
        ),
        "nonPrototypeInitialPose": True,
        "sourceTopLevelPoseUsed": False,
        "leafPoseAnchorsUsed": False,
        "physicalFasteningVerified": False,
        "collisionOrBrep": "not_evaluated",
        "engineeringBoundary": (
            "Exact 204 mm parallel axes and a stable support face are proven. "
            "Hole purpose, pin/bushing choice, load capacity and production fastening remain unverified."
        ),
        "effectiveGraph": graph,
        "evidencePaths": [
            str(discovery_path),
            str(moving_catalog_path),
            str(base_catalog_path),
            str(wrapper_entry_path),
        ],
    }
    return {**core, "candidateDigest": _digest(core)}
