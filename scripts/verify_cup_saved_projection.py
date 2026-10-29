"""Offline mouth projection verification using saved CAD result/state; no CAD."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))
from demo_backend.cup_function_point import verify_saved_cup_projection


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--geometry-report", type=Path, required=True)
    parser.add_argument("--cad-result", type=Path, required=True)
    parser.add_argument("--saved-state", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Refusing to overwrite cup saved-state evidence")
    result = verify_saved_cup_projection(geometry_report_path=args.geometry_report,
        cad_result_path=args.cad_result, saved_state_path=args.saved_state)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({k: result[k] for k in ("status", "targetCupProjectionPassed",
        "threeDimensionalCupMouthAlignmentPassed", "durationSeconds")}, ensure_ascii=False))
    return 0 if result["targetCupProjectionPassed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
