#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.project03_incremental_work_packet import build_project03_ah00_work_packet  # noqa: E402


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    output = ROOT / "demo/semantic_ports/project03_AH00_fifth_increment_v1"
    result = build_project03_ah00_work_packet(
        load(ROOT / "demo/layout_previews/project03_module_mate_graph.json"),
        Path(load(ROOT / "demo/layout_previews/project03_first_stage_geometry.json")["sourceAssemblyPath"]),
        load(ROOT / "demo/layout_previews/project03_service_points.json"),
    )
    output.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "path_recovery_audit.json": result["pathAudit"],
        "face_endpoint_catalog.json": result["endpointCatalog"],
        "semantic_port_catalog.json": result["semanticCatalog"],
        "base_context_graph.json": result["baseGraph"],
        "assembly_plan_request.json": result["request"],
        "assembly_plan_patch.json": result["patch"],
        "assembly_plan_effective.json": result["effectiveGraph"],
        "work_packet_summary.json": {**result["summary"], "generatedAt": datetime.now(timezone.utc).isoformat()},
    }
    for name, payload in artifacts.items():
        (output / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(artifacts["work_packet_summary.json"], ensure_ascii=False, indent=2))
    return 0 if result["summary"]["staticCadReady"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
