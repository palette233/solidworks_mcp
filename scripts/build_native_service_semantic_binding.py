#!/usr/bin/env python3
"""Build native CleaningWeighing service identity bindings; never run CAD."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.native_service_semantic_binding import (  # noqa: E402
    build_native_service_semantic_binding_report,
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    config = (ROOT / args.config).resolve()
    output = (ROOT / args.output).resolve()
    config.relative_to(ROOT)
    output.relative_to(ROOT)
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite native service binding: {output}")
    report = build_native_service_semantic_binding_report(
        ROOT, json.loads(config.read_text(encoding="utf-8-sig"))
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"output": str(output), **report["summary"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
