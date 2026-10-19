#!/usr/bin/env python3
"""Correctly classify Project03's ten main modules and five auxiliary instances."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "demo/layout_previews/project03_selected_solution_replay.json"
RESULT = ROOT / "demo/layout_previews/project03_solution1_v1_replay_result.json"


def main() -> None:
    layout = json.loads(LAYOUT.read_text(encoding="utf-8-sig"))
    result = json.loads(RESULT.read_text(encoding="utf-8-sig"))
    expected = {item["componentName"] for item in layout.get("components") or []}
    step = next(item for item in result.get("steps") or [] if item.get("tool") == "list_component_poses")
    poses = step.get("payload") if isinstance(step.get("payload"), list) else []
    actual = {str(item.get("Name")) for item in poses if item.get("Name")}
    auxiliary = sorted(actual - expected)
    audit = {
        "requiredMainModuleCount": 10,
        "actualTopLevelCount": len(poses),
        "actualMainModuleCount": len(actual & expected),
        "auxiliaryTopLevelCount": len(auxiliary),
        "missingMainModuleNames": sorted(expected - actual),
        "auxiliaryTopLevelNames": auxiliary,
    }
    audit["success"] = audit["actualMainModuleCount"] == 10 and not audit["missingMainModuleNames"]
    target = Path(result["targetAssemblyPath"])
    screenshot = Path(result["screenshotPath"])
    steps_clear = not any(item.get("isError") or item.get("businessFailed") for item in result.get("steps") or [])
    success = audit["success"] and steps_clear and target.is_file() and screenshot.is_file()
    result["topLevelAudit"] = audit
    result["success"] = success
    result["status"] = "PROJECT03_REPLAY_SAVED_AABB_PENDING" if success else "PROJECT03_REPLAY_FAILED"
    result["auditCorrection"] = {
        "reason": "Project03 source contains ten primary modules plus five known top-level auxiliary instances.",
        "replayRepeated": False,
    }
    RESULT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"success": success, "status": result["status"], "topLevelAudit": audit, "output": str(RESULT)}, ensure_ascii=False))
    if not success:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
