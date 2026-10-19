from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.project02_dynamic_scan import (  # noqa: E402
    build_project02_dynamic_scan_window,
)


DEFAULT_REQUEST = ROOT / "demo" / "FL9A24D062A000_real_process_request.json"
DEFAULT_STATION = ROOT / "demo" / "layout_previews" / "project02_scan_station_inference.json"
DEFAULT_OPTICAL = ROOT / "demo" / "layout_previews" / "project02_scanner_barcode_points.json"
DEFAULT_OUTPUT = ROOT / "demo" / "layout_previews" / "project02_dynamic_scan_window.json"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the Project02 coarse dynamic carrier scan window."
    )
    parser.add_argument("--request", type=Path, default=DEFAULT_REQUEST)
    parser.add_argument("--station", type=Path, default=DEFAULT_STATION)
    parser.add_argument("--optical", type=Path, default=DEFAULT_OPTICAL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--no-apply", action="store_true")
    args = parser.parse_args()

    updated, report = build_project02_dynamic_scan_window(
        _read(args.request), _read(args.station), _read(args.optical)
    )
    report["generatedAt"] = datetime.now(timezone.utc).isoformat()
    report["sourceEvidence"] = {
        "scanStation": _portable(args.station),
        "opticalPointPair": _portable(args.optical),
    }
    _write(args.output, report)
    if not args.no_apply:
        transport = updated["moduleSemantics"]["FL9A24D062A800.001-1"]
        transport["parameters"]["dynamicScanWindowEvidencePath"] = _portable(
            args.output
        )
        _write(args.request, updated)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.resolve().read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def _write(path: Path, value: dict[str, Any]) -> None:
    path.resolve().parent.mkdir(parents=True, exist_ok=True)
    path.resolve().write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _portable(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
