#!/usr/bin/env python3
"""Audit whether existing Project02 CAD data can unlock the dynamic gate."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.dynamic_engineering_acquisition import build_dynamic_source_audit


def main() -> int:
    a700_dir = ROOT / "demo/semantic_ports/project02_service_installations_v1/A700"
    source_assembly = Path(
        r"D:\zengshuang\workspace\cuhksz\cad_data\001-给港中文AI训练用资料_20260624\项目02\01-项目3D图纸\FL9A24D062A000.001\FL9A24D062A000.001.SLDASM"
    )
    v14 = a700_dir / "project02_A800_A180_then_A700_snapshot_context_insert_V14.SLDASM"
    candidates = [
        {
            "stateId": "cleaning",
            "snapshotPath": str(a700_dir / "a700_prototype_disk_clean_subtree_poses_v2.json"),
            "assemblyPath": str(source_assembly),
            "sourceAuditAccepted": True,
        },
        {
            "stateId": "weighing",
            "snapshotPath": str(a700_dir / "a700_v14_subtree_poses.json"),
            "assemblyPath": str(v14),
            "sourceAuditAccepted": True,
        },
        {
            "stateId": "maintenance",
            "snapshotPath": str(a700_dir / "a700_v15_subtree_poses.json"),
            "assemblyPath": str(
                ROOT / "demo/semantic_ports/project02_service_installations_v1/A300/"
                "project02_A800_A180_A700snapshot_then_A300_context_insert_V15.SLDASM"
            ),
            "sourceAuditAccepted": True,
        },
    ]
    # The only named mate previously found in the A100 graph is an ordinary
    # distance mate at one current position.  Keep it as a rejected candidate
    # so the audit records why it must not be promoted to a travel limit.
    a100_sources = [
        {
            "axis": "unresolved",
            "valve": "unresolved",
            "mateName": "LimitDistance1",
            "mateType": "swMateDISTANCE",
            "limitKind": "current-position",
            "minimumMeters": None,
            "maximumMeters": None,
            "authority": "prototype-estimated",
            "sourceReference": str(ROOT / "demo/layout_previews/project02_a100_internal_mate_graph.json"),
        }
    ]
    report = build_dynamic_source_audit(candidates, a100_sources)
    a700_graph_path = ROOT / (
        "demo/semantic_ports/project02_full_machine_increment_v1/"
        "a700_internal_module_mate_graph.json"
    )
    a100_graph_path = ROOT / "demo/layout_previews/project02_a100_internal_mate_graph.json"
    a700_graph = json.loads(a700_graph_path.read_text(encoding="utf-8")) if a700_graph_path.is_file() else {}
    a100_graph = json.loads(a100_graph_path.read_text(encoding="utf-8")) if a100_graph_path.is_file() else {}

    def mate_types(graph: dict) -> list[str]:
        return sorted({str(row.get("MateTypeName") or "") for row in graph.get("Mates") or []})

    def dynamic_mates(graph: dict) -> list[dict]:
        result = []
        for row in graph.get("Mates") or []:
            name = str(row.get("MateName") or "")
            mate_type = str(row.get("MateTypeName") or "")
            if "LIMIT" in mate_type.upper() or "限位" in name or "LIMIT" in name.upper():
                result.append({"name": name, "type": mate_type, "distance": row.get("Distance")})
        return result

    report["cadDeepAudit"] = {
        "a700InternalMateGraph": {
            "path": str(a700_graph_path),
            "moduleCount": a700_graph.get("ModuleCount"),
            "interModuleMateCount": a700_graph.get("InterModuleMateCount"),
            "mateTypes": mate_types(a700_graph),
            "dynamicLimitMates": dynamic_mates(a700_graph),
            "conclusion": "A710/A720/A730只有重合、宽度、平行等静态安装关系；未发现三状态或限位配合。",
        },
        "a100InternalMateGraph": {
            "path": str(a100_graph_path),
            "mateTypes": mate_types(a100_graph),
            "dynamicLimitMates": dynamic_mates(a100_graph),
            "conclusion": "名为LimitDistance1的对象导出类型为普通swMateDISTANCE，只证明当前距离，不证明[min,max]。",
        },
    }
    report["generatedAt"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    report["decision"] = {
        "runProductionDynamicGate": report["productionEvidenceReady"],
        "runStaticDemo": True,
        "blockingInputs": [
            "A700清洁、称重、维护三个真实机械状态（当前三个候选的模块局部姿态并不独立）",
            "A100左右阀XYZ六组可追溯[min,max]限位",
        ],
    }
    output = ROOT / (
        "demo/semantic_ports/project02_full_machine_increment_v1/"
        "dynamic_engineering_source_audit.json"
    )
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "productionEvidenceReady": report["productionEvidenceReady"], "a700DistinctStates": report["a700"]["acceptedDistinctStateCount"], "a100AcceptedSources": report["a100"]["acceptedLimitSourceCount"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
