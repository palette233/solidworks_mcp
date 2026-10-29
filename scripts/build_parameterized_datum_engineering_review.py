#!/usr/bin/env python3
"""Build unconfirmed multi-role datum engineering decisions."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.parameterized_datum_engineering_review import (  # noqa: E402
    build_axis_pair_confirmation_template,
    build_confirmation_templates,
    build_flexible_slot_confirmation_template,
    build_manual_input_barrier,
    build_parameterized_datum_engineering_review,
    build_prioritized_mixed_recommendation_batch,
)
from demo_backend.parameterized_datum_position_decisions import (  # noqa: E402
    build_prioritized_position_recommendation_batch,
    build_priority_batch_confirmation_template,
    build_position_decision_request_template,
)
from demo_backend.parameterized_datum_geometry_decisions import (  # noqa: E402
    build_geometry_decision_request_template,
)


def _write(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _focused_position_template(template: dict, *, recommendation_available: bool) -> dict:
    """Return a digest-protected partial request template for one review path."""

    core = {
        key: value
        for key, value in template.items()
        if key not in {"requests", "requestTemplateDigest"}
    }
    core["requests"] = [
        row
        for row in template.get("requests") or []
        if row.get("recommendationAvailable") is recommendation_available
    ]
    core["templateSubset"] = (
        "recommendation_acceptance_review"
        if recommendation_available
        else "explicit_position_input_required"
    )
    digest = hashlib.sha256(
        json.dumps(
            core, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    return {**core, "requestTemplateDigest": digest}


def _markdown(review: dict) -> str:
    lines = [
        "# 参数化基准待确认工程决策",
        "",
        "以下各项均不是CAD执行授权。已有同角色工位时给出参考建议；没有同角色工位时明确要求工程师填写三个位置参数，系统不会猜测。",
        "位置决策同时拆分为`position-recommendation-acceptance-template.json`和`position-manual-input-template.json`，便于分别审核已有建议与必须手填的组合；两份模板默认均未确认。",
        "",
        "|模组|目标基座|决策|参考原生模组|系统推荐|状态|",
        "|---|---|---|---|---|---|",
    ]
    for row in review["decisions"]:
        candidate_stations = row["reference"].get("candidateRoleStations") or []
        reference = row["reference"].get("referenceModuleDefinitionId") or (
            "候选："
            + "、".join(
                candidate["referenceModuleDefinitionId"]
                for candidate in candidate_stations
            )
            if candidate_stations
            else "无已登记同角色工位"
        )
        if row["decisionKind"] == "position_parameters":
            p = row["recommendedParametersMeters"]
            recommendation = (
                f"纵向 {p['longitudinal'] * 1000:.3f} mm；"
                f"横向 {p['lateral'] * 1000:.3f} mm；"
                f"支承间隙 {p['supportGap'] * 1000:.3f} mm"
                if isinstance(p, dict)
                else "需填写纵向、横向和支承间隙"
            )
            decision = "工位参数"
        elif row["decisionKind"] == "axis_selection":
            if row.get("recommendedAxisEndpointId"):
                recommendation = (
                    f"`{row['recommendedAxisEndpointId']}`；"
                    f"距参考工位 "
                    f"{row['recommendedAxisDistanceMeters'] * 1000:.3f} mm"
                )
            else:
                recommendation = (
                    "需先在多个扫描工位间消歧，再从 "
                    f"{int(row.get('availableAxisLineCount') or 0)} 条稳定轴线中选择"
                    if candidate_stations
                    else "需先确认扫描工位，再从 "
                    f"{int(row.get('availableAxisLineCount') or 0)} 条稳定轴线中选择"
                )
            decision = "定位轴线"
        elif row["decisionKind"] == "axis_pair_selection":
            recommendation = (
                f"`{row['recommendedCandidatePairId']}`；"
                f"双点RMS {row['recommendedPairRmsMeters'] * 1000:.3f} mm；"
                f"主次轴映射 {row['recommendedAxisAssignment']}"
                if row.get("recommendedCandidatePairId")
                else f"从 {row['candidatePairCount']} 组"
                f"{row['reference']['requiredSpacingMeters'] * 1000:.1f} mm轴对中确认一组"
            )
            decision = "双定位轴"
        else:
            if row.get("recommendedAxisEndpointId"):
                recommendation = (
                    f"`{row['recommendedAxisEndpointId']}`；"
                    f"距原生语义工位 "
                    f"{row['recommendedAxisDistanceMeters'] * 1000:.3f} mm；"
                    f"纵向距离 {row['recommendedLongitudinalOffsetMeters'] * 1000:.3f} mm"
                )
            else:
                recommendation = (
                    f"从 {row['reference']['candidateAxisLineCount']} 条稳定轴线中"
                    "选择一条，并填写纵向距离"
                )
            decision = "柔性槽轴＋距离"
        lines.append(
            f"|{row['moduleDefinitionId']}|{row['slotDefinitionId']}|{decision}|"
            f"{reference}|{recommendation}|待工程确认|"
        )
    lines.extend(
        [
            "",
            "## 确认边界",
            "",
            "- A180推荐复用目标基座同项目原生扫描模组的功能工位投影，不代表A180外形和光学通道已经验证。",
            "- F000推荐选择最接近该功能工位的稳定圆柱轴，只是候选排序；孔用途、安装侧和紧固方式仍需确认。",
            "- BD00/AH00/SS00/AE00可用各自原型中已发布的主、次定位孔工位对A000轴对进行排序；首选轴对及主次映射仍须确认，孔距一致不等于机械兼容。",
            "- G000可按A000已发布原生语义工位对目标基座稳定轴线排序，并建议复用482 mm关系参数；它们只用于审阅，仍须同时确认目标轴线、槽可达性、安装侧和纵向距离。",
            "- A300/P000若目标基座已有排胶工位则可作为位置建议；没有工位时模板保留空参数，必须人工填写。",
            "- 原生角色工位建议由原型中已发布关系的面几何测量得到，只用于审阅；原型顶层位姿不会写入接口合同，也不会作为CAD执行权限。",
            "- 若同一精确模组在至少两个其他基座登记了完全一致的语义坐标，系统可给出跨基座共识建议；该建议不代表目标基座包络已经验证，仍必须人工确认。",
            "- 模板默认`confirmed=false`，不能直接传入CAD验证队列。",
            "- 确认后仍需非原型初始位姿、真实配合、完全约束、保存重开和不可变发布。",
            "- 碰撞/B-rep及生产放行不属于本审阅包。",
            "- `first-batch-position-recommendations.json`只选取5～8项证据最强的位置建议作为首批审阅；其中所有`confirmed`仍为false。",
            "",
            f"审阅摘要：`{review['reviewDigest']}`",
            "",
        ]
    )
    return "\n".join(lines)


def _first_batch_markdown(batch: dict) -> str:
    lines = [
        "# 第一批位置建议确认清单",
        "",
        "本清单是系统依据现有原型工位和跨基座一致参数筛出的首批高置信建议。它不是CAD执行授权；机械工程师应逐项选择接受、修改或拒绝。",
        "",
        "|序号|模组→基座|角色|推荐位置（mm）|依据|确认结果|",
        "|---:|---|---|---|---|---|",
    ]
    labels = {
        "target_base_registered_role_station": "目标基座已有同角色工位",
        "prototype_native_role_station_review_evidence": "原型原生同角色工位（仅审阅）",
        "exact_module_native_station_demo_projection": "同一精确模组原型工位投影（Demo候选）",
        "exact_module_cross_base_consensus": "同一模组跨至少两个基座位置一致",
        "other_review_recommendation": "其他可审计建议",
    }
    for index, row in enumerate(batch["selected"], start=1):
        p = row["recommendedParametersMeters"]
        position = (
            f"纵向 {p['longitudinal'] * 1000:.3f}；"
            f"横向 {p['lateral'] * 1000:.3f}；"
            f"支承 {p['supportGap'] * 1000:.3f}"
        )
        lines.append(
            f"|{index}|{row['moduleDefinitionId']} → {row['slotDefinitionId']}|"
            f"{row['moduleRole']}|{position}|"
            f"{labels.get(row['evidenceClass'], row['evidenceClass'])}|待确认|"
        )
    lines.extend(
        [
            "",
            "## 统一确认方式",
            "",
            "请对每项标记为：`接受建议`、`修改参数`或`拒绝该组合`。只有明确接受或给出修改参数的项目，才会被编译为非原型CAD候选。",
            "",
            "接受建议只确认CAD基准位置，不代表孔槽紧固、碰撞/B-rep、包络、工艺或生产可用性已经通过。",
            "",
            f"批次摘要：`{batch['batchDigest']}`",
            "",
        ]
    )
    return "\n".join(lines)


def _mixed_batch_markdown(
    batch: dict, *, title: str = "下一批跨类型工程建议"
) -> str:
    lines = [
        f"# {title}",
        "",
        "本批把剩余可靠的位置、单轴、双轴对与柔性槽建议合并审阅，以保持每批5～8项。所有项目仍为未确认状态，不会启动CAD。",
        "",
        "|序号|模组→基座|决策|系统建议|证据|确认结果|",
        "|---:|---|---|---|---|---|",
    ]
    for index, row in enumerate(batch["selected"], start=1):
        recommendation = row["recommendation"]
        if row["decisionKind"] == "position_parameters":
            p = recommendation["parametersMeters"]
            value = (
                f"纵向 {p['longitudinal'] * 1000:.3f} mm；"
                f"横向 {p['lateral'] * 1000:.3f} mm；"
                f"支承 {p['supportGap'] * 1000:.3f} mm"
            )
            decision = "位置参数"
        elif row["decisionKind"] == "axis_selection":
            value = (
                f"轴线 `{recommendation['selectedAxisEndpointId']}`；"
                f"距参考工位 {recommendation['axisDistanceMeters'] * 1000:.3f} mm"
            )
            decision = "扫描定位轴"
        elif row["decisionKind"] == "axis_pair_selection":
            value = (
                f"轴对 `{recommendation['selectedCandidatePairId']}`；"
                f"双点RMS {recommendation['pairRmsMeters'] * 1000:.3f} mm；"
                f"映射 {recommendation['axisAssignment']}"
            )
            decision = "双定位轴"
        else:
            value = (
                f"轴线 `{recommendation['selectedAxisEndpointId']}`；"
                f"距原生语义工位 {recommendation['axisDistanceMeters'] * 1000:.3f} mm；"
                f"纵向距离 {recommendation['longitudinalOffsetMeters'] * 1000:.3f} mm"
            )
            decision = "柔性槽轴＋距离"
        lines.append(
            f"|{index}|{row['moduleDefinitionId']} → {row['slotDefinitionId']}|"
            f"{decision}|{value}|{row['evidenceClass']}|待确认|"
        )
    deferred = batch.get("deferred") or []
    if deferred:
        lines.extend(
            [
                "",
                "## 延后到下一批",
                "",
                "以下建议已有证据，但受每批最多8项限制未纳入本批；它们仍为未确认状态，不会单独启动CAD：",
                "",
            ]
        )
        for row in deferred:
            lines.append(
                f"- `{row['moduleDefinitionId']} → {row['slotDefinitionId']}`（{row['decisionKind']}）"
            )
    lines.extend(
        [
            "",
            "位置建议只确认CAD语义坐标；轴线及柔性槽建议还必须确认孔用途、安装侧和槽可达性。接受后仍需非原型初始位姿、真实配合、完全约束、保存重开和不可变发布。",
            "",
            f"批次摘要：`{batch['batchDigest']}`",
            "",
        ]
    )
    return "\n".join(lines)


def _manual_barrier_markdown(barrier: dict) -> str:
    lines = [
        "# 必须由机械工程确认的位置缺口",
        "",
        "以下精确组合已有稳定三基准，可以执行明确的位置参数；但现有证据不能唯一决定合理工位，因此系统不会猜测，也不会启动CAD。",
        "",
        "|模组→基座|角色|缺少的信息|可选处理|",
        "|---|---|---|---|",
    ]
    for row in barrier.get("pairs") or []:
        lines.append(
            f"|{row['moduleDefinitionId']} → {row['slotDefinitionId']}|"
            f"{row['moduleRole']}|纵向、横向、支承间隙|填写三个语义坐标，或明确拒绝该组合|"
        )
    lines.extend(
        [
            "",
            "已知原生工位若属于双轴、柔性槽等另一接口族，不能直接当作三平面位置；除非补充两种接口之间的语义偏移。原型顶层位姿、最近点和零坐标均不作为替代。",
            "",
            f"清单摘要：`{barrier['barrierCatalogDigest']}`",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--axis-candidate-limit", type=int, default=5)
    parser.add_argument(
        "--allow-exact-module-native-station-demo-projection",
        action="store_true",
        help=(
            "Explicitly enable Demo-only projection of an exact module's measured "
            "native semantic coordinates into another registered base frame."
        ),
    )
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite engineering review: {output}")
    review = build_parameterized_datum_engineering_review(
        ROOT,
        ranked_axis_limit=args.axis_candidate_limit,
        allow_exact_module_native_station_demo_projection=(
            args.allow_exact_module_native_station_demo_projection
        ),
    )
    manual_barrier = build_manual_input_barrier(review)
    position, axes = build_confirmation_templates(review)
    axis_pairs = build_axis_pair_confirmation_template(review)
    flexible_slots = build_flexible_slot_confirmation_template(review)
    position_language_requests = build_position_decision_request_template(review)
    first_batch = build_prioritized_position_recommendation_batch(review, limit=8)
    first_batch_confirmation = build_priority_batch_confirmation_template(first_batch)
    mixed_batch = build_prioritized_mixed_recommendation_batch(review, limit=8)
    mixed_pairs = {
        (row["moduleDefinitionId"], row["slotDefinitionId"])
        for row in mixed_batch["selected"]
    }
    following_batch = build_prioritized_mixed_recommendation_batch(
        review,
        limit=8,
        exclude_pairs=mixed_pairs,
    )
    geometry_requests = build_geometry_decision_request_template(review)
    output.mkdir(parents=True)
    _write(output / "engineering-review.json", review)
    _write(output / "manual-input-barrier.json", manual_barrier)
    (output / "MECHANICAL-INPUT-REQUIRED-CN.md").write_text(
        _manual_barrier_markdown(manual_barrier), encoding="utf-8"
    )
    _write(
        output / "native-role-station-evidence.json",
        review["nativeRoleStationEvidence"],
    )
    _write(
        output / "two-axis-native-station-evidence.json",
        review["twoAxisNativeStationEvidence"],
    )
    _write(output / "position-confirmation-template.json", position)
    _write(output / "axis-confirmation-template.json", axes)
    _write(output / "axis-pair-confirmation-template.json", axis_pairs)
    _write(output / "flexible-slot-confirmation-template.json", flexible_slots)
    _write(
        output / "position-language-request-template.json",
        position_language_requests,
    )
    _write(output / "first-batch-position-recommendations.json", first_batch)
    _write(
        output / "first-batch-position-confirmation-template.json",
        first_batch_confirmation,
    )
    (output / "FIRST-BATCH-REVIEW-CN.md").write_text(
        _first_batch_markdown(first_batch), encoding="utf-8"
    )
    _write(output / "next-batch-mixed-recommendations.json", mixed_batch)
    _write(
        output / "next-batch-position-confirmation-template.json",
        first_batch_confirmation,
    )
    selected_axis_pairs = {
        (row["moduleDefinitionId"], row["slotDefinitionId"])
        for row in mixed_batch["selected"]
        if row["decisionKind"] == "axis_selection"
    }
    _write(
        output / "next-batch-axis-confirmation-template.json",
        {
            **axes,
            "pairs": [
                row
                for row in axes.get("pairs") or []
                if (row["moduleDefinitionId"], row["slotDefinitionId"])
                in selected_axis_pairs
            ],
        },
    )
    selected_flexible_pairs = {
        (row["moduleDefinitionId"], row["slotDefinitionId"])
        for row in mixed_batch["selected"]
        if row["decisionKind"] == "flexible_slot_selection"
    }
    _write(
        output / "next-batch-flexible-slot-confirmation-template.json",
        {
            **flexible_slots,
            "pairs": [
                row
                for row in flexible_slots.get("pairs") or []
                if (row["moduleDefinitionId"], row["slotDefinitionId"])
                in selected_flexible_pairs
            ],
        },
    )
    selected_axis_pair_pairs = {
        (row["moduleDefinitionId"], row["slotDefinitionId"])
        for row in mixed_batch["selected"]
        if row["decisionKind"] == "axis_pair_selection"
    }
    _write(
        output / "next-batch-axis-pair-confirmation-template.json",
        {
            **axis_pairs,
            "pairs": [
                row
                for row in axis_pairs.get("pairs") or []
                if (row["moduleDefinitionId"], row["slotDefinitionId"])
                in selected_axis_pair_pairs
            ],
        },
    )
    (output / "NEXT-BATCH-REVIEW-CN.md").write_text(
        _mixed_batch_markdown(mixed_batch), encoding="utf-8"
    )
    _write(
        output / "following-batch-mixed-recommendations.json",
        following_batch,
    )
    _write(
        output / "following-batch-geometry-decision-request-template.json",
        geometry_requests,
    )
    (output / "FOLLOWING-BATCH-REVIEW-CN.md").write_text(
        _mixed_batch_markdown(
            following_batch,
            title="后继八项几何选择工程建议",
        ),
        encoding="utf-8",
    )
    _write(
        output / "position-recommendation-acceptance-template.json",
        _focused_position_template(
            position_language_requests, recommendation_available=True
        ),
    )
    _write(
        output / "position-manual-input-template.json",
        _focused_position_template(
            position_language_requests, recommendation_available=False
        ),
    )
    _write(output / "geometry-decision-request-template.json", geometry_requests)
    # Keep the original filenames as compatibility aliases for existing
    # documentation and automation; their contents are now multi-role.
    _write(output / "A180-position-confirmation-template.json", position)
    _write(output / "F000-axis-confirmation-template.json", axes)
    (output / "README-CN.md").write_text(_markdown(review), encoding="utf-8")
    print(
        json.dumps(
            {
                "decisionCount": review["decisionCount"],
                "positionDecisionCount": review["positionDecisionCount"],
                "axisDecisionCount": review["axisDecisionCount"],
                "axisPairDecisionCount": review["axisPairDecisionCount"],
                "flexibleSlotDecisionCount": review["flexibleSlotDecisionCount"],
                "allRecommendationsUnconfirmed": review[
                    "allRecommendationsUnconfirmed"
                ],
                "reviewDigest": review["reviewDigest"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
