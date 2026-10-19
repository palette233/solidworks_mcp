#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.project05_migration import build_project05_migration_skeleton  # noqa: E402
from demo_backend.project05_service_points import infer_project05_service_points  # noqa: E402


def _load(name: str) -> dict:
    return json.loads((ROOT / "demo/layout_previews" / name).read_text(encoding="utf-8-sig"))


def main() -> int:
    result = infer_project05_service_points(
        _load("project05_g000_world_leaf_envelopes.json"),
        _load("project05_n000_world_leaf_envelopes.json"),
        _load("project05_p000_world_leaf_envelopes.json"),
        _load("project05_first_stage_geometry.json"),
    )
    result["generatedAt"] = datetime.now(timezone.utc).isoformat()
    output = ROOT / "demo/layout_previews/project05_service_points.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    readiness = build_project05_migration_skeleton(ROOT)
    readiness["generatedAt"] = datetime.now(timezone.utc).isoformat()
    text = json.dumps(readiness, ensure_ascii=False, indent=2) + "\n"
    (ROOT / "demo/project05_parameter_package.json").write_text(text, encoding="utf-8")
    (ROOT / "demo/layout_previews/project05_migration_readiness.json").write_text(
        text, encoding="utf-8"
    )
    print(json.dumps({
        "success": True,
        "output": str(output),
        "servicePortCount": len(result["servicePorts"]),
        "missingEvidence": readiness["missingRequiredEvidence"],
        "partialEvidence": readiness["partialEvidence"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
