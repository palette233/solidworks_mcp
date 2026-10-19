#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.project03_scanner import infer_project03_scanner_geometry
from demo_backend.project_migration import build_project03_migration_skeleton


def main() -> int:
    capture = json.loads(
        (ROOT / "demo/layout_previews/project03_ai00_leaf_envelopes.json").read_text(
            encoding="utf-8-sig"
        )
    )
    geometry = json.loads(
        (ROOT / "demo/layout_previews/project03_first_stage_geometry.json").read_text(
            encoding="utf-8-sig"
        )
    )
    result = infer_project03_scanner_geometry(capture, geometry)
    result["generatedAt"] = datetime.now(timezone.utc).isoformat()
    output = ROOT / "demo/layout_previews/project03_scanner_geometry.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    readiness = build_project03_migration_skeleton(ROOT)
    readiness["generatedAt"] = datetime.now(timezone.utc).isoformat()
    text = json.dumps(readiness, ensure_ascii=False, indent=2) + "\n"
    (ROOT / "demo/project03_parameter_package.json").write_text(text, encoding="utf-8")
    (ROOT / "demo/layout_previews/project03_migration_readiness.json").write_text(
        text, encoding="utf-8"
    )
    scanner = result["scanners"][0]
    print(
        json.dumps(
            {
                "success": True,
                "output": str(output),
                "scannerCount": result["scannerCount"],
                "workingDistanceMeters": scanner["modeledWorkingDistanceMeters"],
                "opticalDirectionWorld": scanner["opticalDirectionWorld"],
                "targetInstallationFrameMeters": scanner[
                    "targetProxyInstallationFrameMeters"
                ],
                "missingEvidence": readiness["missingRequiredEvidence"],
                "partialEvidence": readiness["partialEvidence"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
