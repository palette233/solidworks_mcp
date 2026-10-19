#!/usr/bin/env python3
from __future__ import annotations
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))
from demo_backend.project01_final_gantry_work_packets import (  # noqa: E402
    build_project01_lm00_work_packet,
    build_project01_zz00_work_packet,
)

PROTOTYPE = Path(r"D:\zengshuang\workspace\cuhksz\cad_data\001-给港中文AI训练用资料_20260624\项目01\01-项目3D图纸\CITLB24N074&CITLB24N075\FL9C24N074AA00.001.SLDASM")
LM_DIR = ROOT / "demo/semantic_ports/project01_LM00_final_stage_action1_v1"
ZZ_DIR = ROOT / "demo/semantic_ports/project01_ZZ00_final_stage_action2_v1"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_packet(output: Path, result: dict) -> None:
    output.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "path_recovery_audit.json": result["pathAudit"],
        "face_endpoint_catalog.json": result["endpointCatalog"],
        "semantic_port_catalog.json": result["semanticCatalog"],
        "base_context_graph.json": result["baseGraph"],
        "assembly_plan_request.json": result["request"],
        "assembly_plan_patch.json": result["patch"],
        "assembly_plan_effective.json": result["effectiveGraph"],
        "work_packet_summary.json": {
            **result["summary"],
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "outputDirectory": str(output.resolve()),
        },
    }
    for name, payload in artifacts.items():
        (output / name).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


def main() -> int:
    source = load(ROOT / "demo/layout_previews/project01_module_mate_graph.json")
    prior = load(
        ROOT
        / "demo/semantic_ports/project01_GJ00_sixth_increment_v1/assembly_plan_effective.json"
    )
    lm = build_project01_lm00_work_packet(
        source,
        prior,
        PROTOTYPE,
        load(LM_DIR / "prototype_LM00_subtree_poses.json"),
    )
    write_packet(LM_DIR, lm)
    zz = build_project01_zz00_work_packet(source, lm["effectiveGraph"], PROTOTYPE)
    write_packet(ZZ_DIR, zz)
    print(json.dumps({"lm00": lm["summary"], "zz00": zz["summary"]}, ensure_ascii=False, indent=2))
    return 0 if lm["summary"]["safeToStartStaticCad"] and zz["summary"]["safeToStartStaticCad"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
