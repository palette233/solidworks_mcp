"""Publish a CAD-validated exact direct mechanical-interface pair.

The direct interface compiler proves that a normalized two-port contract can
instantiate real mates without using prototype pose anchors.  This bridge adds
the missing promotion step: it revalidates the CAD result, creates an immutable
exact-pair release, registers two semantic ports and one direct-installation
template in the global catalog, and emits the standard relation release used by
the cumulative assembly executor.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

from .global_module_catalog import validate_global_module_catalog
from .global_relation_catalog_release import (
    build_relation_catalog_release,
    finalize_relation_catalog_release,
    load_relation_catalog_release,
)
from .mechanical_interface_contracts import MechanicalInterfaceContractError
from .semantic_port_catalog import validate_semantic_port_catalog


PACKAGE_SCHEMA = "direct-interface-cad-validation-package/v1"
PAIR_RELEASE_SCHEMA = "direct-interface-pair-release/v1"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_new(path: Path, value: Any) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite immutable artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _reference(workspace: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(workspace.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _definition(catalog: dict[str, Any], identity: str) -> dict[str, Any]:
    project, token = identity.split("::", 1)
    rows = [
        row
        for row in catalog.get("moduleDefinitions") or []
        if any(
            alias.get("projectId") == project and alias.get("moduleToken") == token
            for alias in row.get("projectAliases") or []
        )
    ]
    if len(rows) != 1:
        raise MechanicalInterfaceContractError(
            f"Cannot resolve exact module identity: {identity}"
        )
    return rows[0]


def load_materialized_direct_interface_package(
    validation_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    manifest_path = validation_dir / "validation-package.json"
    package = _read(manifest_path)
    if package.get("schemaVersion") != PACKAGE_SCHEMA:
        raise MechanicalInterfaceContractError("unsupported direct validation package")
    artifacts = package.get("artifacts") or {}
    graph_binding = artifacts.get("effectiveGraph") or {}
    endpoint_binding = artifacts.get("selectedEndpointCatalog") or {}
    graph_path = Path(str(graph_binding.get("path") or ""))
    endpoint_path = Path(str(endpoint_binding.get("path") or ""))
    if (
        not graph_path.is_file()
        or _sha(graph_path) != graph_binding.get("sha256")
        or not endpoint_path.is_file()
        or _sha(endpoint_path) != endpoint_binding.get("sha256")
    ):
        raise MechanicalInterfaceContractError(
            "direct validation graph or endpoint artifact changed"
        )
    graph = _read(graph_path)
    endpoints = _read(endpoint_path)
    original = {
        key: value
        for key, value in package.items()
        if key not in {"packageDigest", "artifacts"}
    }
    original["effectiveMateGraph"] = graph
    original["selectedEndpointCatalog"] = endpoints
    if package.get("packageDigest") != _digest(original):
        raise MechanicalInterfaceContractError("direct validation package digest mismatch")
    if package.get("effectiveMateGraphDigest") != _digest(graph):
        raise MechanicalInterfaceContractError("direct validation graph digest mismatch")
    return package, graph, endpoints


def build_direct_interface_pair_release(
    validation_dir: Path,
) -> dict[str, Any]:
    package, graph, _ = load_materialized_direct_interface_package(validation_dir)
    result_path = validation_dir / "cad-result.json"
    if not result_path.is_file():
        raise FileNotFoundError(result_path)
    result = _read(result_path)
    graph_binding = package["artifacts"]["effectiveGraph"]
    if (
        result.get("success") is not True
        or result.get("effectiveGraphSha256") != graph_binding["sha256"]
    ):
        raise MechanicalInterfaceContractError(
            "direct CAD result is unsuccessful or not graph-bound"
        )
    tool = result.get("toolResult") or {}
    expected_mates = len(graph.get("Mates") or [])
    checks = {
        "independentComponentInserted": tool.get("IndependentComponentInserted")
        is True,
        "allMatesCreated": expected_mates > 0
        and int(tool.get("RequestedMateCount") or 0) == expected_mates
        and int(tool.get("CreatedMateCount") or 0) == expected_mates,
        "saveCloseReopenPassed": tool.get("Reopened") is True
        and tool.get("ReopenedMateParametersMatch") is True,
        "targetFullyConstrained": tool.get("TargetConstraintStateAccepted") is True
        and tool.get("TargetFullyConstrained") is True,
        "mateSolveClean": tool.get("MateSolveClean") is True,
        "noPrototypePoseAnchor": tool.get("TargetCaseAnchored") is False
        and int(tool.get("RequestedTargetLeafPoseAnchorCount") or 0) == 0
        and int(tool.get("AppliedTargetLeafPoseAnchorCount") or 0) == 0,
        "sourceAssemblyUnchanged": result.get("sourceAssemblyUnchanged") is True,
        "outputClosed": result.get("outputClosedAfterVerification") is True,
        "targetSourceSessionClean": result.get("targetSourceSessionClean") is True,
    }
    failed = [name for name, passed in checks.items() if passed is not True]
    if failed:
        raise MechanicalInterfaceContractError(
            "direct CAD validation cannot be released: " + ", ".join(failed)
        )
    output = Path(str(result.get("outputAssemblyPath") or ""))
    if not output.is_file() or _sha(output) != result.get("outputAssemblySha256"):
        raise MechanicalInterfaceContractError("validated direct output assembly changed")
    policy = graph.get("EditPolicy") or {}
    modules = graph.get("Modules") or []
    base = str(modules[0].get("ModuleToken") or "") if modules else ""
    target = str(modules[1].get("ModuleToken") or "") if len(modules) > 1 else ""
    if (
        policy.get("initialPlacementMode") != "deterministic"
        or policy.get("fixedModuleTokens") != [base]
        or policy.get("caseAnchoredModuleTokens")
        or policy.get("targetLeafPoseAnchors")
        or target in policy.get("fixedModuleTokens", [])
        or package.get("prototypeTopLevelTargetPoseUsed") is not False
    ):
        raise MechanicalInterfaceContractError(
            "direct graph uses a fixed target or prototype pose anchor"
        )
    core = {
        "schemaVersion": PAIR_RELEASE_SCHEMA,
        "releaseId": "direct-interface-"
        + _digest(
            [
                package["moduleDefinitionId"],
                package["slotDefinitionId"],
                graph_binding["sha256"],
            ]
        )[:16],
        "moduleDefinitionId": package["moduleDefinitionId"],
        "slotDefinitionId": package["slotDefinitionId"],
        "matchId": package["matchId"],
        "templateId": package["templateId"],
        "interfaceFamily": package["interfaceFamily"],
        "nonPrototypeCadValidated": True,
        "prototypeTopLevelTargetPoseUsed": False,
        "caseAnchorUsed": False,
        "targetLeafPoseAnchorsUsed": False,
        "directMechanicalInterfaceCompatible": True,
        "physicalFasteningVerified": False,
        "productionReady": False,
        "collisionOrBrep": "not_evaluated",
        "checks": checks,
        "durationSeconds": result.get("durationSeconds"),
        "effectiveGraphPath": str(Path(graph_binding["path"]).resolve()),
        "effectiveGraphSha256": graph_binding["sha256"],
        "selectedEndpointCatalogPath": str(
            Path(package["artifacts"]["selectedEndpointCatalog"]["path"]).resolve()
        ),
        "cadResultPath": str(result_path.resolve()),
        "cadResultSha256": _sha(result_path),
        "outputAssemblyPath": str(output.resolve()),
        "outputAssemblySha256": _sha(output),
        "claimBoundary": (
            "Released for exact-pair direct CAD installation only. Interface topology "
            "and spacing are compatible and the real mates locate the module from a "
            "non-prototype pose. Fastener fit, collision and production approval remain "
            "unverified."
        ),
    }
    return {**core, "releaseDigest": _digest(core)}


def derive_direct_interface_relation_release_id(
    pair_release: dict[str, Any]
) -> str:
    if pair_release.get("schemaVersion") != PAIR_RELEASE_SCHEMA:
        raise MechanicalInterfaceContractError("unsupported direct pair release schema")
    digest = str(pair_release.get("releaseDigest") or "")
    module = str(pair_release.get("moduleDefinitionId") or "").replace("::", "-")
    slot = str(pair_release.get("slotDefinitionId") or "").replace("::", "-")
    if len(digest) != 64 or not module or not slot:
        raise MechanicalInterfaceContractError("direct pair release identity is incomplete")
    return f"relation-direct-{module.lower()}-{slot.lower()}-{digest[:12]}"


def plan_direct_interface_cad_validation(
    workspace: Path, validation_dir: Path
) -> dict[str, Any]:
    workspace = workspace.resolve()
    validation_dir = validation_dir.resolve()
    package, graph, _ = load_materialized_direct_interface_package(validation_dir)
    graph_binding = package["artifacts"]["effectiveGraph"]
    source = Path(str(package.get("baseWrapperPath") or ""))
    if not source.is_file() or _sha(source) != package.get("baseWrapperSha256"):
        raise MechanicalInterfaceContractError("direct validation base wrapper changed")
    modules = graph.get("Modules") or []
    if len(modules) != 2:
        raise MechanicalInterfaceContractError("direct validation graph must have two modules")
    target_token = str(modules[1].get("ModuleToken") or "")
    if not target_token:
        raise MechanicalInterfaceContractError("direct validation target token is missing")
    output = validation_dir / (
        package["slotDefinitionId"].replace("::", "-").lower()
        + "-"
        + package["moduleDefinitionId"].replace("::", "-").lower()
        + "-direct-validation-v1.SLDASM"
    )
    result = validation_dir / "cad-result.json"
    pair_release = validation_dir / "pair-release.json"
    relation_binding = validation_dir / "relation-release-binding.json"
    for path in (output, result, pair_release, relation_binding):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite direct validation evidence: {path}")
    adapter = workspace / "scripts/run_context_mate_graph_insert.py"
    if not adapter.is_file():
        raise FileNotFoundError(adapter)
    command = [
        sys.executable,
        str(adapter),
        "--source",
        str(source),
        "--effective",
        str(Path(graph_binding["path"])),
        "--output",
        str(output),
        "--target",
        target_token,
        "--expected-source-sha256",
        str(package["baseWrapperSha256"]),
        "--expected-effective-sha256",
        str(graph_binding["sha256"]),
        "--result",
        str(result),
        "--direct-stdio",
    ]
    return {
        "schemaVersion": "direct-interface-cad-validation-execution-plan/v1",
        "moduleDefinitionId": package["moduleDefinitionId"],
        "slotDefinitionId": package["slotDefinitionId"],
        "validationDirectory": str(validation_dir),
        "validationPackagePath": str(validation_dir / "validation-package.json"),
        "sourceAssemblyPath": str(source),
        "sourceAssemblySha256": package["baseWrapperSha256"],
        "effectiveGraphPath": str(Path(graph_binding["path"])),
        "effectiveGraphSha256": graph_binding["sha256"],
        "outputAssemblyPath": str(output),
        "cadResultPath": str(result),
        "pairReleasePath": str(pair_release),
        "relationReleaseBindingPath": str(relation_binding),
        "command": command,
        "preconditions": {
            "solidWorksOpenDocumentCountMustEqual": 0,
            "nonPrototypeInitialPoseRequired": True,
            "saveCloseReopenRequired": True,
            "stopQueueOnFailure": True,
        },
    }


def _endpoint_match(
    endpoints: dict[str, Any], graph_endpoint: dict[str, Any]
) -> dict[str, Any]:
    matches = [
        row
        for row in endpoints.get("Endpoints") or []
        if all(
            (row.get("Endpoint") or {}).get(key) == graph_endpoint.get(key)
            for key in (
                "RelativeLeafHierarchyPath",
                "BodyIndex",
                "FaceIndexInBody",
            )
        )
    ]
    if len(matches) != 1:
        raise MechanicalInterfaceContractError(
            "direct mate endpoint is not uniquely registered"
        )
    return copy.deepcopy(matches[0])


def build_direct_interface_catalog_package(
    *,
    base_global_catalog: dict[str, Any],
    validation_dir: Path,
    semantic_catalog_path: str,
    endpoint_catalog_path: str,
    base_graph_path: str,
) -> dict[str, Any]:
    validate_global_module_catalog(base_global_catalog)
    package, graph, endpoints = load_materialized_direct_interface_package(
        validation_dir
    )
    pair = _read(validation_dir / "pair-release.json")
    rebuilt = build_direct_interface_pair_release(validation_dir)
    if pair != rebuilt:
        raise MechanicalInterfaceContractError(
            "direct pair release differs from current CAD evidence"
        )
    result = copy.deepcopy(base_global_catalog)
    definitions = [
        _definition(result, pair["moduleDefinitionId"]),
        _definition(result, pair["slotDefinitionId"]),
    ]
    template = package["instantiatedTemplate"]
    steps = copy.deepcopy(template["mateSteps"])
    graph_mates = {row["MateName"]: row for row in graph.get("Mates") or []}
    modules = graph.get("Modules") or []
    if len(modules) != 2:
        raise MechanicalInterfaceContractError("direct graph must contain two modules")
    tokens = [str(modules[1]["ModuleToken"]), str(modules[0]["ModuleToken"])]
    release_endpoints = copy.deepcopy(endpoints)
    release_endpoint_index = {
        str(row.get("EndpointId") or ""): row
        for row in release_endpoints.get("Endpoints") or []
        if row.get("EndpointId")
    }
    recipe_id = "direct_recipe_" + _digest(
        {
            "module": pair["moduleDefinitionId"],
            "slot": pair["slotDefinitionId"],
            "steps": steps,
            "endpoints": package["selectedEndpointIds"],
        }
    )[:20]
    ports: list[dict[str, Any]] = []
    for side, token in enumerate(tokens):
        graph_side = 0 if side == 0 else 1
        bindings: list[dict[str, Any]] = []
        evidence: list[dict[str, Any]] = []
        hierarchy = None
        for step in steps:
            mate = graph_mates.get(step["mateName"])
            if not mate:
                raise MechanicalInterfaceContractError(
                    "direct graph is missing a template mate"
                )
            row = _endpoint_match(endpoints, mate["Endpoints"][graph_side])
            endpoint = row["Endpoint"]
            endpoint["ModuleToken"] = token
            hierarchy = endpoint.get("ModuleHierarchyPath")
            release_row = release_endpoint_index.get(str(row["EndpointId"]))
            if release_row is None:
                raise MechanicalInterfaceContractError(
                    "direct release endpoint is absent from its normalized catalog"
                )
            release_endpoint = release_row.get("Endpoint") or {}
            release_endpoint["ModuleToken"] = token
            release_endpoint["ModuleHierarchyPath"] = hierarchy
            role = step["endpointRoleA" if side == 0 else "endpointRoleB"]
            bindings.append({"role": role, "endpointId": row["EndpointId"]})
            evidence.append(
                {
                    "role": role,
                    "endpointId": row["EndpointId"],
                    "geometryClass": endpoint.get("SurfaceType")
                    or row.get("GeometryClass"),
                    "recoveryConfidence": row.get("RecoveryConfidence"),
                    "relativeLeafHierarchyPath": endpoint.get(
                        "RelativeLeafHierarchyPath"
                    ),
                    "bodyIndex": endpoint.get("BodyIndex"),
                    "faceIndexInBody": endpoint.get("FaceIndexInBody"),
                    "hasPersistentReference": bool(
                        endpoint.get("SourceAssemblyPersistentReferenceBase64")
                    ),
                    "rolePortable": True,
                    "portabilityReasons": [],
                }
            )
        identity = pair["moduleDefinitionId" if side == 0 else "slotDefinitionId"]
        ports.append(
            {
                "portId": f"{token}.{recipe_id}",
                "displayName": f"{token}直接机械安装端口",
                "moduleToken": token,
                "moduleHierarchyPath": hierarchy,
                "projectId": identity.split("::", 1)[0],
                "category": "mechanical",
                "interfaceType": pair["interfaceFamily"],
                "capabilities": ["installation"],
                "aliases": [f"{token}机械安装接口"],
                "status": "confirmed",
                "portable": True,
                "endpointBindings": bindings,
                "endpointEvidence": evidence,
            }
        )
    effect = {
        "fullyLocatesAddedComponent": True,
        "expectedResidualDof": 0,
        "directMechanicalInterfaceCompatible": True,
        "cadValidationStatus": "nonprototype_save_reopen_validated",
        "physicalFasteningVerified": False,
        "collisionOrBrep": "not_evaluated",
    }
    semantic = {
        "schemaVersion": "semantic-port-catalog/v1",
        "projectId": "project-global",
        "catalogPurpose": "Validated exact-pair direct mechanical installation.",
        "endpointCatalogPath": endpoint_catalog_path,
        "effectiveMateGraphPath": base_graph_path,
        "ports": ports,
        "connectionTemplates": [
            {
                "templateId": recipe_id,
                "purposes": ["installation"],
                "interfaceTypeA": pair["interfaceFamily"],
                "interfaceTypeB": pair["interfaceFamily"],
                "constraintEffect": effect,
                "mateSteps": steps,
            }
        ],
    }
    validate_semantic_port_catalog(semantic, release_endpoints)
    provenance = {
        "projectId": "project-global",
        "semanticCatalogPath": semantic_catalog_path,
        "endpointCatalogPath": endpoint_catalog_path,
        "effectiveMateGraphPath": base_graph_path,
        "semanticCatalogDigest": _digest(semantic),
    }
    global_ids: list[str] = []
    for port, definition in zip(ports, definitions):
        global_id = definition["moduleDefinitionId"] + "::port/" + recipe_id
        global_ids.append(global_id)
        result.setdefault("semanticPorts", []).append(
            {
                "globalPortId": global_id,
                "moduleDefinitionId": definition["moduleDefinitionId"],
                "displayName": port["displayName"],
                "description": "已验证精确直接机械安装；实际紧固仍未确认。",
                "category": "mechanical",
                "interfaceType": pair["interfaceFamily"],
                "capabilities": ["installation"],
                "aliases": port["aliases"],
                "portable": True,
                "portabilityReasons": [],
                "endpointEvidence": port["endpointEvidence"],
                "functionalGeometry": None,
                "provenance": [
                    {
                        **provenance,
                        "portProjectId": port["projectId"],
                        "legacyPortId": port["portId"],
                        "moduleToken": port["moduleToken"],
                        "moduleHierarchyPath": port["moduleHierarchyPath"],
                        "status": "nonprototype_save_reopen_validated",
                    }
                ],
            }
        )
        definition["portIds"] = sorted(
            set(definition.get("portIds", []) + [global_id])
        )
    global_template_id = f"template/project-global/{recipe_id}"
    result.setdefault("connectionTemplates", []).append(
        {
            "globalTemplateId": global_template_id,
            "legacyTemplateId": recipe_id,
            "purposes": ["installation"],
            "interfaceTypeA": pair["interfaceFamily"],
            "interfaceTypeB": pair["interfaceFamily"],
            "candidatePortIdsA": [global_ids[0]],
            "candidatePortIdsB": [global_ids[1]],
            "constraintEffect": effect,
            "mateSteps": steps,
            "provenance": provenance,
        }
    )
    result.setdefault("compatibility", []).append(
        {
            "portAId": global_ids[0],
            "portBId": global_ids[1],
            "globalTemplateId": global_template_id,
            "purpose": "installation",
            "directional": True,
            "portableForTemplate": True,
        }
    )
    result.setdefault("sourceCatalogs", []).append(
        {
            "path": semantic_catalog_path,
            "projectId": "project-global",
            "status": "validated-direct-interface",
        }
    )
    result["summary"] = {
        **result.get("summary", {}),
        "semanticPortCount": len(result["semanticPorts"]),
        "portablePortCount": sum(
            row.get("portable") is True for row in result["semanticPorts"]
        ),
        "connectionTemplateCount": len(result["connectionTemplates"]),
        "compatibilityCount": len(result["compatibility"]),
    }
    result.pop("catalogDigest", None)
    result["catalogDigest"] = _digest(result)
    validate_global_module_catalog(result)
    return {
        "semanticCatalog": semantic,
        "endpointCatalog": release_endpoints,
        "baseGraph": graph,
        "candidateGlobalCatalog": result,
        "globalTemplateId": global_template_id,
        "pairRelease": pair,
        "globalModuleDefinitionId": definitions[0]["moduleDefinitionId"],
        "globalSlotDefinitionId": definitions[1]["moduleDefinitionId"],
    }


def publish_direct_interface_relation_release(
    workspace: Path,
    validation_dir: Path,
    release_id: str,
    base_catalog_path: Path,
    *,
    output_root: Path | None = None,
) -> dict[str, Any]:
    if not release_id or any(
        ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
        for ch in release_id
    ):
        raise ValueError("release_id must be filesystem-safe")
    output = (output_root or workspace / "demo/global_assembly_catalog/releases") / release_id
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite immutable release: {output}")
    semantic_dir = output / "semantic-package"
    paths = {
        "semantic": semantic_dir / "semantic_port_catalog.json",
        "endpoints": semantic_dir / "face_endpoint_catalog.json",
        "graph": semantic_dir / "base_direct_interface_graph.json",
        "catalog": semantic_dir / "candidate_global_catalog.json",
    }
    package = build_direct_interface_catalog_package(
        base_global_catalog=_read(base_catalog_path),
        validation_dir=validation_dir,
        semantic_catalog_path=_reference(workspace, paths["semantic"]),
        endpoint_catalog_path=_reference(workspace, paths["endpoints"]),
        base_graph_path=_reference(workspace, paths["graph"]),
    )
    for key, value_key in (
        ("semantic", "semanticCatalog"),
        ("endpoints", "endpointCatalog"),
        ("graph", "baseGraph"),
        ("catalog", "candidateGlobalCatalog"),
    ):
        _write_new(paths[key], package[value_key])
    pair = package["pairRelease"]
    derivation_path = output / "derivation-evidence.json"
    _write_new(
        derivation_path,
        {
            "schemaVersion": "global-relation-derivation-evidence/v1",
            "status": "ready",
            "outputCatalogDigest": package["candidateGlobalCatalog"]["catalogDigest"],
            "derivations": [
                {
                    "source": {
                        "semanticPortCatalogPath": _reference(
                            workspace, paths["semantic"]
                        ),
                        "liveCadResultPath": _reference(
                            workspace, Path(pair["cadResultPath"])
                        ),
                        "effectiveGraphSha256": pair["effectiveGraphSha256"],
                        "selectedEndpointCatalogSha256": _sha(paths["endpoints"]),
                        "pairReleasePath": _reference(
                            workspace, validation_dir / "pair-release.json"
                        ),
                        "pairReleaseDigest": pair["releaseDigest"],
                    },
                    "result": {
                        "derivedGlobalTemplateId": package["globalTemplateId"]
                    },
                }
            ],
            "statement": (
                "Exact-pair direct mechanical installation only; physical fastening "
                "and collision remain unverified."
            ),
        },
    )
    catalog, manifest = build_relation_catalog_release(
        catalog_path=paths["catalog"],
        derivation_evidence_path=derivation_path,
        validation_evidence_paths=[Path(pair["cadResultPath"])],
        release_id=release_id,
        authorized_driving_template_ids=[package["globalTemplateId"]],
        release_metadata={
            "relationExecutionMode": "direct_installation",
            "templateEvidenceClasses": {
                package["globalTemplateId"]: "direct_installation"
            },
            "directMechanicalInterfaceCompatible": True,
            "physicalFasteningVerified": False,
            "collisionOrBrep": "not_evaluated",
            "directInterfacePairBinding": pair,
        },
    )
    catalog_path = output / "global_module_catalog.json"
    manifest_path = output / "release-manifest.json"
    _write_new(catalog_path, catalog)
    manifest = finalize_relation_catalog_release(
        manifest,
        released_catalog_path=catalog_path,
        workspace_root=workspace,
    )
    _write_new(manifest_path, manifest)
    load_relation_catalog_release(manifest_path, workspace_root=workspace)
    return {
        "releaseId": release_id,
        "releaseDigest": manifest["releaseDigest"],
        "releaseManifestPath": _reference(workspace, manifest_path),
        "globalTemplateId": package["globalTemplateId"],
        "moduleDefinitionId": pair["moduleDefinitionId"],
        "slotDefinitionId": pair["slotDefinitionId"],
        "globalModuleDefinitionId": package["globalModuleDefinitionId"],
        "globalSlotDefinitionId": package["globalSlotDefinitionId"],
        "relationExecutionMode": "direct_installation",
        "physicalFasteningVerified": False,
        "collisionOrBrep": "not_evaluated",
        "cadStarted": False,
    }


def ensure_direct_interface_relation_release(
    workspace: Path,
    validation_dir: Path,
    base_catalog_path: Path,
    *,
    output_root: Path | None = None,
) -> dict[str, Any]:
    """Finish or recover direct exact-pair publication without rerunning CAD.

    A successful CAD result may survive a process interruption before the pair
    or relation release is written.  This helper authenticates every existing
    artifact and only creates the missing immutable layer.  Existing evidence
    is never overwritten.
    """

    workspace = workspace.resolve()
    validation_dir = validation_dir.resolve()
    rebuilt_pair = build_direct_interface_pair_release(validation_dir)
    pair_path = validation_dir / "pair-release.json"
    pair_created = False
    if pair_path.is_file():
        pair = _read(pair_path)
        if pair != rebuilt_pair:
            raise MechanicalInterfaceContractError(
                "existing direct pair release differs from current CAD evidence"
            )
    else:
        _write_new(pair_path, rebuilt_pair)
        pair = rebuilt_pair
        pair_created = True

    release_id = derive_direct_interface_relation_release_id(pair)
    release_base = (output_root or workspace / "demo/global_assembly_catalog/releases").resolve()
    release_dir = release_base / release_id
    manifest_path = release_dir / "release-manifest.json"
    release_created = False
    if release_dir.exists():
        if not manifest_path.is_file():
            raise MechanicalInterfaceContractError(
                "direct relation release directory is incomplete: " + str(release_dir)
            )
        catalog, manifest = load_relation_catalog_release(
            manifest_path, workspace_root=workspace
        )
        metadata = manifest.get("releaseMetadata") or {}
        if (
            metadata.get("directInterfacePairBinding") != pair
            or metadata.get("relationExecutionMode") != "direct_installation"
        ):
            raise MechanicalInterfaceContractError(
                "existing direct relation release is not bound to this exact pair"
            )
        authorized = (manifest.get("scope") or {}).get(
            "authorizedDrivingTemplateIds"
        ) or []
        if len(authorized) != 1:
            raise MechanicalInterfaceContractError(
                "direct relation release must authorize exactly one template"
            )
        if catalog.get("catalogDigest") != manifest.get("catalogDigest"):
            raise MechanicalInterfaceContractError(
                "direct relation release catalog digest mismatch"
            )
        relation = {
            "releaseId": manifest["releaseId"],
            "releaseDigest": manifest["releaseDigest"],
            "releaseManifestPath": _reference(workspace, manifest_path),
            "globalTemplateId": authorized[0],
            "moduleDefinitionId": pair["moduleDefinitionId"],
            "slotDefinitionId": pair["slotDefinitionId"],
            "relationExecutionMode": "direct_installation",
            "physicalFasteningVerified": False,
            "collisionOrBrep": "not_evaluated",
            "cadStarted": False,
        }
    else:
        relation = publish_direct_interface_relation_release(
            workspace,
            validation_dir,
            release_id,
            base_catalog_path,
            output_root=release_base,
        )
        release_created = True
    return {
        "schemaVersion": "direct-interface-publication-recovery/v1",
        "pairRelease": pair,
        "pairReleasePath": _reference(workspace, pair_path),
        "pairReleaseCreated": pair_created,
        "relationRelease": relation,
        "relationReleaseCreated": release_created,
        "releaseManifestPath": relation["releaseManifestPath"],
        "cadRerun": False,
    }
