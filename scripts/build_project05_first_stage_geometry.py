#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))
from demo_backend.project05_geometry import infer_project05_first_stage_geometry  # noqa: E402
from demo_backend.project05_migration import build_project05_migration_skeleton  # noqa: E402


def load(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8-sig"))


def main() -> None:
    result = infer_project05_first_stage_geometry(
        load("demo/layout_previews/project05_module_mate_graph.json"),
        load("demo/layout_previews/project05_top_level_poses.json"),
    )
    output = ROOT / "demo/layout_previews/project05_first_stage_geometry.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    readiness = build_project05_migration_skeleton(ROOT)
    text = json.dumps(readiness, ensure_ascii=False, indent=2) + "\n"
    (ROOT / "demo/project05_parameter_package.json").write_text(text, encoding="utf-8")
    (ROOT / "demo/layout_previews/project05_migration_readiness.json").write_text(text, encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "originWorldMeters": result["installationFrame"]["originWorldMeters"],
        "frameToTransportTransverseDistanceMeters": result["transportInstallationInterface"]["frameToTransportTransverseDistanceMeters"],
        "capturedInstanceCount": result["topLevelOccupancy"]["capturedInstanceCount"],
        "activeMajorModuleInstanceCount": result["topLevelOccupancy"]["activeMajorModuleInstanceCount"],
        "readinessStatus": readiness["status"],
        "missingCount": len(readiness["missingRequiredEvidence"]),
        "partialCount": len(readiness["partialEvidence"]),
        "output": str(output),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
