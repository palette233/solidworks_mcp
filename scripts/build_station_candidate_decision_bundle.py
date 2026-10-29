#!/usr/bin/env python3
"""Combine calibration and transport decisions for the generic gap queue; never CAD."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.calibration_function_point import (  # noqa: E402
    build_combined_station_candidate_decision_report,
    build_station_candidate_decision_index,
)
from demo_backend.transport_station_review_queue import (  # noqa: E402
    apply_transport_station_confirmation_packets,
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calibration-report", type=Path, required=True)
    parser.add_argument("--transport-review", type=Path, required=True)
    parser.add_argument(
        "--transport-confirmation", type=Path, action="append", default=[],
        help="Authenticated exact-pair position packet; repeatable.",
    )
    parser.add_argument("--scanner-review", type=Path)
    parser.add_argument(
        "--extra-report", type=Path, action="append", default=[],
        help="Optional standardized station-candidate-extension-report/v1; repeatable.",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    output = (ROOT / args.output).resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite station decision bundle: {output}")
    calibration_path = (ROOT / args.calibration_report).resolve()
    transport_path = (ROOT / args.transport_review).resolve()
    transport_confirmation_paths = [
        (ROOT / value).resolve() for value in args.transport_confirmation
    ]
    scanner_path = (ROOT / args.scanner_review).resolve() if args.scanner_review else None
    extra_paths = [(ROOT / value).resolve() for value in args.extra_report]
    calibration_path.relative_to(ROOT)
    transport_path.relative_to(ROOT)
    for path in transport_confirmation_paths:
        path.relative_to(ROOT)
    if scanner_path is not None:
        scanner_path.relative_to(ROOT)
    for path in extra_paths:
        path.relative_to(ROOT)
    transport_review = _read(transport_path)
    if transport_confirmation_paths:
        transport_review = apply_transport_station_confirmation_packets(
            transport_review, [_read(path) for path in transport_confirmation_paths]
        )
    report = build_combined_station_candidate_decision_report(
        _read(calibration_path), transport_review,
        _read(scanner_path) if scanner_path is not None else None,
        [_read(path) for path in extra_paths],
    )
    report["sourceEvidence"] = [
        {"path": str(calibration_path.relative_to(ROOT)).replace("\\", "/"),
         "sha256": _sha(calibration_path)},
        {"path": str(transport_path.relative_to(ROOT)).replace("\\", "/"),
         "sha256": _sha(transport_path)},
    ]
    if scanner_path is not None:
        report["sourceEvidence"].append({
            "path": str(scanner_path.relative_to(ROOT)).replace("\\", "/"),
            "sha256": _sha(scanner_path),
        })
    for path in extra_paths:
        report["sourceEvidence"].append({
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "sha256": _sha(path),
        })
    for path in transport_confirmation_paths:
        report["sourceEvidence"].append({
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "sha256": _sha(path),
        })
    output.mkdir(parents=True)
    report_path = output / "station-candidate-decisions.json"
    _write(report_path, report)
    index = build_station_candidate_decision_index(
        report,
        report_path=str(report_path.relative_to(ROOT)).replace("\\", "/"),
        report_sha256=_sha(report_path),
    )
    _write(output / "station-candidate-decision-index.json", index)
    print(json.dumps({"output": str(output), **report["summary"], "cadExecuted": False},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
