#!/usr/bin/env python3
"""Scan released catalogs for alternate target slots before adapter design."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.cross_project_alternate_slot_discovery import (  # noqa: E402
    build_alternate_slot_discovery,
)


DEFAULT_MATRIX = (
    ROOT
    / "demo/cross_project_substitution/coverage-v1/"
    "cross_project_candidate_matrix.json"
)
DEFAULT_RELEASES = ROOT / "demo/global_assembly_catalog/releases"
DEFAULT_BASE = ROOT / "demo/global_assembly_catalog/v1/global_module_catalog.json"
DEFAULT_OUTPUT = ROOT / "demo/cross_project_substitution/alternate-slot-discovery-v1"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _latest_release_catalogs(root: Path) -> list[Path]:
    pattern = re.compile(r"^relation-v(?P<version>\d+)-(?P<project>project\d+)-")
    latest: dict[str, tuple[int, Path]] = {}
    for directory in root.iterdir() if root.is_dir() else []:
        match = pattern.match(directory.name)
        catalog = directory / "global_module_catalog.json"
        if not match or not catalog.is_file():
            continue
        key = match.group("project")
        version = int(match.group("version"))
        if key not in latest or version > latest[key][0]:
            latest[key] = (version, catalog)
    return [latest[key][1] for key in sorted(latest)]


def _markdown(report: dict) -> str:
    counts = report["statusCounts"]
    return "\n".join(
        [
            "# 跨项目备用安装槽位扫描",
            "",
            f"- 扫描有向拓扑不一致关系：{report['scannedDirectionalPairCount']}",
            f"- 找到可直接使用的已登记备用槽位：{counts['registered_alternate_slot_ready']}",
            f"- 找到需几何复核的备用槽位：{counts['registered_alternate_slot_needs_geometry_review']}",
            f"- 已登记备用槽位仍不兼容：{counts['registered_alternate_slots_incompatible']}",
            f"- 没有已登记备用槽位：{counts['no_registered_alternate_slot']}",
            "",
            "本报告只扫描已经登记的provided端口，不从未登记CAD几何猜测孔、面或槽。",
            "没有备用槽位不等于基座实体一定不存在其他孔系，而是表示现有语义目录尚无相关证据。",
            "碰撞/B-rep未执行，也不参与本阶段判断。",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--releases", type=Path, default=DEFAULT_RELEASES)
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    catalog_paths = [args.base.resolve(), *_latest_release_catalogs(args.releases.resolve())]
    report = build_alternate_slot_discovery(
        _read(args.matrix.resolve()),
        evidence_catalogs=[_read(path) for path in catalog_paths],
    )
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    report_path = output / "alternate_slot_discovery.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output / "alternate_slot_discovery.md").write_text(
        _markdown(report), encoding="utf-8"
    )
    summary = {
        "success": True,
        "discoveryDigest": report["discoveryDigest"],
        "statusCounts": report["statusCounts"],
        "sourceCatalogPaths": [str(path) for path in catalog_paths],
        "report": str(report_path),
    }
    (output / "build_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
