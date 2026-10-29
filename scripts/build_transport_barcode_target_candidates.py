"""Build transport-local barcode target candidates without choosing a role."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.scanner_point_pair_profile import (  # noqa: E402
    build_scanner_optical_source_candidate_catalog,
    build_transport_barcode_target_candidate_catalog,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--optical-geometry", required=True, type=Path)
    parser.add_argument("--module-graph", required=True, type=Path)
    parser.add_argument("--transport")
    parser.add_argument("--scanner")
    parser.add_argument(
        "--kind", choices=("transport-target", "scanner-source"), default="transport-target"
    )
    parser.add_argument("--catalog-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    output.relative_to(ROOT.resolve())
    if output.exists():
        raise FileExistsError(output)
    if args.kind == "transport-target":
        if not args.transport:
            parser.error("--transport is required for transport-target")
        result = build_transport_barcode_target_candidate_catalog(
            repository_root=ROOT,
            optical_geometry_path=(ROOT / args.optical_geometry).resolve(),
            module_graph_path=(ROOT / args.module_graph).resolve(),
            transport_module_definition_id=args.transport,
            catalog_id=args.catalog_id,
        )
    else:
        if not args.scanner:
            parser.error("--scanner is required for scanner-source")
        result = build_scanner_optical_source_candidate_catalog(
            repository_root=ROOT,
            optical_geometry_path=(ROOT / args.optical_geometry).resolve(),
            module_graph_path=(ROOT / args.module_graph).resolve(),
            scanner_module_definition_id=args.scanner,
            catalog_id=args.catalog_id,
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(output),
                "candidateCount": len(result["candidates"]),
                "selectionRequired": result.get("roleSelectionRequired")
                or result.get("roleAndDirectionSelectionRequired"),
                "cadStarted": False,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
