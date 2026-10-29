#!/usr/bin/env python3
"""Materialize read-only station witnesses, without starting SolidWorks."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.role_station_geometry import (  # noqa: E402
    build_gn00_aa00_station_witness,
    build_gn00_live_support_audit,
    build_n000_a600_station_witness,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--live-state", type=Path)
    parser.add_argument("--moving-live-catalog", type=Path)
    parser.add_argument("--base-live-catalog", type=Path)
    args = parser.parse_args()
    live_inputs = (args.live_state, args.moving_live_catalog, args.base_live_catalog)
    if any(live_inputs) and not all(live_inputs):
        parser.error("All three live state/catalog paths must be supplied together")
    output = args.output_dir.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite station evidence: {output}")
    started = time.perf_counter()
    started_at = datetime.now(timezone.utc).isoformat()
    reports = {"gn00-aa00-station-witness.json": build_gn00_aa00_station_witness(ROOT),
               "n000-a600-station-witness.json": build_n000_a600_station_witness(ROOT)}
    if all(live_inputs):
        reports["gn00-live-support-audit.json"] = build_gn00_live_support_audit(ROOT, *live_inputs)
    output.mkdir(parents=True)
    for name, report in reports.items():
        (output / name).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    timing = {"startedAtUtc": started_at, "finishedAtUtc": datetime.now(timezone.utc).isoformat(),
              "durationSeconds": time.perf_counter() - started, "liveCadStartedByThisScript": False,
              "freshReadOnlyCadEvidenceConsumed": all(live_inputs), "reportCount": len(reports)}
    (output / "timing-report.json").write_text(json.dumps(timing, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"outputDirectory": str(output), "durationSeconds": time.perf_counter() - started,
                      "checks": {name: {key: value["passed"] for key, value in report.get("checks", {}).items()} for name, report in reports.items()},
                      "liveSupportPassed": reports.get("gn00-live-support-audit.json", {}).get("supportGeometryMeasurementPassed")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
