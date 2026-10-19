#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))
from demo_backend.project05_local_capture import (  # noqa: E402
    map_standalone_capture_to_project05_world,
    map_standalone_capture_to_project05_world_instances,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--poses", type=Path, default=ROOT / "demo/layout_previews/project05_top_level_poses.json")
    parser.add_argument("--module-token", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--all-instances",
        action="store_true",
        help="Map the standalone capture to every matching active top-level instance.",
    )
    args = parser.parse_args()
    mapper = (
        map_standalone_capture_to_project05_world_instances
        if args.all_instances
        else map_standalone_capture_to_project05_world
    )
    result = mapper(
        json.loads(args.input.read_text(encoding="utf-8-sig")),
        json.loads(args.poses.read_text(encoding="utf-8-sig")),
        args.module_token,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "moduleToken": result["moduleToken"],
        "leafComponentCount": result.get("leafComponentCount", result.get("leafComponentCountPerInstance")),
        "bodyCount": result["bodyCount"],
        "instanceCount": result.get("instanceCount", 1),
        "output": str(args.output.resolve()),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
