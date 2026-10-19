#!/usr/bin/env python3
"""Build an engineering triage report for active incompatible module pairs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.cross_project_interface_triage import (  # noqa: E402
    build_adapter_requirement,
    build_incompatibility_triage,
)


DEFAULT_MATRIX = (
    ROOT
    / "demo/cross_project_substitution/coverage-v1/"
    "cross_project_candidate_matrix.json"
)
DEFAULT_OUTPUT = ROOT / "demo/cross_project_substitution/incompatibility-triage-v1"


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _markdown(triage: dict, adapter: dict) -> str:
    counts = triage["classificationCounts"]
    source = adapter["sourceModule"]
    target = adapter["targetNativeModule"]
    return "\n".join(
        [
            "# 跨项目机械不兼容分层与转接需求",
            "",
            "## 汇总",
            "",
            f"- 有向不兼容项：{triage['directionalIncompatibleCount']}",
            f"- 去重模组对：{triage['undirectedPairCount']}",
            f"- 安装拓扑不同：{counts.get('topology_mismatch_adapter_or_slot_redesign', 0)}",
            f"- 已知定位图案尺寸不同：{counts.get('known_pattern_mismatch_adapter_candidate', 0)}",
            f"- 安装上下文架构不同：{counts.get('context_architecture_mismatch', 0)}",
            "- 所有上述关系均禁止直接启动CAD。",
            "- 碰撞/B-rep不属于本阶段门禁。",
            "",
            "## 首个转接需求样例",
            "",
            f"- 待装模组：{source['projectIds'][0]}:{source['moduleTokens'][0]}",
            f"- 原槽位模组：{target['projectIds'][0]}:{target['moduleTokens'][0]}",
            f"- 模组侧定位间距：{adapter['moduleSide']['locatingPairSpacingsMeters']}",
            f"- 基座侧定位间距：{adapter['baseSide']['locatingPairSpacingsMeters']}",
            "- 结论：现有槽位不能直接安装；需要实体转接件或等效双接口支架。",
            "- 当前状态：缺少转接件CAD几何，失败关闭，不生成虚假配合。",
            "",
            "## 转接件进入可执行目录前",
            "",
            *[f"- {row}" for row in adapter["releaseChecks"]],
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    matrix = json.loads(args.matrix.read_text(encoding="utf-8-sig"))
    triage = build_incompatibility_triage(matrix)
    # Pilot: install the Project03 scanner in the Project01 scanner slot.
    adapter = build_adapter_requirement(
        triage,
        source_project="project03",
        source_token="AI00",
        target_project="project01",
        target_token="SM00",
    )
    output = args.output.resolve()
    _write(output / "incompatibility_triage.json", triage)
    _write(output / "project03_AI00_to_project01_SM00_adapter_requirement.json", adapter)
    (output / "incompatibility_triage.md").write_text(
        _markdown(triage, adapter), encoding="utf-8"
    )
    summary = {
        "success": True,
        "triageDigest": triage["triageDigest"],
        "requirementDigest": adapter["requirementDigest"],
        "counts": triage["classificationCounts"],
        "directCadExecutionAllowed": False,
        "output": str(output),
    }
    _write(output / "build_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
