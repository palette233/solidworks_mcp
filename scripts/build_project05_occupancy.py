#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.project05_migration import build_project05_migration_skeleton  # noqa: E402
from demo_backend.project05_occupancy import build_project05_occupancy_and_collision_policy  # noqa: E402
from demo_backend.project05_structural_capture_plan import REQUIRED_CAPTURE_CODES  # noqa: E402


def _load(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8-sig"))


def _discover_complete_world_captures() -> dict[str, dict]:
    """Load every durable Project05 world capture that is complete.

    Structural modules are acquired incrementally and can be absent while a
    long CAD capture is still pending.  The occupancy builder must therefore
    discover captures from the shared contract instead of keeping a second,
    stale hard-coded list of the first six modules.
    """

    captures: dict[str, dict] = {}
    for code in REQUIRED_CAPTURE_CODES:
        path = ROOT / "demo/layout_previews" / f"project05_{code.lower()}_world_leaf_envelopes.json"
        if not path.is_file():
            continue
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if payload.get("coverageComplete") is True:
            captures[code] = payload
    return captures


def main() -> int:
    captures = _discover_complete_world_captures()
    result = build_project05_occupancy_and_collision_policy(
        _load("demo/layout_previews/project05_top_level_poses.json"),
        _load("demo/layout_previews/project05_first_stage_geometry.json"),
        world_captures_by_code=captures,
    )
    result["generatedAt"] = datetime.now(timezone.utc).isoformat()
    output = ROOT / "demo/layout_previews/project05_module_occupancy.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    readiness = build_project05_migration_skeleton(ROOT)
    readiness["generatedAt"] = datetime.now(timezone.utc).isoformat()
    text = json.dumps(readiness, ensure_ascii=False, indent=2) + "\n"
    (ROOT / "demo/project05_parameter_package.json").write_text(text, encoding="utf-8")
    (ROOT / "demo/layout_previews/project05_migration_readiness.json").write_text(text, encoding="utf-8")
    policy = result["staticCollisionPolicy"]
    print(json.dumps({
        "status": result["status"],
        "solverOccupancyReady": result["solverOccupancyReady"],
        "leafCompleteModuleCodes": result["coverage"]["leafCompleteModuleCodes"],
        "pairCount": policy["pairCount"],
        "strictPairs": len(policy["strictMultiAabbPairs"]),
        "conditionalPairs": len(policy["conditionalBrepPairs"]),
        "installationPairs": len(policy["installationContactPairs"]),
        "missingEvidence": readiness["missingRequiredEvidence"],
        "partialEvidence": readiness["partialEvidence"],
        "output": str(output),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
