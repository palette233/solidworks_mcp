#!/usr/bin/env python3
"""Materialize the review-only G000 flexible-slot candidate inventory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.flexible_calibration_slot_selection import (  # noqa: E402
    build_g000_flexible_slot_candidate_catalog,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite candidate catalog: {output}")
    report = build_g000_flexible_slot_candidate_catalog(ROOT)
    output.mkdir(parents=True)
    (output / "candidate-catalog.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# G000柔性四关系跨基座候选",
        "",
        "|目标基座|状态|稳定轴线候选数|",
        "|---|---|---:|",
    ]
    for row in report["baseSlots"]:
        lines.append(
            f"|{row['slotDefinitionId']}|{row['state']}|{row['candidateAxisLineCount']}|"
        )
    lines.extend(
        [
            "",
            "候选仅用于工程审阅。必须确认具体轴线和纵向距离后，才能生成非原型CAD验证包；候选不等于发布。",
            "",
            f"目录摘要：`{report['catalogDigest']}`",
            "",
        ]
    )
    (output / "README-CN.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
