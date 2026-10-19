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

from demo_backend.project02_scan_station import infer_project02_scan_station  # noqa: E402


DEFAULT_OPTICAL = ROOT / "demo" / "layout_previews" / "project02_scanner_barcode_points.json"
DEFAULT_BODIES = ROOT / "demo" / "FL9A24D062A800_leaf_body_envelopes.json"
DEFAULT_REQUEST = ROOT / "demo" / "FL9A24D062A000_real_process_request.json"
DEFAULT_OUTPUT = ROOT / "demo" / "layout_previews" / "project02_scan_station_inference.json"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Infer and audit the Project02 A800 buffer/entry scan carrier."
    )
    parser.add_argument("--optical", type=Path, default=DEFAULT_OPTICAL)
    parser.add_argument("--bodies", type=Path, default=DEFAULT_BODIES)
    parser.add_argument("--request", type=Path, default=DEFAULT_REQUEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--no-apply", action="store_true")
    args = parser.parse_args()

    result = infer_project02_scan_station(
        _read_json(args.optical), _read_json(args.bodies)
    )
    result["generatedAt"] = datetime.now(timezone.utc).isoformat()
    result["sourceEvidence"] = {
        "opticalPointPair": _portable(args.optical),
        "prototypeA800LeafBodies": _portable(args.bodies),
    }
    _write_json(args.output, result)

    if not args.no_apply:
        request = _read_json(args.request)
        transport = request["moduleSemantics"]["FL9A24D062A800.001-1"]
        parameters = transport.setdefault("parameters", {})
        parameters.update(
            {
                "scanCarrierPositionCadInferred": bool(
                    result["usableForCoarseLayout"]
                ),
                "scanCarrierPositionInferenceAudited": bool(
                    result["usableForCoarseLayout"]
                ),
                "scanCarrierInstance": result["selectedCarrierInstance"],
                "scanCarrierCandidateCount": result["candidateCount"],
                "scanCarrierNearestDistanceMarginMeters": result[
                    "nearestDistanceMarginMeters"
                ],
                "scanCarrierInferenceEvidencePath": _portable(args.output),
                "scanCarrierPositionInterpretation": result["inference"],
                "dynamicScanStopConfirmed": False,
            }
        )
        _write_json(args.request, request)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["success"] else 1


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.resolve().read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
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
