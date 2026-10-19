#!/usr/bin/env python3
"""Build the first Project 01 independent incremental CAD work packet."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.project01_incremental_work_packet import (  # noqa: E402
    build_project01_ss00_work_packet,
)


DEFAULT_GRAPH = ROOT / "demo/layout_previews/project01_module_mate_graph.json"
DEFAULT_PROTOTYPE = Path(
    r"D:\zengshuang\workspace\cuhksz\cad_data\001-给港中文AI训练用资料_20260624\项目01\01-项目3D图纸\CITLB24N074&CITLB24N075\FL9C24N074AA00.001.SLDASM"
)
DEFAULT_OUTPUT = ROOT / "demo/semantic_ports/project01_SS00_first_increment_v1"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--prototype", type=Path, default=DEFAULT_PROTOTYPE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = build_project01_ss00_work_packet(
        load(args.graph.resolve()), args.prototype.resolve()
    )
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "path_recovery_audit.json": result["pathAudit"],
        "face_endpoint_catalog.json": result["endpointCatalog"],
        "semantic_port_catalog.json": result["semanticCatalog"],
        "base_JJ00_HL00_graph.json": result["baseGraph"],
        "assembly_plan_request.json": result["request"],
        "assembly_plan_patch.json": result["patch"],
        "assembly_plan_effective.json": result["effectiveGraph"],
        "work_packet_summary.json": {
            **result["summary"],
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "sourceGraphPath": str(args.graph.resolve()),
            "outputDirectory": str(output),
        },
    }
    for name, payload in artifacts.items():
        (output / name).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(artifacts["work_packet_summary.json"], ensure_ascii=False, indent=2))
    return 0 if result["summary"]["safeToStartCad"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
