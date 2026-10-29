#!/usr/bin/env python3
"""Build the read-only Project01 GN00 base-only orientation candidate."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.project01_gn00_base_only_datum import (  # noqa: E402
    build_project01_gn00_base_only_datum_candidate,
)


OUTPUT = (
    ROOT
    / "demo/cross_project_substitution/cleaning-weighing-base-only-v1/"
    "project01_GN00_project03_AG00"
)


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _markdown(report: dict[str, Any]) -> str:
    selected = report.get("selectedCandidate") or {}
    comparison = report["comparisonToProject03Ag00"]
    return "\n".join(
        [
            "# Project01 GN00纯基座方向基准候选",
            "",
            f"- 状态：`{report['status']}`",
            f"- JJ00候选方向基准面：{report['candidateCount']}个",
            f"- 首选端点：`{selected.get('endpointId') or '无'}`",
            f"- 首选面面积：{float(selected.get('faceAreaSquareMeters') or 0.0):.6f} m²",
            f"- 去除SS00语义依赖：{'是' if report['proposedArchitecture']['semanticTransportDependencyRemoved'] else '否'}",
            f"- 已证明GN00↔AG00直接机械兼容：{'是' if comparison['directMechanicalTopologyCompatible'] else '否'}",
            f"- CAD启动：{'允许' if report['cadLaunchAllowed'] else '禁止'}",
            "",
            "## 结论",
            "",
            "现有JJ00静态承载叶上存在可稳定恢复、与GN00防转面平行且独立于支承面的方向基准，",
            "因此可以继续验证GN00是否能由JJ00单独确定方向，不必在语义上依赖SS00传输模组。",
            "",
            "但该候选只是方向基准，不证明实际防转接触或紧固。GN00的候选拓扑仍为",
            "“安装面＋单孔＋方向面”，AG00为“安装面＋双孔”，两者仍不能直接判为机械兼容。",
            "",
            "## 下一步",
            "",
            "1. 确认首选JJ00面是否可作为工程装配方向基准；",
            "2. 确认后生成GN00非原型初始位姿三配合CAD验证包；",
            "3. 若要求GN00与AG00直接跨项目互换，继续寻找双方共同的第二物理定位特征；",
            "4. 不通过放宽配合拓扑或复用原型位姿制造兼容结论。",
            "",
            f"证据摘要：`{report['candidateDigest']}`",
            "",
        ]
    )


def main() -> int:
    report = build_project01_gn00_base_only_datum_candidate(
        native_endpoint_catalog=_json(
            ROOT
            / "demo/semantic_ports/project01_GN00_fourth_increment_v1/"
            "face_endpoint_catalog.json"
        ),
        jj00_support_leaf_catalog=_json(
            ROOT
            / "demo/cross_project_substitution/scanner-slot-discovery-v1/"
            "project01_JJ00_project03_AI00/"
            "jj00-scanner-support-leaf-face-catalog.json"
        ),
        gn00_anti_rotation_endpoint_id="face:gn00:2a78145c441c9159",
        jj00_primary_support_endpoint_id="face:jj00:cf4e0ac0baf70ae1",
    )
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "base_only_datum_candidate.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (OUTPUT / "base_only_datum_candidate-CN.md").write_text(
        _markdown(report), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "candidateCount": report["candidateCount"],
                "selectedEndpointId": (
                    report.get("selectedCandidate") or {}
                ).get("endpointId"),
                "semanticTransportDependencyRemoved": report[
                    "proposedArchitecture"
                ]["semanticTransportDependencyRemoved"],
                "directCrossProjectCompatibilityProven": report[
                    "directCrossProjectCompatibilityProven"
                ],
                "cadLaunchAllowed": report["cadLaunchAllowed"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
