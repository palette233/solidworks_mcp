#!/usr/bin/env python3
"""Build a calibration-point catalog and read-only pair screening; never CAD."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.calibration_function_point import (  # noqa: E402
    build_calibration_function_point_catalog,
    build_station_functional_screening_reports,
    screen_calibration_gap_pairs,
)


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, default=Path("data/assembly_stations/calibration-function-point-sources-v1.json"))
    parser.add_argument("--gap-queue", type=Path, required=True)
    parser.add_argument("--base-index", type=Path,
                        default=Path("data/assembly_stations/station-functional-screening-index-v1.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    output = (ROOT / args.output).resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite calibration screening: {output}")
    catalog = build_calibration_function_point_catalog(ROOT, args.sources)
    gaps = json.loads((ROOT / args.gap_queue).read_text(encoding="utf-8-sig"))
    screening = screen_calibration_gap_pairs(ROOT, catalog, gaps)
    base_index_path = (ROOT / args.base_index).resolve()
    base_index = json.loads(base_index_path.read_text(encoding="utf-8-sig"))
    if base_index.get("schemaVersion") != "station-functional-screening-index/v1":
        raise ValueError("unsupported base station functional screening index")
    output.mkdir(parents=True)
    _write(output / "calibration-function-point-catalog.json", catalog)
    _write(output / "calibration-pair-screening.json", screening)
    pair_dir = output / "pair-reports"
    pair_dir.mkdir()
    entries = list(base_index.get("entries") or [])
    existing = {(row["sourceModuleDefinitionId"], row["targetBaseDefinitionId"], row["role"])
                for row in entries}
    for report in build_station_functional_screening_reports(screening):
        key = (report["sourceModuleDefinitionId"], report["targetBaseDefinitionId"], report["role"])
        if key in existing:
            raise ValueError(f"duplicate station functional screening pair: {key}")
        name = "-".join((key[0].replace("::", "-"), key[1].replace("::", "-"), "calibration.json"))
        path = pair_dir / name
        _write(path, report)
        entries.append({
            "sourceModuleDefinitionId": key[0],
            "targetBaseDefinitionId": key[1],
            "role": key[2],
            "reportPath": str(path.relative_to(ROOT)).replace("\\", "/"),
            "reportSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "passed": report["screening"]["passed"],
            "status": report["screening"]["status"],
            "nextAction": report["nextAction"],
            "boundary": report["boundary"],
        })
        existing.add(key)
    _write(output / "station-functional-screening-index.json", {
        "schemaVersion": "station-functional-screening-index/v1",
        "entries": entries,
    })
    print(json.dumps({"output": str(output), **screening["summary"],
                      "functionalIndexEntryCount": len(entries), "cadExecuted": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
