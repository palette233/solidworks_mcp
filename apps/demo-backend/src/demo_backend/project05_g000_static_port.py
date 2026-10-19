"""Build the Project05 G000 static four-relation installation candidate.

The source assembly contains a coincident, parallel, dormant distance and Free
slot relation.  The first migration omitted the slot because the v1 executor
could not reconstruct advanced slot options.  Current execution supports the
source ``SlotConstraint=Free`` option, so the real relation can be restored
without a case or leaf pose anchor.
"""

from __future__ import annotations

import copy
from typing import Any


class Project05G000StaticPortError(ValueError):
    pass


_NAMES = {
    0: "重合14",
    3: "平行4",
    5: "距离2",
    21: "槽口1",
}


def _reference(endpoint: dict[str, Any]) -> str:
    return str(endpoint.get("SourceAssemblyPersistentReferenceBase64") or "")


def _endpoint_id(catalog: dict[str, Any], endpoint: dict[str, Any]) -> str:
    reference = _reference(endpoint)
    matches = [
        str(row.get("EndpointId") or "")
        for row in catalog.get("Endpoints") or []
        if _reference(row.get("Endpoint") or {}) == reference
    ]
    if len(matches) != 1 or not matches[0]:
        raise Project05G000StaticPortError(
            f"G000/A000源配合端点在目录中命中{len(matches)}项。"
        )
    return matches[0]


def _source_bundle(prototype_graph: dict[str, Any]) -> list[dict[str, Any]]:
    by_type: dict[int, dict[str, Any]] = {}
    for row in prototype_graph.get("Mates") or []:
        if {str(value).upper() for value in row.get("ModuleTokens") or []} != {
            "A000",
            "G000",
        }:
            continue
        mate_type = int(row.get("MateType", -1))
        if mate_type not in _NAMES:
            continue
        if mate_type in by_type:
            raise Project05G000StaticPortError(
                f"G000/A000的{row.get('MateTypeName')}源关系不唯一。"
            )
        mate = copy.deepcopy(row)
        mate["MateName"] = _NAMES[mate_type]
        mate["IsSuppressed"] = False
        by_type[mate_type] = mate
    missing = [value for value in _NAMES if value not in by_type]
    if missing:
        raise Project05G000StaticPortError(f"G000/A000缺少源关系类型：{missing}。")
    slot = by_type[21]
    advanced = slot.get("AdvancedOptions") or {}
    if int(advanced.get("SlotConstraint", -1)) != 0:
        raise Project05G000StaticPortError("槽口1必须保留源Free约束参数。")
    # Preserve the established three-relation order, then restore the slot.
    return [by_type[0], by_type[3], by_type[5], by_type[21]]


