"""Create a new version of occupancy bound to original single-instance capture."""
import argparse
import json
import sys
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))
from demo_backend.occupancy_capture_binding import bind_occupancy_capture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--occupancy", type=Path, required=True)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--module", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    started = perf_counter()
    result = bind_occupancy_capture(args.occupancy, args.capture, args.module)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"output": str(args.output), "module": args.module,
                      "durationSeconds": perf_counter() - started, "cadStarted": False}))


if __name__ == "__main__":
    main()
