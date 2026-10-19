from __future__ import annotations

from typing import Any


class MateOverconstraintAuditError(ValueError):
    pass


def _value(item: dict[str, Any], pascal: str, default: Any = None) -> Any:
    camel = pascal[0].lower() + pascal[1:]
    return item.get(pascal, item.get(camel, default))


def analyze_mate_overconstraint_evidence(
    source_graph: dict[str, Any],
    experiment_results: list[dict[str, Any]],
    focus_tokens: tuple[str, ...] = ("A500", "A700"),
) -> dict[str, Any]:
    if not experiment_results:
        raise MateOverconstraintAuditError("At least one reconstruction result is required.")
    mates = source_graph.get("Mates") or []
    mate_by_name = {str(item.get("MateName") or ""): item for item in mates}
    incident = [
        {
            "mateName": item.get("MateName"),
            "mateType": item.get("MateType"),
            "mateTypeName": item.get("MateTypeName"),
            "moduleTokens": item.get("ModuleTokens") or [],
            "distanceMeters": item.get("Distance"),
            "isBasicTwoFaceRebuildable": item.get("IsBasicTwoFaceRebuildable"),
        }
        for item in mates
        if set(str(value) for value in item.get("ModuleTokens") or []) & set(focus_tokens)
    ]

    experiments: list[dict[str, Any]] = []
    overdefined_sets: list[set[str]] = []
    for result in experiment_results:
        mate_results = _value(result, "MateResults", []) or []
        overdefined = [
            str(_value(item, "MateName", ""))
            for item in mate_results
            if str(_value(item, "ErrorName", "")) == "swAddMateError_OverDefinedAssembly"
        ]
        overdefined_sets.append(set(overdefined))
        component_results = _value(result, "ComponentResults", []) or []
        statuses = {
            str(_value(item, "ModuleToken", "")): str(_value(item, "ConstrainedStatusName", ""))
            for item in component_results
            if str(_value(item, "ModuleToken", "")) in focus_tokens
        }
        experiments.append(
            {
                "mode": _value(result, "Mode"),
                "outputAssemblyPath": _value(result, "OutputAssemblyPath"),
                "focusComponentStatuses": statuses,
                "overdefinedMatesInCreationOrder": overdefined,
                "firstOverdefinedMate": overdefined[0] if overdefined else None,
                "failedMateNames": [
                    str(_value(item, "MateName", ""))
                    for item in mate_results
                    if not bool(_value(item, "Success", False))
                ],
            }
        )

    common_overdefined = set.intersection(*overdefined_sets) if overdefined_sets else set()
    first_order = experiments[0]["overdefinedMatesInCreationOrder"]
    ordered_common = [name for name in first_order if name in common_overdefined]
    root_candidate = ordered_common[0] if ordered_common else None
    secondary_candidates = ordered_common[1:]
    root_modules = set(str(value) for value in (mate_by_name.get(root_candidate or "", {}).get("ModuleTokens") or []))
    a500_direct_overdefined = any(
        "A500" in set(str(value) for value in (mate_by_name.get(name, {}).get("ModuleTokens") or []))
        for name in common_overdefined
    )
    a500_a700_link_exists = any(
        {"A500", "A700"}.issubset(set(str(value) for value in item.get("ModuleTokens") or []))
        for item in mates
    )

    return {
        "schemaVersion": "mate-overconstraint-audit/v1",
        "focusModules": list(focus_tokens),
        "experimentCount": len(experiments),
        "experiments": experiments,
        "incidentMateInventory": incident,
        "commonOverdefinedMates": ordered_common,
        "firstCommonOverdefinedMate": root_candidate,
        "secondaryCandidates": secondary_candidates,
        "inference": {
            "rootCandidateModuleTokens": sorted(root_modules),
            "a500HasDirectOverdefinedMate": a500_direct_overdefined,
            "a500A700DirectLinkExists": a500_a700_link_exists,
            "a500OverconstraintMayBePropagatedThroughA700": (
                not a500_direct_overdefined and a500_a700_link_exists and "A700" in root_modules
            ),
            "confidence": "high-cross-mode-repeatability" if len(experiments) >= 3 and root_candidate else "provisional",
            "statement": (
                f"三组重建均在'{root_candidate}'首次报告过定义；后续配合不能据此单独判为根因。"
                if root_candidate
                else "现有结果未报告共同的过定义配合。"
            ),
        },
        "recommendedIsolationExperiments": [
            {
                "id": "A700-without-width10",
                "modules": ["A600", "A700"],
                "removeMateNames": ["宽度10"],
                "purpose": "验证距离29在移除首个过定义配合后是否可正常创建。",
            },
            {
                "id": "A700-without-distance29",
                "modules": ["A600", "A700"],
                "removeMateNames": ["距离29"],
                "purpose": "验证宽度10本身是否已超出最小定位所需约束。",
            },
            {
                "id": "A500-base-bundle",
                "modules": ["A600", "A500"],
                "removeMateNames": [],
                "purpose": "隔离验证A500自身安装配合组是否过定义。",
            },
            {
                "id": "reintroduce-distance8",
                "modules": ["A600", "A500", "A700"],
                "removeMateNames": ["宽度10"],
                "purpose": "在A700根因候选移除后重新加入A500-A700距离8，判断A500状态是否由约束传播造成。",
            },
        ],
    }