def build_g000_static_candidate(
    semantic: dict[str, Any],
    endpoint_catalog: dict[str, Any],
    effective_graph: dict[str, Any],
    prototype_graph: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    mates = _source_bundle(prototype_graph)
    candidate_endpoints = copy.deepcopy(endpoint_catalog)
    target_bindings: list[dict[str, str]] = []
    context_bindings: list[dict[str, str]] = []
    steps: list[dict[str, Any]] = []
    for mate in mates:
        counts = {"G000": 0, "A000": 0}
        roles: list[dict[str, str]] = []
        for endpoint in mate.get("Endpoints") or []:
            token = str(endpoint.get("ModuleToken") or "").upper()
            if token not in counts:
                raise Project05G000StaticPortError(
                    f"关系{mate['MateName']}出现范围外端点：{token}。"
                )
            counts[token] += 1
            side = "A" if token == "G000" else "B"
            role = (
                f"{mate['MateName']}_"
                f"{'target' if side == 'A' else 'context'}_{counts[token]}"
            )
            binding = {
                "role": role,
                "endpointId": _endpoint_id(candidate_endpoints, endpoint),
            }
            (target_bindings if side == "A" else context_bindings).append(binding)
            roles.append({"side": side, "role": role})
        if counts != {"G000": 1, "A000": 1}:
            raise Project05G000StaticPortError(
                f"关系{mate['MateName']}不是一对G000/A000端点。"
            )
        step: dict[str, Any] = {
            "mateName": mate["MateName"],
            "mateType": mate["MateType"],
            "mateTypeName": mate["MateTypeName"],
            "alignment": mate["Alignment"],
            "alignmentName": mate["AlignmentName"],
            "endpointRoles": roles,
        }
        if mate.get("Distance") is not None:
            step["distanceMeters"] = mate["Distance"]
        if mate.get("AdvancedOptions") is not None:
            step["advancedOptions"] = copy.deepcopy(mate["AdvancedOptions"])
        steps.append(step)

    candidate = copy.deepcopy(semantic)
    candidate["schemaVersion"] = "semantic-port-catalog/v2-candidate"
    candidate["catalogPurpose"] = (
        "Project05 G000 static demo installation: restore the source Free slot "
        "and use the source dormant distance as the static travel datum."
    )
    candidate["endpointCatalogPath"] = "face_endpoint_catalog.json"
    candidate["effectiveMateGraphPath"] = "assembly_plan_effective.json"
    candidate["drivingScope"] = {
        "status": "candidate_only_not_released",
        "allowedModuleTokens": ["A000", "G000"],
        "exactMateBundleRequired": True,
        "mateNames": [_NAMES[value] for value in (0, 3, 5, 21)],
        "caseAnchorAllowed": False,
        "targetLeafPoseAnchorAllowed": False,
        "parameterAuthority": "prototype_source_relation",
        "productionReady": False,
        "externalPlacementWitnessRequired": True,
    }
    by_token = {
        str(row.get("moduleToken") or "").upper(): row
        for row in candidate.get("ports") or []
    }
    by_token["G000"]["endpointBindings"] = target_bindings
    by_token["A000"]["endpointBindings"] = context_bindings
    by_token["G000"]["status"] = "candidate-static-demo"
    by_token["A000"]["status"] = "candidate-static-demo"
    template = copy.deepcopy((candidate.get("connectionTemplates") or [])[0])
    template["templateId"] = "G000_to_A000_static_four_relation_v2"
    template["constraintEffect"] = {
        "purpose": "Locate the external G000 root while preserving its source flexible solving state.",
        "fullyLocatesAddedComponent": True,
        "expectedResidualDof": 0,
        "residualDofPolicy": "source_free_slot_plus_source_dormant_distance_for_static_demo",
        "internalFlexibilityPreserved": True,
        "externalPlacementWitnessRequired": True,
        "parameterAuthority": "prototype_source_relation",
        "productionReady": False,
    }
    template["mateSteps"] = steps
    candidate["connectionTemplates"] = [template]
    candidate["readOnlySourceRelations"] = []
    candidate["upgradedSourceRelations"] = [
        {
            "mateName": "槽口1",
            "previousMode": "evidence_only",
            "candidateMode": "driving_as_part_of_exact_static_bundle",
            "reason": "当前执行器已支持源SlotConstraint=Free及稳定端点恢复。",
        },
        {
            "mateName": "距离2",
            "sourceSuppressed": True,
            "candidateMode": "driving_static_travel_datum",
            "distanceMeters": 0.482,
            "reason": "仅用于当前静态Demo封闭槽向行程；不宣称动态工位已验证。",
        },
    ]

    graph = copy.deepcopy(effective_graph)
    graph["Mates"] = mates
    graph["InterModuleMateCount"] = 4
    graph["MateBundleCount"] = 1
    graph["MateBundles"] = [
        {
            "FirstModuleToken": "A000",
            "SecondModuleToken": "G000",
            "MateCount": 4,
            "MateNames": [_NAMES[value] for value in (0, 3, 5, 21)],
            "MateTypes": [mates[index]["MateTypeName"] for index in range(4)],
            "HasPositionDimension": True,
            "HasCompoundPositioningMate": True,
            "HasOrientationRelation": True,
            "InstallationRelationAssessment": "STATIC_POSITION_AND_ORIENTATION_BUNDLE_CANDIDATE",
        }
    ]
    policy = graph.setdefault("EditPolicy", {})
    policy["baseModuleToken"] = "A000"
    policy["initialPlacementMode"] = "deterministic_non_source_pose"
    policy["fixedModuleTokens"] = ["A000"]
    policy["caseAnchoredModuleTokens"] = []
    policy["targetLeafPoseAnchors"] = []
    policy["sourceMateNamesToSuppress"] = []
    graph["SemanticAssemblyPlanAudit"] = {
        "planId": "project05-add-G000-static-four-relation-v2",
        "addedComponentHierarchyPath": "FL9C254098G000.001-1",
        "generatedMateNames": [_NAMES[value] for value in (0, 3, 5, 21)],
        "validationRelations": [],
        "executionMode": "nonprototype_static_external_placement",
        "constraintAssessment": template["constraintEffect"],
        "warnings": [
            "距离2在源原型中处于抑制状态；本候选只用于静态Demo封闭槽向位置。",
            "G000保持柔性，必须通过重开后的外部根位姿见证，不能只看完全约束状态。",
        ],
    }
    return candidate, graph
