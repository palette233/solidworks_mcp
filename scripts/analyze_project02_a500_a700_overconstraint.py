#!/usr/bin/env python3
"""Create a repeatable stage-1 audit of Project 02 A500/A700 overconstraint evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "apps" / "demo-backend" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from demo_backend.mate_overconstraint_audit import analyze_mate_overconstraint_evidence


DEFAULT_GRAPH = ROOT / "demo" / "layout_previews" / "project02_module_mate_graph_v3.json"
DEFAULT_RESULTS = [
    ROOT / "demo" / "mate_reconstruction_experiments" / "project02_mate_reconstruction_A_source_pose_v6.result.json",
    ROOT / "demo" / "mate_reconstruction_experiments" / "project02_mate_reconstruction_B_mate_only_v6.result.json",
    ROOT / "demo" / "mate_reconstruction_experiments" / "project02_mate_reconstruction_C_residual_anchors_v6.result.json",
]
DEFAULT_OUTPUT = (
    ROOT
    / "demo"
    / "mate_graph_edit"
    / "diagnostics"
    / "project02_A500_A700_overconstraint_stage1_v1.json"
)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--results", nargs="+", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing audit: {output}")
    report = analyze_mate_overconstraint_evidence(
        read_json(args.graph.resolve()),
        [read_json(path.resolve()) for path in args.results],
    )
    report["sourceGraphPath"] = str(args.graph.resolve())
    report["sourceResultPaths"] = [str(path.resolve()) for path in args.results]
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"output": str(output), "inference": report["inference"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
