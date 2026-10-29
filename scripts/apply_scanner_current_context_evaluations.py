#!/usr/bin/env python3
"""Apply immutable saved-context scanner evaluations to a review queue; never CAD."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.scanner_transport_binding_queue import (  # noqa: E402
    apply_scanner_current_context_evaluations,
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", required=True, type=Path)
    parser.add_argument("--evaluation", required=True, type=Path, action="append")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    queue_path = args.queue.resolve()
    evaluation_paths = [path.resolve() for path in args.evaluation]
    output = args.output.resolve()
    if output.exists():
        parser.error("Output already exists; preserve old evidence and choose a new path")
    for path in [queue_path, *evaluation_paths, output.parent]:
        path.relative_to(ROOT)
    result = apply_scanner_current_context_evaluations(
        _read(queue_path),
        [_read(path) for path in evaluation_paths],
        evidence=[
            {
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "sha256": _sha(path),
            }
            for path in evaluation_paths
        ],
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(output), **result["summary"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
