#!/usr/bin/env python3
"""Build the targeted A600 calibration-slot geometry acquisition request."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.cross_project_slot_acquisition import (  # noqa: E402
    build_calibration_slot_acquisition_request,
    build_slot_port_candidate,
    screen_slot_capture,
    select_operation_side_candidate,
)


CATALOG = (
    ROOT
    / "demo/global_assembly_catalog/releases/"
    "relation-v39-project03-ab00-complete-driving-20261012/"
    "global_module_catalog.json"
)
GEOMETRY = (
    ROOT
    / "demo/layout_previews/project02_a600_installation_geometry_capture.json"
)
SURFACE = ROOT / "demo/layout_previews/project02_a600_installation_surface.json"
FRAME = ROOT / "demo/layout_previews/project02_a600_installation_frame.json"
EXISTING_BOUNDED_CATALOG = (
    ROOT
    / "demo/semantic_ports/project02_A500_full_installation_v2/"
    "face_endpoint_catalog.json"
)
TARGETED_LEAF_CATALOG = (
    ROOT
    / "demo/cross_project_substitution/alternate-slot-discovery-v1/"
    "project02_A600_calibration_slot_acquisition/"
    "a600-native-service-leaf-face-catalog-v1.json"
)
ENDPOINT_RECOVERY_EVIDENCE = (
    ROOT
    / "demo/cross_project_substitution/alternate-slot-discovery-v1/"
    "project02_A600_calibration_slot_acquisition/"
    "endpoint_recovery_evidence.json"
)
OUTPUT = (
    ROOT
    / "demo/cross_project_substitution/alternate-slot-discovery-v1/"
    "project02_A600_calibration_slot_acquisition"
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _markdown(request: dict) -> str:
    required = request["requiredInterface"]
    plan = request["targetedCapturePlan"]
    return "\n".join(
        [
            "# Project02 A600 校准备用槽位采集任务",
            "",
            f"- 状态：`{request['status']}`",
            f"- 来源模组：`{request['sourceModule']['projectId']}/{request['sourceModule']['moduleToken']}`",
            f"- 目标基座：`{request['targetBase']['projectId']}/{request['targetBase']['moduleToken']}`",
            f"- 目标CAD：`{request['targetBase']['cadPath']}`",
            f"- 所需接口：支承面 + 两定位孔/轴，孔距 `{required['locatingPairSpacingMeters'] * 1000:.3f} mm`",
            f"- 筛选容差：`±{required['spacingToleranceMeters'] * 1000:.3f} mm`（工程筛选估计）",
            f"- 定向扫描叶零件：`{plan['primaryLeafHierarchyPath']}`",
            f"- 优先实体索引：`{plan['priorityBodyIndicesFromNativeSlot']}`",
            "",
            "## 为什么现有证据不足",
            "",
            "- A600现有708个实体记录为包围盒，不含权威孔/面拓扑；",
            "- 安装平台与坐标系适合粗布局，不能证明存在50 mm孔系；",
            "- 原生A500槽位采用支承面、宽度侧面和偏置面，不等价于双孔定位接口。",
            "",
            "## 执行边界",
            "",
            "只定向扫描原生槽位所在静止叶零件；若自动筛选无结果，再人工选择两个定位面和一个支承面。",
            "在端点目录生成、保存重开恢复和证据发布完成前，不允许启动跨项目安装CAD事务。",
            "本阶段不要求碰撞或B-rep检查，也不虚构转接件或备用槽位。",
            "",
        ]
    )


def _candidate_markdown(selection: dict, port_candidate: dict | None) -> str:
    selected = selection["selectedCandidate"]
    position = selected["candidateCenterInA600FrameMeters"]
    lines = [
        "# Project02 A600 校准备用槽位候选",
        "",
        f"- 状态：`{selection['status']}`",
        "- 选择规则：优先选择更靠近操作面的50 mm定位孔列；",
        f"- 支承面：`{selected['supportPlaneEndpointIds'][0]}`",
        f"- 定位孔1：`{selected['locatingEndpointIds'][0]}`",
        f"- 定位孔2：`{selected['locatingEndpointIds'][1]}`",
        f"- 孔半径：`{selected['locatingRadiusMeters'] * 1000:.3f} mm`",
        f"- 孔距：`{selected['axisSpacingMeters'] * 1000:.3f} mm`",
        f"- A600坐标：x入机 `{position['xIntoMachineMeters']:.4f} m`，"
        f"y传输横向 `{position['yTransportLateralMeters']:.4f} m`，"
        f"z向上 `{position['zUpMeters']:.4f} m`；",
        f"- 备用候选数：`{len(selection['alternateCandidates'])}`。",
        "",
    ]
    if port_candidate:
        lines.extend(
            [
                "## 端点恢复",
                "",
                f"- 状态：`{port_candidate['status']}`",
                f"- 三个端点全部恢复：`{str(port_candidate['endpointRecovery']['allRecovered']).lower()}`",
                "- 当前只允许候选跨项目CAD验证，尚未发布到全局端口目录；",
                "- 下一步：从非原型初始位姿插入AH00，创建1个重合与2个同心配合，并保存重开复核。",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "## 当前门槛",
                "",
                "三个端点尚需在SolidWorks中逐个恢复；恢复成功后仍只进入候选CAD验证，不直接发布。",
                "",
            ]
        )
    lines.append("碰撞/B-rep不属于本阶段验收。")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    request = build_calibration_slot_acquisition_request(
        _read(CATALOG),
        geometry_capture=_read(GEOMETRY),
        installation_surface=_read(SURFACE),
        installation_frame=_read(FRAME),
    )
    OUTPUT.mkdir(parents=True, exist_ok=True)
    request_path = OUTPUT / "slot_acquisition_request.json"
    request_path.write_text(
        json.dumps(request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (OUTPUT / "slot_acquisition_request.md").write_text(
        _markdown(request), encoding="utf-8"
    )
    screening = screen_slot_capture(request, _read(EXISTING_BOUNDED_CATALOG))
    screening_path = OUTPUT / "existing_catalog_screening.json"
    screening_path.write_text(
        json.dumps(screening, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    targeted_screening = None
    targeted_screening_path = None
    candidate_selection = None
    candidate_selection_path = None
    candidate_port = None
    candidate_port_path = None
    stale_recovery_evidence_ignored = False
    if TARGETED_LEAF_CATALOG.is_file():
        targeted_screening = screen_slot_capture(
            request, _read(TARGETED_LEAF_CATALOG)
        )
        targeted_screening_path = OUTPUT / "targeted_leaf_screening.json"
        targeted_screening_path.write_text(
            json.dumps(targeted_screening, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        if targeted_screening["candidateCount"]:
            candidate_selection = select_operation_side_candidate(
                request,
                targeted_screening,
                _read(TARGETED_LEAF_CATALOG),
                _read(FRAME),
            )
            candidate_selection_path = OUTPUT / "candidate_selection.json"
            candidate_selection_path.write_text(
                json.dumps(candidate_selection, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            recovery_evidence = (
                _read(ENDPOINT_RECOVERY_EVIDENCE)
                if ENDPOINT_RECOVERY_EVIDENCE.is_file()
                else None
            )
            if recovery_evidence and recovery_evidence.get(
                "selectionDigest"
            ) != candidate_selection.get("selectionDigest"):
                recovery_evidence = None
                stale_recovery_evidence_ignored = True
            candidate_port = build_slot_port_candidate(
                request,
                candidate_selection,
                _read(TARGETED_LEAF_CATALOG),
                endpoint_recovery_evidence=recovery_evidence,
            )
            candidate_port_path = OUTPUT / "candidate_semantic_port.json"
            candidate_port_path.write_text(
                json.dumps(candidate_port, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            (OUTPUT / "candidate_selection.md").write_text(
                _candidate_markdown(candidate_selection, candidate_port),
                encoding="utf-8",
            )
    summary = {
        "success": True,
        "status": (
            candidate_port["status"] if candidate_port else request["status"]
        ),
        "requestDigest": request["requestDigest"],
        "requestPath": str(request_path),
        "publishedCadExecutionAllowed": request["executionPolicy"][
            "cadExecutionAllowed"
        ],
        "candidateValidationCadAllowed": (
            candidate_port["decision"]["cadExecutionAllowed"]
            if candidate_port
            else False
        ),
        "existingCatalogScreeningStatus": screening["status"],
        "existingCatalogCandidateCount": screening["candidateCount"],
        "existingCatalogScreeningPath": str(screening_path),
        "targetedLeafCatalogPresent": targeted_screening is not None,
        "targetedLeafScreeningStatus": (
            targeted_screening["status"] if targeted_screening else None
        ),
        "targetedLeafCandidateCount": (
            targeted_screening["candidateCount"] if targeted_screening else None
        ),
        "targetedLeafScreeningPath": (
            str(targeted_screening_path) if targeted_screening_path else None
        ),
        "candidateSelectionStatus": (
            candidate_selection["status"] if candidate_selection else None
        ),
        "candidateSelectionPath": (
            str(candidate_selection_path) if candidate_selection_path else None
        ),
        "candidatePortStatus": candidate_port["status"] if candidate_port else None,
        "candidatePortPath": str(candidate_port_path) if candidate_port_path else None,
        "endpointRecoveryAllPassed": (
            candidate_port["endpointRecovery"]["allRecovered"]
            if candidate_port
            else False
        ),
        "staleEndpointRecoveryEvidenceIgnored": stale_recovery_evidence_ignored,
        "selectedLocatingEndpointIds": (
            candidate_selection["selectedCandidate"]["locatingEndpointIds"]
            if candidate_selection
            else []
        ),
        "nextAction": (
            candidate_port["decision"]["nextAction"]
            if candidate_port
            else candidate_selection["decision"]["nextAction"]
            if candidate_selection
            else targeted_screening["decision"]["nextAction"]
            if targeted_screening
            else "targeted-read-only-face-catalog"
        ),
    }
    (OUTPUT / "build_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
