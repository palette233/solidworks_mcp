#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "demo-backend" / "src"))

from demo_backend.project02_engineering_inputs import apply_confirmed_project02_engineering_inputs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Write confirmed sections to the request")
    args = parser.parse_args()
    input_path = ROOT / "demo/project02_engineering_inputs.json"
    request_path = ROOT / "demo/FL9A24D062A000_real_process_request.json"
    inputs = json.loads(input_path.read_text(encoding="utf-8-sig"))
    request = json.loads(request_path.read_text(encoding="utf-8-sig"))
    updated, report = apply_confirmed_project02_engineering_inputs(request, inputs)
    report["mode"] = "apply" if args.apply else "dry-run"
    if args.apply and report["appliedSections"]:
        request_path.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report["requestUpdated"] = True
    else:
        report["requestUpdated"] = False
    output = ROOT / "demo/layout_previews/project02_engineering_input_application.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
