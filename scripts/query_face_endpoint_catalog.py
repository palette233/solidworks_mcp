#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "apps/demo-backend/src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.face_endpoint_catalog import list_face_candidates, select_face_endpoint


def main() -> int:
    parser = argparse.ArgumentParser(description="Query a reusable face-endpoint catalog.")
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--endpoint-id")
    parser.add_argument("--module")
    parser.add_argument("--geometry", default="Plane")
    parser.add_argument("--minimum-area", type=float, default=0.0)
    parser.add_argument("--leaf-contains")
    args = parser.parse_args()
    catalog = json.loads(args.catalog.resolve().read_text(encoding="utf-8-sig"))
    if args.endpoint_id:
        result = [select_face_endpoint(catalog, args.endpoint_id)]
    else:
        result = list_face_candidates(
            catalog,
            module_token=args.module,
            geometry_class=args.geometry,
            minimum_area=args.minimum_area,
            leaf_contains=args.leaf_contains,
        )
    print(json.dumps({"count": len(result), "endpoints": result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
