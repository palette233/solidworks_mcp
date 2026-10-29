"""Consolidate station-gap engineering choices without granting CAD authority."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA = "station-engineering-decision-summary/v1"


DECISION_GUIDANCE = {
    "target_functional_geometry_mismatch": {
        "question": (
            "当前功能点或目标区域与候选安装位置不一致；请选择其他目标工位，"
            "或给出可接受的显式残差及工程容差。"
        ),
        "requiredDecision": "alternate_station_or_explicit_residual_policy",
    },
    "target_function_point_height_decision_required": {
        "question": (
            "平面投影已满足，但功能点高度仍有残差；请确认显式高度偏移，"
            "或选择其他目标工位。"
        ),
        "requiredDecision": "height_offset_or_alternate_station",
    },
    "target_function_point_height_and_interface_review_required": {
        "question": (
            "柔性槽或定位轴尚未唯一；请同时选择具体接口基准和功能点高度偏移。"
        ),
        "requiredDecision": "exact_interface_and_height_offset",
    },
    "target_service_capability_semantic_mapping_decision_required": {
        "question": (
            "目标项目存在近似功能提供者，但语义不完全一致；请确认能力等价关系，"
            "或指定承担每项服务能力的实际模组。"
        ),
        "requiredDecision": "capability_equivalence_or_explicit_providers",
    },
    "transport_work_area_context_and_policy_required": {
        "question": (
            "传输工作区间距或上下文不同；请确认载具/轨道适配、工作位间距容差，"
            "并选择用于后检的工艺上下文。"
        ),
        "requiredDecision": "transport_context_and_spacing_policy",
    },
    "target_station_engineering_confirmation_required": {
        "question": (
            "已有目标原生工位建议；请确认该工位参数以及轨道、载具和工作区适配。"
        ),
        "requiredDecision": "confirm_target_native_station_and_work_area",
    },
    "scanner_role_selection_from_candidate_catalog_required": {
        "question": (
            "扫描源或条码目标存在多个有限候选；请从目录中选择读头、出光方向、"
            "载具码或产品码角色。"
        ),
        "requiredDecision": "scanner_head_direction_and_or_barcode_target_role",
    },
}


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _relative(workspace: Path, path: Path) -> str:
    return path.resolve().relative_to(workspace.resolve()).as_posix()


def _evidence_references(row: dict[str, Any]) -> list[dict[str, Any]]:
    references: list[dict[str, Any]] = []
    for key in (
        "transportWorkAreaReview",
        "scannerRuleReadiness",
        "functionalGeometryScreening",
        "candidateDecision",
        "serviceCapabilityCoverage",
    ):
        value = row.get(key)
        if not isinstance(value, dict):
            continue
        reference = {"kind": key}
        for field in (
            "reportPath",
            "reportSha256",
            "status",
            "comparisonDigest",
            "sourceOpticalCandidateCatalogPath",
            "transportBarcodeTargetCandidateCatalogPath",
        ):
            if value.get(field) not in (None, "", []):
                reference[field] = value[field]
        if len(reference) > 1:
            references.append(reference)
    return references


def build_station_engineering_decision_summary(
    workspace: Path, gap_report_path: Path
) -> dict[str, Any]:
    workspace = workspace.resolve()
    gap_report_path = gap_report_path.resolve()
    gap_report_path.relative_to(workspace)
    report = _read(gap_report_path)
    if report.get("schemaVersion") != "station-gap-batch-preparation/v1":
        raise ValueError("unsupported station gap report")

    rows = [
        row
        for row in report.get("queue") or []
        if row.get("workClass") == "engineering_decision"
    ]
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        category = str(row.get("gapCategory") or "")
        if category not in DECISION_GUIDANCE:
            raise ValueError(f"engineering decision category has no guidance: {category}")
        role = str(row.get("role") or "")
        groups.setdefault((role, category), []).append(row)

    topics: list[dict[str, Any]] = []
    for (role, category), members in sorted(groups.items()):
        guidance = DECISION_GUIDANCE[category]
        exact_pairs = []
        for row in sorted(
            members,
            key=lambda item: (
                str(item.get("sourceModuleDefinitionId") or ""),
                str(item.get("targetBaseDefinitionId") or ""),
            ),
        ):
            exact_pairs.append(
                {
                    "sourceModuleDefinitionId": row["sourceModuleDefinitionId"],
                    "targetBaseDefinitionId": row["targetBaseDefinitionId"],
                    "gapCategory": category,
                    "evidenceReferences": _evidence_references(row),
                }
            )
        topic_core = {
            "role": role,
            "gapCategory": category,
            "question": guidance["question"],
            "requiredDecision": guidance["requiredDecision"],
            "pairCount": len(exact_pairs),
            "exactPairs": exact_pairs,
            "confirmed": False,
            "cadLaunchAllowed": False,
        }
        topics.append(
            {
                "topicId": "engineering-decision/" + _digest(topic_core)[:16],
                **topic_core,
            }
        )

    core = {
        "schemaVersion": SCHEMA,
        "sourceGapReport": {
            "path": _relative(workspace, gap_report_path),
            "sha256": _sha256(gap_report_path),
        },
        "status": "engineering_confirmation_required" if rows else "no_decisions",
        "decisionPairCount": len(rows),
        "topicCount": len(topics),
        "topics": topics,
        "confirmed": False,
        "cadLaunchAllowed": False,
        "boundary": (
            "This summary only consolidates engineering choices. It does not accept "
            "residuals, infer semantic equivalence, select scanner roles or authorize CAD."
        ),
    }
    return {**core, "summaryDigest": _digest(core)}


def validate_station_engineering_decision_summary(report: dict[str, Any]) -> None:
    if report.get("schemaVersion") != SCHEMA:
        raise ValueError("unsupported decision summary")
    digest = report.get("summaryDigest")
    core = {key: value for key, value in report.items() if key != "summaryDigest"}
    if digest != _digest(core):
        raise ValueError("decision summary digest mismatch")
    topics = report.get("topics") or []
    if report.get("decisionPairCount") != sum(
        int(topic.get("pairCount") or 0) for topic in topics
    ):
        raise ValueError("decision pair count changed")
    if report.get("topicCount") != len(topics):
        raise ValueError("decision topic count changed")
    if any(
        topic.get("confirmed") is not False
        or topic.get("cadLaunchAllowed") is not False
        for topic in topics
    ):
        raise ValueError("unconfirmed summary cannot authorize CAD")
