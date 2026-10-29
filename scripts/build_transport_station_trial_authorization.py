#!/usr/bin/env python3
"""Build one immutable exact-pair transport CAD-trial authorization packet."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.transport_station_review_queue import (  # noqa: E402
    build_transport_station_trial_authorization_packet,
)


def _pair(value: str) -> tuple[str, str]:
    parts = value.split("->", 1)
    if len(parts) != 2 or not all(part.strip() for part in parts):
        raise argparse.ArgumentTypeError(
            "pair must be formatted as projectNN::TOKEN->projectNN::TOKEN"
        )
    return parts[0].strip(), parts[1].strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--pair", type=_pair, action="append", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--authorized-by", required=True)
    parser.add_argument("--authorized-at", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    review_path = (ROOT / args.review).resolve()
    output = (ROOT / args.output).resolve()
    review_path.relative_to(ROOT)
    output.relative_to(ROOT)
    if output.exists():
        raise FileExistsError(
            f"Refusing to overwrite transport trial authorization: {output}"
        )
    packet = build_transport_station_trial_authorization_packet(
        json.loads(review_path.read_text(encoding="utf-8-sig")),
        exact_pairs=args.pair,
        source=args.source,
        authorized_by=args.authorized_by,
        authorized_at=args.authorized_at,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(packet, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "output": str(output.relative_to(ROOT)).replace("\\", "/"),
        "authorizedPairCount": packet["confirmedPairCount"],
        "decisionPacketDigest": packet["decisionPacketDigest"],
        "trackAndWorkAreaFitConfirmed": False,
        "cadStarted": False,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
