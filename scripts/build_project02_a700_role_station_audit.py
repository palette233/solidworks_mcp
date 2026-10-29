#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.project02_a700_role_station_audit import (  # noqa: E402
    build_project02_a700_role_station_audit,
)


def main() -> int:
    output = ROOT / (
        "demo/goal_role_station_and_matched_slot_cases_20261028/"
        "n000-a600-a700-role-station-audit.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    report = build_project02_a700_role_station_audit(ROOT)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "output": str(output), "classification": report["classification"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
