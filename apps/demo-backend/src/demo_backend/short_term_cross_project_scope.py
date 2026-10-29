"""Summarize the short-term cross-project assembly scope without overclaiming.

The repository already contains three different kinds of evidence:

* portable installation ports for individual modules;
* immutable direct cross-project execution releases;
* cumulative CAD chains and mechanical-review decisions.

This module joins those layers into one fail-closed readiness report for the
six module families selected for the current milestone.  It does not infer new
mechanical compatibility and never turns a datum-placement demo into a direct
installation authorization.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable


SCHEMA = "short-term-cross-project-scope-readiness/v2"
ALTERNATE_ROUTE_SCHEMA = "cross-project-alternate-installation-route/v1"
PARAMETERIZED_DATUM_QUEUE_SCHEMA = "parameterized-datum-validation-queue/v1"

TARGET_GROUPS: tuple[dict[str, Any], ...] = (
    {
        "groupId": "base_environment",
        "displayName": "箱体、机架与固定基座",
        "roles": ("Base",),
    },
    {
        "groupId": "transport",
        "displayName": "产品传输与载具输送",
        "roles": ("Transport",),
    },
    {
        "groupId": "scanner",
        "displayName": "条码扫描",
        "roles": ("Scanner",),
    },
    {
        "groupId": "calibration",
        "displayName": "喷嘴校准与标定",
        "roles": ("Calibration",),
    },
    {
        "groupId": "cleaning_weighing",
        "displayName": "清洁与称重",
        "roles": ("Cleaning", "CleaningWeighing"),
    },
    {
        "groupId": "waste_handling",
        "displayName": "排胶与废胶处理",
        "roles": ("WasteCup",),
    },
)


class ShortTermCrossProjectScopeError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _status_ready(status: str) -> bool:
    return status in {"portable_verified", "context_provider_verified"}


def _project_refs(row: dict[str, Any]) -> list[str]:
    return sorted(str(value) for value in row.get("projectModuleRefs") or [])


def _validated_parameterized_datum_rows(
    queue: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], str | None]:
    """Authenticate an optional immutable datum queue used by the scope report.

    The queue is planning evidence, not CAD evidence.  Keeping that distinction
    here prevents a compatible or materialized candidate from being counted as
    a released installation relation.
    """

    if queue is None:
        return [], None
    if queue.get("schemaVersion") != PARAMETERIZED_DATUM_QUEUE_SCHEMA:
        raise ShortTermCrossProjectScopeError("不支持的参数化基准验证队列版本。")
    expected_digest = _digest(
        {key: value for key, value in queue.items() if key != "queueDigest"}
    )
    if queue.get("queueDigest") != expected_digest:
        raise ShortTermCrossProjectScopeError("参数化基准验证队列摘要不匹配。")
    source_digest = str(queue.get("sourceCatalogDigest") or "")
    if len(source_digest) != 64:
        raise ShortTermCrossProjectScopeError("参数化基准验证队列缺少规范目录摘要。")
    rows = [deepcopy(row) for row in queue.get("pairs") or []]
    identities: set[tuple[str, str]] = set()
    allowed_states = {
        "released",
        "ready_for_nonprototype_cad_validation",
        "explicit_position_parameters_required",
        "explicit_axis_selection_required",
        "explicit_axis_pair_selection_required",
        "explicit_flexible_slot_selection_required",
        "axis_pair_not_found_in_authoritative_catalog",
        "flexible_slot_axis_not_found_in_authoritative_catalog",
        "blocked_before_cad",
    }
    for row in rows:
        identity = (
            str(row.get("moduleDefinitionId") or ""),
            str(row.get("slotDefinitionId") or ""),
        )
        if not all(identity) or identity in identities:
            raise ShortTermCrossProjectScopeError(
                f"参数化基准验证队列包含空或重复配对：{identity}"
            )
        identities.add(identity)
        if str(row.get("state") or "") not in allowed_states:
            raise ShortTermCrossProjectScopeError(
                f"参数化基准验证队列包含未知状态：{row.get('state')}"
            )
    return rows, source_digest


def build_short_term_cross_project_scope_readiness(
    *,
    role_overlay: dict[str, Any],
    gap_report: dict[str, Any],
    candidate_matrix: dict[str, Any],
    chain_evidence: Iterable[dict[str, Any]],
    mechanical_review_decisions: Iterable[dict[str, Any]] = (),
    alternate_installation_routes: Iterable[dict[str, Any]] = (),
    parameterized_datum_queue: dict[str, Any] | None = None,
    parameterized_datum_catalog_digest: str | None = None,
) -> dict[str, Any]:
    """Build the milestone readiness report from existing immutable evidence."""

    if role_overlay.get("schemaVersion") != "module-semantic-role-overlay/v1":
        raise ShortTermCrossProjectScopeError("不支持的模组角色覆盖版本。")
    if gap_report.get("schemaVersion") != "global-module-gap-report/v1":
        raise ShortTermCrossProjectScopeError("不支持的全目录缺口报告版本。")
    if candidate_matrix.get("schemaVersion") != (
        "cross-project-module-candidate-matrix/v1"
    ):
        raise ShortTermCrossProjectScopeError("不支持的跨项目候选矩阵版本。")

    roles_by_definition = {
        str(row.get("moduleDefinitionId") or ""): str(row.get("primaryRole") or "")
        for row in role_overlay.get("modules") or []
    }
    modules_by_role: dict[str, list[dict[str, Any]]] = {}
    for row in gap_report.get("modules") or []:
        definition_id = str(row.get("moduleDefinitionId") or "")
        role = roles_by_definition.get(definition_id)
        if not role:
            raise ShortTermCrossProjectScopeError(
                f"缺口报告模组没有角色覆盖：{definition_id}"
            )
        modules_by_role.setdefault(role, []).append(row)

    matrix_rows = list(candidate_matrix.get("rows") or [])
    reviewed_cases = {
        str(row.get("caseId") or ""): row
        for row in mechanical_review_decisions
        if str(row.get("caseId") or "")
    }
    chains = list(chain_evidence)
    for chain in chains:
        if chain.get("mode") != "support_position_demo":
            continue
        if not (
            chain.get("evidenceKind") == "datum_placement_demo"
            and chain.get("actualFixationMethod") == "not_verified"
            and chain.get("holePatternMatchRequired") is False
            and chain.get("directMechanicalCompatibilityClaim") is False
            and chain.get("directMechanicalInterfaceCompatible") is False
        ):
            raise ShortTermCrossProjectScopeError(
                "支承定位Demo必须明确孔位非门禁、实际固定方式未验证及非直接机械兼容。"
            )
        if chain.get("status") == "passed" and chain.get("cadEvidenceVerified") is not True:
            raise ShortTermCrossProjectScopeError("支承定位Demo缺少已绑定输出的CAD闭环证据。")
        if chain.get("cumulativeAssemblyVerified") is True:
            sequence = chain.get("moduleSequence") or []
            base_token = chain.get("targetBaseToken", "A600")
            if not (
                chain.get("status") == "passed"
                and len(sequence) > 2
                and len(set(sequence)) == len(sequence)
                and len(sequence) == chain.get("topLevelModuleCount")
                and base_token in {"A600", "AA00"}
                and {base_token, "P000"}.issubset(sequence)
            ):
                raise ShortTermCrossProjectScopeError("支承定位累计链的模组清点或闭环状态不完整。")
    alternate_routes = list(alternate_installation_routes)
    for route in alternate_routes:
        if route.get("schemaVersion") != ALTERNATE_ROUTE_SCHEMA:
            raise ShortTermCrossProjectScopeError("不支持的备用槽位路线证据版本。")
        if route.get("nativeSlotCompatible") is not False:
            raise ShortTermCrossProjectScopeError(
                "备用槽位路线必须明确保留原生槽位不兼容结论。"
            )
        if route.get("cadLaunchAllowed") is True and route.get("status") != (
            "alternate_slot_released"
        ):
            raise ShortTermCrossProjectScopeError(
                "未发布的备用槽位路线不得允许启动CAD。"
            )
    datum_rows, datum_source_catalog_digest = _validated_parameterized_datum_rows(
        parameterized_datum_queue
    )
    if parameterized_datum_queue is not None:
        expected_catalog_digest = str(parameterized_datum_catalog_digest or "")
        if len(expected_catalog_digest) != 64:
            raise ShortTermCrossProjectScopeError(
                "参数化基准验证队列缺少当前规范目录摘要核对。"
            )
        if datum_source_catalog_digest != expected_catalog_digest:
            raise ShortTermCrossProjectScopeError(
                "参数化基准验证队列来源已落后于当前规范目录。"
            )
    group_rows: list[dict[str, Any]] = []

    for group in TARGET_GROUPS:
        roles = set(group["roles"])
        modules = [
            row
            for role in roles
            for row in modules_by_role.get(role, [])
            if row.get("status") != "deferred"
        ]
        ready_modules = [row for row in modules if _status_ready(str(row.get("status")))]
        cross_rows = [
            row
            for row in matrix_rows
            if str(row.get("primaryRole") or "") in roles
            and row.get("deferred") is not True
        ]
        status_counts = Counter(str(row.get("status") or "unknown") for row in cross_rows)
        released = [
            row for row in cross_rows if row.get("status") == "released_direct_execution"
        ]
        datum_cases = [
            row
            for row in chains
            if row.get("evidenceKind") == "datum_placement_demo"
            and roles.intersection(set(row.get("roles") or []))
            and row.get("status") == "passed"
        ]
        support_cases = [row for row in datum_cases if row.get("mode") == "support_position_demo"]
        cumulative_support_cases = [
            row for row in support_cases if row.get("cumulativeAssemblyVerified") is True
        ]
        role_alternate_routes = [
            deepcopy(row)
            for row in alternate_routes
            if str(row.get("role") or "") in roles
        ]
        released_alternate_routes = [
            row
            for row in role_alternate_routes
            if row.get("status") == "alternate_slot_released"
        ]
        pending_alternate_routes = [
            row
            for row in role_alternate_routes
            if row.get("status") != "alternate_slot_released"
        ]
        role_datum_rows = [
            deepcopy(row)
            for row in datum_rows
            if str(row.get("moduleRole") or "") in roles
        ]
        released_datum_rows = [
            row for row in role_datum_rows if row.get("state") == "released"
        ]
        ready_datum_rows = [
            row
            for row in role_datum_rows
            if row.get("state") == "ready_for_nonprototype_cad_validation"
        ]
        decision_datum_rows = [
            row
            for row in role_datum_rows
            if row.get("state")
            in {
                "explicit_position_parameters_required",
                "explicit_axis_selection_required",
                "explicit_axis_pair_selection_required",
                "explicit_flexible_slot_selection_required",
            }
        ]
        datum_state_counts = Counter(
            str(row.get("state") or "unknown") for row in role_datum_rows
        )

        if group["groupId"] == "base_environment":
            cross_state = "context_provider_ready"
        elif released:
            cross_state = "released_direct_execution"
        elif released_alternate_routes:
            cross_state = "alternate_slot_released"
        elif released_datum_rows:
            cross_state = "parameterized_datum_pair_released"
        elif ready_datum_rows:
            cross_state = "parameterized_datum_cad_validation_ready"
        elif decision_datum_rows:
            cross_state = "parameterized_datum_engineering_decision_required"
        elif pending_alternate_routes and all(
            row.get("status") == "alternate_slot_blocked_process_proxy_mismatch"
            for row in pending_alternate_routes
        ):
            cross_state = "alternate_slot_blocked_process_proxy_mismatch"
        elif pending_alternate_routes and all(
            row.get("status")
            == "alternate_slot_geometry_found_pending_mechanical_review"
            for row in pending_alternate_routes
        ):
            cross_state = (
                "alternate_slot_geometry_found_pending_mechanical_review"
            )
        elif pending_alternate_routes and all(
            row.get("status") == "alternate_slot_required_spacing_mismatch"
            for row in pending_alternate_routes
        ):
            cross_state = "alternate_slot_required_spacing_mismatch"
        elif pending_alternate_routes:
            cross_state = "alternate_slot_pending_validation"
        elif cumulative_support_cases:
            cross_state = "support_position_cumulative_demo_verified"
        elif support_cases:
            cross_state = "support_position_demo_verified"
        elif datum_cases:
            cross_state = "datum_demo_only"
        elif cross_rows and status_counts.get("incompatible", 0) == len(cross_rows):
            cross_state = "direct_cross_project_incompatible"
        else:
            cross_state = "direct_cross_project_not_released"

        group_rows.append(
            {
                "groupId": group["groupId"],
                "displayName": group["displayName"],
                "roles": sorted(roles),
                "catalogModuleCount": len(modules),
                "portableOrContextVerifiedCount": len(ready_modules),
                "modulePortCoverageReady": bool(modules)
                and len(ready_modules) == len(modules),
                "projectModuleRefs": sorted(
                    ref for row in modules for ref in _project_refs(row)
                ),
                "crossProjectState": cross_state,
                "nativeSlotDirectState": (
                    "direct_cross_project_incompatible"
                    if cross_rows
                    and status_counts.get("incompatible", 0) == len(cross_rows)
                    else "mixed_or_released"
                ),
                "releasedDirectExecutionCount": len(released),
                "releasedAlternateSlotCount": len(released_alternate_routes),
                "pendingAlternateSlotCount": len(pending_alternate_routes),
                "alternateInstallationRoutes": role_alternate_routes,
                "candidateStatusCounts": dict(sorted(status_counts.items())),
                "datumPlacementDemoCount": len(datum_cases),
                "datumPlacementCases": deepcopy(datum_cases),
                "supportPositionDemoCount": len(support_cases),
                "cumulativeSupportPositionDemoCount": len(cumulative_support_cases),
                "supportPositionCumulativeAssemblyVerified": bool(cumulative_support_cases),
                "parameterizedDatumPairCount": len(role_datum_rows),
                "parameterizedDatumReleasedPairCount": len(released_datum_rows),
                "parameterizedDatumCadReadyPairCount": len(ready_datum_rows),
                "parameterizedDatumDecisionRequiredPairCount": len(
                    decision_datum_rows
                ),
                "parameterizedDatumStateCounts": dict(
                    sorted(datum_state_counts.items())
                ),
                "parameterizedDatumPairs": role_datum_rows,
            }
        )

    successful_chains = [row for row in chains if row.get("status") == "passed"]
    complete_role_chains = [
        row
        for row in successful_chains
        if set(row.get("groupIds") or [])
        >= {group["groupId"] for group in TARGET_GROUPS}
    ]
    complete_cross_project_chains = [
        row for row in complete_role_chains
        if row.get("cadEvidenceVerified") is True
        and row.get("cumulativeAssemblyVerified") is True
        and len(set(row.get("crossProjectIds") or [])) > 1
    ]
    reviewed_cross_project = [
        row
        for row in reviewed_cases.values()
        if row.get("decision") == "accepted_for_stage_demo"
        and row.get("caseKind") == "direct_installation_cross_project"
    ]
    direct_roles = sorted(
        {
            role
            for row in matrix_rows
            if row.get("status") == "released_direct_execution"
            and row.get("deferred") is not True
            for role in [str(row.get("primaryRole") or "")]
            if role
        }
    )
    all_ports_ready = all(row["modulePortCoverageReady"] for row in group_rows)

    if all_ports_ready and complete_role_chains and reviewed_cross_project:
        overall = "stage_demo_ready_cross_project_expansion_in_progress"
    elif all_ports_ready:
        overall = "module_ports_ready_chain_evidence_incomplete"
    else:
        overall = "module_port_coverage_incomplete"

    priority_by_group = {
        "scanner": 10,
        "cleaning_weighing": 20,
        "waste_handling": 30,
        "transport": 40,
        "calibration": 50,
        "base_environment": 60,
    }
    disposition_queue = []
    for row in group_rows:
        if row["crossProjectState"] in {
            "released_direct_execution",
            "alternate_slot_released",
            "context_provider_ready",
        }:
            continue
        action = {
            "support_position_demo_verified": (
                "支承面与显式位置参数Demo的非原型CAD单包已通过；"
                "以显式Demo模式追加到已有累计检查点，复核原有模组、真实配合与保存重开。"
                "不要求先匹配孔位，实际固定方式暂未验证，不增加直接机械兼容结论。"
            ),
            "support_position_cumulative_demo_verified": (
                "支承定位Demo已通过累计追加与保存重开；复用该累计检查点继续演示或按需求调整位置参数。"
                "孔位匹配不作为当前Demo门禁，实际固定方式暂未验证；"
                "该证据不等于六类全覆盖或直接机械互换。"
            ),
            "datum_demo_only": (
                "三基准Demo已通过；来源接口需以完整原型配合图复核，"
                "随后匹配目标支承与孔槽特征，补齐显式位置参数后再验证。"
            ),
            "direct_cross_project_incompatible": (
                "不放宽现有硬不兼容结论；优先寻找同基座备用槽位或选择另一同角色模组。"
            ),
            "direct_cross_project_not_released": (
                "从已验证端口中选择一组接口拓扑一致的来源/目标，完成非原型CAD闭环后发布。"
            ),
            "alternate_slot_pending_validation": (
                "保留原生槽位不兼容结论；完成已发现备用槽位的工艺语义、候选位姿、"
                "非原型CAD配合与保存重开验证，验证通过前不得发布。"
            ),
            "alternate_slot_blocked_process_proxy_mismatch": (
                "备用孔位可解出安装位姿，但当前条码通道代理验证不通过；"
                "确认真实条码面/载具停位，若目标不变则否决该备用槽位。"
            ),
            "alternate_slot_required_spacing_mismatch": (
                "双方原生安装端口已分别通过非原型CAD，但定位孔距不一致；"
                "在目标基座有界搜索匹配孔距的备用槽位，找不到则保持不兼容。"
            ),
            "alternate_slot_geometry_found_pending_mechanical_review": (
                "目标基座限定静止叶已发现精确孔距候选，但孔用途、孔径/紧固方式、"
                "支承面和工位区域尚未确认；机械评审通过前不得登记端口或启动CAD。"
            ),
            "parameterized_datum_pair_released": (
                "已有至少一组参数化基准配对完成非原型CAD、保存重开和不可变发布；"
                "继续按验证队列处理同角色的其余多基座组合。"
            ),
            "parameterized_datum_cad_validation_ready": (
                "语义端口与完整定位配方已生成，下一步逐组执行非原型CAD、保存重开及配对发布。"
            ),
            "parameterized_datum_engineering_decision_required": (
                "接口几何已登记，但具体位置参数或定位轴线仍需明确确认；确认后才能物化CAD候选。"
            ),
        }[row["crossProjectState"]]
        if row["crossProjectState"] == "datum_demo_only" and any(
            case.get("sourceAttachmentCandidateStatus")
            == "source_slot_installation_confirmed_target_interface_pending"
            for case in row["datumPlacementCases"]
        ):
            action = (
                "P000原型已确认支承面与长圆槽外部安装关系，双槽宽6.6 mm、间距82 mm；"
                "接下来匹配A600原生/备用孔位并补齐沿槽位置参数，再执行非原型CAD。"
            )
        if row["crossProjectState"] == "support_position_cumulative_demo_verified" and complete_cross_project_chains:
            action = (
                "已形成六类齐全的跨项目累计定位Demo；优先复核实际执行顺序的等价性和按需演示。"
                "排胶杯仍是支承面加位置参数定位，实际固定方式暂未验证；"
                "不增加直接机械兼容结论，也不表示所有模组可任意互换。"
            )
        disposition_queue.append(
            {
                "groupId": row["groupId"],
                "displayName": row["displayName"],
                "currentState": row["crossProjectState"],
                "recommendedAction": action,
            }
        )
    disposition_queue.sort(key=lambda row: priority_by_group[row["groupId"]])

    core = {
        "schemaVersion": SCHEMA,
        "overallStatus": overall,
        "targetGroupCount": len(TARGET_GROUPS),
        "modulePortCoverageComplete": all_ports_ready,
        "completeRoleChainEvidencePresent": bool(complete_role_chains),
        "completeCrossProjectRoleChainEvidencePresent": bool(complete_cross_project_chains),
        "completeCrossProjectRoleChains": deepcopy(complete_cross_project_chains),
        "verifiedCrossProjectAssemblyOrders": [list(row.get("moduleSequence") or []) for row in complete_cross_project_chains],
        "crossProjectOrderVariationVerified": any(
            row.get("orderEquivalenceVerified") is True
            and (row.get("orderComparisonEvidence") or {}).get("cadEvidenceVerified") is True
            and (row.get("orderComparisonEvidence") or {}).get("status") == "passed"
            for row in complete_cross_project_chains
        ),
        "crossProjectOrderComparisons": list({
            row["orderComparisonEvidence"]["comparisonPath"]: deepcopy(row["orderComparisonEvidence"])
            for row in complete_cross_project_chains if row.get("orderComparisonEvidence")
        }.values()),
        "mechanicallyReviewedCrossProjectCasePresent": bool(reviewed_cross_project),
        "directCrossProjectRoles": direct_roles,
        "directCrossProjectRoleCount": len(direct_roles),
        "groups": group_rows,
        "completeRoleChains": deepcopy(complete_role_chains),
        "reviewedCrossProjectCases": deepcopy(reviewed_cross_project),
        "alternateInstallationRoutes": deepcopy(alternate_routes),
        "parameterizedDatumQueuePresent": parameterized_datum_queue is not None,
        "parameterizedDatumSourceCatalogDigest": datum_source_catalog_digest,
        "parameterizedDatumCanonicalCatalogDigest": (
            str(parameterized_datum_catalog_digest)
            if parameterized_datum_catalog_digest is not None
            else None
        ),
        "parameterizedDatumPairCount": len(datum_rows),
        "parameterizedDatumReleasedPairCount": sum(
            row.get("state") == "released" for row in datum_rows
        ),
        "parameterizedDatumCadReadyPairCount": sum(
            row.get("state") == "ready_for_nonprototype_cad_validation"
            for row in datum_rows
        ),
        "parameterizedDatumDecisionRequiredPairCount": sum(
            row.get("state")
            in {
                "explicit_position_parameters_required",
                "explicit_axis_selection_required",
                "explicit_axis_pair_selection_required",
                "explicit_flexible_slot_selection_required",
            }
            for row in datum_rows
        ),
        "engineeringDispositionQueue": disposition_queue,
        # Backward-compatible alias.  New consumers should use
        # engineeringDispositionQueue because incompatible rows are engineering
        # dispositions, not a promise that software will make them compatible.
        "nextWorkQueue": deepcopy(disposition_queue),
        "claimBoundary": {
            "prototypeTopLevelPoseDefaultAllowed": False,
            "datumPlacementEqualsDirectMechanicalCompatibility": False,
            "alternateSlotCandidateEqualsReleasedCompatibility": False,
            "collisionOrBrepRequiredForCurrentMilestone": False,
            "holePatternMatchRequiredForSupportPositionDemo": False,
            "supportPositionDemoVerifiesActualFixation": False,
            "statement": (
                "当前状态只证明端口、发布授权、非原型CAD定位、累计装配和阶段机械评审；"
                "不代表任意同角色模组均可直接互换，也不代表碰撞、动态工艺或生产放行。"
            ),
        },
    }
    return {**core, "reportDigest": _digest(core)}


def validate_short_term_cross_project_scope_readiness(
    report: dict[str, Any],
) -> dict[str, Any]:
    if report.get("schemaVersion") != SCHEMA:
        raise ShortTermCrossProjectScopeError("不支持的短期范围报告版本。")
    groups = list(report.get("groups") or [])
    expected_ids = [row["groupId"] for row in TARGET_GROUPS]
    if [str(row.get("groupId") or "") for row in groups] != expected_ids:
        raise ShortTermCrossProjectScopeError("六类目标模组顺序或覆盖不完整。")
    expected = _digest({key: value for key, value in report.items() if key != "reportDigest"})
    if report.get("reportDigest") != expected:
        raise ShortTermCrossProjectScopeError("短期范围报告摘要不匹配。")
    return {
        "success": True,
        "overallStatus": report.get("overallStatus"),
        "targetGroupCount": len(groups),
        "reportDigest": expected,
    }


def load_short_term_cross_project_scope_readiness(workspace: Path) -> dict[str, Any]:
    """Load the generated milestone report for API and UI consumers."""

    path = (
        workspace.resolve()
        / "demo/global_assembly_catalog/short-term-cross-project-scope-v1/readiness.json"
    )
    if not path.is_file():
        raise ShortTermCrossProjectScopeError(
            "短期跨项目范围报告尚未生成，请先运行"
            " scripts/build_short_term_cross_project_scope.py。"
        )
    report = json.loads(path.read_text(encoding="utf-8-sig"))
    validate_short_term_cross_project_scope_readiness(report)
    return report
