#!/usr/bin/env python3
"""Build a reviewable cross-project replacement candidate matrix."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from time import perf_counter
from typing import Any


WORKSPACE = Path(__file__).resolve().parents[1]
BACKEND_SRC = WORKSPACE / "apps" / "demo-backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.cross_project_module_substitution import (  # noqa: E402
    build_cross_project_candidate_matrix,
    build_module_role_overlay,
)


DEFAULT_CATALOG = (
    WORKSPACE / "demo" / "global_assembly_catalog" / "v1" / "global_module_catalog.json"
)
DEFAULT_RELEASES = WORKSPACE / "demo" / "global_assembly_catalog" / "releases"
DEFAULT_OUTPUT = (
    WORKSPACE / "demo" / "cross_project_substitution" / "coverage-v1"
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _latest_project_release_paths(releases: Path) -> list[Path]:
    latest: dict[str, tuple[int, Path]] = {}
    pattern = re.compile(r"^relation-v(?P<version>\d+)-(?P<project>project\d+)-")
    for directory in releases.iterdir() if releases.is_dir() else []:
        if not directory.is_dir():
            continue
        match = pattern.match(directory.name)
        catalog = directory / "global_module_catalog.json"
        if not match or not catalog.is_file():
            continue
        project = match.group("project")
        version = int(match.group("version"))
        previous = latest.get(project)
        if previous is None or version > previous[0]:
            latest[project] = (version, catalog)
    return [latest[key][1] for key in sorted(latest)]


def _all_project_release_paths(releases: Path) -> list[Path]:
    """Return every immutable project release catalog for authorization audit.

    Candidate inference intentionally consumes only the newest catalog for each
    project, while a direct-execution authorization remains valid evidence in
    the immutable release that issued it.  Keeping these two source sets
    separate avoids both stale candidate inference and lost historical
    authorization.
    """

    pattern = re.compile(r"^relation-v\d+-project\d+-")
    return sorted(
        directory / "global_module_catalog.json"
        for directory in releases.iterdir() if releases.is_dir()
        if directory.is_dir()
        and pattern.match(directory.name)
        and (directory / "global_module_catalog.json").is_file()
    )


def _released_direct_executions(release_paths: list[Path]) -> list[dict[str, Any]]:
    """Return only cross-project templates authorized by immutable releases."""

    records_by_template: dict[str, dict[str, Any]] = {}
    for catalog_path in release_paths:
        manifest_path = catalog_path.with_name("release-manifest.json")
        if not manifest_path.is_file():
            continue
        catalog = _read_json(catalog_path)
        manifest = _read_json(manifest_path)
        authorized_ids = set(
            (manifest.get("scope") or {}).get("authorizedDrivingTemplateIds") or []
        )
        ports = {
            str(row.get("globalPortId") or ""): row
            for row in catalog.get("semanticPorts") or []
        }
        definitions = {
            str(row.get("moduleDefinitionId") or ""): row
            for row in catalog.get("moduleDefinitions") or []
        }
        for template in catalog.get("connectionTemplates") or []:
            template_id = str(template.get("globalTemplateId") or "")
            if template_id not in authorized_ids:
                continue
            port_ids = {
                *(template.get("candidatePortIdsA") or []),
                *(template.get("candidatePortIdsB") or []),
            }
            definition_ids = {
                str(ports[port_id].get("moduleDefinitionId") or "")
                for port_id in port_ids
                if port_id in ports
            }
            project_ids = {
                str(alias.get("projectId") or "").lower()
                for definition_id in definition_ids
                for alias in (
                    definitions.get(definition_id, {}).get("projectAliases") or []
                )
                if str(alias.get("projectId") or "").strip()
            }
            if len(project_ids) < 2:
                continue
            provenance = template.get("provenance") or {}
            record = {
                    "status": "released_direct_execution",
                    "releaseId": manifest.get("releaseId"),
                    "releaseManifestPath": str(manifest_path.resolve()),
                    "globalTemplateId": template_id,
                    "legacyTemplateId": template.get("legacyTemplateId"),
                    "projectIds": sorted(project_ids),
                    "moduleDefinitionIds": sorted(definition_ids),
                    "sourceModuleTemplateId": provenance.get(
                        "sourceModuleTemplateId"
                    ),
                    "targetSlotTemplateId": provenance.get("targetSlotTemplateId"),
                    "collisionStatus": "not_evaluated",
                }
            previous = records_by_template.get(template_id)
            if previous is None or str(record["releaseId"]) > str(
                previous["releaseId"]
            ):
                records_by_template[template_id] = record
    return sorted(
        records_by_template.values(),
        key=lambda row: (
            str(row.get("releaseId") or ""),
            str(row.get("globalTemplateId") or ""),
        ),
    )


def _markdown(matrix: dict[str, Any], source_paths: list[Path]) -> str:
    counts = matrix["statusCounts"]
    active_counts = matrix["activeStatusCounts"]
    lines = [
        "# 全目录跨项目同角色模组替换候选矩阵",
        "",
        "## 汇总",
        "",
        f"- 模组定义：{matrix['moduleDefinitionCount']}",
        f"- 有向跨项目同角色组合：{matrix['directionalPairCount']}",
        f"- 已发布可直接执行：{counts['released_direct_execution']}",
        f"- 可直接组合有效图：{counts['ready_for_effective_graph_composition']}",
        f"- 需要机械几何复核：{counts['needs_mechanical_geometry_review']}",
        f"- 需要模板消歧：{counts['needs_template_disambiguation']}",
        f"- 缺少端口或模板：{counts['needs_endpoint_or_template']}",
        f"- 已确认不兼容：{counts['incompatible']}",
        f"- 当前开发范围内组合：{matrix['activeDirectionalPairCount']}（延期 {matrix['deferredDirectionalPairCount']}）",
        f"- 当前范围缺少端口或模板：{active_counts['needs_endpoint_or_template']}",
        f"- 当前范围已发布可直接执行：{active_counts['released_direct_execution']}",
        f"- 当前范围可直接组合有效图：{active_counts['ready_for_effective_graph_composition']}",
        f"- 当前范围闭合状态：{matrix['activeCoverageClosure']['status']}",
        f"- 当前范围未决组合：{matrix['activeCoverageClosure']['unresolvedDirectionalPairCount']}",
        f"- 跨项目不可变发布关系：{matrix['releasedDirectExecutionCount']}",
        f"- 延期项目：{', '.join(matrix['policy']['deferredProjectIds']) or '无'}",
        "- 碰撞/B-rep：本阶段不要求，未参与候选分级。",
        "",
        "## 证据目录",
        "",
    ]
    lines.extend(f"- `{path}`" for path in source_paths)
    lines.extend(
        [
            "",
            "## 按角色聚合",
            "",
            "|角色|活动组合|已发布直接执行|可组合|不兼容|延期缺口|",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in matrix.get("roleSummaries") or []:
        active = row["activeStatusCounts"]
        total = row["statusCounts"]
        lines.append(
            f"|{row['group']}|{row['activeDirectionalPairCount']}|"
            f"{active['released_direct_execution']}|"
            f"{active['ready_for_effective_graph_composition']}|"
            f"{active['incompatible']}|"
            f"{total['needs_endpoint_or_template'] - active['needs_endpoint_or_template']}|"
        )
    lines.extend(
        [
            "",
            "## 按项目方向聚合",
            "",
            "|项目方向|活动组合|已发布直接执行|可组合|不兼容|延期组合|",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in matrix.get("projectPairSummaries") or []:
        active = row["activeStatusCounts"]
        lines.append(
            f"|{row['group']}|{row['activeDirectionalPairCount']}|"
            f"{active['released_direct_execution']}|"
            f"{active['ready_for_effective_graph_composition']}|"
            f"{active['incompatible']}|"
            f"{row['directionalPairCount'] - row['activeDirectionalPairCount']}|"
        )
    lines.extend(
        [
            "",
            "## 推荐下一候选",
            "",
            "|状态|角色|源模组|目标槽位|主要缺口|",
            "|---|---|---|---|---|",
        ]
    )
    for row in matrix.get("recommendedNextCandidates") or []:
        source = f"{','.join(row['sourceProjectIds'])}:{','.join(row['sourceModuleTokens'])}"
        target = f"{','.join(row['targetProjectIds'])}:{','.join(row['targetModuleTokens'])}"
        blockers = ", ".join(item["code"] for item in row.get("blockers") or []) or "无"
        lines.append(
            f"|{row['status']}|{row['primaryRole']}|{source}|{target}|{blockers}|"
        )
    lines.extend(
        [
            "",
            "## 判定说明",
            "",
            "- `released_direct_execution`：已经取得不可变发布授权，可由自然语言直接编译并驱动CAD；不再作为新的有效图组合候选。",
            "- `ready_for_effective_graph_composition`：角色、接口、配合拓扑、可移植性和定位几何均通过，可进入有效图组合。",
            "- `needs_mechanical_geometry_review`：接口和配合拓扑一致，但现有端点不足以自动比较定位几何。",
            "- `needs_template_disambiguation`：同一模组存在多个零自由度安装模板，需要指定实际槽位。",
            "- `needs_endpoint_or_template`：至少一侧尚无完整零自由度安装端口。",
            "- `incompatible`：已发现接口、配合拓扑或定位几何硬冲突，不应直接替换。",
            "- 原子安装端口至少包含两项驱动配合；单个辅助/防转关系不独立代表一个可定位安装接口。",
            "- `required`表示模组自身安装端口，`provided`表示该模组向其他模组提供的槽位；两者不混计。",
            "- 多安装配置先按目标槽位上下文自动选择；硬性机械冲突优先于模板消歧报告。",
            "",
            "该矩阵只消费既有不可变发布作为证据，不修改任何历史发布。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--releases", type=Path, default=DEFAULT_RELEASES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    started = perf_counter()
    catalog_path = args.catalog.resolve()
    release_paths = _latest_project_release_paths(args.releases.resolve())
    source_paths = [catalog_path, *release_paths]
    catalogs = [_read_json(path) for path in source_paths]
    direct_executions = _released_direct_executions(
        _all_project_release_paths(args.releases.resolve())
    )
    catalog = catalogs[0]
    overlay = build_module_role_overlay(catalog)
    matrix = build_cross_project_candidate_matrix(
        catalog,
        overlay,
        evidence_catalogs=catalogs,
        deferred_project_ids={"project06"},
        released_direct_executions=direct_executions,
    )
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    matrix_path = output / "cross_project_candidate_matrix.json"
    markdown_path = output / "cross_project_candidate_matrix.md"
    summary_path = output / "build_summary.json"
    _write_json(matrix_path, matrix)
    markdown_path.write_text(_markdown(matrix, source_paths), encoding="utf-8")
    summary = {
        "schemaVersion": "cross-project-candidate-matrix-build/v1",
        "success": True,
        "matrixDigest": matrix["matrixDigest"],
        "statusCounts": matrix["statusCounts"],
        "activeStatusCounts": matrix["activeStatusCounts"],
        "activeCoverageClosure": matrix["activeCoverageClosure"],
        "deferredDirectionalPairCount": matrix["deferredDirectionalPairCount"],
        "sourceCatalogPaths": [str(path) for path in source_paths],
        "outputPaths": {
            "matrix": str(matrix_path),
            "markdown": str(markdown_path),
        },
        "durationSeconds": round(perf_counter() - started, 6),
    }
    _write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
