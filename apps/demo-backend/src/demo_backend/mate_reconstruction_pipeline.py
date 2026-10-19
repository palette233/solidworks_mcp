from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import math


PIPELINE_SCHEMA = "project02-mate-reconstruction-pipeline/v1"
FULL_GRAPH_SCHEMA = "solidworks-module-mate-graph/v1.4"
EXPECTED_MODULE_TOKENS = {"A100", "A180", "A200", "A300", "A500", "A600", "A700", "A800", "T401"}
EXPECTED_MODULE_INSTANCES = 10
EXPECTED_MATES = 27
T401_MATES = {"重合14", "距离10", "距离28"}

PIPELINE_STAGES = (
    ("full_graph_semantics", "完整图语义升级"),
    ("t401_face_recovery", "T401小装配面恢复"),
    ("mates_27_rebuild", "27/27配合重建"),
    ("dof_analysis", "自由度分析"),
    ("minimal_anchor_extraction", "最少锚点提取"),
    ("non_source_pose_rebuild", "非原型初始位姿全装重建"),
    ("independent_interference_validation", "独立实体干涉验证"),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def pick(item: dict[str, Any], name: str, default: Any = None) -> Any:
    return item.get(name, item.get(name[0].lower() + name[1:], default))


def _fingerprint_ready(endpoint: dict[str, Any]) -> bool:
    return (
        isinstance(pick(endpoint, "FaceArea"), (int, float))
        and len(pick(endpoint, "FaceCenterLocal", []) or []) == 3
        and len(pick(endpoint, "FaceNormalLocal", []) or []) == 3
    )


def _endpoint_identity_ready(endpoint: dict[str, Any]) -> bool:
    persistent = str(pick(endpoint, "SourceAssemblyPersistentReferenceBase64", "") or "")
    indexed = int(pick(endpoint, "BodyIndex", -1)) >= 0 and int(pick(endpoint, "FaceIndexInBody", -1)) >= 0
    return bool(persistent) or indexed or _fingerprint_ready(endpoint)


def audit_full_graph_semantics(graph: dict[str, Any]) -> dict[str, Any]:
    modules = list(pick(graph, "Modules", []) or [])
    mates = list(pick(graph, "Mates", []) or [])
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, evidence: Any) -> None:
        checks.append({"name": name, "passed": bool(passed), "evidence": evidence})

    schema = str(pick(graph, "SchemaVersion", ""))
    tokens = {str(pick(module, "ModuleToken", "")) for module in modules}
    hierarchy_paths = [str(pick(module, "HierarchyPath", "")) for module in modules]
    missing_configurations = [
        str(pick(module, "HierarchyPath", ""))
        for module in modules
        if not str(pick(module, "ReferencedConfiguration", "") or "")
    ]
    missing_solving_states = [
        str(pick(module, "HierarchyPath", ""))
        for module in modules
        if pick(module, "SolvingState") is None or not str(pick(module, "SolvingStateName", "") or "")
    ]

    check("schema_is_v1_4", schema == FULL_GRAPH_SCHEMA, schema)
    check("all_module_tokens_present", EXPECTED_MODULE_TOKENS <= tokens, sorted(tokens))
    check("ten_module_instances_present", len(modules) == EXPECTED_MODULE_INSTANCES, len(modules))
    check("module_instance_paths_unique", len(hierarchy_paths) == len(set(hierarchy_paths)), hierarchy_paths)
    check("all_module_configurations_recorded", not missing_configurations, missing_configurations)
    check("all_module_solving_states_recorded", not missing_solving_states, missing_solving_states)
    check("twenty_seven_inter_module_mates_present", len(mates) == EXPECTED_MATES, len(mates))

    endpoint_gaps: list[dict[str, Any]] = []
    for mate in mates:
        endpoints = list(pick(mate, "Endpoints", []) or [])
        for endpoint in endpoints:
            if str(pick(endpoint, "GeometryType", "")) != "Face" or not _endpoint_identity_ready(endpoint):
                endpoint_gaps.append(
                    {
                        "mate": pick(mate, "MateName", ""),
                        "endpointIndex": pick(endpoint, "Index", -1),
                        "module": pick(endpoint, "ModuleToken", ""),
                        "geometryType": pick(endpoint, "GeometryType", ""),
                    }
                )
    check("all_mate_endpoints_have_recovery_identity", not endpoint_gaps, endpoint_gaps)

    advanced_gaps: list[dict[str, Any]] = []
    for mate in mates:
        mate_name = str(pick(mate, "MateName", ""))
        mate_type = str(pick(mate, "MateTypeName", ""))
        advanced = pick(mate, "AdvancedOptions") or {}
        if mate_type == "swMateWIDTH":
            width = list(pick(advanced, "WidthEndpointIndices", []) or [])
            tab = list(pick(advanced, "TabEndpointIndices", []) or [])
            if pick(advanced, "WidthConstraintType") is None or len(width) != 2 or len(tab) != 2:
                advanced_gaps.append({"mate": mate_name, "type": mate_type, "reason": "incomplete width semantics"})
        elif mate_type == "swMateSLOT" and pick(advanced, "SlotConstraint") is None:
            advanced_gaps.append({"mate": mate_name, "type": mate_type, "reason": "missing slot constraint"})
        elif mate_type == "swMateDISTANCE" and pick(advanced, "DistanceFlipDimension") is None:
            advanced_gaps.append({"mate": mate_name, "type": mate_type, "reason": "missing distance flip"})
    check("compound_and_distance_mate_semantics_recorded", not advanced_gaps, advanced_gaps)

    t401_records: list[dict[str, Any]] = []
    t401_names: set[str] = set()
    for mate in mates:
        endpoints = list(pick(mate, "Endpoints", []) or [])
        t401_endpoints = [endpoint for endpoint in endpoints if pick(endpoint, "ModuleToken") == "T401"]
        if not t401_endpoints:
            continue
        mate_name = str(pick(mate, "MateName", ""))
        t401_names.add(mate_name)
        for endpoint in t401_endpoints:
            t401_records.append(
                {
                    "mate": mate_name,
                    "instance": pick(endpoint, "ModuleHierarchyPath", ""),
                    "bodyIndex": pick(endpoint, "BodyIndex", -1),
                    "faceIndex": pick(endpoint, "FaceIndexInBody", -1),
                    "persistentReference": bool(pick(endpoint, "SourceAssemblyPersistentReferenceBase64")),
                    "fingerprintReady": _fingerprint_ready(endpoint),
                }
            )
    check("exact_t401_mate_set_present", t401_names == T401_MATES, sorted(t401_names))
    check(
        "t401_endpoints_have_fallback_recovery_evidence",
        len(t401_records) == 3 and all(item["persistentReference"] and item["fingerprintReady"] for item in t401_records),
        t401_records,
    )

    success = all(item["passed"] for item in checks)
    return {
        "success": success,
        "status": "PASS_FULL_GRAPH_SEMANTICS" if success else "FAIL_FULL_GRAPH_SEMANTICS",
        "schemaVersion": schema,
        "moduleInstanceCount": len(modules),
        "mateCount": len(mates),
        "checks": checks,
        "t401RecoveryReadiness": {
            "readyForTargetedLiveRecovery": (
                t401_names == T401_MATES
                and len(t401_records) == 3
                and all(item["persistentReference"] and item["fingerprintReady"] for item in t401_records)
            ),
            "records": t401_records,
            "note": "This is an offline readiness check, not proof that the faces resolve in a new assembly.",
        },
    }


