"""Build a review-only WasteCup target-station candidate from saved CAD."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.wastecup_station_candidate import (  # noqa: E402
    build_wastecup_station_candidate,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mapping-config", type=Path, required=True)
    parser.add_argument("--mapping-report", type=Path, required=True)
    parser.add_argument("--inspection-request", type=Path, required=True)
    parser.add_argument("--saved-state", type=Path, required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    if output.exists():
        raise FileExistsError(f"candidate evidence already exists: {output}")
    result = build_wastecup_station_candidate(
        ROOT,
        mapping_config_path=args.mapping_config,
        mapping_report_path=args.mapping_report,
        inspection_request_path=args.inspection_request,
        saved_state_path=args.saved_state,
        source_module_definition_id=args.source,
        target_base_definition_id=args.target,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "success": True,
        "output": str(output.resolve()),
        "candidateDigest": result["candidateDigest"],
        "positionParametersMeters": result["positionParametersMeters"],
        "cadLaunchAllowed": result["cadLaunchAllowed"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
