#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.project03_occupancy import build_project03_occupancy_and_collision_policy
from demo_backend.project_migration import build_project03_migration_skeleton


def _load(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8-sig"))


def main() -> int:
    captures = [
        _load("demo/layout_previews/project03_ae00_ad00_leaf_envelopes.json"),
        _load("demo/layout_previews/project03_ai00_leaf_envelopes.json"),
        _load("demo/layout_previews/project03_ag00_ah00_leaf_envelopes.json"),
        _load("demo/layout_previews/project03_ab00_ac00_leaf_envelopes.json"),
    ]
    result = build_project03_occupancy_and_collision_policy(
        _load("demo/layout_previews/project03_top_level_poses.json"),
        _load("demo/layout_previews/project03_first_stage_geometry.json"),
        captures,
    )
    result["generatedAt"] = datetime.now(timezone.utc).isoformat()
    output = ROOT / "demo/layout_previews/project03_module_occupancy.json"
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    readiness = build_project03_migration_skeleton(ROOT)
    readiness["generatedAt"] = datetime.now(timezone.utc).isoformat()
    text = json.dumps(readiness, ensure_ascii=False, indent=2) + "\n"
    (ROOT / "demo/project03_parameter_package.json").write_text(text, encoding="utf-8")
    (ROOT / "demo/layout_previews/project03_migration_readiness.json").write_text(
        text, encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "success": result["status"] == "PROJECT03_OCCUPANCY_AND_COLLISION_POLICY_READY",
                "output": str(output),
                "capturedLeafBodies": result["coverage"]["capturedLeafBodyCount"],
                "layoutObjects": result["coverage"]["layoutObjectCount"],
                "pairCount": result["staticCollisionPolicy"]["pairCount"],
                "strictPairs": len(result["staticCollisionPolicy"]["strictMultiAabbPairs"]),
                "conditionalPairs": len(result["staticCollisionPolicy"]["conditionalBrepPairs"]),
                "installationPairs": len(result["staticCollisionPolicy"]["installationContactPairs"]),
                "top3SolveReady": readiness["top3SolveReady"],
                "partialEvidence": readiness["partialEvidence"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if result["status"] == "PROJECT03_OCCUPANCY_AND_COLLISION_POLICY_READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
