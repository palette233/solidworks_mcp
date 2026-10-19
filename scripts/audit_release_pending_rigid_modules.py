#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "apps/demo-backend/src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.release_pending_evidence_audit import (  # noqa: E402
    build_release_pending_evidence_audit,
)


DEFAULT_OUTPUT = ROOT / "demo/global_assembly_catalog/coverage-v2"


CASE_SPECS = (
    {
        "projectId": "project01",
        "moduleToken": "FF00",
        "moduleRole": "Positioning",
        "templateId": "FF00_to_JJ00_three_datum_installation",
        "expectedMateCount": 3,
        "patterns": (
            "demo/semantic_ports/project01_FF00_second_increment_v1/*.result.json",
            "demo/global_assembly_catalog/coverage-v2/ff00-checkpoint-refresh-v1/*.result.json",
        ),
    },
    {
        "projectId": "project01",
        "moduleToken": "GJ00",
        "moduleRole": "GlueSupply",
        "templateId": "GJ00_to_JJ00_three_datum_installation",
        "expectedMateCount": 3,
        "patterns": (
            "demo/semantic_ports/project01_GJ00_sixth_increment_v1/*.result.json",
            "demo/global_assembly_catalog/coverage-v2/gj00-checkpoint-refresh-v1/*.result.json",
        ),
    },
    {
        "projectId": "project01",
        "moduleToken": "LM00",
        "moduleRole": "Gantry",
        "templateId": "LM00_to_JJ00_three_datum_installation",
        "expectedMateCount": 3,
        "patterns": (
            "demo/semantic_ports/project01_LM00_final_stage_action1_v1/*.result.json",
            "demo/global_assembly_catalog/coverage-v2/lm00-checkpoint-refresh-v1/*.result.json",
            "demo/global_assembly_catalog/coverage-v2/lm00-checkpoint-refresh-v2/*.result.json",
        ),
    },
    {
        "projectId": "project03",
        "moduleToken": "AG00",
        "moduleRole": "CleaningWeighing",
        "templateId": "AG00_to_AA00_three_datum_installation_v1",
        "expectedMateCount": 3,
        "patterns": (
            "demo/global_assembly_catalog/coverage-v2/"
            "ag00-three-datum-candidate-v1/*.result.json",
        ),
    },
)


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON根节点必须是对象：{path}")
    return value


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _load_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for spec in CASE_SPECS:
        paths: set[Path] = set()
        for pattern in spec["patterns"]:
            paths.update(ROOT.glob(pattern))
        cases.append(
            {
                key: value
                for key, value in spec.items()
                if key != "patterns"
            }
            | {
                "evidence": [
                    {"path": _relative(path), "payload": _read(path)}
                    for path in sorted(paths)
                ]
            }
        )
    return cases


def _markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# 待发布刚性模组历史CAD证据审计",
        "",
        "## 结论边界",
        "",
        "- 只审计既有CAD结果能否证明语义端口独立决定外部位姿。",
        "- 不启动SolidWorks，不改历史装配体，不评价碰撞/B-rep。",
        "- 旧版成功结果不自动等同于当前checkpoint安全发布证据。",
        "",
        "## 汇总",
        "",
        f"- 审计模组：{summary['moduleCount']}",
        f"- 可直接进入受控发布：{summary['reusableForReleaseCount']}",
        f"- 仅需新版checkpoint重放：{summary['checkpointRefreshRequiredCount']}",
        f"- 需补完整定位配合束：{summary['installationBundleRepairRequiredCount']}",
        f"- 其他阻塞：{summary['otherBlockedCount']}",
        "",
        "## 模组结论",
        "",
        "|项目模组|角色|模板|历史结果数|结论|下一动作|",
        "|---|---|---|---:|---|---|",
    ]
    for row in report["modules"]:
        lines.append(
            f"|{row['projectId']}:{row['moduleToken']}|{row.get('moduleRole') or ''}|"
            f"{row['templateId']}|{len(row['evidence'])}|{row['state']}|"
            f"{row['nextAction']}|"
        )
    lines.extend(["", "## 历史证据明细", ""])
    for row in report["modules"]:
        lines.extend(
            [
                f"### {row['projectId']}:{row['moduleToken']}",
                "",
            ]
        )
        for evidence in row["evidence"]:
            assessment = evidence["assessment"]
            observation = assessment.get("constraintStateObservation") or {}
            lines.append(
                f"- `{evidence['state']}`：`{evidence['path']}`；"
                f"配合{assessment.get('createdMateCount', 0)}/"
                f"{assessment.get('requestedMateCount', 0)}；"
                f"案例锚点={str(evidence['casePoseAnchorUsed']).lower()}；"
                f"叶级锚点={evidence['leafPoseAnchorCount']}；"
                f"外部位姿闭合={str(bool(observation.get('externalPlacementEquivalenceProven'))).lower()}。"
            )
        if not row["evidence"]:
            lines.append("- 未找到历史结果。")
        lines.append("")
    lines.extend(
        [
            "## 后续处置原则",
            "",
            "1. `reusable_for_release`表示现有新版证据可进入受控发布；实际发布状态以全目录缺口报告为准。",
            "2. `checkpoint_refresh_required`只重放既有完整模板，不重新提取端口。",
            "3. AG00旧版两配合证据只作为失败历史保留；当前审计以已补齐的三基准、零锚点checkpoint为准。",
            "4. 每次重放均要求源文件不变、输出哈希、保存关闭重开和配合参数复核。",
            "",
            f"审计摘要：`{report['auditDigest']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="审计待发布刚性模组的历史CAD证据。")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    report = build_release_pending_evidence_audit(_load_cases())
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "release_pending_rigid_module_evidence_audit.json"
    markdown_path = output / "release_pending_rigid_module_evidence_audit.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "success": True,
                "summary": report["summary"],
                "outputs": {
                    "json": str(json_path),
                    "markdown": str(markdown_path),
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
