#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.goal_matched_alternate_slot_cases import (  # noqa: E402
    compile_gn00_aa00_204mm_candidate,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "demo/goal_role_station_and_matched_slot_cases_20261028/gn00-aa00-204mm",
    )
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    package = compile_gn00_aa00_204mm_candidate(ROOT)
    graph = package.pop("effectiveGraph")
    graph_path = output / "effective-mate-graph.json"
    package_path = output / "candidate-package.json"
    graph_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    package["effectiveGraphPath"] = str(graph_path)
    package_path.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "package": str(package_path), "graph": str(graph_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
