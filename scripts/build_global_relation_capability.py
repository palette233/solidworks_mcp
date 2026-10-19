#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "demo-backend" / "src"))

from demo_backend.global_module_catalog import validate_global_module_catalog
from demo_backend.global_module_port_coverage import (
    assess_module_selection_readiness,
    build_global_module_port_coverage_matrix,
)
from demo_backend.global_relation_semantics import (
    build_relation_capability_matrix,
    parse_relation_intent,
    validate_relation_capability_matrix,
)


INITIAL_SUPPORT_CHAINS = {
    "project02_process_core": [
        "project02:A600",
        "project02:A800",
        "project02:A180",
        "project02:A500",
        "project02:A700",
    ],
    "project03_process_core": [
        "project03:AA00",
        "project03:AE00",
        "project03:AI00",
        "project03:AH00",
        "project03:AJ00",
    ],
    "project05_process_core": [
        "project05:A000",
        "project05:M000",
        "project05:F000",
        "project05:P000",
        "project05:G000",
    ],
}


LANGUAGE_CASES = [
    {"id": "install-cn", "text": "将扫描模组安装到箱体上", "primary": "installation", "status": "parsed"},
    {"id": "install-en", "text": "mount scanner on frame", "primary": "installation", "status": "parsed"},
    {"id": "coincident", "text": "让两个安装面重合", "primary": "coincident", "status": "parsed"},
    {"id": "concentric", "text": "让两个孔同轴", "primary": "concentric", "status": "parsed"},
    {"id": "parallel", "text": "令两个基准面平行", "primary": "parallel", "status": "parsed"},
    {"id": "perpendicular", "text": "令两个基准面垂直", "primary": "perpendicular", "status": "parsed"},
    {"id": "spacing-50mm", "text": "保持50 mm间距", "primary": "spacing", "status": "parsed", "distanceMeters": 0.05},
    {"id": "distance-6cm", "text": "两个面距离6厘米", "primary": "distance", "status": "parsed", "distanceMeters": 0.06},
    {"id": "angle", "text": "两个平面夹角30度", "primary": "angle", "status": "parsed", "angleDegrees": 30.0},
    {"id": "centered", "text": "将模组在槽内居中", "primary": "centered", "status": "parsed"},
    {"id": "operator-side", "text": "将清洁模组放在操作面侧", "primary": "side_placement", "status": "parsed", "sideQualifier": "operator_side"},
    {"id": "ambiguous-align", "text": "把两个模组对齐", "primary": "unspecified", "status": "blocked", "blocker": "ALIGNMENT_KIND_REQUIRED"},
    {"id": "multiple-distance", "text": "保持50mm或60mm间距", "primary": "spacing", "status": "blocked", "blocker": "MULTIPLE_DISTANCE_VALUES"},
    {"id": "install-distance", "text": "安装扫描模组并保持100mm距离", "primary": "installation", "status": "parsed", "distanceMeters": 0.1},
]


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="生成全局关系语义能力矩阵和阶段C测试基线。")
    parser.add_argument(
        "--catalog",
        type=Path,
        default=ROOT / "demo/global_assembly_catalog/v1/global_module_catalog.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "demo/global_assembly_catalog/v1",
    )
    args = parser.parse_args()

    catalog = json.loads(args.catalog.resolve().read_text(encoding="utf-8-sig"))
    validate_global_module_catalog(catalog)
    coverage = build_global_module_port_coverage_matrix(catalog)
    capability = build_relation_capability_matrix(catalog)
    validation = validate_relation_capability_matrix(capability, catalog=catalog)

    output_dir = args.output_dir.resolve()
    capability_path = output_dir / "global_relation_capability_matrix.json"
    _write(capability_path, capability)

    support_rows = []
    for chain_id, references in INITIAL_SUPPORT_CHAINS.items():
        assessment = assess_module_selection_readiness(coverage, references)
        support_rows.append(
            {
                "chainId": chain_id,
                "moduleReferences": references,
                "selectionReadiness": assessment,
            }
        )
    support = {
        "schemaVersion": "global-relation-initial-support-set/v1",
        "sourceCatalogDigest": catalog["catalogDigest"],
        "relationCapabilityMatrixDigest": capability["matrixDigest"],
        "selectionPolicy": (
            "首批覆盖Project02/03/05的箱体、传输、扫描、校准、清洁/称重、CCD和供胶类别；"
            "是否可执行仍由每条模板的自由度证据决定。"
        ),
        "chains": support_rows,
        "collisionStatus": "not_evaluated",
    }
    support_path = output_dir / "global_relation_initial_support_set.json"
    _write(support_path, support)

    parsed_cases = []
    for case in LANGUAGE_CASES:
        parsed_cases.append({**case, "actual": parse_relation_intent(case["text"])})
    cases = {
        "schemaVersion": "global-relation-language-cases/v1",
        "caseCount": len(parsed_cases),
        "cases": parsed_cases,
    }
    cases_path = output_dir / "global_relation_language_cases.json"
    _write(cases_path, cases)

    print(
        json.dumps(
            {
                "capabilityMatrix": str(capability_path),
                "initialSupportSet": str(support_path),
                "languageCases": str(cases_path),
                "summary": capability["summary"],
                "validation": validation,
                "supportChainStatuses": {
                    row["chainId"]: row["selectionReadiness"]["status"]
                    for row in support_rows
                },
                "languageCaseCount": len(parsed_cases),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
