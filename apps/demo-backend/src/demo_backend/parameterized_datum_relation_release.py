"""Thin bridge from exact-pair datum CAD evidence to the existing executor.

No new execution engine lives here. A validated three-plane recipe becomes the
same semantic/global catalog and immutable relation release used by native
ports. Physical fastening and collision are deliberately not inferred.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from .global_module_catalog import validate_global_module_catalog
from .global_relation_catalog_release import (
    build_relation_catalog_release, finalize_relation_catalog_release,
    load_relation_catalog_release,
)
from .mechanical_interface_contracts import MechanicalInterfaceContractError
from .parameterized_datum_placement import publish_parameterized_datum_pair_release
from .semantic_port_catalog import validate_semantic_port_catalog


INTERFACE_TYPE = "parameterized_three_orthogonal_planar_datums"
HYBRID_PLANE_AXIS_INTERFACE_TYPE = "reviewed_support_orientation_axis_datum"
FLEXIBLE_SLOT_INTERFACE_TYPE = "reviewed_flexible_calibration_slot_datum"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_new(path: Path, value: Any) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite immutable artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _definition(catalog: dict[str, Any], identity: str) -> dict[str, Any]:
    project, token = identity.split("::", 1)
    rows = [row for row in catalog["moduleDefinitions"] if any(
        alias.get("projectId") == project and alias.get("moduleToken") == token
        for alias in row.get("projectAliases") or []
    )]
    if len(rows) != 1:
        raise MechanicalInterfaceContractError(f"Cannot resolve exact module identity: {identity}")
    return rows[0]


def _verified_inputs(validation_dir: Path) -> tuple[dict, dict, dict, dict]:
    package = _read(validation_dir / "validation-package.json")
    result = _read(validation_dir / "cad-result.json")
    recorded = _read(validation_dir / "pair-release.json")
    # Re-run the release checks against the unchanged real CAD result, instead
    # of trusting a boolean copied into the module interface catalog.
    rebuilt = publish_parameterized_datum_pair_release(package, result)
    if recorded != rebuilt:
        raise MechanicalInterfaceContractError("Pair release differs from validated package evidence")
    artifacts = package.get("artifacts") or {}
    endpoint_binding = artifacts.get("selectedEndpointCatalog") or {}
    endpoint_path = Path(str(endpoint_binding.get("path") or ""))
    if not endpoint_path.is_file() or _sha(endpoint_path) != endpoint_binding.get("sha256"):
        raise MechanicalInterfaceContractError("Selected endpoint catalog changed after validation")
    graph = _read(Path(recorded["effectiveGraphPath"]))
    endpoints = _read(endpoint_path)
    policy = graph.get("EditPolicy") or {}
    base, target = package["baseModuleToken"], package["targetModuleToken"]
    if (
        policy.get("initialPlacementMode") != "deterministic"
        or policy.get("fixedModuleTokens") != [base]
        or policy.get("caseAnchoredModuleTokens")
        or policy.get("targetLeafPoseAnchors")
        or graph.get("CaseAnchor") or graph.get("TargetLeafPoseAnchors")
        or target in policy.get("fixedModuleTokens", [])
        or package.get("prototypeTopLevelTargetPoseUsed") is not False
    ):
        raise MechanicalInterfaceContractError("Datum graph uses fixed target or prototype anchors")
    steps = package["instantiatedTemplate"]["mateSteps"]
    mates = {row["MateName"]: row for row in graph.get("Mates") or []}
    placement_mode = str(
        package.get("placementMode") or "parameterized_three_plane_datum"
    )
    expected_count = 4 if placement_mode == "reviewed_flexible_calibration_slot" else 3
    if len(steps) != expected_count or len(mates) != expected_count:
        raise MechanicalInterfaceContractError(
            f"Datum recipe must preserve exactly {expected_count} real mates"
        )
    for step in steps:
        mate = mates.get(step["mateName"]) or {}
        if (mate.get("MateType") != step["mateType"]
                or mate.get("Alignment") != step["alignment"]
                or mate.get("Distance") != step.get("distanceMeters")
                or mate.get("IsSuppressed") is not False):
            raise MechanicalInterfaceContractError("Recipe parameters changed after CAD validation")
    return package, recorded, graph, endpoints


def build_parameterized_datum_catalog_package(
    *, base_global_catalog: dict, validation_dir: Path,
    semantic_catalog_path: str, endpoint_catalog_path: str, base_graph_path: str,
) -> dict[str, Any]:
    """Adapt one verified pair; no source files or published evidence are edited."""
    validate_global_module_catalog(base_global_catalog)
    package, pair, graph, endpoints = _verified_inputs(validation_dir)
    placement_mode = str(
        package.get("placementMode") or "parameterized_three_plane_datum"
    )
    is_hybrid = placement_mode == "reviewed_hybrid_plane_axis_datum"
    is_flexible = placement_mode == "reviewed_flexible_calibration_slot"
    interface_type = (
        HYBRID_PLANE_AXIS_INTERFACE_TYPE
        if is_hybrid
        else FLEXIBLE_SLOT_INTERFACE_TYPE
        if is_flexible
        else INTERFACE_TYPE
    )
    steps = copy.deepcopy(package["instantiatedTemplate"]["mateSteps"])
    recipe_id = "datum_recipe_" + _digest({
        "module": pair["moduleDefinitionId"], "slot": pair["slotDefinitionId"],
        "steps": steps, "endpoints": endpoints,
    })[:20]
    result = copy.deepcopy(base_global_catalog)
    definitions = [_definition(result, pair[key]) for key in ("moduleDefinitionId", "slotDefinitionId")]
    tokens = [package["targetModuleToken"], package["baseModuleToken"]]
    graph_mates = {row["MateName"]: row for row in graph["Mates"]}
    ports = []
    parameters = {}
    parameter_roles = {
        "longitudinal_datum": "longitudinal",
        "lateral_datum": "lateral",
        "support_datum": "supportGap",
    }
    for step in steps:
        parameter_name = parameter_roles.get(str(step.get("endpointRoleA") or ""))
        if parameter_name:
            parameters[parameter_name] = step.get("distanceMeters", 0)
    if is_hybrid:
        hybrid_selection = package.get("hybridAxisSelection") or {}
        selected_axis = str(hybrid_selection.get("selectedAxisEndpointId") or "")
        selection_digest = str(hybrid_selection.get("selectionDigest") or "")
        if not selected_axis or not selection_digest:
            raise MechanicalInterfaceContractError(
                "Hybrid relation publication is missing reviewed axis evidence"
            )
        boundary = {
            "mode": placement_mode,
            "holePatternMatchRequired": False,
            "actualFixationMethod": "not_verified",
            "actualFixationNotice": "实际固定方式及孔轴直径相容性暂未验证",
            "directMechanicalCompatibilityClaim": False,
            "productionReady": False,
            "selectedAxisEndpointId": selected_axis,
            "hybridAxisSelectionDigest": selection_digest,
            "diameterCompatibility": "not_evaluated",
            "notVendorDatum": True,
            "usesPrototypeTopPose": False,
            "targetSourceTransformMeaning": "identity_placeholder_not_final_pose_witness",
            "collisionOrBrep": "not_evaluated",
        }
    elif is_flexible:
        flexible_selection = package.get("flexibleSlotSelection") or {}
        boundary = {
            "mode": placement_mode,
            "holePatternMatchRequired": False,
            "actualFixationMethod": "not_verified",
            "actualFixationNotice": "实际紧固方式暂未验证",
            "directMechanicalCompatibilityClaim": False,
            "productionReady": False,
            "selectedAxisEndpointId": flexible_selection.get(
                "selectedAxisEndpointId"
            ),
            "flexibleSlotSelectionDigest": flexible_selection.get(
                "selectionDigest"
            ),
            "longitudinalOffsetMeters": (
                package.get("positionParametersOverride") or {}
            ).get("longitudinalOffsetMeters"),
            "internalFlexibilityPreserved": True,
            "externalPlacementRepeatabilityRequired": True,
            "notVendorDatum": True,
            "usesPrototypeTopPose": False,
            "targetSourceTransformMeaning": "identity_placeholder_not_final_pose_witness",
            "collisionOrBrep": "not_evaluated",
        }
    else:
        boundary = {
            "mode": "parameterized_datum_placement", "holePatternMatchRequired": False,
            "actualFixationMethod": "not_verified", "actualFixationNotice": "实际固定方式暂未验证",
            "directMechanicalCompatibilityClaim": False, "productionReady": False,
            "positionParametersMeters": parameters, "parameterSource": (
                "explicit_validation_candidate_override" if package.get("positionParametersOverride")
                else "module_calibrated_station_projection"
            ), "notVendorDatum": True, "usesPrototypeTopPose": False,
            "targetSourceTransformMeaning": "identity_placeholder_not_final_pose_witness",
            "collisionOrBrep": "not_evaluated",
        }
    for side, token in enumerate(tokens):
        bindings, evidence = [], []
        hierarchy = None
        for step in steps:
            mate_endpoint = graph_mates[step["mateName"]]["Endpoints"][side]
            matches = [row for row in endpoints["Endpoints"] if all(
                (row.get("Endpoint") or {}).get(key) == mate_endpoint.get(key)
                for key in ("ModuleHierarchyPath", "RelativeLeafHierarchyPath", "BodyIndex", "FaceIndexInBody")
            )]
            if len(matches) != 1:
                raise MechanicalInterfaceContractError("Validated mate endpoint is not uniquely registered")
            row, role = matches[0], step["endpointRoleA" if side == 0 else "endpointRoleB"]
            endpoint = row["Endpoint"]
            # Leaf catalog captures sometimes retain a full CAD occurrence as
            # ModuleToken; normalize only this routing alias to the validated
            # graph token. Persistent references and leaf identity are untouched.
            endpoint["ModuleToken"] = token
            hierarchy = endpoint["ModuleHierarchyPath"]
            bindings.append({"role": role, "endpointId": row["EndpointId"]})
            geometry_class = str(
                endpoint.get("SurfaceType") or row.get("GeometryClass") or ""
            )
            # Older, already released three-plane endpoint catalogs predate
            # SurfaceType and carry only normals. Their immutable evidence was
            # already validated as planar by the original bridge, so preserve
            # that interpretation. New hybrid catalogs must state the surface
            # class explicitly because the locating endpoint is cylindrical.
            if not geometry_class and not is_hybrid and not is_flexible:
                geometry_class = "Plane"
            if geometry_class not in {"Plane", "Cylinder"}:
                raise MechanicalInterfaceContractError(
                    "Validated datum endpoint must be planar or cylindrical"
                )
            if not is_hybrid and not is_flexible and geometry_class != "Plane":
                raise MechanicalInterfaceContractError(
                    "Three-plane datum publication contains a non-planar endpoint"
                )
            evidence.append({
                "role": role, "endpointId": row["EndpointId"], "geometryClass": geometry_class,
                "recoveryConfidence": row.get("RecoveryConfidence"),
                "relativeLeafHierarchyPath": endpoint.get("RelativeLeafHierarchyPath"),
                "bodyIndex": endpoint.get("BodyIndex"), "faceIndexInBody": endpoint.get("FaceIndexInBody"),
                "hasPersistentReference": bool(endpoint.get("SourceAssemblyPersistentReferenceBase64")),
                "rolePortable": True, "portabilityReasons": [],
            })
        ports.append({
            "portId": f"{token}.{recipe_id}", "displayName": f"{token}参数化基准定位端口",
            "moduleToken": token, "moduleHierarchyPath": hierarchy,
            "projectId": pair["moduleDefinitionId" if side == 0 else "slotDefinitionId"].split("::")[0],
            "category": "mechanical", "interfaceType": interface_type,
            "capabilities": ["installation", "datum_placement_demo"],
            "aliases": [f"{token}基准定位"], "status": "confirmed", "portable": True,
            "endpointBindings": bindings, "endpointEvidence": evidence,
        })
    effect = {"fullyLocatesAddedComponent": True, "expectedResidualDof": 0,
              "directMechanicalInterfaceCompatible": False,
              "cadValidationStatus": "nonprototype_save_reopen_validated",
              "supportPositionDemoPolicy": boundary}
    if is_flexible:
        effect.update(
            {
                "internalFlexibilityPreserved": True,
                "externalPlacementWitness": "two_nonprototype_initial_poses_converged",
                "constraintAcceptance": "accepted_flexible_external_root",
            }
        )
    semantic = {
        "schemaVersion": "semantic-port-catalog/v1", "projectId": "project-global",
        "catalogPurpose": (
            "Validated exact-pair reviewed plane/axis datum placement only."
            if is_hybrid else
            "Validated exact-pair flexible support/distance/slot placement only."
            if is_flexible else
            "Validated exact-pair parameterized datum placement only."
        ),
        "endpointCatalogPath": endpoint_catalog_path, "effectiveMateGraphPath": base_graph_path,
        "ports": ports, "supportPositionDemoPolicy": boundary,
        "connectionTemplates": [{"templateId": recipe_id,
            "purposes": ["installation", "datum_placement_demo"],
            "interfaceTypeA": interface_type, "interfaceTypeB": interface_type,
            "constraintEffect": effect, "mateSteps": steps}],
    }
    validate_semantic_port_catalog(semantic, endpoints)
    provenance = {
        "projectId": "project-global", "semanticCatalogPath": semantic_catalog_path,
        "endpointCatalogPath": endpoint_catalog_path, "effectiveMateGraphPath": base_graph_path,
        "semanticCatalogDigest": _digest(semantic),
    }
    global_ids = []
    for port, definition in zip(ports, definitions):
        global_id = definition["moduleDefinitionId"] + "::port/" + recipe_id
        global_ids.append(global_id)
        result.setdefault("semanticPorts", []).append({
            "globalPortId": global_id, "moduleDefinitionId": definition["moduleDefinitionId"],
            "displayName": port["displayName"], "description": "基准定位Demo；实际固定方式暂未验证。",
            "category": "mechanical", "interfaceType": interface_type,
            "capabilities": port["capabilities"], "aliases": port["aliases"],
            "portable": True, "portabilityReasons": [], "endpointEvidence": port["endpointEvidence"],
            "functionalGeometry": None, "provenance": [{**provenance,
                "portProjectId": port["projectId"], "legacyPortId": port["portId"],
                "moduleToken": port["moduleToken"], "moduleHierarchyPath": port["moduleHierarchyPath"],
                "status": "nonprototype_save_reopen_validated"}],
        })
        definition["portIds"] = sorted(set(definition.get("portIds", []) + [global_id]))
    global_template_id = f"template/project-global/{recipe_id}"
    result.setdefault("connectionTemplates", []).append({
        "globalTemplateId": global_template_id, "legacyTemplateId": recipe_id,
        "purposes": ["installation", "datum_placement_demo"],
        "interfaceTypeA": interface_type, "interfaceTypeB": interface_type,
        "candidatePortIdsA": [global_ids[0]], "candidatePortIdsB": [global_ids[1]],
        "constraintEffect": effect, "mateSteps": steps, "provenance": provenance,
    })
    result.setdefault("compatibility", []).append({
        "portAId": global_ids[0], "portBId": global_ids[1], "globalTemplateId": global_template_id,
        "purpose": "installation", "directional": True, "portableForTemplate": True,
    })
    result.setdefault("sourceCatalogs", []).append({
        "path": semantic_catalog_path, "projectId": "project-global", "status": "validated-datum-placement-demo",
    })
    result["summary"] = {**result.get("summary", {}),
        "semanticPortCount": len(result["semanticPorts"]),
        "portablePortCount": sum(row.get("portable") is True for row in result["semanticPorts"]),
        "connectionTemplateCount": len(result["connectionTemplates"]),
        "compatibilityCount": len(result["compatibility"]),
    }
    result.pop("catalogDigest", None)
    result["catalogDigest"] = _digest(result)
    validate_global_module_catalog(result)
    return {"semanticCatalog": semantic, "endpointCatalog": endpoints,
            "baseGraph": graph, "candidateGlobalCatalog": result,
            "globalTemplateId": global_template_id, "pairRelease": pair,
            "boundary": boundary, "globalModuleDefinitionId": definitions[0]["moduleDefinitionId"],
            "globalSlotDefinitionId": definitions[1]["moduleDefinitionId"]}


def publish_parameterized_datum_relation_release(
    workspace: Path, validation_dir: Path, release_id: str, base_catalog_path: Path,
    *, output_root: Path | None = None,
) -> dict[str, Any]:
    if not release_id or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for ch in release_id):
        raise ValueError("release_id must be a filesystem-safe name")
    output = (output_root or workspace / "demo/global_assembly_catalog/releases") / release_id
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite immutable release: {output}")
    semantic_dir = output / "semantic-package"
    paths = {"semantic": semantic_dir / "semantic_port_catalog.json",
             "endpoints": semantic_dir / "face_endpoint_catalog.json",
             "graph": semantic_dir / "base_parameterized_datum_graph.json",
             "catalog": semantic_dir / "candidate_global_catalog.json"}
    def reference(path: Path) -> str:
        try:
            return path.resolve().relative_to(workspace.resolve()).as_posix()
        except ValueError:
            return str(path.resolve())
    package = build_parameterized_datum_catalog_package(
        base_global_catalog=_read(base_catalog_path), validation_dir=validation_dir,
        semantic_catalog_path=reference(paths["semantic"]),
        endpoint_catalog_path=reference(paths["endpoints"]), base_graph_path=reference(paths["graph"]),
    )
    for key, value_key in (("semantic", "semanticCatalog"), ("endpoints", "endpointCatalog"),
                           ("graph", "baseGraph"), ("catalog", "candidateGlobalCatalog")):
        _write_new(paths[key], package[value_key])
    pair = package["pairRelease"]
    derivation_path = output / "derivation-evidence.json"
    _write_new(derivation_path, {
        "schemaVersion": "global-relation-derivation-evidence/v1", "status": "ready",
        "outputCatalogDigest": package["candidateGlobalCatalog"]["catalogDigest"],
        "derivations": [{"source": {"semanticPortCatalogPath": reference(paths["semantic"]),
            "liveCadResultPath": reference(Path(pair["cadResultPath"])),
            "effectiveGraphSha256": pair["effectiveGraphSha256"],
            "selectedEndpointCatalogSha256": _sha(paths["endpoints"]),
            "pairReleasePath": reference(validation_dir / "pair-release.json"),
            "pairReleaseDigest": pair["releaseDigest"]},
            "result": {"derivedGlobalTemplateId": package["globalTemplateId"]}}],
        "statement": "Exact-pair CAD datum placement only; physical fastening remains unverified.",
    })
    catalog, manifest = build_relation_catalog_release(
        catalog_path=paths["catalog"], derivation_evidence_path=derivation_path,
        validation_evidence_paths=[Path(pair["cadResultPath"])], release_id=release_id,
        authorized_driving_template_ids=[package["globalTemplateId"]],
        release_metadata={"relationExecutionMode": "datum_placement_demo",
            "templateEvidenceClasses": {package["globalTemplateId"]: "datum_placement_demo"},
            "directMechanicalInterfaceCompatible": False, "physicalFasteningVerified": False,
            "actualFasteningMethod": "not_verified", "collisionOrBrep": "not_evaluated",
            "supportPositionDemoPolicy": package["boundary"],
            "parameterizedDatumPairBinding": pair},
    )
    catalog_path, manifest_path = output / "global_module_catalog.json", output / "release-manifest.json"
    _write_new(catalog_path, catalog)
    manifest = finalize_relation_catalog_release(manifest, released_catalog_path=catalog_path, workspace_root=workspace)
    _write_new(manifest_path, manifest)
    load_relation_catalog_release(manifest_path, workspace_root=workspace)
    return {"releaseId": release_id, "releaseDigest": manifest["releaseDigest"],
            "releaseManifestPath": reference(manifest_path), "globalTemplateId": package["globalTemplateId"],
            "moduleDefinitionId": pair["moduleDefinitionId"], "slotDefinitionId": pair["slotDefinitionId"],
            "globalModuleDefinitionId": package["globalModuleDefinitionId"],
            "globalSlotDefinitionId": package["globalSlotDefinitionId"],
            "relationExecutionMode": "datum_placement_demo", "physicalFasteningVerified": False,
            "collisionOrBrep": "not_evaluated", "cadStarted": False}
