#!/usr/bin/env python3
"""Review one bounded transport leaf scan and optionally confirm one triplet."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "apps/demo-backend/src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.transport_datum_port_acquisition import (  # noqa: E402
    ACQUISITION_ROOT,
    PLAN_SCHEMA,
    _digest,
    confirm_transport_datum_port_candidate,
    review_transport_datum_leaf_scan,
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_new(path: Path, value: dict) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite evidence: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--plan",
        type=Path,
        default=ROOT / ACQUISITION_ROOT / "scan-plan.json",
    )
    parser.add_argument("--module-definition-id", required=True)
    parser.add_argument("--scan-catalog", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--confirm-candidate-id")
    parser.add_argument("--longitudinal-endpoint-id")
    parser.add_argument("--lateral-endpoint-id")
    parser.add_argument("--confirmation-source")
    parser.add_argument("--confirmed-output", type=Path)
    args = parser.parse_args()

    plan = _read(args.plan.resolve())
    if plan.get("schemaVersion") != PLAN_SCHEMA:
        raise ValueError("unsupported acquisition plan schema")
    core = {key: value for key, value in plan.items() if key != "planDigest"}
    if _digest(core) != plan.get("planDigest"):
        raise ValueError("acquisition plan digest mismatch")
    matches = [
        row
        for row in plan.get("items") or []
        if row.get("moduleDefinitionId") == args.module_definition_id
    ]
    if len(matches) != 1:
        raise ValueError("module definition is absent or ambiguous in scan plan")
    item = matches[0]
    seed = _read(ROOT / item["seedCatalogPath"])
    scan_path = (
        args.scan_catalog.resolve()
        if args.scan_catalog
        else (ROOT / item["scanOutputPath"]).resolve()
    )
    scan = _read(scan_path)
    review = review_transport_datum_leaf_scan(item, seed, scan)
    _write_new(args.output.resolve(), review)

    confirmed_path = None
    if args.confirm_candidate_id:
        if (
            not args.confirmation_source
            or not args.confirmed_output
            or not args.longitudinal_endpoint_id
            or not args.lateral_endpoint_id
        ):
            raise ValueError(
                "confirmation requires --longitudinal-endpoint-id, "
                "--lateral-endpoint-id, --confirmation-source and --confirmed-output"
            )
        confirmed = confirm_transport_datum_port_candidate(
            review,
            selected_candidate_id=args.confirm_candidate_id,
            longitudinal_endpoint_id=args.longitudinal_endpoint_id,
            lateral_endpoint_id=args.lateral_endpoint_id,
            confirmation_source=args.confirmation_source,
        )
        confirmed_path = args.confirmed_output.resolve()
        _write_new(confirmed_path, confirmed)
    elif (
        args.confirmation_source
        or args.confirmed_output
        or args.longitudinal_endpoint_id
        or args.lateral_endpoint_id
    ):
        raise ValueError(
            "confirmation arguments require --confirm-candidate-id"
        )

    print(
        json.dumps(
            {
                "success": True,
                "review": str(args.output.resolve()),
                "status": review["status"],
                "candidateCount": review["candidateCount"],
                "confirmedPort": str(confirmed_path) if confirmed_path else None,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
