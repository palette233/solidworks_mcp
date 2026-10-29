#!/usr/bin/env python3
"""Build a catalog-only cleaning/weighing capability pre-screen; never start CAD."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.cleaning_service_region import (  # noqa: E402
    build_cleaning_service_capability_audit,
    build_discovered_cleaning_service_capability_audit,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--target-base", required=True)
    parser.add_argument("--provider", action="append")
    parser.add_argument(
        "--auto-discover-project-providers",
        action="store_true",
        help=(
            "Use all reviewed modules in the target base project whose exact "
            "capability labels intersect the source requirements."
        ),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite capability evidence: {output}")
    if args.auto_discover_project_providers and args.provider:
        parser.error("--provider and --auto-discover-project-providers are exclusive")
    if not args.auto_discover_project_providers and not args.provider:
        parser.error("one or more --provider values or auto discovery is required")
    discovery = None
    providers = args.provider
    if args.auto_discover_project_providers:
        report = build_discovered_cleaning_service_capability_audit(
            ROOT, args.source, args.target_base
        )
    else:
        report = build_cleaning_service_capability_audit(
            ROOT,
            args.source,
            args.target_base,
            providers,
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(output),
                "passed": report["capabilityCoverage"]["passed"],
                "missingCapabilities": report["capabilityCoverage"][
                    "missingCapabilities"
                ],
                "cadStarted": False,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
