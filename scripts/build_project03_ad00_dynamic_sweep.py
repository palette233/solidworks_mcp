#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.project03_dynamic_sweep import (  # noqa: E402
    build_project03_ad00_dynamic_sweep,
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    result = build_project03_ad00_dynamic_sweep(
        load(ROOT / "demo/layout_previews/project03_work_positions.json"),
        load(ROOT / "demo/layout_previews/project03_first_stage_geometry.json"),
        load(ROOT / "demo/layout_previews/project03_module_occupancy.json"),
        load(ROOT / "demo/semantic_ports/project03_dynamic_estimates_v1.json"),
    )
    result["generatedAt"] = datetime.now(timezone.utc).isoformat()
    output = ROOT / "demo/layout_previews/project03_ad00_dynamic_sweep_estimate.json"
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "workPositionCount": len(result["workPositionSweeps"]),
                "broadPhaseCandidateCount": result["broadPhaseCandidateCount"],
                "candidateModules": sorted(
                    {row["otherModuleCode"] for row in result["broadPhaseCandidates"]}
                ),
                "productionDynamicReady": result["productionDynamicReady"],
                "output": str(output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result["success"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
