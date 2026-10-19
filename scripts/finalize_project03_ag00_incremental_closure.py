#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.project03_ag00_incremental_closure import (  # noqa: E402
    build_project03_ag00_incremental_closure,
)


ANCHORED = ROOT / "demo/semantic_ports/project03_AG00_fourth_increment_anchored_v1"
DIAGNOSTIC = ROOT / "demo/semantic_ports/project03_AG00_fourth_increment_diagnostic_v1"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    result = build_project03_ag00_incremental_closure(
        source_graph=load(ROOT / "demo/layout_previews/project03_module_mate_graph.json"),
        diagnostic_result=load(DIAGNOSTIC / "step04_AG00_diagnostic.result.json"),
        anchored_result=load(ANCHORED / "step04_AG00_increment.result.json"),
        poses=load(ANCHORED / "step04_top_level_poses.json"),
        screening=load(ANCHORED / "step04_interference_screening.json"),
        service_points=load(ROOT / "demo/layout_previews/project03_service_points.json"),
        assembly_path=ANCHORED / "step04_AA00_AF00_AE00_AD00_AI00_AG00_increment.SLDASM",
    )
    output = ANCHORED / "step04_AG00_incremental_closure.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "success": result["success"],
        "residualDofConfirmed": result["installationSemantics"]["diagnosticConfirmedResidualDof"],
        "serviceTargetCount": result["serviceTargetGate"]["targetCount"],
        "pairCount": result["collisionGate"]["pairCount"],
        "output": str(output),
    }, ensure_ascii=False, indent=2))
    return 0 if result["success"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
