#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.project03_geometry import build_project03_first_stage_geometry
from demo_backend.project_migration import build_project03_migration_skeleton


def main() -> int:
    graph = json.loads((ROOT / "demo/layout_previews/project03_module_mate_graph.json").read_text(encoding="utf-8-sig"))
    poses = json.loads((ROOT / "demo/layout_previews/project03_top_level_poses.json").read_text(encoding="utf-8-sig"))
    result = build_project03_first_stage_geometry(graph, poses)
    result["generatedAt"] = datetime.now(timezone.utc).isoformat()
    output = ROOT / "demo/layout_previews/project03_first_stage_geometry.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    readiness = build_project03_migration_skeleton(ROOT)
    readiness["generatedAt"] = datetime.now(timezone.utc).isoformat()
    text = json.dumps(readiness, ensure_ascii=False, indent=2) + "\n"
    (ROOT / "demo/project03_parameter_package.json").write_text(text, encoding="utf-8")
    (ROOT / "demo/layout_previews/project03_migration_readiness.json").write_text(text, encoding="utf-8")
    print(json.dumps({
        "success": True,
        "output": str(output),
        "majorModuleCount": result["topLevelOccupancy"]["majorModuleCount"],
        "looseAuxiliaryInstanceCount": result["topLevelOccupancy"]["looseAuxiliaryInstanceCount"],
        "operationSideCandidate": result["operationSideInference"]["candidate"],
        "missingEvidence": readiness["missingRequiredEvidence"],
        "partialEvidence": readiness["partialEvidence"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