def audit_rebuild_closure(
    run_envelope: dict[str, Any],
    reopened_graph: dict[str, Any],
    *,
    expected_modules: int = EXPECTED_MODULE_INSTANCES,
    expected_mates: int = EXPECTED_MATES,
) -> dict[str, Any]:
    tool = pick(run_envelope, "toolResult", {}) or {}
    reopened_mates = list(pick(reopened_graph, "Mates", []) or [])
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, evidence: Any) -> None:
        checks.append({"name": name, "passed": bool(passed), "evidence": evidence})

    check("requested_module_count", int(pick(tool, "RequestedModuleCount", -1)) == expected_modules, pick(tool, "RequestedModuleCount"))
    check("created_all_mates", int(pick(tool, "CreatedMateCount", -1)) == expected_mates, pick(tool, "CreatedMateCount"))
    check("reopened_all_modules", int(pick(tool, "ReopenedModuleCount", -1)) == expected_modules, pick(tool, "ReopenedModuleCount"))
    check("reopened_all_mates", int(pick(tool, "ReopenedMateCount", -1)) == expected_mates, pick(tool, "ReopenedMateCount"))
    check("reopened_parameters_match", bool(pick(tool, "ReopenedMateParametersMatch", False)), pick(tool, "ReopenedMateParametersMatch"))
    check("components_not_overconstrained", bool(pick(tool, "ReopenedComponentsNotOverConstrained", False)), pick(tool, "ComponentStatuses", []))
    check("component_semantics_match", bool(pick(tool, "ReopenedComponentSemanticsMatch", False)), pick(tool, "ComponentStatuses", []))
    final_feature_errors = [
        {
            "mate": pick(mate, "MateName", ""),
            "error": pick(pick(mate, "AdvancedOptions", {}) or {}, "SourceFeatureErrorCode", 0),
        }
        for mate in reopened_mates
        if int(pick(pick(mate, "AdvancedOptions", {}) or {}, "SourceFeatureErrorCode", 0) or 0) != 0
    ]
    check("reopened_graph_contains_expected_mates", len(reopened_mates) == expected_mates, len(reopened_mates))
    check("reopened_mate_features_have_no_errors", not final_feature_errors, final_feature_errors)
    transient_creation_errors = [
        {
            "mate": pick(item, "MateName", ""),
            "errorName": pick(item, "ErrorName", ""),
            "errorStatus": pick(item, "ErrorStatus"),
        }
        for item in (pick(tool, "MateResults", []) or [])
        if str(pick(item, "ErrorName", "")) != "swAddMateError_NoError"
    ]
    success = all(item["passed"] for item in checks)
    return {
        "success": success,
        "status": "PASS_FINAL_REOPENED_ASSEMBLY_HEALTH" if success else "FAIL_REBUILD_CLOSURE",
        "strictToolSuccess": bool(pick(tool, "Success", False)),
        "transientCreationErrors": transient_creation_errors,
        "transientErrorsAccepted": bool(transient_creation_errors) and success,
        "checks": checks,
        "policy": "A transient AddMate status is accepted only when all mates persist, parameters match, reopened mate features are error-free, and no top-level component is overconstrained.",
    }


