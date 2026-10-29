#!/usr/bin/env python3
"""Index exact scanner/transport/base triples in existing saved CAD states."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "demo-backend" / "src"))

from demo_backend.scanner_saved_context_inventory import (  # noqa: E402
    build_scanner_saved_context_inventory,
    discover_saved_state_paths,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-queue", type=Path, required=True)
    parser.add_argument(
        "--module-catalog",
        type=Path,
        default=ROOT / "demo/global_assembly_catalog/v1/global_module_catalog.json",
    )
    parser.add_argument("--search-root", type=Path, default=ROOT / "demo")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result = build_scanner_saved_context_inventory(
        workspace_root=ROOT,
        review_queue_path=args.review_queue,
        module_catalog_path=args.module_catalog,
        state_paths=discover_saved_state_paths(args.search_root),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
