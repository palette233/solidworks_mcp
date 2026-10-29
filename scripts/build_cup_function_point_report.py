"""Measure cup-mouth candidates from existing bounded leaf catalogs; no CAD."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))
from demo_backend.cup_function_point import build_cup_function_point_report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Refusing to overwrite existing cup geometry evidence")
    report = build_cup_function_point_report(args.request)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"output": str(args.output.resolve()),
                      "allRequestedCatalogsHaveMouthEvidence": report["allRequestedCatalogsHaveMouthEvidence"],
                      "durationSeconds": report["durationSeconds"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