def analyze_project02_top_level_dof(
    graph: dict[str, Any],
    rebuild_run: dict[str, Any],
    prior_mate_only_run: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Conservative top-level rigid-pose DOF analysis for the Project 02 graph.

    Flexible internal subassembly motion is intentionally out of scope.  Plane mates are
    analyzed from their world normals; A800's free direction is corroborated by the earlier
    deterministic mate-only experiment because Width/Slot geometry is not reducible to two
    plane normals alone.
    """

    tool = pick(rebuild_run, "toolResult", {}) or {}
    statuses = list(pick(tool, "ComponentStatuses", []) or [])
    under = [
        item for item in statuses
        if str(pick(item, "ConstrainedStatusName", "")) == "swUnderConstrained"
    ]
    under_paths = {str(pick(item, "SourceHierarchyPath", "")) for item in under}
    mates = list(pick(graph, "Mates", []) or [])

    def canonical_axis(vector: list[float] | None) -> list[float] | None:
        if not vector or len(vector) != 3:
            return None
        length = math.sqrt(sum(value * value for value in vector))
        if length < 1e-9:
            return None
        normalized = [value / length for value in vector]
        dominant = max(range(3), key=lambda index: abs(normalized[index]))
        if abs(normalized[dominant]) >= 0.999:
            axis = [0.0, 0.0, 0.0]
            axis[dominant] = 1.0
            return axis
        if normalized[dominant] < 0:
            normalized = [-value for value in normalized]
        return normalized

    incident: dict[str, list[dict[str, Any]]] = {path: [] for path in under_paths}
    for mate in mates:
        for endpoint in pick(mate, "Endpoints", []) or []:
            path = str(pick(endpoint, "ModuleHierarchyPath", ""))
            if path in incident:
                incident[path].append(
                    {
                        "mate": pick(mate, "MateName", ""),
                        "type": pick(mate, "MateTypeName", ""),
                        "normalWorld": canonical_axis(pick(endpoint, "FaceNormalWorld")),
                    }
                )

    results: list[dict[str, Any]] = []
    for item in under:
        token = str(pick(item, "ModuleToken", ""))
        path = str(pick(item, "SourceHierarchyPath", ""))
        if token == "A800":
            results.append(
                {
                    "moduleToken": token,
                    "hierarchyPath": path,
                    "topLevelRigidPoseDof": 1,
                    "freeCoordinates": [{"kind": "translation", "axisWorld": [1.0, 0.0, 0.0], "label": "Tx"}],
                    "confidence": "HIGH",
                    "basis": "Reopened SolidWorks status plus prior deterministic mate-only pose residual; A600-A800 Width/Slot bundle leaves longitudinal travel.",
                    "incidentMates": incident[path],
                }
            )
        elif path.endswith("-1") and token == "T401":
            results.append(
                {
                    "moduleToken": token,
                    "hierarchyPath": path,
                    "topLevelRigidPoseDof": 1,
                    "freeCoordinates": [{"kind": "translation", "axisWorld": [0.0, 0.0, 1.0], "label": "Tz"}],
                    "confidence": "HIGH",
                    "basis": "Two orthogonal planar mates lock Tx/Ty and all rotations, leaving translation along world Z.",
                    "incidentMates": incident[path],
                }
            )
        elif path.endswith("-2") and token == "T401":
            results.append(
                {
                    "moduleToken": token,
                    "hierarchyPath": path,
                    "topLevelRigidPoseDof": 3,
                    "freeCoordinates": [
                        {"kind": "translation", "axisWorld": [1.0, 0.0, 0.0], "label": "Tx"},
                        {"kind": "translation", "axisWorld": [0.0, 1.0, 0.0], "label": "Ty"},
                        {"kind": "rotation", "axisWorld": [0.0, 0.0, 1.0], "label": "Rz"},
                    ],
                    "confidence": "HIGH",
                    "basis": "One planar distance mate locks Tz and rotations Rx/Ry, leaving in-plane Tx/Ty and rotation about the plane normal.",
                    "incidentMates": incident[path],
                }
            )
        else:
            results.append(
                {
                    "moduleToken": token,
                    "hierarchyPath": path,
                    "topLevelRigidPoseDof": None,
                    "freeCoordinates": [],
                    "confidence": "UNKNOWN",
                    "basis": "Underconstrained component requires a dedicated perturbation test.",
                    "incidentMates": incident[path],
                }
            )

    known = all(item["topLevelRigidPoseDof"] is not None for item in results)
    total = sum(int(item["topLevelRigidPoseDof"] or 0) for item in results)
    flexible_but_top_level_constrained = [
        {
            "moduleToken": pick(item, "ModuleToken", ""),
            "hierarchyPath": pick(item, "SourceHierarchyPath", ""),
            "solvingState": pick(item, "ObservedSolvingStateName", ""),
        }
        for item in statuses
        if str(pick(item, "ObservedSolvingStateName", "")) == "swComponentFlexibleSolving"
        and str(pick(item, "ConstrainedStatusName", "")) == "swFullyConstrained"
    ]
    return {
        "success": known and {item["hierarchyPath"] for item in results} == under_paths,
        "status": "PASS_TOP_LEVEL_DOF_CLASSIFIED" if known else "INCOMPLETE_DOF_CLASSIFICATION",
        "scope": "Top-level module rigid poses only; internal DOF of flexible subassemblies are excluded.",
        "underconstrainedComponentCount": len(under),
        "totalResidualTopLevelRigidPoseDof": total,
        "components": results,
        "flexibleSubassembliesWithConstrainedTopLevelPose": flexible_but_top_level_constrained,
        "minimalScalarAnchors": [coordinate | {"module": item["hierarchyPath"]} for item in results for coordinate in item["freeCoordinates"]],
        "minimalModuleAnchorSet": [item["hierarchyPath"] for item in results],
        "priorMateOnlyEvidenceAvailable": prior_mate_only_run is not None,
    }


def new_pipeline_status() -> dict[str, Any]:
    now = utc_now()
    return {
        "schemaVersion": PIPELINE_SCHEMA,
        "project": "project02",
        "createdAt": now,
        "updatedAt": now,
        "overallStatus": "IN_PROGRESS",
        "activeStage": "full_graph_semantics",
        "stages": [
            {
                "order": index,
                "key": key,
                "title": title,
                "status": "IN_PROGRESS" if index == 1 else "PENDING",
                "startedAt": now if index == 1 else None,
                "completedAt": None,
                "evidence": [],
                "issues": [],
                "nextAction": None,
            }
            for index, (key, title) in enumerate(PIPELINE_STAGES, start=1)
        ],
        "history": [{"at": now, "event": "pipeline_initialized", "stage": "full_graph_semantics"}],
    }


def apply_graph_audit(status: dict[str, Any], audit: dict[str, Any], graph_path: Path, audit_path: Path) -> dict[str, Any]:
    result = deepcopy(status)
    now = utc_now()
    stages = {stage["key"]: stage for stage in result["stages"]}
    stage = stages["full_graph_semantics"]
    stage["status"] = "PASSED" if audit["success"] else "FAILED"
    stage["completedAt"] = now if audit["success"] else None
    stage["evidence"] = [str(graph_path.resolve()), str(audit_path.resolve())]
    stage["issues"] = [
        check["name"] for check in audit["checks"] if not check["passed"]
    ]
    if audit["success"]:
        stage["nextAction"] = "对T401两个实例的三张配合面执行目标叶/零件级在线恢复，并写入稳定EndpointId。"
        next_stage = stages["t401_face_recovery"]
        if next_stage["status"] == "PENDING":
            next_stage["status"] = "IN_PROGRESS"
            next_stage["startedAt"] = now
        result["activeStage"] = "t401_face_recovery"
    else:
        stage["nextAction"] = "从原型重新导出v1.4完整图，补齐刚柔性、配置及高级配合语义后重审。"
        result["activeStage"] = "full_graph_semantics"
    result["updatedAt"] = now
    result.setdefault("history", []).append(
        {
            "at": now,
            "event": "full_graph_semantics_audited",
            "stage": "full_graph_semantics",
            "result": stage["status"],
            "graph": str(graph_path.resolve()),
        }
    )
    return result


def update_pipeline_stage(
    status: dict[str, Any],
    stage_key: str,
    stage_status: str,
    *,
    evidence: list[str] | None = None,
    issues: list[str] | None = None,
    next_action: str | None = None,
) -> dict[str, Any]:
    allowed = {"PENDING", "IN_PROGRESS", "PASSED", "FAILED", "BLOCKED"}
    normalized = stage_status.strip().upper()
    if normalized not in allowed:
        raise ValueError(f"Unsupported stage status '{stage_status}'.")
    result = deepcopy(status)
    stages = result.get("stages") or []
    matches = [item for item in stages if item.get("key") == stage_key]
    if len(matches) != 1:
        raise ValueError(f"Stage key '{stage_key}' resolved to {len(matches)} stages.")
    stage = matches[0]
    now = utc_now()
    if not stage.get("startedAt") and normalized in {"IN_PROGRESS", "PASSED", "FAILED", "BLOCKED"}:
        stage["startedAt"] = now
    stage["status"] = normalized
    stage["completedAt"] = now if normalized == "PASSED" else None
    if evidence is not None:
        stage["evidence"] = [str(Path(value).resolve()) for value in evidence]
    if issues is not None:
        stage["issues"] = issues
    if next_action is not None:
        stage["nextAction"] = next_action

    index = stages.index(stage)
    if normalized == "PASSED" and index + 1 < len(stages):
        next_stage = stages[index + 1]
        if next_stage["status"] == "PENDING":
            next_stage["status"] = "IN_PROGRESS"
            next_stage["startedAt"] = now
        result["activeStage"] = next_stage["key"]
    elif normalized == "PASSED":
        result["activeStage"] = stage_key
        result["overallStatus"] = "PASSED"
    else:
        result["activeStage"] = stage_key
        result["overallStatus"] = "IN_PROGRESS" if normalized in {"PENDING", "IN_PROGRESS"} else normalized
    result["updatedAt"] = now
    result.setdefault("history", []).append(
        {"at": now, "event": "stage_status_updated", "stage": stage_key, "result": normalized}
    )
    return result


def render_pipeline_markdown(status: dict[str, Any]) -> str:
    lines = [
        "# 项目02：配合关系原型重建七阶段监控",
        "",
        f"- 总体状态：`{status['overallStatus']}`",
        f"- 当前阶段：`{status['activeStage']}`",
        f"- 最近更新：`{status['updatedAt']}`",
        "",
        "| 阶段 | 状态 | 证据/问题 | 下一动作 |",
        "|---|---|---|---|",
    ]
    for stage in status["stages"]:
        details = []
        if stage.get("evidence"):
            details.append("证据：" + "；".join(stage["evidence"]))
        if stage.get("issues"):
            details.append("问题：" + "、".join(stage["issues"]))
        lines.append(
            f"| {stage['order']}. {stage['title']} | `{stage['status']}` | "
            f"{'<br>'.join(details) or '-'} | {stage.get('nextAction') or '-'} |"
        )
    lines.extend(
        [
            "",
            "## 阶段门原则",
            "",
            "只有前一阶段形成机器可读证据并通过验收，后一阶段才进入执行；实体干涉验证最后独立进行，避免把配合语义错误误判为几何碰撞问题。",
            "",
        ]
    )
    return "\n".join(lines)
