#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "demo-backend" / "src"))

from demo_backend.project_migration import build_project03_migration_skeleton


def main() -> int:
    result = build_project03_migration_skeleton(ROOT)
    result["generatedAt"] = datetime.now(timezone.utc).isoformat()
    output = ROOT / "demo/project03_parameter_package.json"
    readiness = ROOT / "demo/layout_previews/project03_migration_readiness.json"
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    output.write_text(text, encoding="utf-8")
    readiness.write_text(text, encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "resolvedModuleCadCount": result["resolvedModuleCadCount"],
        "moduleCount": result["moduleCount"],
        "missingRequiredEvidence": result["missingRequiredEvidence"],
        "partialEvidence": result["partialEvidence"],
        "top3SolveReady": result["top3SolveReady"],
        "output": str(output),
    }, ensure_ascii=False, indent=2))
    return 0 if result["sourceAssemblyExists"] and result["allModuleCadPathsResolved"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
