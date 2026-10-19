#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.project01_valve_reach import infer_project01_valve_reach
from demo_backend.project_migration import build_project01_migration_skeleton


def _load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8-sig"))


def main() -> int:
    result = infer_project01_valve_reach(
        _load("demo/layout_previews/project01_lm00_zz00_leaf_envelopes.json"),
        _load("demo/layout_previews/project01_first_stage_geometry.json"),
        _load("demo/layout_previews/project01_work_positions.json"),
        _load("demo/layout_previews/project01_service_points.json"),
    )
    result["generatedAt"] = datetime.now(timezone.utc).isoformat()
    output = ROOT / "demo/layout_previews/project01_dual_valve_reach.json"
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    readiness = build_project01_migration_skeleton(ROOT)
    readiness["generatedAt"] = datetime.now(timezone.utc).isoformat()
    text = json.dumps(readiness, ensure_ascii=False, indent=2) + "\n"
    (ROOT / "demo/project01_parameter_package.json").write_text(text, encoding="utf-8")
    (ROOT / "demo/layout_previews/project01_migration_readiness.json").write_text(
        text, encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "success": True,
                "output": str(output),
                "allRequiredTargetsInsideCommonReach": result[
                    "allRequiredTargetsInsideCommonReach"
                ],
                "requiredTargetCount": result["requiredTargetCount"],
                "minimumMarginMeters": result["minimumTargetBoundaryMarginMeters"],
                "missingEvidence": len(readiness["missingRequiredEvidence"]),
            },
            ensure_ascii=False,
        )
    )
    return 0 if result["allRequiredTargetsInsideCommonReach"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
