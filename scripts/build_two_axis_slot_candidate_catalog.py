#!/usr/bin/env python3
"""Write the immutable review catalog for Project05 A000 50/58 mm axis pairs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.two_axis_slot_selection import (  # noqa: E402
    build_two_axis_slot_candidate_catalog,
)


DEFAULT_OUTPUT = (
    ROOT
    / "demo/cross_project_substitution/two-axis-slot-selection-v1/"
    "project05-a000-candidate-catalog-v2"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite candidate catalog: {output}")
    catalog = build_two_axis_slot_candidate_catalog(ROOT)
    output.mkdir(parents=True)
    (output / "candidate-catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Project05 A000 双定位轴候选目录",
        "",
        "本目录只列出与既有50/58 mm移动端口间距一致的稳定轴线对，未自动选择任何一组。",
        "",
        "|角色|所需间距|候选轴对|待确认模组|",
        "|---|---:|---:|---|",
    ]
    for row in catalog["families"]:
        lines.append(
            f"|{row['moduleRole']}|{row['requiredSpacingMeters'] * 1000:.1f} mm|"
            f"{row['candidatePairCount']}|{', '.join(row['moduleDefinitionIds'])}|"
        )
    lines.extend(
        [
            "",
            "必须由工程审阅确认孔用途、安装侧与具体轴对；确认后仍需非原型CAD、保存重开和精确配对发布。",
            "间距相符不等于孔径、紧固方式或承载能力相容。",
            "",
            f"目录摘要：`{catalog['catalogDigest']}`",
            "",
        ]
    )
    (output / "README-CN.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(catalog["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
