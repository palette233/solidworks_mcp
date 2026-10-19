#!/usr/bin/env python3
"""Compile and validate the first real Project03 incremental CAD work packet."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.project03_incremental_work_packet import (  # noqa: E402
    build_project03_ae00_work_packet,
)


DEFAULT_GRAPH = ROOT / "demo/layout_previews/project03_module_mate_graph.json"
DEFAULT_GEOMETRY = ROOT / "demo/layout_previews/project03_first_stage_geometry.json"
DEFAULT_OUTPUT = ROOT / "demo/semantic_ports/project03_AE00_first_increment_v1"


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--geometry", type=Path, default=DEFAULT_GEOMETRY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    graph = load(args.graph.resolve())
    geometry = load(args.geometry.resolve())
    prototype = Path(str(geometry["sourceAssemblyPath"]))
    result = build_project03_ae00_work_packet(graph, prototype)
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "path_recovery_audit.json": result["pathAudit"],
        "face_endpoint_catalog.json": result["endpointCatalog"],
        "semantic_port_catalog.json": result["semanticCatalog"],
        "base_AA00_AF00_graph.json": result["baseGraph"],
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
    for name, value in artifacts.items():
        write(output / name, value)
    print(json.dumps(artifacts["work_packet_summary.json"], ensure_ascii=False, indent=2))
    return 0 if result["summary"]["safeToStartCad"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
