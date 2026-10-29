#!/usr/bin/env python3
"""Build the exact all-model x all-base coverage and implementation queue."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.broad_combination_coverage import (  # noqa: E402
    build_broad_combination_coverage,
    discover_global_relation_release_pairs,
    validate_broad_combination_coverage,
)
from demo_backend.mechanical_interface_contracts import (  # noqa: E402
    load_calibration_contract_catalog,
    load_cleaning_weighing_contract_catalog,
    load_contextual_scanner_contract_catalog,
    load_contextual_transport_contract_catalog,
    load_native_wastecup_contract_catalog,
    load_scanner_contract_catalog,
    load_transport_contract_catalog,
    load_wastecup_contract_catalog,
)


DEFAULT_OUTPUT = ROOT / "demo/global_assembly_catalog/broad-combination-coverage-v1"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _current_queue() -> dict:
    catalog = _read(
        ROOT
        / "demo/cross_project_substitution/parameterized-datum-placement-v1/"
        "interface-contract-catalog.json"
    )
    digest = str(catalog.get("catalogDigest") or "")
    candidates: list[tuple[int, Path, dict]] = []
    root = ROOT / "demo/cross_project_substitution"
    for path in root.rglob("validation-queue.json"):
        match = re.search(r"-v(\d+)$", path.parent.name)
        version = int(match.group(1)) if match else -1
        payload = _read(path)
        if payload.get("sourceCatalogDigest") == digest:
            candidates.append((version, path, payload))
    if not candidates:
        raise FileNotFoundError("no validation queue matches the canonical datum catalog")
    candidates.sort(key=lambda row: (row[0], str(row[1])))
    return candidates[-1][2]


def _markdown(report: dict) -> str:
    lines = [
        "# 六类全型号 × 多基座覆盖矩阵",
        "",
        f"- 移动模组：{report['summary']['movingModuleCount']}种",
        f"- 基座：{report['summary']['baseCount']}种",
        f"- 精确组合：{report['summary']['expectedPairCount']}组",
        f"- 已发布可执行：{report['summary']['releasedExecutionCount']}组",
        f"- 可进入CAD验证：{report['summary']['cadValidationReadyCount']}组",
        f"- 待位置/单轴/双轴对确认：{report['summary']['engineeringDecisionRequiredCount']}组",
        f"- 当前目录无匹配轴对、需换安装策略：{report['summary']['incompatibleOrAlternateStrategyRequiredCount']}组",
        f"- 待补混合模板或端点：{report['summary']['semanticImplementationRequiredCount']}组",
        "",
        "|角色|模组数|组合数|已发布|待CAD|待工程确认|需换策略|待语义实现|",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["roleSummaries"]:
        lines.append(
            f"|{row['role']}|{row['moduleCount']}|{row['expectedPairCount']}|"
            f"{row['releasedExecutionCount']}|{row['cadValidationReadyCount']}|"
            f"{row['engineeringDecisionRequiredCount']}|"
            f"{row['incompatibleOrAlternateStrategyRequiredCount']}|"
            f"{row['semanticImplementationRequiredCount']}|"
        )
    lines.extend(
        [
            "",
            "## 待语义实现的精确组合",
            "",
        ]
    )
    for row in report["pairs"]:
        if row["state"] in {
            "mixed_support_two_axis_recipe_required",
            "mixed_support_orientation_slot_recipe_required",
            "base_axis_endpoint_capture_required",
            "semantic_port_capture_required",
        }:
            lines.append(
                f"- `{row['moduleDefinitionId']} → {row['baseDefinitionId']}`："
                f"`{row['state']}`"
            )
    lines.extend(
        [
            "",
            "## 结论边界",
            "",
            report["claimBoundary"]["statement"],
            "",
            f"覆盖摘要：`{report['coverageDigest']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    readiness = _read(
            ROOT
            / "demo/global_assembly_catalog/short-term-cross-project-scope-v1/readiness.json"
        )
    groups = {row["groupId"]: row for row in readiness["groups"]}
    base_ids = [
        value.replace(":", "::", 1)
        for value in groups["base_environment"]["projectModuleRefs"]
    ]
    known_ids = {
        value.replace(":", "::", 1)
        for group in readiness["groups"]
        for value in group["projectModuleRefs"]
    }
    report = build_broad_combination_coverage(
        readiness=readiness,
        parameterized_queue=_current_queue(),
        direct_catalogs=[
            load_transport_contract_catalog(ROOT),
            load_contextual_transport_contract_catalog(ROOT),
            load_scanner_contract_catalog(ROOT),
            load_contextual_scanner_contract_catalog(ROOT),
            load_calibration_contract_catalog(ROOT),
            load_cleaning_weighing_contract_catalog(ROOT),
            load_wastecup_contract_catalog(ROOT),
            load_native_wastecup_contract_catalog(ROOT),
        ],
        released_relation_pairs=discover_global_relation_release_pairs(
            ROOT,
            known_definition_ids=known_ids,
            base_definition_ids=base_ids,
        ),
    )
    validate_broad_combination_coverage(report)
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / "coverage.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output / "coverage-CN.md").write_text(_markdown(report), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
