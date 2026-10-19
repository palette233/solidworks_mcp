#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "demo-backend" / "src"))

from demo_backend.project02_valve_reach import build_project02_valve_reach_audit


def main() -> int:
    request = json.loads((ROOT / "demo/FL9A24D062A000_real_process_request.json").read_text(encoding="utf-8-sig"))
    preview = json.loads((ROOT / "demo/layout_previews/project02_preview.json").read_text(encoding="utf-8-sig"))
    report = build_project02_valve_reach_audit(request, preview)
    output = ROOT / "demo/layout_previews/project02_dual_valve_reach_audit.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
