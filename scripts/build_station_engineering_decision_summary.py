#!/usr/bin/env python3
"""Build one auditable engineering-decision summary from a station-gap report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.station_engineering_decisions import (  # noqa: E402
    build_station_engineering_decision_summary,
    validate_station_engineering_decision_summary,
)


def _write_markdown(report: dict, path: Path) -> None:
    lines = [
        "# 目标工位工程决策汇总",
        "",
        f"- 精确配对：{report['decisionPairCount']}项",
        f"- 决策主题：{report['topicCount']}组",
        "- 当前状态：未确认，不允许启动CAD",
        "",
    ]
    for index, topic in enumerate(report["topics"], start=1):
        lines.extend(
            [
                f"## {index}. {topic['role']} / {topic['gapCategory']}",
                "",
                topic["question"],
                "",
                f"所需决策：`{topic['requiredDecision']}`",
                "",
            ]
        )
        for row in topic["exactPairs"]:
            lines.append(
                "- "
                + row["sourceModuleDefinitionId"]
                + " → "
                + row["targetBaseDefinitionId"]
            )
        lines.append("")
    lines.extend(
        [
            "## 边界",
            "",
            "本文件只合并待确认问题，不自动接受功能残差、能力等价、扫描角色或传输工艺差异，也不提供CAD启动权限。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gap-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    gap = args.gap_report.resolve() if args.gap_report.is_absolute() else (ROOT / args.gap_report).resolve()
    output = args.output.resolve() if args.output.is_absolute() else (ROOT / args.output).resolve()
    output.relative_to(ROOT)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite decision summary: {output}")
    report = build_station_engineering_decision_summary(ROOT, gap)
    validate_station_engineering_decision_summary(report)
    output.mkdir(parents=True)
    (output / "decision-summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_markdown(report, output / "README-CN.md")
    print(
        json.dumps(
            {
                "success": True,
                "decisionPairCount": report["decisionPairCount"],
                "topicCount": report["topicCount"],
                "cadLaunchAllowed": report["cadLaunchAllowed"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
