#!/usr/bin/env python3
"""Build the aggregate interface-family coverage report."""
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.interface_contract_coverage import (  # noqa: E402
    build_interface_contract_coverage,
    validate_interface_contract_coverage,
)


def main() -> int:
    report = build_interface_contract_coverage(ROOT)
    validate_interface_contract_coverage(report)
    output = ROOT / "demo/cross_project_substitution/interface-contract-coverage-v1"
    output.mkdir(parents=True, exist_ok=True)
    (output / "coverage-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# 机械接口契约覆盖报告", "",
        "| 角色 | 模组端口 | 基座槽位 | 候选组合 | 兼容 | 不兼容 | 已发布 | 工艺只读端口 |", "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["families"]:
        lines.append(
            f"| {row['role']} | {row['movingModuleCount']} | {row['baseSlotCount']} | "
            f"{row['candidatePairCount']} | {row['compatiblePairCount']} | {row['incompatiblePairCount']} | "
            f"{row['releasedPairCount']} | {row['readOnlyProcessPortCount']} |"
        )
    totals = report["totals"]
    lines += [
        "", f"当前共{totals['familyCount']}个接口族、{totals['movingModuleContractCount']}个移动模组端口、"
        f"{totals['baseSlotContractCount']}个基座槽位、{totals['candidatePairCount']}个候选组合；"
        f"其中{totals['compatiblePairCount']}个兼容且均已有配对发布。", "",
        "## 下一批缺口", "",
    ]
    for row in report["remainingPriorityGaps"]:
        lines.append(f"- {row['role']}：{', '.join(row['moduleDefinitionIds'])}；{row['needed']}。")
    lines += [
        "", "## 边界", "",
        "- WasteCup为支承定位Demo，不宣称孔位、紧固件或直接机械互换。",
        "- Scanner光轴与工作距离是只读工艺关系，不参与驱动定位。",
        "- Project06、A700内部柔性结构、碰撞/B-rep当前不进入主线。",
    ]
    (output / "coverage-report-CN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"success": True, "output": str(output), **totals}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
