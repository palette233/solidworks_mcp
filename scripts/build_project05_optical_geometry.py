#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))
from demo_backend.project05_migration import build_project05_migration_skeleton  # noqa: E402
from demo_backend.project05_optical_geometry import build_project05_optical_geometry  # noqa: E402


def _load(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8-sig"))


def main() -> int:
    result = build_project05_optical_geometry(
        _load("demo/layout_previews/project05_f000_world_leaf_envelopes.json"),
        _load("demo/layout_previews/project05_m000_world_leaf_envelopes.json"),
        _load("demo/layout_previews/project05_first_stage_geometry.json"),
        _load("demo/layout_previews/project05_work_positions.json"),
    )
    result["generatedAt"] = datetime.now(timezone.utc).isoformat()
    output = ROOT / "demo/layout_previews/project05_optical_geometry.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    readiness = build_project05_migration_skeleton(ROOT)
    readiness["generatedAt"] = datetime.now(timezone.utc).isoformat()
    text = json.dumps(readiness, ensure_ascii=False, indent=2) + "\n"
    (ROOT / "demo/project05_parameter_package.json").write_text(text, encoding="utf-8")
    (ROOT / "demo/layout_previews/project05_migration_readiness.json").write_text(text, encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "scannerBeamCount": result["scanner"]["explicitBeamCount"],
        "scannerCoarseAxisUsable": result["scanner"]["axisGeometryCoarseLayoutUsable"],
        "ccdCoarseAxisUsable": result["ccd"]["axisGeometryCoarseLayoutUsable"],
        "preciseOpticalConstraintMayBeUsed": result["releaseDecision"]["preciseOpticalConstraintMayBeUsed"],
        "missingEvidence": readiness["missingRequiredEvidence"],
        "partialEvidence": readiness["partialEvidence"],
        "output": str(output),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
