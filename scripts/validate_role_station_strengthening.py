"""Timestamped offline regression; no CAD process is started by this runner."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
TESTS = [
    "test_goal_role_station_matched_slot_report.py",
    "test_goal_matched_alternate_slot_cases.py",
    "test_role_station_geometry.py",
    "test_wastecup_target_station.py",
    "test_scanner_target_association.py",
    "test_cross_project_scanner_alternate_route.py",
    "test_target_station_chain_preflight.py",
    "test_natural_language_staged_chain.py",
    "test_leaf_face_catalog_timing.py",
    "test_cleaning_service_region.py",
    "test_cup_function_point.py",
    "test_functional_chain_closure.py",
    "test_station_candidate_append.py",
]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--full", action="store_true")
    args = p.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    test_root = ROOT / "apps/demo-backend/tests"
    targets = [test_root] if args.full else [test_root / name for name in TESTS]
    for path in targets:
        if not path.exists():
            raise FileNotFoundError(path)
    args.output.mkdir(parents=True)
    cmd = [sys.executable, "-m", "pytest", *map(str, targets), "-q"]
    start, clock = datetime.now(timezone.utc).isoformat(), perf_counter()
    timed_out = False
    try:
        completed = subprocess.run(cmd, cwd=ROOT, capture_output=True, timeout=1200)
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        completed = subprocess.CompletedProcess(cmd, 124, exc.stdout or b"", exc.stderr or b"validation timeout")
    elapsed = perf_counter()-clock
    (args.output / "pytest-stdout.log").write_bytes(completed.stdout)
    (args.output / "pytest-stderr.log").write_bytes(completed.stderr)
    report = {"schemaVersion": "role-station-development-validation/v1", "command": cmd,
              "scope": "full_backend" if args.full else "targeted_offline",
              "startedAtUtc": start, "finishedAtUtc": datetime.now(timezone.utc).isoformat(),
              "durationSeconds": elapsed, "exitCode": completed.returncode,
              "success": completed.returncode == 0, "timedOut": timed_out, "liveCadExecuted": False,
              "boundary": "Mock CAD control-flow tests and read-only historical evidence are not new live CAD closure."}
    (args.output / "validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(completed.stdout.decode("utf-8", errors="replace"), end="")
    print(json.dumps(report, ensure_ascii=False))
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
