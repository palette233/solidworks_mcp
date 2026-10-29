"""Measure historical P000/A600 placement; never starts CAD or publishes."""
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))
from demo_backend.wastecup_target_station import build_p000_a600_target_station_audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--state", type=Path)
    parser.add_argument("--cad-result", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    clock, start = perf_counter(), datetime.now(timezone.utc).isoformat()
    report = build_p000_a600_target_station_audit(ROOT, state_path=args.state, cad_path=args.cad_result)
    report["scriptTiming"] = {"startedAtUtc": start, "finishedAtUtc": datetime.now(timezone.utc).isoformat(), "durationSeconds": perf_counter()-clock}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"status": report["status"], "measurements": report["measurements"], "durationSeconds": report["scriptTiming"]["durationSeconds"], "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
