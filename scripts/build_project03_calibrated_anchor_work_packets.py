#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.project03_incremental_work_packet import (  # noqa: E402
    build_project03_ab00_work_packet,
    build_project03_ag00_work_packet,
)


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
        },
    }
    for name, payload in artifacts.items():
        (output / name).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def main() -> int:
    graph = load(ROOT / "demo/layout_previews/project03_module_mate_graph.json")
    geometry = load(ROOT / "demo/layout_previews/project03_first_stage_geometry.json")
    prototype = Path(geometry["sourceAssemblyPath"])
    parameters = load(
        ROOT / "demo/semantic_ports/project03_calibrated_parameters_v1.json"
    )
    ag00 = build_project03_ag00_work_packet(
        graph,
        prototype,
        load(ROOT / "demo/layout_previews/project03_service_points.json"),
        case_anchored=True,
        calibrated_parameters=parameters,
    )
    ab00 = build_project03_ab00_work_packet(
        graph,
        prototype,
        load(ROOT / "demo/layout_previews/project03_dual_valve_reach.json"),
        calibrated_parameters=parameters,
    )
    outputs = {
        "AG00": ROOT
        / "demo/semantic_ports/project03_AG00_fourth_increment_calibrated_v2",
        "AB00": ROOT
        / "demo/semantic_ports/project03_AB00_final_stage_calibrated_v2",
    }
    write_packet(outputs["AG00"], ag00)
    write_packet(outputs["AB00"], ab00)
    summary = {
        "schemaVersion": "project03-calibrated-anchor-work-packets/v1",
        "success": bool(
            ag00["summary"]["staticCadReady"]
            and ag00["summary"]["calibratedAnchorApplied"]
            and ab00["summary"]["staticCadReady"]
            and ab00["summary"]["calibratedAnchorApplied"]
        ),
        "parameters": str(
            ROOT / "demo/semantic_ports/project03_calibrated_parameters_v1.json"
        ),
        "outputs": {key: str(value) for key, value in outputs.items()},
        "summaries": {"AG00": ag00["summary"], "AB00": ab00["summary"]},
    }
    summary_path = (
        ROOT
        / "demo/semantic_ports/project03_deprototype_ablation_v1/calibrated_work_packets.json"
    )
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["success"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