def analyze_mate_overconstraint_isolation_results(
    source_reconstruction_result: dict[str, Any],
    isolation_runs: list[dict[str, Any]],
    candidate_mate_names: tuple[str, ...] = ("宽度10", "距离29"),
) -> dict[str, Any]:
    """Compare bounded editable-graph rebuilds without claiming the source design is invalid."""

    if not isolation_runs:
        raise MateOverconstraintAuditError("At least one isolation run is required.")
    source_health: dict[str, dict[str, Any]] = {}
    for item in _value(source_reconstruction_result, "MateResults", []) or []:
        name = str(_value(item, "MateName", ""))
        if name not in candidate_mate_names:
            continue
        advanced = _value(item, "AdvancedOptions", {}) or {}
        source_health[name] = {
            "sourceFeatureErrorCode": _value(advanced, "SourceFeatureErrorCode"),
            "sourceFeatureIsWarning": _value(advanced, "SourceFeatureIsWarning"),
            "reconstructionCreationErrorName": _value(item, "ErrorName"),
        }

    run_summaries: list[dict[str, Any]] = []
    for run in isolation_runs:
        raw_result = run.get("result") or {}
        tool_result = _value(raw_result, "ToolResult", raw_result) or {}
        mate_results = _value(tool_result, "MateResults", []) or []
        overdefined = [
            str(_value(item, "MateName", ""))
            for item in mate_results
            if str(_value(item, "ErrorName", "")) == "swAddMateError_OverDefinedAssembly"
        ]
        run_summaries.append(
            {
                "id": str(run.get("id") or ""),
                "removedMateNames": [str(value) for value in run.get("removedMateNames") or []],
                "success": bool(_value(raw_result, "Success", _value(tool_result, "Success", False))),
                "durationSeconds": _value(raw_result, "DurationSeconds"),
                "requestedMateCount": _value(tool_result, "RequestedActiveMateCount"),
                "createdMateCount": _value(tool_result, "CreatedMateCount"),
                "reopenedMateCount": _value(tool_result, "ReopenedMateCount"),
                "parametersMatch": _value(tool_result, "ReopenedMateParametersMatch"),
                "overdefinedMates": overdefined,
                "mateCreationStatuses": {
                    str(_value(item, "MateName", "")): str(_value(item, "ErrorName", ""))
                    for item in mate_results
                },
                "outputAssemblyPath": _value(raw_result, "OutputAssemblyPath", _value(tool_result, "OutputAssemblyPath")),
            }
        )

    width_only = next(
        (item for item in run_summaries if set(item["removedMateNames"]) == {"宽度10"}),
        None,
    )
    both_removed = next(
        (
            item
            for item in run_summaries
            if {"宽度10", "距离29"}.issubset(set(item["removedMateNames"]))
        ),
        None,
    )
    source_candidates_healthy = all(
        source_health.get(name, {}).get("sourceFeatureErrorCode") == 0
        and source_health.get(name, {}).get("sourceFeatureIsWarning") is False
        for name in candidate_mate_names
    )
    width_removal_insufficient = bool(
        width_only and "距离29" in width_only["overdefinedMates"]
    )
    both_removal_clears = bool(both_removed and not both_removed["overdefinedMates"])

    return {
        "schemaVersion": "mate-overconstraint-isolation-audit/v1",
        "candidateMateNames": list(candidate_mate_names),
        "sourceFeatureHealth": source_health,
        "runs": run_summaries,
        "findings": {
            "sourceCandidatesHealthy": source_candidates_healthy,
            "removingWidth10AloneIsInsufficient": width_removal_insufficient,
            "distance29RemainsOverdefinedWithoutWidth10": width_removal_insufficient,
            "removingBothClearsCreationOverdefinedErrors": both_removal_clears,
            "classification": (
                "reconstruction-redundancy-or-semantic-difference"
                if source_candidates_healthy and width_removal_insufficient and both_removal_clears
                else "inconclusive"
            ),
            "statement": (
                "宽度10不是唯一触发项；删除后距离29仍报告过定义，同时删除两者后创建错误消失。"
                "原型中的两条源特征均无错误，因此应继续检查重建顺序、刚柔性和高级配合语义，"
                "不能把实验结果直接解释为原型设计错误。"
                if source_candidates_healthy and width_removal_insufficient and both_removal_clears
                else "现有隔离结果尚不足以形成稳定结论。"
            ),
        },
        "limitations": [
            "editable rebuild v1 does not yet return reopened component GetConstrainedStatus values",
            "mate creation status and reopen parameter verification do not prove zero B-rep interference",
        ],
        "recommendedNextStep": {
            "id": "preserve-source-semantics",
            "purpose": "补充重开后的组件约束状态，并核对A700刚柔性、配合创建顺序及Width高级选项后再决定是否删减设计关系。",
        },
    }


