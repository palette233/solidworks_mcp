#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))
from demo_backend.project05_migration import build_project05_migration_skeleton  # noqa: E402
from demo_backend.project05_workstations import infer_project05_work_positions  # noqa: E402


def main() -> int:
    capture = json.loads(
        (ROOT / "demo/layout_previews/project05_k000_world_leaf_envelopes.json").read_text(
            encoding="utf-8-sig"
        )
    )
    geometry = json.loads(
        (ROOT / "demo/layout_previews/project05_first_stage_geometry.json").read_text(
            encoding="utf-8-sig"
        )
    )
    result = infer_project05_work_positions(capture, geometry)
    result["generatedAt"] = datetime.now(timezone.utc).isoformat()
    output = ROOT / "demo/layout_previews/project05_work_positions.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    readiness = build_project05_migration_skeleton(ROOT)
    readiness["generatedAt"] = datetime.now(timezone.utc).isoformat()
    text = json.dumps(readiness, ensure_ascii=False, indent=2) + "\n"
    (ROOT / "demo/project05_parameter_package.json").write_text(text, encoding="utf-8")
    (ROOT / "demo/layout_previews/project05_migration_readiness.json").write_text(text, encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "coarseLayoutUsable": result["coarseLayoutUsable"],
        "centerSeparationMeters": result["centerSeparationMeters"],
        "workPositions": [item["installationFramePointMeters"] for item in result["workPositions"]],
        "missingEvidence": readiness["missingRequiredEvidence"],
        "partialEvidence": readiness["partialEvidence"],
        "output": str(output),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
