"""Close and publish a CAD-validated cross-project semantic slot.

The release is deliberately narrower than a production or collision release.
It proves that the declared three-datum interface locates an independently
inserted module from a deterministic non-source pose and survives save/reopen.
Collision and B-rep remain explicitly outside this contract.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from .semantic_port_catalog import validate_semantic_port_catalog
from .global_module_catalog import validate_global_module_catalog


SCHEMA = "cross-project-slot-release-closure/v1"
LEGACY_TEMPLATE_ID = "AH00_to_A600_cross_project_three_datum_installation"
TRANSPORT_LEGACY_TEMPLATE_ID = (
    "cross_project_project03_AE00_to_project01_SS00_slot"
)


class CrossProjectSlotReleaseError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _endpoint_index(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if catalog.get("SchemaVersion") != "solidworks-face-endpoint-catalog/v1":
        raise CrossProjectSlotReleaseError("不支持的面端点目录版本。")
    return {
        str(row.get("EndpointId") or ""): row
        for row in catalog.get("Endpoints") or []
        if str(row.get("EndpointId") or "")
    }


def _single_port(catalog: dict[str, Any], port_id: str) -> dict[str, Any]:
    matches = [
        row for row in catalog.get("ports") or [] if row.get("portId") == port_id
    ]
    if len(matches) != 1:
        raise CrossProjectSlotReleaseError(f"无法唯一定位端口：{port_id}。")
    return copy.deepcopy(matches[0])


def _require(checks: dict[str, bool]) -> None:
    failed = [name for name, passed in checks.items() if passed is not True]
    if failed:
        raise CrossProjectSlotReleaseError(
            "跨项目槽位发布门禁未通过：" + ", ".join(failed)
        )


def finalize_a600_ah00_cross_project_slot(
    *,
    candidate: dict[str, Any],
    validation_plan: dict[str, Any],
    effective_graph: dict[str, Any],
    effective_graph_file_sha256: str,
    cad_result: dict[str, Any],
    output_assembly_sha256: str,
    current_source_sha256: dict[str, str],
    a600_face_catalog: dict[str, Any],
    ah00_semantic_catalog: dict[str, Any],
    ah00_face_catalog: dict[str, Any],
    endpoint_catalog_path: str,
    effective_graph_path: str,
    validation_evidence_path: str,
    output_assembly_path: str,
) -> dict[str, Any]:
    """Return a released semantic package and an immutable closure manifest."""

    if candidate.get("schemaVersion") != "cross-project-slot-port-candidate/v1":
        raise CrossProjectSlotReleaseError("候选端口版本不受支持。")
    if validation_plan.get("schemaVersion") != "cross-project-slot-cad-validation-plan/v1":
        raise CrossProjectSlotReleaseError("验证计划版本不受支持。")
    if cad_result.get("schemaVersion") != "context-incremental-insert-run/v1":
        raise CrossProjectSlotReleaseError("真实CAD结果版本不受支持。")

    tool = cad_result.get("toolResult") or {}
    mate_results = tool.get("MateResults") or []
    verifications = tool.get("MateVerifications") or []
    plan_sources = validation_plan.get("sourceModuleSha256") or {}
    checks = {
        "candidateMatchesPlan": candidate.get("candidatePortDigest")
        == validation_plan.get("candidatePortDigest"),
        "candidateWasUnpublished": candidate.get("decision", {}).get(
            "semanticPortPublished"
        )
        is False,
        "planUsedNoCaseAnchor": validation_plan.get("caseAnchorUsed") is False,
        "planUsedNoPrototypeTargetPose": validation_plan.get(
            "prototypeTopLevelTargetPoseUsed"
        )
        is False,
        "collisionWasNotAReleaseClaim": validation_plan.get("acceptance", {}).get(
            "collisionOrBrepInScope"
        )
        is False,
        "effectiveGraphSemanticDigestMatches": _digest(effective_graph)
        == validation_plan.get("effectiveMateGraphDigest"),
        "effectiveGraphFileDigestMatchesCadRun": str(
            effective_graph_file_sha256
        ).lower()
        == str(cad_result.get("effectiveGraphSha256") or "").lower(),
        "baseWrapperDigestMatches": str(
            validation_plan.get("baseWrapperSha256") or ""
        ).lower()
        == str(cad_result.get("sourceAssemblySha256") or "").lower(),
        "sourceA600Unchanged": str(current_source_sha256.get("A600") or "").lower()
        == str(plan_sources.get("A600") or "").lower(),
        "sourceAH00Unchanged": str(current_source_sha256.get("AH00") or "").lower()
        == str(plan_sources.get("AH00") or "").lower(),
        "cadRunSucceeded": cad_result.get("success") is True
        and tool.get("Success") is True,
        "independentTargetInserted": tool.get("IndependentComponentInserted")
        is True,
        "targetWasNotCaseAnchored": tool.get("TargetCaseAnchored") is False,
        "noLeafPoseAnchorsRequestedOrApplied": int(
            tool.get("RequestedTargetLeafPoseAnchorCount") or 0
        )
        == 0
        and int(tool.get("AppliedTargetLeafPoseAnchorCount") or 0) == 0,
        "threeOfThreeMatesCreated": int(tool.get("RequestedMateCount") or 0)
        == 3
        and int(tool.get("CreatedMateCount") or 0) == 3,
        "allMateCreatesPassed": len(mate_results) == 3
        and all(
            row.get("Success") is True
            and row.get("ErrorName") == "swAddMateError_NoError"
            for row in mate_results
        ),
        "allEndpointsUsedPersistentReferences": len(mate_results) == 3
        and all(
            len(row.get("EndpointResolutionStrategies") or []) == 2
            and all(
                "SourceAssemblyPersistentReference" in str(strategy)
                for strategy in row.get("EndpointResolutionStrategies") or []
            )
            for row in mate_results
        ),
        "targetFullyConstrained": tool.get("TargetFullyConstrained") is True
        and tool.get("TargetConstraintStateAccepted") is True,
        "mateSolveClean": tool.get("MateSolveClean") is True,
        "componentSemanticsMatch": tool.get("ComponentSemanticsMatch") is True,
        "saveCloseReopenPassed": tool.get("Reopened") is True
        and tool.get("ReopenedMateParametersMatch") is True,
        "allReopenedMateChecksPassed": len(verifications) == 3
        and all(
            row.get("Found") is True
            and row.get("TypeMatches") is True
            and row.get("AlignmentMatches") is True
            and row.get("DistanceMatches") is True
            and row.get("AngleMatches") is True
            and row.get("AdvancedOptionsMatch") is True
            for row in verifications
        ),
        "outputAssemblyDigestCaptured": len(str(output_assembly_sha256)) == 64,
        "outputAssemblyPathMatches": str(cad_result.get("outputAssemblyPath") or "")
        == str(output_assembly_path),
    }
    _require(checks)

    a600_port = copy.deepcopy(candidate["candidatePort"])
    a600_port.update(
        {
            "projectId": "project02",
            "status": "confirmed",
            "portable": True,
            "portabilityReasons": [],
            "validationStatus": "real-cad-confirmed-cross-project",
            "evidence": [
                "A600候选槽位三个端点均由持久引用恢复。",
                "Project03 AH00从确定性非原型初始位姿独立插入，3/3配合创建并完全约束。",
                "结果已保存、关闭、重开并复核全部配合参数。",
            ],
        }
    )
    # The large targeted scan is reduced to the six endpoints actually needed
    # by the released relation.  A600 token normalization is intentional: the
    # targeted leaf scan used the CAD occurrence name while the profile alias
    # and semantic port use the stable module token A600.
    a600_index = _endpoint_index(a600_face_catalog)
    a600_entries = []
    for binding in a600_port.get("endpointBindings") or []:
        endpoint_id = str(binding.get("endpointId") or "")
        if endpoint_id not in a600_index:
            raise CrossProjectSlotReleaseError(
                f"A600发布端点不在面目录中：{endpoint_id}。"
            )
        row = copy.deepcopy(a600_index[endpoint_id])
        row["Endpoint"]["ModuleToken"] = "A600"
        row["Endpoint"]["ModuleHierarchyPath"] = a600_port[
            "moduleHierarchyPath"
        ]
        a600_entries.append(row)

    ah00_port = _single_port(ah00_semantic_catalog, "AH00.frame_installation")
    ah00_port.update(
        {
            "projectId": "project03",
            "status": "confirmed",
            "validationStatus": "reused-by-cross-project-real-cad-validation",
        }
    )
    ah00_index = _endpoint_index(ah00_face_catalog)
    ah00_entries = []
    for binding in ah00_port.get("endpointBindings") or []:
        endpoint_id = str(binding.get("endpointId") or "")
        if endpoint_id not in ah00_index:
            raise CrossProjectSlotReleaseError(
                f"AH00发布端点不在面目录中：{endpoint_id}。"
            )
        ah00_entries.append(copy.deepcopy(ah00_index[endpoint_id]))

    endpoint_catalog = {
        "SchemaVersion": "solidworks-face-endpoint-catalog/v1",
        "SourceAssemblyPath": output_assembly_path,
        "CatalogMode": "cross-project-released-interface-endpoints-only",
        "EndpointCount": len(a600_entries) + len(ah00_entries),
        "Endpoints": [*a600_entries, *ah00_entries],
        "Diagnostics": [
            "Only the six endpoints used by the released A600/AH00 three-datum interface are included.",
            "A600 endpoint ModuleToken values were normalized from the scanned occurrence name to the profile token A600.",
        ],
    }
    mate_steps = [
        {
            "mateName": "A600_AH00_重合",
            "mateType": 0,
            "mateTypeName": "swMateCOINCIDENT",
            "alignment": 1,
            "alignmentName": "swMateAlignANTI_ALIGNED",
            "endpointRoleA": "support_plane",
            "endpointRoleB": "support_plane",
        },
        {
            "mateName": "A600_AH00_同心1",
            "mateType": 1,
            "mateTypeName": "swMateCONCENTRIC",
            "alignment": 0,
            "alignmentName": "swMateAlignALIGNED",
            "endpointRoleA": "locating_hole_1",
            "endpointRoleB": "locating_hole_1",
        },
        {
            "mateName": "A600_AH00_同心2",
            "mateType": 1,
            "mateTypeName": "swMateCONCENTRIC",
            "alignment": 0,
            "alignmentName": "swMateAlignALIGNED",
            "endpointRoleA": "locating_hole_2",
            "endpointRoleB": "locating_hole_2",
        },
    ]
    semantic_catalog = {
        "schemaVersion": "semantic-port-catalog/v1",
        "projectId": "project02",
        "catalogPurpose": (
            "Register the CAD-validated Project02 A600 alternate calibration "
            "slot and its cross-project Project03 AH00 driving relation."
        ),
        "endpointCatalogPath": endpoint_catalog_path,
        "effectiveMateGraphPath": effective_graph_path,
        "ports": [ah00_port, a600_port],
        "connectionTemplates": [
            {
                "templateId": LEGACY_TEMPLATE_ID,
                "purposes": ["installation", "cross_project_substitution"],
                "sideSemantics": ["operator_side"],
                "interfaceTypeA": "project03_calibration_frame_installation",
                "interfaceTypeB": "project03_calibration_frame_installation",
                "constraintEffect": {
                    "purpose": (
                        "Locate Project03 AH00 on the validated Project02 A600 "
                        "operation-side calibration slot."
                    ),
                    "fullyLocatesAddedComponent": True,
                    "expectedResidualDof": 0,
                    "drivingAuthorization": (
                        "real_cad_validated_nonprototype_initial_pose"
                    ),
                    "exactMateBundleRequired": True,
                },
                "mateSteps": mate_steps,
            }
        ],
        "validationEvidence": {
            "schemaVersion": SCHEMA,
            "path": validation_evidence_path,
            "checks": copy.deepcopy(checks),
            "outputAssemblySha256": str(output_assembly_sha256).lower(),
        },
        "releaseScope": {
            "semanticInstallationPortability": True,
            "collisionOrBrep": "not_evaluated",
            "productionReady": False,
        },
    }
    semantic_validation = validate_semantic_port_catalog(
        semantic_catalog, endpoint_catalog
    )
    closure = {
        "schemaVersion": SCHEMA,
        "status": "released_for_cross_project_semantic_installation",
        "productionReady": False,
        "checks": checks,
        "candidatePortDigest": candidate.get("candidatePortDigest"),
        "validationPlanDigest": validation_plan.get("planDigest"),
        "effectiveGraphSemanticDigest": _digest(effective_graph),
        "effectiveGraphFileSha256": str(effective_graph_file_sha256).lower(),
        "sourceModuleSha256Before": copy.deepcopy(plan_sources),
        "sourceModuleSha256After": {
            key: str(value).lower() for key, value in current_source_sha256.items()
        },
        "outputAssemblyPath": output_assembly_path,
        "outputAssemblySha256": str(output_assembly_sha256).lower(),
        "cadDurationSeconds": cad_result.get("durationSeconds"),
        "phaseDurationsSeconds": copy.deepcopy(
            tool.get("PhaseDurationsSeconds") or {}
        ),
        "semanticCatalogDigest": _digest(semantic_catalog),
        "endpointCatalogDigest": _digest(endpoint_catalog),
        "semanticValidation": semantic_validation,
        "publishedPortIds": [
            a600_port["portId"],
            ah00_port["portId"],
        ],
        "publishedTemplateId": LEGACY_TEMPLATE_ID,
        "scope": {
            "crossProjectSemanticInstallation": True,
            "nonPrototypeInitialPose": True,
            "saveCloseReopen": True,
            "collisionOrBrep": False,
        },
        "knownLimits": [
            "本发布证明语义安装关系可驱动AH00位姿，不证明实体无干涉。",
            "本发布不包含运动行程、维护空间或生产参数签认。",
        ],
    }
    closure["closureDigest"] = _digest(closure)
    return {
        "semanticCatalog": semantic_catalog,
        "endpointCatalog": endpoint_catalog,
        "closure": closure,
    }


def build_a600_ah00_driving_release_evidence(
    catalog: dict[str, Any], closure: dict[str, Any]
) -> dict[str, Any]:
    """Bind the validated slot closure to one global driving template."""

    if closure.get("schemaVersion") != SCHEMA or closure.get("status") != (
        "released_for_cross_project_semantic_installation"
    ):
        raise CrossProjectSlotReleaseError("跨项目槽位闭环尚未发布。")
    if not closure.get("checks") or not all(closure["checks"].values()):
        raise CrossProjectSlotReleaseError("跨项目槽位闭环存在未通过检查。")
    matches = [
        row
        for row in catalog.get("connectionTemplates") or []
        if row.get("legacyTemplateId") == LEGACY_TEMPLATE_ID
    ]
    if len(matches) != 1:
        raise CrossProjectSlotReleaseError(
            f"全局目录无法唯一定位模板：{LEGACY_TEMPLATE_ID}。"
        )
    template = matches[0]
    effect = template.get("constraintEffect") or {}
    port_ids = {
        *(template.get("candidatePortIdsA") or []),
        *(template.get("candidatePortIdsB") or []),
    }
    ports = {
        row.get("globalPortId"): row
        for row in catalog.get("semanticPorts") or []
        if row.get("globalPortId") in port_ids
    }
    module_ids = {row.get("moduleDefinitionId") for row in ports.values()}
    project_ids = {
        alias.get("projectId")
        for module in catalog.get("moduleDefinitions") or []
        if module.get("moduleDefinitionId") in module_ids
        for alias in module.get("projectAliases") or []
    }
    compatibility = [
        row
        for row in catalog.get("compatibility") or []
        if row.get("globalTemplateId") == template.get("globalTemplateId")
        and row.get("portAId") in port_ids
        and row.get("portBId") in port_ids
    ]
    checks = {
        f"{LEGACY_TEMPLATE_ID}:drivesPlacement": effect.get(
            "fullyLocatesAddedComponent"
        )
        is True,
        f"{LEGACY_TEMPLATE_ID}:declaredClosed": int(
            effect.get("expectedResidualDof", -1)
        )
        == 0,
        f"{LEGACY_TEMPLATE_ID}:crossProjectPortOwnership": project_ids
        == {"project02", "project03"},
        f"{LEGACY_TEMPLATE_ID}:allCandidatePortsPortable": len(ports) == 2
        and all(row.get("portable") is True for row in ports.values()),
        f"{LEGACY_TEMPLATE_ID}:compatibilityPublished": bool(compatibility)
        and all(row.get("portableForTemplate") is True for row in compatibility),
        f"{LEGACY_TEMPLATE_ID}:liveCadPassed": all(
            closure.get("checks", {}).values()
        ),
        f"{LEGACY_TEMPLATE_ID}:nonPrototypeInitialPose": closure.get(
            "scope", {}
        ).get("nonPrototypeInitialPose")
        is True,
    }
    _require(checks)
    global_id = str(template.get("globalTemplateId") or "")
    return {
        "schemaVersion": "generic-driving-candidate-evidence/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": "ready",
        "projectId": "project02",
        "drivingScope": "project02_A600_with_project03_AH00_cross_project_slot",
        "outputCatalogDigest": catalog.get("catalogDigest"),
        "authorizedDrivingTemplateIds": [global_id],
        "authorizedTemplateCombinationIds": [],
        "checks": checks,
        "derivations": [
            {
                "entry": {
                    "mode": "register_cross_project_driving_bundle",
                    "sourceProjectId": "project03",
                    "targetProjectId": "project02",
                    "legacyTemplateId": LEGACY_TEMPLATE_ID,
                },
                "result": {
                    "derivedGlobalTemplateId": global_id,
                    "drivingScope": (
                        "project02_A600_with_project03_AH00_cross_project_slot"
                    ),
                },
            }
        ],
        "cadAssessment": {
            "schemaVersion": SCHEMA,
            "success": True,
            "checks": copy.deepcopy(closure["checks"]),
            "durationSeconds": closure.get("cadDurationSeconds"),
            "phaseDurationsSeconds": copy.deepcopy(
                closure.get("phaseDurationsSeconds") or {}
            ),
            "outputAssemblyPath": closure.get("outputAssemblyPath"),
            "outputAssemblySha256": closure.get("outputAssemblySha256"),
        },
        "solidWorksExecutedInThisPublish": False,
        "collisionStatus": "not_evaluated",
        "statement": (
            "发布Project02 A600操作面侧校准槽位与Project03 AH00的三基准跨项目安装束；"
            "已通过独立插入、非原型初始位姿、完全约束及保存重开复核。"
        ),
    }


def augment_release_catalog_with_cross_project_template(
    base_catalog: dict[str, Any],
    slot_catalog: dict[str, Any],
    *,
    legacy_template_id: str,
    require_bidirectional_compatibility: bool = False,
) -> dict[str, Any]:
    """Add one validated cross-project relation to an existing release lineage.

    The helper deliberately performs a thin evidence merge.  It does not
    rebuild the global catalog or infer new ports: only the selected template,
    its two already registered portable ports, and its compatibility rows are
    admitted.  This keeps the Project02 A600/AH00 and Project01 JJ00/AE00
    release paths on the same code path instead of hard-coding one module pair.
    """

    validate_global_module_catalog(base_catalog)
    validate_global_module_catalog(slot_catalog)
    result = copy.deepcopy(base_catalog)
    template_matches = [
        row
        for row in slot_catalog.get("connectionTemplates") or []
        if row.get("legacyTemplateId") == legacy_template_id
    ]
    if len(template_matches) != 1:
        raise CrossProjectSlotReleaseError(
            f"槽位目录无法唯一定位模板：{legacy_template_id}。"
        )
    template = copy.deepcopy(template_matches[0])
    referenced_port_ids = {
        *(template.get("candidatePortIdsA") or []),
        *(template.get("candidatePortIdsB") or []),
    }
    slot_ports = {
        row.get("globalPortId"): row
        for row in slot_catalog.get("semanticPorts") or []
        if row.get("globalPortId") in referenced_port_ids
    }
    if len(slot_ports) != 2 or not all(
        row.get("portable") is True for row in slot_ports.values()
    ):
        raise CrossProjectSlotReleaseError("跨项目模板必须恰好引用两个可移植端口。")

    result_ports = {
        row.get("globalPortId"): row for row in result.get("semanticPorts") or []
    }
    for port_id, port in slot_ports.items():
        if port_id not in result_ports:
            result.setdefault("semanticPorts", []).append(copy.deepcopy(port))
            result_ports[port_id] = result["semanticPorts"][-1]
        definition_id = port.get("moduleDefinitionId")
        definitions = [
            row
            for row in result.get("moduleDefinitions") or []
            if row.get("moduleDefinitionId") == definition_id
        ]
        if len(definitions) != 1:
            raise CrossProjectSlotReleaseError(
                f"发布基线缺少端口所属模组：{definition_id}。"
            )
        if port_id not in definitions[0].setdefault("portIds", []):
            definitions[0]["portIds"].append(port_id)
            definitions[0]["portIds"].sort()

    existing_templates = {
        row.get("globalTemplateId")
        for row in result.get("connectionTemplates") or []
    }
    if template.get("globalTemplateId") not in existing_templates:
        result.setdefault("connectionTemplates", []).append(template)
    result["connectionTemplates"] = sorted(
        result.get("connectionTemplates") or [],
        key=lambda row: str(row.get("globalTemplateId") or ""),
    )

    compatibility_ids = {
        (
            row.get("portAId"),
            row.get("portBId"),
            row.get("globalTemplateId"),
        )
        for row in result.get("compatibility") or []
    }
    slot_compatibility = [
        row
        for row in slot_catalog.get("compatibility") or []
        if row.get("globalTemplateId") == template.get("globalTemplateId")
        and row.get("portAId") in referenced_port_ids
        and row.get("portBId") in referenced_port_ids
    ]
    minimum_compatibility_count = 2 if require_bidirectional_compatibility else 1
    if len(slot_compatibility) < minimum_compatibility_count or not all(
        row.get("portableForTemplate") is True for row in slot_compatibility
    ):
        direction = "双向" if require_bidirectional_compatibility else "有效"
        raise CrossProjectSlotReleaseError(
            f"跨项目模板缺少{direction}可移植兼容记录。"
        )
    for row in slot_compatibility:
        identity = (
            row.get("portAId"),
            row.get("portBId"),
            row.get("globalTemplateId"),
        )
        if identity not in compatibility_ids:
            result.setdefault("compatibility", []).append(copy.deepcopy(row))
            compatibility_ids.add(identity)
    result["compatibility"] = sorted(
        result.get("compatibility") or [],
        key=lambda row: (
            str(row.get("portAId") or ""),
            str(row.get("portBId") or ""),
            str(row.get("globalTemplateId") or ""),
        ),
    )

    provenance = template.get("provenance") or {}
    source_paths = {
        str(provenance.get("semanticCatalogPath") or ""),
        str((provenance.get("sideAProvenance") or {}).get("semanticCatalogPath") or ""),
        str((provenance.get("sideBProvenance") or {}).get("semanticCatalogPath") or ""),
    }
    source_paths.discard("")
    slot_sources = [
        row
        for row in slot_catalog.get("sourceCatalogs") or []
        if row.get("path") in source_paths
    ]
    existing_source_paths = {
        row.get("path") for row in result.get("sourceCatalogs") or []
    }
    for row in slot_sources:
        if row.get("path") not in existing_source_paths:
            result.setdefault("sourceCatalogs", []).append(copy.deepcopy(row))
            existing_source_paths.add(row.get("path"))
    result["sourceCatalogs"] = sorted(
        result.get("sourceCatalogs") or [],
        key=lambda row: str(row.get("path") or ""),
    )

    result["semanticPorts"] = sorted(
        result.get("semanticPorts") or [],
        key=lambda row: str(row.get("globalPortId") or ""),
    )
    result["summary"] = {
        **(result.get("summary") or {}),
        "moduleDefinitionCount": len(result.get("moduleDefinitions") or []),
        "semanticPortCount": len(result.get("semanticPorts") or []),
        "portablePortCount": sum(
            row.get("portable") is True for row in result.get("semanticPorts") or []
        ),
        "connectionTemplateCount": len(result.get("connectionTemplates") or []),
        "templateCombinationCount": len(result.get("templateCombinations") or []),
        "compatibilityCount": len(result.get("compatibility") or []),
        "blockerCount": len(result.get("blockers") or []),
    }
    result.pop("catalogDigest", None)
    result["catalogDigest"] = _digest(result)
    validate_global_module_catalog(result)
    return result


def augment_project02_release_catalog_with_a600_ah00_slot(
    base_catalog: dict[str, Any], slot_catalog: dict[str, Any]
) -> dict[str, Any]:
    """Add the validated A600/AH00 slot to the Project02 release lineage."""

    return augment_release_catalog_with_cross_project_template(
        base_catalog,
        slot_catalog,
        legacy_template_id=LEGACY_TEMPLATE_ID,
        require_bidirectional_compatibility=True,
    )


def build_jj00_ae00_transport_release_evidence(
    catalog: dict[str, Any],
    cad_result: dict[str, Any],
) -> dict[str, Any]:
    """Bind the reviewed JJ00/AE00 transport slot to its existing live CAD proof."""

    validate_global_module_catalog(catalog)
    templates = [
        row
        for row in catalog.get("connectionTemplates") or []
        if row.get("legacyTemplateId") == TRANSPORT_LEGACY_TEMPLATE_ID
    ]
    if len(templates) != 1:
        raise CrossProjectSlotReleaseError(
            f"全局目录无法唯一定位模板：{TRANSPORT_LEGACY_TEMPLATE_ID}。"
        )
    template = templates[0]
    template_id = str(template.get("globalTemplateId") or "")
    effect = template.get("constraintEffect") or {}
    port_ids = {
        *(template.get("candidatePortIdsA") or []),
        *(template.get("candidatePortIdsB") or []),
    }
    ports = {
        row.get("globalPortId"): row
        for row in catalog.get("semanticPorts") or []
        if row.get("globalPortId") in port_ids
    }
    module_ids = {row.get("moduleDefinitionId") for row in ports.values()}
    project_ids = {
        alias.get("projectId")
        for module in catalog.get("moduleDefinitions") or []
        if module.get("moduleDefinitionId") in module_ids
        for alias in module.get("projectAliases") or []
    }
    compatibility = [
        row
        for row in catalog.get("compatibility") or []
        if row.get("globalTemplateId") == template_id
        and row.get("portAId") in port_ids
        and row.get("portBId") in port_ids
    ]
    tool = cad_result.get("toolResult") or {}
    mate_results = tool.get("MateResults") or []
    verifications = tool.get("MateVerifications") or []
    checks = {
        "templateDrivesPlacement": effect.get("fullyLocatesAddedComponent") is True,
        "templateDeclaresZeroResidualDof": int(
            effect.get("expectedResidualDof", -1)
        )
        == 0,
        "crossProjectPortOwnership": project_ids == {"project01", "project03"},
        "twoPortablePorts": len(ports) == 2
        and all(row.get("portable") is True for row in ports.values()),
        "portableCompatibilityPublished": bool(compatibility)
        and all(row.get("portableForTemplate") is True for row in compatibility),
        "checkpointCadRunPassed": cad_result.get("success") is True
        and cad_result.get("schemaVersion")
        == "checkpoint-selected-face-context-insert-run/v1"
        and tool.get("Success") is True,
        "independentNonAnchoredInsertion": tool.get("OriginalComponentRemoved") is True
        and tool.get("IndependentComponentInserted") is True
        and tool.get("TargetCaseAnchored") is False,
        "threeOfThreeMatesCreated": int(tool.get("RequestedMateCount") or 0) == 3
        and int(tool.get("CreatedMateCount") or 0) == 3
        and len(mate_results) == 3
        and all(row.get("Success") is True for row in mate_results),
        "targetFullyLocatedAndSolveClean": tool.get("TargetFullyConstrained") is True
        and tool.get("TargetConstraintStateAccepted") is True
        and tool.get("MateSolveClean") is True,
        "saveCloseReopenPassed": tool.get("Reopened") is True
        and tool.get("ReopenedMateParametersMatch") is True
        and len(verifications) == 3
        and all(
            row.get("Found") is True
            and row.get("TypeMatches") is True
            and row.get("AlignmentMatches") is True
            and row.get("DistanceMatches") is True
            and row.get("AngleMatches") is True
            and row.get("AdvancedOptionsMatch") is True
            for row in verifications
        ),
        "sourceAndSessionPreserved": cad_result.get("sourceAssemblyUnchanged") is True
        and cad_result.get("outputClosedAfterVerification") is True
        and cad_result.get("targetSourceSessionClean") is True,
        "collisionNotClaimed": True,
    }
    _require(checks)
    return {
        "schemaVersion": "generic-driving-candidate-evidence/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": "ready",
        "projectId": "project01",
        "drivingScope": "project01_JJ00_with_project03_AE00_transport_slot",
        "outputCatalogDigest": catalog.get("catalogDigest"),
        "authorizedDrivingTemplateIds": [template_id],
        "authorizedTemplateCombinationIds": [],
        "checks": checks,
        "derivations": [
            {
                "entry": {
                    "mode": "register_cross_project_driving_bundle",
                    "sourceProjectId": "project03",
                    "targetProjectId": "project01",
                    "legacyTemplateId": TRANSPORT_LEGACY_TEMPLATE_ID,
                },
                "result": {
                    "derivedGlobalTemplateId": template_id,
                    "drivingScope": (
                        "project01_JJ00_with_project03_AE00_transport_slot"
                    ),
                },
            }
        ],
        "cadAssessment": {
            "schemaVersion": cad_result.get("schemaVersion"),
            "success": True,
            "checks": copy.deepcopy(checks),
            "durationSeconds": cad_result.get("durationSeconds"),
            "outputAssemblyPath": cad_result.get("outputAssemblyPath"),
            "outputAssemblySha256": cad_result.get("outputAssemblySha256"),
        },
        "solidWorksExecutedInThisPublish": False,
        "collisionStatus": "not_evaluated",
        "statement": (
            "发布Project01 JJ00传输安装位与Project03 AE00传输模组的三基准"
            "跨项目安装束；已有独立非锚定插入、完全约束及保存重开证据。"
        ),
    }


def build_cross_project_direct_release_evidence(
    catalog: dict[str, Any],
    cad_result: dict[str, Any],
    *,
    legacy_template_id: str,
    release_project_id: str,
    source_project_id: str,
    target_project_id: str,
    driving_scope: str,
    statement: str,
) -> dict[str, Any]:
    """Build release evidence for any reviewed two-port cross-project bundle."""

    validate_global_module_catalog(catalog)
    templates = [
        row
        for row in catalog.get("connectionTemplates") or []
        if row.get("legacyTemplateId") == legacy_template_id
    ]
    if len(templates) != 1:
        raise CrossProjectSlotReleaseError(
            f"全局目录无法唯一定位模板：{legacy_template_id}。"
        )
    template = templates[0]
    template_id = str(template.get("globalTemplateId") or "")
    effect = template.get("constraintEffect") or {}
    port_ids = {
        *(template.get("candidatePortIdsA") or []),
        *(template.get("candidatePortIdsB") or []),
    }
    ports = {
        row.get("globalPortId"): row
        for row in catalog.get("semanticPorts") or []
        if row.get("globalPortId") in port_ids
    }
    module_ids = {row.get("moduleDefinitionId") for row in ports.values()}
    project_ids = {
        str(alias.get("projectId") or "").lower()
        for module in catalog.get("moduleDefinitions") or []
        if module.get("moduleDefinitionId") in module_ids
        for alias in module.get("projectAliases") or []
        if str(alias.get("projectId") or "").strip()
    }
    compatibility = [
        row
        for row in catalog.get("compatibility") or []
        if row.get("globalTemplateId") == template_id
        and row.get("portAId") in port_ids
        and row.get("portBId") in port_ids
    ]
    tool = cad_result.get("toolResult") or {}
    mate_results = tool.get("MateResults") or []
    verifications = tool.get("MateVerifications") or []
    expected_projects = {
        source_project_id.strip().lower(),
        target_project_id.strip().lower(),
    }
    checks = {
        "templateDrivesPlacement": effect.get("fullyLocatesAddedComponent") is True,
        "templateDeclaresZeroResidualDof": int(
            effect.get("expectedResidualDof", -1)
        )
        == 0,
        "crossProjectPortOwnership": project_ids == expected_projects,
        "twoPortablePorts": len(ports) == 2
        and all(row.get("portable") is True for row in ports.values()),
        "portableCompatibilityPublished": bool(compatibility)
        and all(row.get("portableForTemplate") is True for row in compatibility),
        "checkpointCadRunPassed": cad_result.get("success") is True
        and cad_result.get("schemaVersion")
        == "checkpoint-selected-face-context-insert-run/v1"
        and tool.get("Success") is True,
        "independentNonAnchoredInsertion": tool.get("OriginalComponentRemoved")
        is True
        and tool.get("IndependentComponentInserted") is True
        and tool.get("TargetCaseAnchored") is False
        and int(tool.get("RequestedTargetLeafPoseAnchorCount") or 0) == 0
        and int(tool.get("AppliedTargetLeafPoseAnchorCount") or 0) == 0,
        "threeOfThreeMatesCreated": int(tool.get("RequestedMateCount") or 0) == 3
        and int(tool.get("CreatedMateCount") or 0) == 3
        and len(mate_results) == 3
        and all(row.get("Success") is True for row in mate_results),
        "targetFullyLocatedAndSolveClean": tool.get("TargetFullyConstrained")
        is True
        and tool.get("TargetConstraintStateAccepted") is True
        and tool.get("MateSolveClean") is True
        and tool.get("ComponentSemanticsMatch") is True,
        "saveCloseReopenPassed": tool.get("Reopened") is True
        and tool.get("ReopenedMateParametersMatch") is True
        and len(verifications) == 3
        and all(
            row.get("Found") is True
            and row.get("TypeMatches") is True
            and row.get("AlignmentMatches") is True
            and row.get("DistanceMatches") is True
            and row.get("AngleMatches") is True
            and row.get("AdvancedOptionsMatch") is True
            for row in verifications
        ),
        "sourceAndSessionPreserved": cad_result.get("sourceAssemblyUnchanged")
        is True
        and cad_result.get("outputClosedAfterVerification") is True
        and cad_result.get("targetSourceSessionClean") is True,
        "outputDigestCaptured": len(str(cad_result.get("outputAssemblySha256") or ""))
        == 64,
        "collisionNotClaimed": True,
    }
    _require(checks)
    return {
        "schemaVersion": "generic-driving-candidate-evidence/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": "ready",
        "projectId": release_project_id,
        "drivingScope": driving_scope,
        "outputCatalogDigest": catalog.get("catalogDigest"),
        "authorizedDrivingTemplateIds": [template_id],
        "authorizedTemplateCombinationIds": [],
        "checks": checks,
        "derivations": [
            {
                "entry": {
                    "mode": "register_cross_project_driving_bundle",
                    "sourceProjectId": source_project_id,
                    "targetProjectId": target_project_id,
                    "legacyTemplateId": legacy_template_id,
                },
                "result": {
                    "derivedGlobalTemplateId": template_id,
                    "drivingScope": driving_scope,
                },
            }
        ],
        "cadAssessment": {
            "schemaVersion": cad_result.get("schemaVersion"),
            "success": True,
            "checks": copy.deepcopy(checks),
            "durationSeconds": cad_result.get("durationSeconds"),
            "outputAssemblyPath": cad_result.get("outputAssemblyPath"),
            "outputAssemblySha256": cad_result.get("outputAssemblySha256"),
        },
        "solidWorksExecutedInThisPublish": False,
        "collisionStatus": "not_evaluated",
        "statement": statement,
    }


def augment_a600_ah00_template_with_operation_side_semantics(
    catalog: dict[str, Any],
) -> dict[str, Any]:
    """Declare the already validated A600 slot as an operator-side slot.

    The CAD relation, endpoints and template identity are deliberately left
    unchanged.  This only adds the bounded natural-language qualifier that is
    already evidenced by the released A600 port alias and the slot acquisition
    record.  A caller must publish the returned catalog as a new immutable
    release; historical releases are never edited in place.
    """

    validate_global_module_catalog(catalog)
    result = copy.deepcopy(catalog)
    templates = [
        row
        for row in result.get("connectionTemplates") or []
        if row.get("legacyTemplateId") == LEGACY_TEMPLATE_ID
    ]
    if len(templates) != 1:
        raise CrossProjectSlotReleaseError(
            f"全局目录无法唯一定位模板：{LEGACY_TEMPLATE_ID}。"
        )
    template = templates[0]
    referenced_port_ids = {
        *(template.get("candidatePortIdsA") or []),
        *(template.get("candidatePortIdsB") or []),
    }
    referenced_ports = [
        row
        for row in result.get("semanticPorts") or []
        if row.get("globalPortId") in referenced_port_ids
    ]
    operation_side_ports = [
        row
        for row in referenced_ports
        if any(
            str(alias).casefold().endswith("operation_side")
            for alias in row.get("aliases") or []
        )
    ]
    if len(referenced_ports) != 2 or len(operation_side_ports) != 1:
        raise CrossProjectSlotReleaseError(
            "A600/AH00模板没有唯一的operation_side槽位证据。"
        )
    side_semantics = {
        str(value).strip()
        for value in template.get("sideSemantics") or []
        if str(value).strip()
    }
    unsupported = side_semantics - {"operator_side"}
    if unsupported:
        raise CrossProjectSlotReleaseError(
            "模板已有冲突的方位语义：" + ", ".join(sorted(unsupported))
        )
    template["sideSemantics"] = ["operator_side"]
    provenance = template.setdefault("provenance", {})
    provenance["naturalLanguageSideSemantics"] = {
        "qualifier": "operator_side",
        "authority": "released_slot_alias_and_geometry_acquisition",
        "targetSlotPortId": operation_side_ports[0]["globalPortId"],
        "changesMateGeometry": False,
    }
    result.pop("catalogDigest", None)
    result["catalogDigest"] = _digest(result)
    validate_global_module_catalog(result)
    return result


def build_a600_ah00_operation_side_release_evidence(
    catalog: dict[str, Any],
    *,
    source_catalog: dict[str, Any],
    source_manifest: dict[str, Any],
    closure: dict[str, Any],
) -> dict[str, Any]:
    """Bind the natural-language qualifier to the existing live CAD proof."""

    validate_global_module_catalog(catalog)
    validate_global_module_catalog(source_catalog)
    templates = [
        row
        for row in catalog.get("connectionTemplates") or []
        if row.get("legacyTemplateId") == LEGACY_TEMPLATE_ID
    ]
    source_templates = [
        row
        for row in source_catalog.get("connectionTemplates") or []
        if row.get("legacyTemplateId") == LEGACY_TEMPLATE_ID
    ]
    if len(templates) != 1 or len(source_templates) != 1:
        raise CrossProjectSlotReleaseError("A600/AH00模板证据不唯一。")
    template = templates[0]
    source_template = source_templates[0]
    template_id = str(template.get("globalTemplateId") or "")
    source_scope = source_manifest.get("scope") or {}
    checks = {
        "sourceReleaseCatalogMatches": source_manifest.get("catalogDigest")
        == source_catalog.get("catalogDigest"),
        "sourceReleaseAuthorizedTemplate": template_id
        in set(source_scope.get("authorizedDrivingTemplateIds") or []),
        "templateIdentityUnchanged": template_id
        == source_template.get("globalTemplateId"),
        "mateBundleUnchanged": template.get("mateSteps")
        == source_template.get("mateSteps"),
        "candidatePortsUnchanged": {
            *(template.get("candidatePortIdsA") or []),
            *(template.get("candidatePortIdsB") or []),
        }
        == {
            *(source_template.get("candidatePortIdsA") or []),
            *(source_template.get("candidatePortIdsB") or []),
        },
        "operationSideDeclared": template.get("sideSemantics")
        == ["operator_side"],
        "operationSideDoesNotChangeGeometry": (
            (template.get("provenance") or {})
            .get("naturalLanguageSideSemantics", {})
            .get("changesMateGeometry")
            is False
        ),
        "liveCadClosureStillPassed": bool(closure.get("checks"))
        and all(closure["checks"].values()),
        "collisionNotClaimed": closure.get("scope", {}).get("collisionOrBrep")
        is False,
    }
    _require(checks)
    return {
        "schemaVersion": "generic-driving-candidate-evidence/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": "ready",
        "projectId": "project02",
        "drivingScope": (
            "project02_A600_project03_AH00_operator_side_natural_language"
        ),
        "outputCatalogDigest": catalog["catalogDigest"],
        "authorizedDrivingTemplateIds": [template_id],
        "authorizedTemplateCombinationIds": [],
        "checks": checks,
        "derivations": [
            {
                "entry": {
                    "mode": "add_bounded_natural_language_side_semantics",
                    "sourceReleaseId": source_manifest.get("releaseId"),
                    "legacyTemplateId": LEGACY_TEMPLATE_ID,
                    "sideQualifier": "operator_side",
                },
                "result": {
                    "derivedGlobalTemplateId": template_id,
                    "drivingScope": (
                        "project02_A600_project03_AH00_operator_side_natural_language"
                    ),
                },
            }
        ],
        "cadAssessment": {
            "schemaVersion": SCHEMA,
            "success": True,
            "checks": copy.deepcopy(closure["checks"]),
            "durationSeconds": closure.get("cadDurationSeconds"),
            "phaseDurationsSeconds": copy.deepcopy(
                closure.get("phaseDurationsSeconds") or {}
            ),
            "outputAssemblyPath": closure.get("outputAssemblyPath"),
            "outputAssemblySha256": closure.get("outputAssemblySha256"),
        },
        "solidWorksExecutedInThisPublish": False,
        "collisionStatus": "not_evaluated",
        "statement": (
            "在不改变端点或三配合几何的前提下，为已验证A600备用校准槽位"
            "补充operator_side自然语言方位语义。"
        ),
    }
