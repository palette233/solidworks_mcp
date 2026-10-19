#!/usr/bin/env python3
"""Screen two bounded face catalogs for a secondary installation datum."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "apps/demo-backend/src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.installation_datum_discovery import (
    discover_secondary_installation_datums,
)
from demo_backend.face_endpoint_catalog import merge_face_endpoint_catalogs


def _read(path: Path) -> dict:
    return json.loads(path.resolve().read_text(encoding="utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--moving-catalog", required=True, type=Path, action="append"
    )
    parser.add_argument("--target-catalog", required=True, type=Path, action="append")
    parser.add_argument("--primary-moving-endpoint", required=True)
    parser.add_argument("--primary-target-endpoint", required=True)
    parser.add_argument("--support-moving-endpoint")
    parser.add_argument("--support-target-endpoint")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite datum discovery: {output}")
    moving_catalog = _read(args.moving_catalog[0])
    for path in args.moving_catalog[1:]:
        moving_catalog = merge_face_endpoint_catalogs(moving_catalog, _read(path))
    target_catalog = _read(args.target_catalog[0])
    for path in args.target_catalog[1:]:
        target_catalog = merge_face_endpoint_catalogs(target_catalog, _read(path))

    result = discover_secondary_installation_datums(
        moving_catalog,
        target_catalog,
        primary_moving_endpoint_id=args.primary_moving_endpoint,
        primary_target_endpoint_id=args.primary_target_endpoint,
        support_moving_endpoint_id=args.support_moving_endpoint,
        support_target_endpoint_id=args.support_target_endpoint,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "success": True,
                "status": result["status"],
                "secondaryAxisCandidateCount": result[
                    "secondaryAxisCandidateCount"
                ],
                "directionPlaneCandidateCount": result[
                    "directionPlaneCandidateCount"
                ],
                "output": str(output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
