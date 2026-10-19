#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.project05_migration import build_project05_migration_skeleton  # noqa: E402
from demo_backend.project05_structural_capture_plan import build_project05_structural_capture_plan  # noqa: E402


def main() -> int:
    readiness = build_project05_migration_skeleton(ROOT)
    result = build_project05_structural_capture_plan(ROOT, readiness)
    result["generatedAt"] = datetime.now(timezone.utc).isoformat()
    result["lastCadAttempt"] = {
        "date": "2026-10-01",
        "defaultSession": {
            "result": "MCP initialize handshake did not return",
            "elapsedSecondsBeforeAbort": 591,
        },
        "forceNewInstance": {
            "result": "MCP initialize handshake did not return and no second SolidWorks process appeared",
            "elapsedSecondsBeforeAbort": 120,
        },
        "mainSolidWorksProcessPreserved": True,
        "geometryCaptureStarted": False,
    }
    output = ROOT / "demo/layout_previews/project05_structural_capture_plan.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "success": True,
        "output": str(output),
        "completeCaptureCount": result["completeCaptureCount"],
        "pendingCaptureCodes": result["pendingCaptureCodes"],
        "coarseTop3SolveAllowed": result["releaseGate"]["coarseTop3SolveAllowed"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
