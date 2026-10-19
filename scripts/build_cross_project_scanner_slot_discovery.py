#!/usr/bin/env python3
"""Build bounded scanner-slot evidence in both active project directions."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.cross_project_scanner_slot_discovery import (  # noqa: E402
    build_scanner_slot_discovery,
)


MATRIX = (
    ROOT
    / "demo/cross_project_substitution/coverage-v1/"
    "cross_project_candidate_matrix.json"
)
OUTPUT_ROOT = ROOT / "demo/cross_project_substitution/scanner-slot-discovery-v1"
CASES = [
    {
        "directory": "project03_AA00_project01_SM00",
        "catalog": "aa00-scanner-support-leaf-face-catalog.json",
        "sourceProject": "project01",
        "sourceToken": "SM00",
        "targetProject": "project03",
        "targetToken": "AI00",
        "targetLeaf": (
            "FL9A24D063AA10.001-1/FL9A24D063AA11.001-1/"
            "FL5A24D063AA11002.02-1"
        ),
        "nativeSlotCenterLocal": [-0.462, 0.078, 0.00615],
    },
    {
        "directory": "project01_JJ00_project03_AI00",
        "catalog": "jj00-scanner-support-leaf-face-catalog.json",
        "sourceProject": "project03",
        "sourceToken": "AI00",
        "targetProject": "project01",
        "targetToken": "SM00",
        "targetLeaf": (
            "FL9C24N074JA00.001-1/FL9C24N074JA10.001-1/"
            "FL5C24N074JA20001.01-1"
        ),
        "nativeSlotCenterLocal": [-0.2915, 0.107, 0.01],
    },
]


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _markdown(report: dict) -> str:
    relation = report["sourceRelation"]
    lines = [
        (
            f"# {relation['targetProjectId']} 原生扫描支承叶上的 "
            f"{relation['sourceProjectId']}/{relation['sourceModuleToken']} "
            "槽位定向发现"
        ),
        "",
        f"- 状态：`{report['status']}`",
        f"- 来源模组所需双孔距：`{report['requiredLocatingSpacingMeters'] * 1000:.3f} mm`",
        f"- 目标原生扫描槽位双孔距：`{report['nativeTargetLocatingSpacingMeters'] * 1000:.3f} mm`",
        f"- 定向扫描面数：`{report['captureScope']['catalogEndpointCount']}`",
        f"- 精确兼容候选：`{report['directCandidateCount']}`",
        f"- 近似但不兼容候选：`{report['nearCandidateCount']}`",
        "",
    ]
    for index, candidate in enumerate(report["candidates"], start=1):
        displacement = candidate.get("nativeStationDisplacementMeters")
        lines.extend(
            [
                f"## 候选 {index}",
                "",
                f"- 实测孔距：`{candidate['axisSpacingMeters'] * 1000:.6f} mm`",
                f"- 与所需孔距残差：`{candidate['spacingResidualMeters'] * 1000:.6f} mm`",
                f"- 直接兼容：`{str(candidate['directFit']).lower()}`",
                (
                    f"- 相对原生扫描工位中心偏移：`{displacement * 1000:.3f} mm`"
                    if displacement is not None
                    else "- 相对原生扫描工位中心偏移：`未计算`"
                ),
                f"- 定位圆柱端点：`{candidate['locatingEndpointIds']}`",
                f"- 支承面端点：`{candidate['supportPlaneEndpointIds']}`",
                "",
            ]
        )
    lines.extend(["## 结论", ""])
    if report["directCandidateCount"]:
        selected = report["selectedCandidate"]
        lines.extend(
            [
                "当前叶件存在名义孔距完全兼容的机械候选。",
                (
                    "按最接近原生扫描工位的规则选中孔列："
                    f"`{selected['locatingEndpointIds']}`。"
                ),
                "该候选仍需端点恢复、非源初始位姿配合验证及扫描光轴/条码目标复核，尚未发布。",
            ]
        )
    else:
        lines.extend(
            [
                "当前叶件中没有满足1微米名义孔距比较门槛的直接安装槽位。",
                "近似孔列不能同时建立两个精确同心配合；该方向仍需转接件、新孔系或另一个有界支承叶。",
            ]
        )
    lines.extend(
        [
            "本轮不引入Project06，也不执行碰撞/B-rep。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    matrix = _read(MATRIX)
    reports = []
    for case in CASES:
        output = OUTPUT_ROOT / case["directory"]
        report = build_scanner_slot_discovery(
            matrix,
            _read(output / case["catalog"]),
            source_project=case["sourceProject"],
            source_token=case["sourceToken"],
            target_project=case["targetProject"],
            target_token=case["targetToken"],
            target_leaf_hierarchy_path=case["targetLeaf"],
            native_slot_center_local=case["nativeSlotCenterLocal"],
        )
        output.mkdir(parents=True, exist_ok=True)
        report_path = output / "scanner_slot_discovery.json"
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (output / "scanner_slot_discovery.md").write_text(
            _markdown(report), encoding="utf-8"
        )
        case_summary = {
            "source": f"{case['sourceProject']}/{case['sourceToken']}",
            "target": f"{case['targetProject']}/{case['targetToken']}",
            "status": report["status"],
            "directCandidateCount": report["directCandidateCount"],
            "nearCandidateCount": report["nearCandidateCount"],
            "discoveryDigest": report["discoveryDigest"],
            "report": str(report_path.resolve()),
        }
        (output / "build_summary.json").write_text(
            json.dumps({"success": True, **case_summary}, ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )
        reports.append(case_summary)
    summary = {
        "success": True,
        "project06Included": False,
        "caseCount": len(reports),
        "cases": reports,
    }
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    (OUTPUT_ROOT / "build_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
