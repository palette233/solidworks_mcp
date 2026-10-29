#!/usr/bin/env python3
"""Audit actual staged CAD/state/function evidence; never start CAD or publish."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))
from demo_backend.functional_chain_closure import build_functional_chain_closure  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output exists; choose a fresh evidence file")
    request = json.loads(args.request.read_text(encoding="utf-8-sig"))
    started = time.perf_counter()
    result = build_functional_chain_closure(
        ROOT, stages=request["stages"], functional_reports=request.get("functionalReports"),
        required_roles=request.get("requiredRoles"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "cadPassed": result["cadPassed"],
                      "proxyGeometryPassed": result["proxyGeometryPassed"], "functionalPassed": result["functionalPassed"],
                      "unknownFunctionalRoles": result["unknownFunctionalRoles"],
                      "offlineDurationSeconds": time.perf_counter()-started, "cadSeconds": 0}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
