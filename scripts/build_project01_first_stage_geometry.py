#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.project01_geometry import build_project01_first_stage_geometry
from demo_backend.project_migration import build_project01_migration_skeleton


def main() -> int:
    graph_path = ROOT / "demo/layout_previews/project01_module_mate_graph.json"
    poses_path = ROOT / "demo/layout_previews/project01_top_level_poses.json"
    output_path = ROOT / "demo/layout_previews/project01_first_stage_geometry.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8-sig"))
    poses = json.loads(poses_path.read_text(encoding="utf-8-sig"))
    result = build_project01_first_stage_geometry(graph, poses)
    result["generatedAt"] = datetime.now(timezone.utc).isoformat()
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    readiness = build_project01_migration_skeleton(ROOT)
    readiness["generatedAt"] = datetime.now(timezone.utc).isoformat()
    text = json.dumps(readiness, ensure_ascii=False, indent=2) + "\n"
    (ROOT / "demo/project01_parameter_package.json").write_text(text, encoding="utf-8")
    (ROOT / "demo/layout_previews/project01_migration_readiness.json").write_text(text, encoding="utf-8")
    print(json.dumps({
        "success": True,
        "output": str(output_path),
        "missingEvidence": len(readiness["missingRequiredEvidence"]),
        "partialEvidence": len(readiness["partialEvidence"]),
        "solveObjectCount": len(readiness["proposedTopLevelSolveObjects"]),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
