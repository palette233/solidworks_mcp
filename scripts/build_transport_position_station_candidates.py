#!/usr/bin/env python3
"""Build generic confirmed-transport station candidates; never launch CAD."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.transport_position_station import (  # noqa: E402
    build_transport_position_station_candidates,
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transport-review", type=Path, required=True)
    parser.add_argument("--confirmation", type=Path, action="append", required=True)
    parser.add_argument("--base-registry", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    review_path = (ROOT / args.transport_review).resolve()
    registry_path = (ROOT / args.base_registry).resolve()
    confirmation_paths = [(ROOT / value).resolve() for value in args.confirmation]
    output = (ROOT / args.output).resolve()
    for path in [review_path, registry_path, *confirmation_paths]:
        path.relative_to(ROOT)
        if not path.is_file():
            raise FileNotFoundError(path)
    output.relative_to(ROOT)
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite transport candidate bundle: {output}")
    config_directory = _relative(output / "configs")
    bundle = build_transport_position_station_candidates(
        review_queue=_read(review_path),
        review_binding={"path": _relative(review_path), "sha256": _sha(review_path)},
        confirmation_bindings=[{
            "path": _relative(path), "sha256": _sha(path), "payload": _read(path),
        } for path in confirmation_paths],
        base_registry=_read(registry_path),
        config_directory_path=config_directory,
    )
    output.mkdir(parents=True)
    for item in bundle["configs"]:
        _write(ROOT / item["path"], item["payload"])
    report = {key: value for key, value in bundle.items()
              if key not in {"configs", "candidateRegistry"}}
    _write(output / "candidate-bundle.json", report)
    _write(output / "station-rules.json", bundle["candidateRegistry"])
    print(json.dumps({
        "output": _relative(output),
        "candidateCount": bundle["candidateCount"],
        "unresolvedEngineeringConfirmationCount": bundle[
            "unresolvedEngineeringConfirmationCount"
        ],
        "cadStarted": False,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
