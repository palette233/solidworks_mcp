#!/usr/bin/env python3
"""Materialize the bounded SS00/AE00 transport datum-port scan plan."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "apps/demo-backend/src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.transport_datum_port_acquisition import (  # noqa: E402
    ACQUISITION_ROOT,
    build_transport_datum_port_acquisition_plan,
)


def _render_markdown(plan: dict) -> str:
    lines = [
        "# 传输模组三平面备用端口获取计划",
        "",
        "本计划仅补充真实平面端点，不把A600不存在的58 mm双轴孔位伪装为兼容接口。",
        "",
        "| 模组 | 指定静态叶零件 | 状态 |",
        "|---|---|---|",
    ]
    for item in plan["items"]:
        lines.append(
            f"| {item['moduleDefinitionId']} | `{item['staticMountLeafSelector']}` | "
            f"{item['status']} |"
        )
    lines.extend(
        [
            "",
            "## 执行边界",
            "",
            "- 每次只扫描一个已确认的静态安装叶零件；",
            "- 扫描结果必须保留SolidWorks持久引用；",
            "- 三个平面必须位于同一叶零件并两两正交；",
            "- 候选默认不选中，两个方向面也不会自动命名为纵向/横向；",
            "- 需人工确认候选及纵横角色后，才能登记为参数化端口；",
            "- 确认端口后仍需位置参数、非原型CAD验证、保存重开和精确配对发布；",
            "- 本计划不授权CAD执行，不证明实际固定方式、碰撞或生产可用性。",
            "",
            f"计划摘要：`{plan['planDigest']}`",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / ACQUISITION_ROOT
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    json_path = output_dir / "scan-plan.json"
    markdown_path = output_dir / "scan-plan-CN.md"
    if not args.force and (json_path.exists() or markdown_path.exists()):
        raise FileExistsError(
            f"Refusing to overwrite transport datum acquisition plan: {output_dir}"
        )
    plan = build_transport_datum_port_acquisition_plan(ROOT)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    markdown_path.write_text(_render_markdown(plan), encoding="utf-8")
    print(
        json.dumps(
            {
                "success": True,
                "scanPlan": str(json_path),
                "reviewGuide": str(markdown_path),
                "itemCount": plan["summary"]["itemCount"],
                "planDigest": plan["planDigest"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