def analyze_full_semantics_baseline(
    prior_source_pose_result: dict[str, Any],
    semantic_graph: dict[str, Any],
    semantic_rebuild_run: dict[str, Any],
) -> dict[str, Any]:
    """Compare the old source-pose rebuild with a solving-state-aware full baseline."""

    tool_result = _value(semantic_rebuild_run, "ToolResult", semantic_rebuild_run) or {}
    old_mates = _value(prior_source_pose_result, "MateResults", []) or []
    new_mates = _value(tool_result, "MateResults", []) or []
    old_components = _value(prior_source_pose_result, "ComponentResults", []) or []
    new_components = _value(tool_result, "ComponentStatuses", []) or []
    graph_modules = semantic_graph.get("Modules") or []
    graph_mates = semantic_graph.get("Mates") or []

    def overdefined(items: list[dict[str, Any]]) -> list[str]:
        return [
            str(_value(item, "MateName", ""))
            for item in items
            if str(_value(item, "ErrorName", "")) == "swAddMateError_OverDefinedAssembly"
        ]

    old_status = {
        str(_value(item, "ModuleToken", "")): str(_value(item, "ConstrainedStatusName", ""))
        for item in old_components
    }
    new_status = {
        str(_value(item, "ModuleToken", "")): {
            "constrainedStatusName": str(_value(item, "ConstrainedStatusName", "")),
            "expectedSolvingStateName": _value(item, "ExpectedSolvingStateName"),
            "observedSolvingStateName": _value(item, "ObservedSolvingStateName"),
            "solvingStateMatches": bool(_value(item, "SolvingStateMatches", False)),
        }
        for item in new_components
    }
    source_solving = {
        str(item.get("ModuleToken") or ""): {
            "solvingState": item.get("SolvingState"),
            "solvingStateName": item.get("SolvingStateName"),
        }
        for item in graph_modules
    }
    width = next((item for item in graph_mates if item.get("MateName") == "宽度10"), {})
    width_options = width.get("AdvancedOptions") or {}
    old_width = next(
        (item for item in old_mates if str(_value(item, "MateName", "")) == "宽度10"),
        {},
    )
    same_mate_names = {
        str(_value(item, "MateName", "")) for item in old_mates
        if str(_value(item, "MateName", "")) in {str(mate.get("MateName") or "") for mate in graph_mates}
    } == {str(item.get("MateName") or "") for item in graph_mates}
    prior_overdefined = overdefined(old_mates)
    semantic_overdefined = overdefined(new_mates)
    a700_flexible = source_solving.get("A700", {}).get("solvingStateName") == "swComponentFlexibleSolving"
    a700_recovered = bool(new_status.get("A700", {}).get("solvingStateMatches"))
    old_a700_over = old_status.get("A700") == "swOverConstrained"
    new_a700_not_over = new_status.get("A700", {}).get("constrainedStatusName") != "swOverConstrained"
    full_closure = all(
        [
            bool(_value(semantic_rebuild_run, "Success", False)),
            bool(_value(tool_result, "MateCreationErrorsClear", False)),
            bool(_value(tool_result, "ReopenedComponentsNotOverConstrained", False)),
            bool(_value(tool_result, "ReopenedComponentSemanticsMatch", False)),
            bool(_value(tool_result, "ReopenedMateParametersMatch", False)),
        ]
    )
    confirmed = bool(
        same_mate_names
        and {"宽度10", "距离29"}.issubset(set(prior_overdefined))
        and not semantic_overdefined
        and a700_flexible
        and a700_recovered
        and old_a700_over
        and new_a700_not_over
        and full_closure
    )

    return {
        "schemaVersion": "mate-full-semantics-baseline-audit/v1",
        "sameSixMateSetRetained": same_mate_names,
        "sourceSolvingStates": source_solving,
        "width10AdvancedOptions": width_options,
        "priorRebuild": {
            "overdefinedMates": prior_overdefined,
            "componentStatuses": old_status,
            "widthAdvancedOptionsWereAlreadyAvailable": bool(_value(old_width, "AdvancedOptions")),
        },
        "semanticRebuild": {
            "success": bool(_value(semantic_rebuild_run, "Success", False)),
            "durationSeconds": _value(semantic_rebuild_run, "DurationSeconds"),
            "overdefinedMates": semantic_overdefined,
            "componentStatuses": new_status,
            "mateCreationErrorsClear": _value(tool_result, "MateCreationErrorsClear"),
            "componentsNotOverConstrained": _value(tool_result, "ReopenedComponentsNotOverConstrained"),
            "componentSemanticsMatch": _value(tool_result, "ReopenedComponentSemanticsMatch"),
            "mateParametersMatch": _value(tool_result, "ReopenedMateParametersMatch"),
            "outputAssemblyPath": _value(tool_result, "OutputAssemblyPath"),
        },
        "finding": {
            "confirmed": confirmed,
            "classification": "confirmed-missing-a700-flexible-solving-state" if confirmed else "inconclusive",
            "statement": (
                "保留同一组六条配合和源位姿，仅补齐模组刚柔性并将Width语义写入中间图后，"
                "宽度10与距离29均不再过定义，A700也由过约束恢复为保持柔性的非过约束状态。"
                "结合旧实验已具备Width临时参数，主要缺失语义可定位为A700柔性状态。"
                if confirmed
                else "完整语义基线尚未满足确认根因所需的全部门禁。"
            ),
        },
        "limitations": [
            "A700 is flexible and may legitimately report swUnderConstrained at the top level",
            "this mate-semantic closure does not include AABB or B-rep interference checks",
        ],
    }
