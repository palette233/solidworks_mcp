#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.project05_dual_valve_reach import infer_project05_dual_valve_reach  # noqa: E402
from demo_backend.project05_migration import build_project05_migration_skeleton  # noqa: E402


def _load(name: str) -> dict:
    return json.loads((ROOT / "demo/layout_previews" / name).read_text(encoding="utf-8-sig"))


B000_AXIS_EVIDENCE_FILE_NAMES = [
    # Captured by a read-only directory audit on 2026-10-01.  Keeping the
    # ASCII identifying tokens here avoids the known Windows Python mojibake
    # problem in the Chinese source-tree prefix.
    "linear-motor_TC-D01-T7512A-950L-HA.SLDASM",
    "TC-SLM140-D01-T6009B-800L-TL10-3-2024.8.2(1).SLDPRT",
]


def main() -> int:
    result = infer_project05_dual_valve_reach(
        _load("project05_top_level_poses.json"),
        _load("project05_first_stage_geometry.json"),
        _load("project05_work_positions.json"),
        _load("project05_service_points.json"),
        B000_AXIS_EVIDENCE_FILE_NAMES,
    )
    result["generatedAt"] = datetime.now(timezone.utc).isoformat()
    output = ROOT / "demo/layout_previews/project05_dual_valve_reach.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    readiness = build_project05_migration_skeleton(ROOT)
    readiness["generatedAt"] = datetime.now(timezone.utc).isoformat()
    text = json.dumps(readiness, ensure_ascii=False, indent=2) + "\n"
    (ROOT / "demo/project05_parameter_package.json").write_text(text, encoding="utf-8")
    (ROOT / "demo/layout_previews/project05_migration_readiness.json").write_text(text, encoding="utf-8")
    print(json.dumps({
        "success": True,
        "output": str(output),
        "allTargetsInside": result["allTargetsInsideCommonPlanarReach"],
        "minimumMarginMillimeters": result["minimumPlanarMarginMeters"] * 1000.0,
        "missingEvidence": readiness["missingRequiredEvidence"],
        "partialEvidence": readiness["partialEvidence"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
