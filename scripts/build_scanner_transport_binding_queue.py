#!/usr/bin/env python3
"""Build scanner/transport review candidates or compile selected instances."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "apps/demo-backend/src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.scanner_transport_binding_queue import (  # noqa: E402
    build_scanner_transport_binding_review_queue,
    compile_scanner_transport_binding_selections,
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["review", "compile"])
    parser.add_argument("--gap", type=Path)
    parser.add_argument("--coverage", type=Path)
    parser.add_argument("--measurements", type=Path)
    parser.add_argument("--queue", type=Path)
    parser.add_argument("--selections", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite scanner binding evidence: {output}")
    if args.action == "review":
        if not all((args.gap, args.coverage, args.measurements)):
            parser.error("review requires --gap --coverage --measurements")
        result = build_scanner_transport_binding_review_queue(
            _read(args.gap.resolve()),
            _read(args.coverage.resolve()),
            _read(args.measurements.resolve()),
        )
    else:
        if not all((args.queue, args.selections)):
            parser.error("compile requires --queue --selections")
        result = compile_scanner_transport_binding_selections(
            _read(args.queue.resolve()), _read(args.selections.resolve())
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "success": True,
                "output": str(output),
                "candidateCount": len(result.get("candidates") or []),
                "decisionCount": len(result.get("decisions") or []),
                "cadStarted": result.get("cadStarted"),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
