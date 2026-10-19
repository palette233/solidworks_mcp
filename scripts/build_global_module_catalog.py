from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
BACKEND_SRC = WORKSPACE / "apps" / "demo-backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.global_module_catalog import (  # noqa: E402
    DEFAULT_PROJECT_IDS,
    build_global_module_catalog,
    validate_global_module_catalog,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="构建跨项目全局CAD模组与语义端口目录。")
    parser.add_argument(
        "--projects",
        nargs="*",
        default=list(DEFAULT_PROJECT_IDS),
        help="要纳入的项目编号。默认包含project01/02/03/05/06。",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=WORKSPACE / "demo" / "global_assembly_catalog" / "v1" / "global_module_catalog.json",
    )
    parser.add_argument(
        "--additional-semantic-catalog",
        action="append",
        type=Path,
        default=[],
        help="额外纳入候选语义端口目录；可重复指定，不修改默认语义目录。",
    )
    args = parser.parse_args()
    catalog = build_global_module_catalog(
        WORKSPACE,
        project_ids=args.projects,
        additional_semantic_catalog_paths=args.additional_semantic_catalog,
    )
    validation = validate_global_module_catalog(catalog)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path = output.with_name("migration_report.json")
    report = {
        "schemaVersion": "global-module-migration-report/v1",
        "catalogPath": str(output),
        "validation": validation,
        "summary": catalog["summary"],
        "projects": catalog["projects"],
        "blockers": catalog["blockers"],
        "collisionGate": catalog["collisionPolicy"],
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
