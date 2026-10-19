"""Compile the unpublished A600/AH00 slot candidate into a CAD validation graph."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA = "cross-project-slot-cad-validation-plan/v1"
IDENTITY_TRANSFORM = [
    1.0,
    0.0,
    0.0,
    0.0,
    1.0,
    0.0,
    0.0,
    0.0,
    1.0,
    0.0,
    0.0,
    0.0,
    1.0,
    0.0,
    0.0,
    0.0,
]


class CrossProjectSlotCadValidationError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _endpoint_index(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if catalog.get("SchemaVersion") != "solidworks-face-endpoint-catalog/v1":
        raise CrossProjectSlotCadValidationError("不支持的面端点目录版本。")
    return {
        str(row.get("EndpointId") or ""): row
        for row in catalog.get("Endpoints") or []
    }


def _port(catalog: dict[str, Any], port_id: str) -> dict[str, Any]:
    matches = [
        row for row in catalog.get("ports") or [] if row.get("portId") == port_id
    ]
    if len(matches) != 1:
        raise CrossProjectSlotCadValidationError(
            f"无法唯一定位语义端口：{port_id}。"
        )
    return matches[0]


def _bindings(port: dict[str, Any]) -> dict[str, str]:
    result = {
        str(row.get("role") or ""): str(row.get("endpointId") or "")
        for row in port.get("endpointBindings") or []
    }
    required = {"support_plane", "locating_hole_1", "locating_hole_2"}
    if set(result) != required or any(not value for value in result.values()):
        raise CrossProjectSlotCadValidationError("安装端口必须恰好包含三项定位角色。")
    return result


def _graph_endpoint(
    row: dict[str, Any],
    *,
    index: int,
    module_token: str,
    module_hierarchy_path: str,
) -> dict[str, Any]:
    endpoint = copy.deepcopy(row.get("Endpoint") or {})
    relative = str(endpoint.get("RelativeLeafHierarchyPath") or "")
    if not relative:
        raise CrossProjectSlotCadValidationError("端点缺少叶零件相对层级路径。")
    endpoint.update(
        {
            "Index": index,
            "ModuleToken": module_token,
            "ModuleHierarchyPath": module_hierarchy_path,
            "LeafHierarchyPath": f"{module_hierarchy_path}/{relative}",
        }
    )
    return endpoint


def build_a600_ah00_candidate_validation_plan(
    *,
    acquisition_request: dict[str, Any],
    candidate_port: dict[str, Any],
    a600_face_catalog: dict[str, Any],
    ah00_semantic_catalog: dict[str, Any],
    ah00_face_catalog: dict[str, Any],
    base_wrapper_path: str | Path,
) -> dict[str, Any]:
    """Build a three-mate graph that is authorized only for candidate validation."""

    if candidate_port.get("schemaVersion") != "cross-project-slot-port-candidate/v1":
        raise CrossProjectSlotCadValidationError("不支持的候选端口版本。")
    if candidate_port.get("status") != "endpoint_recovered_pending_cross_project_cad":
        raise CrossProjectSlotCadValidationError("候选端口尚未完成全部端点恢复。")
    decision = candidate_port.get("decision") or {}
    if decision.get("cadExecutionAllowed") is not True or decision.get(
        "allowedCadScope"
    ) != "candidate-cross-project-validation-only":
        raise CrossProjectSlotCadValidationError("候选端口没有跨项目验证授权。")
    if acquisition_request.get("requestDigest") != candidate_port.get(
        "requestDigest"
    ):
        raise CrossProjectSlotCadValidationError("采集请求与候选端口摘要不匹配。")

    wrapper = Path(base_wrapper_path).resolve()
    if not wrapper.is_file():
        raise FileNotFoundError(wrapper)
    a600_source = Path(acquisition_request["targetBase"]["cadPath"]).resolve()
    ah00_source = Path(acquisition_request["sourceModule"]["cadPath"]).resolve()
    if not a600_source.is_file() or not ah00_source.is_file():
        raise FileNotFoundError("A600或AH00独立模组CAD文件不存在。")

    target_port = candidate_port["candidatePort"]
    target_bindings = _bindings(target_port)
    source_port = _port(ah00_semantic_catalog, "AH00.frame_installation")
    source_bindings = _bindings(source_port)
    if target_port.get("interfaceType") != source_port.get("interfaceType"):
        raise CrossProjectSlotCadValidationError("AH00与A600候选端口接口类型不一致。")
    a600_endpoints = _endpoint_index(a600_face_catalog)
    ah00_endpoints = _endpoint_index(ah00_face_catalog)

    base_token = "A600"
    base_hierarchy = "FL9A24D062A600.001-1"
    target_token = str(source_port["moduleToken"])
    target_hierarchy = str(source_port["moduleHierarchyPath"])
    mate_specs = [
        ("A600_AH00_重合", 0, "swMateCOINCIDENT", 1, "swMateAlignANTI_ALIGNED", "support_plane"),
        ("A600_AH00_同心1", 1, "swMateCONCENTRIC", 0, "swMateAlignALIGNED", "locating_hole_1"),
        ("A600_AH00_同心2", 1, "swMateCONCENTRIC", 0, "swMateAlignALIGNED", "locating_hole_2"),
    ]
    mates = []
    for name, mate_type, type_name, alignment, alignment_name, role in mate_specs:
        source_id = source_bindings[role]
        target_id = target_bindings[role]
        if source_id not in ah00_endpoints or target_id not in a600_endpoints:
            raise CrossProjectSlotCadValidationError(
                f"配合角色{role}的端点不能在目录中恢复。"
            )
        source_endpoint = _graph_endpoint(
            ah00_endpoints[source_id],
            index=0,
            module_token=target_token,
            module_hierarchy_path=target_hierarchy,
        )
        target_endpoint = _graph_endpoint(
            a600_endpoints[target_id],
            index=1,
            module_token=base_token,
            module_hierarchy_path=base_hierarchy,
        )
        mates.append(
            {
                "MateName": name,
                "MateType": mate_type,
                "MateTypeName": type_name,
                "Alignment": alignment,
                "AlignmentName": alignment_name,
                "Distance": None,
                "Angle": None,
                "IsSuppressed": False,
                "Endpoints": [source_endpoint, target_endpoint],
                "ModuleTokens": [target_token, base_token],
                "ModuleHierarchyPaths": [target_hierarchy, base_hierarchy],
                "IsBasicTwoFaceRebuildable": True,
                "RebuildRejectionReason": None,
                "MateId": f"mate:a600-ah00-candidate:{role}",
            }
        )

    graph = {
        "SchemaVersion": "editable-module-mate-graph/v1",
        "SourceAssemblyPath": str(wrapper),
        "ModuleCount": 2,
        "InterModuleMateCount": 3,
        "Modules": [
            {
                "ModuleToken": base_token,
                "Name": base_hierarchy,
                "Path": str(a600_source),
                "HierarchyPath": base_hierarchy,
                "SourceTransform": list(IDENTITY_TRANSFORM),
                "IsSuppressed": False,
                "SuppressionState": 2,
                "SuppressionStateName": "swComponentFullyResolved",
                "VisibilityState": 1,
                "SolvingState": 0,
                "SolvingStateName": "swComponentRigidSolving",
            },
            {
                "ModuleToken": target_token,
                "Name": target_hierarchy,
                "Path": str(ah00_source),
                "HierarchyPath": target_hierarchy,
                # This pose is intentionally not used as an anchor.  The CAD
                # adapter starts the inserted module from its own deterministic
                # non-source pose and lets the three mates locate it.
                "SourceTransform": list(IDENTITY_TRANSFORM),
                "IsSuppressed": False,
                "SuppressionState": 2,
                "SuppressionStateName": "swComponentFullyResolved",
                "VisibilityState": 1,
                "SolvingState": 0,
                "SolvingStateName": "swComponentRigidSolving",
            },
        ],
        "Mates": mates,
        "EditPolicy": {
            "baseModuleToken": base_token,
            "initialPlacementMode": "deterministic",
            "sourceGraphImmutable": True,
            "fixedModuleTokens": [base_token],
            "caseAnchoredModuleTokens": [],
            "targetLeafPoseAnchors": [],
            "sourceMateNamesToSuppress": [],
        },
        "SemanticAssemblyPlanAudit": {
            "planId": "project02-a600-project03-ah00-candidate-validation-v1",
            "addedComponentHierarchyPath": target_hierarchy,
            "generatedMateNames": [row["MateName"] for row in mates],
            "validationRelations": [],
            "executionMode": "candidate_cross_project_validation",
            "constraintAssessment": {
                "authority": "released-ah00-three-datum-template-plus-measured-a600-50mm-slot",
                "fullyLocatesAddedComponent": True,
                "expectedResidualDof": 0,
                "caseAnchoredModuleTokens": [],
            },
        },
        "BaseGraphPolicy": {
            "moduleTokens": [base_token],
            "source": "verified-a600-base-wrapper",
        },
        "CandidateValidationPolicy": {
            "semanticPortPublished": False,
            "collisionOrBrepRequired": False,
            "requiredCadChecks": [
                "independent target inserted from deterministic non-source pose",
                "three of three mates created without solver error",
                "target fully constrained",
                "save-close-reopen parameters match",
                "source A600 and AH00 files unchanged",
            ],
        },
    }
    graph_digest = _digest(graph)
    plan_core = {
        "schemaVersion": SCHEMA,
        "status": "ready_for_candidate_cad_validation",
        "candidatePortDigest": candidate_port.get("candidatePortDigest"),
        "baseWrapperPath": str(wrapper),
        "baseWrapperSha256": hashlib.sha256(wrapper.read_bytes()).hexdigest(),
        "sourceModulePaths": {
            "A600": str(a600_source),
            "AH00": str(ah00_source),
        },
        "sourceModuleSha256": {
            "A600": hashlib.sha256(a600_source.read_bytes()).hexdigest(),
            "AH00": hashlib.sha256(ah00_source.read_bytes()).hexdigest(),
        },
        "targetModuleToken": target_token,
        "mateCount": len(mates),
        "caseAnchorUsed": False,
        "prototypeTopLevelTargetPoseUsed": False,
        "effectiveMateGraph": graph,
        "effectiveMateGraphDigest": graph_digest,
        "acceptance": {
            "semanticPortPublishedBeforeRun": False,
            "collisionOrBrepInScope": False,
            "publishPortOnlyAfterCadPass": True,
        },
    }
    return {**plan_core, "planDigest": _digest(plan_core)}
