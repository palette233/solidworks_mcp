#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))
from demo_backend.project05_process import build_project05_process_semantics  # noqa: E402


def main() -> int:
    output = ROOT / "demo/layout_previews/project05_process_semantics.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    result = build_project05_process_semantics()
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "workPositionCount": result["transportProcess"]["workPositionCount"],
        "scanStation": result["scanProcess"]["station"],
        "ccdFieldOfViewMillimeters": result["ccdProcess"]["fieldOfViewMillimeters"],
        "output": str(output),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
