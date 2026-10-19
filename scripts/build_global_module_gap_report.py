#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.global_module_gap_report import (  # noqa: E402
    build_global_module_gap_report,
    validate_global_module_gap_report,
)


DEFAULT_CATALOG = ROOT / "demo/global_assembly_catalog/v1/global_module_catalog.json"
DEFAULT_RELEASES = ROOT / "demo/global_assembly_catalog/releases"
DEFAULT_SAFETY = ROOT / "demo/global_assembly_catalog/relation-driving-safety-v1.json"
DEFAULT_EMPIRICAL_AUDIT = ROOT / (
    "demo/global_assembly_catalog/coverage-v2/"
    "release_pending_rigid_module_evidence_audit.json"
)
DEFAULT_OUTPUT = ROOT / "demo/global_assembly_catalog/coverage-v2"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _release_packages(root: Path) -> list[dict[str, Any]]:
    pattern = re.compile(r"^relation-v\d+-")
    packages: list[dict[str, Any]] = []
    for directory in sorted(root.iterdir()) if root.is_dir() else []:
        catalog_path = directory / "global_module_catalog.json"
        manifest_path = directory / "release-manifest.json"
        if not directory.is_dir() or not pattern.match(directory.name):
            continue
        if not catalog_path.is_file() or not manifest_path.is_file():
            continue
        manifest = _read(manifest_path)
        evidence_path = Path(str(manifest.get("derivationEvidencePath") or ""))
        if evidence_path and not evidence_path.is_absolute():
            evidence_path = ROOT / evidence_path
        evidence = _read(evidence_path) if evidence_path.is_file() else {}
        packages.append(
            {
                "catalog": _read(catalog_path),
                "manifest": manifest,
                "evidence": evidence,
                "catalogPath": str(catalog_path.resolve()),
                "manifestPath": str(manifest_path.resolve()),
                "evidencePath": str(evidence_path.resolve()) if evidence_path else None,
            }
        )
    return packages


def _markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# 全目录模组外部安装端口缺口报告",
        "",
        "## 范围与结论边界",
        "",
        "- 当前项目：Project01、Project02、Project03、Project05。",
        "- Project06暂缓；Project02 A700按当前决策暂缓。",
        "- 本报告只评价外部机械安装端口、完整定位和非原型CAD证据。",
        "- 不评价工艺合理性、转接件、碰撞/B-rep或动态运动。",
        "",
        "## 汇总",
        "",
        f"- 当前范围模组：{summary['activeModuleCount']}",
        f"- 已验证可移植新增模组：{summary['portableVerifiedCount']}",
        f"- 已验证固定环境/槽位提供方：{summary['contextProviderVerifiedCount']}",
        f"- 待补齐模组：{summary['gapModuleCount']}",
        f"- 明确暂缓：{summary['deferredCount']}",
        "",
        "## 模组状态",
        "",
        "|项目模组|角色|状态|机械端口|声明完整模板|兼容边完整模板|已验证模板|下一动作|",
        "|---|---|---|---:|---:|---:|---:|---|",
    ]
    for row in sorted(report["modules"], key=lambda item: str(item["projectModuleRefs"])):
        lines.append(
            f"|{', '.join(row['projectModuleRefs'])}|{row.get('category') or ''}|"
            f"{row['status']}|{row['portableMechanicalPortCount']}|"
            f"{row['declaredCompleteTemplateCount']}|{row['completeInstallationTemplateCount']}|"
            f"{row['verifiedTemplateCount']}|"
            f"{row['nextAction']}|"
        )
    lines.extend(
        [
            "",
            "## 建议补齐队列",
            "",
            "|顺序|项目模组|角色|当前状态|建议动作|阻塞原因|",
            "|---:|---|---|---|---|---|",
        ]
    )
    for index, row in enumerate(report["completionQueue"], start=1):
        lines.append(
            f"|{index}|{', '.join(row['projectModuleRefs'])}|{row.get('category') or ''}|"
            f"{row['status']}|{row['nextAction']}|{', '.join(row['blockers'])}|"
        )
    if not report["completionQueue"]:
        lines.append("|—|—|—|无待补齐项|—|—|")
    lines.extend(
        [
            "",
            "## 状态含义",
            "",
            "- `portable_verified`：已有完整端口、发布授权和非原型CAD闭环证据。",
            "- `context_provider_verified`：作为固定环境或槽位提供方，已有刚性消费者闭环证据。",
            "- `external_pose_evidence_required`：配合执行通过，但未证明外部位姿闭合。",
            "- `cad_evidence_missing`：模板已授权，当前证据仍不完整。",
            "- `release_pending`：端口和完整模板存在，但尚未进入受控发布。",
            "- `installation_bundle_repair_required`：目录虽声明完整，但无锚点CAD实证仍有外部自由度，必须补定位基准。",
            "- `compatibility_edge_missing`：完整模板已经存在，但尚未登记为端口兼容边。",
            "- `template_missing`：稳定机械端点存在，但缺完整定位配合束。",
            "- `endpoint_missing`：缺少可移植机械端点。",
            "- `deferred`：由当前开发范围明确暂缓。",
            "",
            f"报告摘要：`{report['reportDigest']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="生成证据级全目录模组缺口报告。")
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--releases", type=Path, default=DEFAULT_RELEASES)
    parser.add_argument("--safety", type=Path, default=DEFAULT_SAFETY)
    parser.add_argument("--empirical-audit", type=Path, default=DEFAULT_EMPIRICAL_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    base_catalog = _read(args.catalog.resolve())
    packages = _release_packages(args.releases.resolve())
    safety = _read(args.safety.resolve()) if args.safety.resolve().is_file() else None
    empirical_audit = (
        _read(args.empirical_audit.resolve())
        if args.empirical_audit.resolve().is_file()
        else None
    )
    report = build_global_module_gap_report(
        base_catalog,
        packages,
        safety_registry=safety,
        empirical_evidence_audit=empirical_audit,
    )
    validation = validate_global_module_gap_report(report)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "global_module_gap_report.json"
    markdown_path = output / "global_module_gap_report.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    markdown_path.write_text(_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "success": True,
                "validation": validation,
                "summary": report["summary"],
                "outputs": {
                    "json": str(json_path),
                    "markdown": str(markdown_path),
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
