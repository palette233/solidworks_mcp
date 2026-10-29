#!/usr/bin/env python3
"""Build the Project03 AI00 -> Project01 JJ00 alternate-slot audit."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.cross_project_scanner_alternate_route import (  # noqa: E402
    build_scanner_alternate_route_evaluation,
)


CASE = (
    ROOT
    / "demo/cross_project_substitution/scanner-slot-discovery-v1/"
    "project01_JJ00_project03_AI00"
)


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _markdown(report: dict[str, Any]) -> str:
    selected = report["selectedCandidate"]
    process = selected["processProxyChecks"]
    mechanical = selected["mechanicalChecks"]
    return "\n".join(
        [
            "# Project03 AI00 → Project01 JJ00备用槽位评估",
            "",
            f"- 状态：`{report['status']}`",
            f"- 已评估候选位姿：{report['evaluatedPoseCount']}",
            f"- 安装几何求解：{'通过' if mechanical['passed'] else '失败'}",
            f"- 安装面残差：{mechanical['supportPlaneResidualMeters'] * 1000:.6f} mm",
            f"- 最大孔轴横向残差：{max(mechanical['locatingAxisPerpendicularResidualMeters']) * 1000:.6f} mm",
            f"- 扫码通道横向误差：{process['crossTrackErrorMeters'] * 1000:.3f} mm",
            f"- 扫码通道容差：{process['crossTrackToleranceMeters'] * 1000:.3f} mm",
            f"- 代理工艺验证：{'通过' if process['passed'] else '不通过'}",
            f"- CAD启动：{'允许' if report['cadLaunchAllowed'] else '禁止'}",
            "",
            "## 工程结论",
            "",
            "Project01机架存在与AI00孔距匹配的原生200 mm备用孔位，能够解出刚性候选位姿；",
            "但在当前Project01 SS00条码通道代理下，最佳候选仍有超过40 mm的横向偏差，",
            "因此不能仅凭孔距匹配发布跨项目扫描安装模板，也不应启动CAD装配。",
            "",
            "## 下一步",
            "",
            "1. 请机械工程师确认候选孔的用途、螺纹/紧固件规格与承载能力；",
            "2. 若扫码目标确为当前SS00条码通道，则否决该备用槽位；",
            "3. 若实际条码面或载具停位不同，登记真实目标后重新计算；",
            "4. 只有几何与工艺均通过后，才生成非原型初始位姿CAD三配合验证包。",
            "",
            f"证据摘要：`{report['evaluationDigest']}`",
            "",
        ]
    )


def main() -> int:
    report = build_scanner_alternate_route_evaluation(
        discovery=_json(CASE / "scanner_slot_discovery.json"),
        endpoint_recovery=_json(CASE / "endpoint_recovery_evidence.json"),
        source_face_catalog=_json(
            ROOT
            / "demo/semantic_ports/project03_AI00_third_increment_v1/"
            "face_endpoint_catalog.json"
        ),
        target_face_catalog=_json(
            CASE / "jj00-scanner-support-leaf-face-catalog.json"
        ),
        source_graph=_json(
            ROOT
            / "demo/global_assembly_contexts/manifest_jobs/"
            "project-global-job-f0aa2d732403/packet-runs/packet-003-attempt-01/"
            "execution-effective-mate-graph.json"
        ),
        prior_process_evidence=_json(
            ROOT
            / "demo/cross_project_substitution/cumulative-project03-v2/"
            "scanner-transport-process-validation.json"
        ),
        source_support_endpoint_id="face:fl9a24d063ai00:916bba1ff4ce84b0",
        source_hole_endpoint_ids=[
            "face:fl9a24d063ai00:90a1d02db6e9d829",
            "face:fl9a24d063ai00:aa9f3e759104cfd0",
        ],
    )
    (CASE / "alternate_route_evaluation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (CASE / "alternate_route_evaluation-CN.md").write_text(
        _markdown(report), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "candidatePoseTransformSolved": report[
                    "candidatePoseTransformSolved"
                ],
                "processProxyValidationPassed": report[
                    "processProxyValidationPassed"
                ],
                "evaluatedPoseCount": report["evaluatedPoseCount"],
                "selectedCrossTrackErrorMeters": report["selectedCandidate"][
                    "processProxyChecks"
                ]["crossTrackErrorMeters"],
                "cadLaunchAllowed": report["cadLaunchAllowed"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
