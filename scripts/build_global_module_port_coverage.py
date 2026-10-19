#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "demo-backend" / "src"))

from demo_backend.global_module_catalog import (
    build_global_module_catalog,
    validate_global_module_catalog,
)
from demo_backend.global_module_port_coverage import (
    assess_module_selection_readiness,
    build_global_module_port_coverage_matrix,
    validate_global_module_port_coverage_matrix,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="生成全局模组、语义端口、关系模板覆盖矩阵。"
    )
    parser.add_argument(
        "--projects",
        nargs="+",
        default=["project01", "project02", "project03", "project05", "project06"],
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=ROOT
        / "demo"
        / "global_assembly_catalog"
        / "v1"
        / "global_module_catalog.json",
        help="默认只读已签认全局目录，避免审计操作改写目录摘要。",
    )
    parser.add_argument(
        "--refresh-catalog",
        action="store_true",
        help="显式要求从当前项目档案重建内存目录；不会写回--catalog。",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "demo"
        / "global_assembly_catalog"
        / "v1"
        / "global_module_port_coverage_matrix.json",
    )
    parser.add_argument(
        "--assess",
        nargs="*",
        default=None,
        metavar="MODULE",
        help="可选：同时评估一组moduleDefinitionId、projectId:token或唯一token。",
    )
    args = parser.parse_args()

    if args.refresh_catalog:
        catalog = build_global_module_catalog(ROOT, project_ids=tuple(args.projects))
    else:
        catalog_path = args.catalog.resolve()
        if not catalog_path.is_file():
            raise FileNotFoundError(catalog_path)
        catalog = json.loads(catalog_path.read_text(encoding="utf-8-sig"))
        validate_global_module_catalog(catalog)
    matrix = build_global_module_port_coverage_matrix(catalog)
    validation = validate_global_module_port_coverage_matrix(matrix)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(matrix, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result: dict[str, object] = {
        "output": str(output),
        "validation": validation,
        "summary": matrix["summary"],
    }
    if args.assess is not None:
        result["selectionReadiness"] = assess_module_selection_readiness(matrix, args.assess)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
