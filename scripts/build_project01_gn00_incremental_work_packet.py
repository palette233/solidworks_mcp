#!/usr/bin/env python3
from __future__ import annotations
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))
from demo_backend.project01_gn00_work_packet import build_project01_gn00_work_packet  # noqa: E402

PROTOTYPE = Path(r"D:\zengshuang\workspace\cuhksz\cad_data\001-给港中文AI训练用资料_20260624\项目01\01-项目3D图纸\CITLB24N074&CITLB24N075\FL9C24N074AA00.001.SLDASM")
OUTPUT = ROOT / "demo/semantic_ports/project01_GN00_fourth_increment_v1"

def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))

def main() -> int:
    result = build_project01_gn00_work_packet(
        load(ROOT / "demo/layout_previews/project01_module_mate_graph.json"),
        load(ROOT / "demo/semantic_ports/project01_SM00_third_increment_v1/assembly_plan_effective.json"),
        PROTOTYPE,
    )
    OUTPUT.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "path_recovery_audit.json": result["pathAudit"], "face_endpoint_catalog.json": result["endpointCatalog"],
        "semantic_port_catalog.json": result["semanticCatalog"], "base_context_graph.json": result["baseGraph"],
        "assembly_plan_request.json": result["request"], "assembly_plan_patch.json": result["patch"],
        "assembly_plan_effective.json": result["effectiveGraph"],
        "work_packet_summary.json": {**result["summary"], "generatedAt": datetime.now(timezone.utc).isoformat(), "outputDirectory": str(OUTPUT.resolve())},
    }
    for name, payload in artifacts.items():
        (OUTPUT / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(artifacts["work_packet_summary.json"], ensure_ascii=False, indent=2))
    return 0 if result["summary"]["safeToStartStaticCad"] else 2

if __name__ == "__main__":
    raise SystemExit(main())
