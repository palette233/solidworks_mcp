#!/usr/bin/env python3
"""Compile one parameterized-datum candidate into a non-prototype CAD package."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.parameterized_datum_placement import (  # noqa: E402
    compile_parameterized_datum_validation_package,
)


def _write(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", required=True)
    parser.add_argument("--slot", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--initial-placement-variant", type=int, default=1)
    parser.add_argument("--position-parameters-json", help="Explicit longitudinal/lateral/supportGap in metres; creates a new unvalidated candidate")
    parser.add_argument(
        "--bounded-role-station-candidate",
        type=Path,
        help="Authenticated bounded-role candidate that replaces one revoked position recipe",
    )
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite validation package: {output}")
    bounded_candidate = (
        json.loads(
            args.bounded_role_station_candidate.resolve().read_text(encoding="utf-8-sig")
        )
        if args.bounded_role_station_candidate
        else None
    )
    package = compile_parameterized_datum_validation_package(
        ROOT,
        args.module,
        args.slot,
        initial_placement_variant=args.initial_placement_variant,
        position_parameters=json.loads(args.position_parameters_json) if args.position_parameters_json else None,
        distance_flip_dimensions=(
            bounded_candidate.get("distanceFlipDimensions") if bounded_candidate else None
        ),
        bounded_role_station_candidate=bounded_candidate,
    )
    output.mkdir(parents=True)
    effective = output / "effective-mate-graph.json"
    endpoints = output / "selected-face-endpoint-catalog.json"
    manifest = output / "validation-package.json"
    _write(effective, package.pop("effectiveGraph"))
    _write(endpoints, package.pop("selectedEndpointCatalog"))
    package["artifacts"] = {
        "effectiveGraph": {"path": str(effective), "sha256": _sha256(effective)},
        "selectedEndpointCatalog": {
            "path": str(endpoints),
            "sha256": _sha256(endpoints),
        },
    }
    _write(manifest, package)
    print(json.dumps(package, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
