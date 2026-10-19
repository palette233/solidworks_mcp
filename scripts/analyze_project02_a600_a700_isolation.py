#!/usr/bin/env python3
"""Build the stage-2 Project 02 A600/A700 overconstraint isolation report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "apps" / "demo-backend" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from demo_backend.mate_overconstraint_audit import analyze_mate_overconstraint_isolation_results


DIAGNOSTICS = ROOT / "demo" / "mate_graph_edit" / "diagnostics"
DEFAULT_SOURCE_RESULT = (
    ROOT
    / "demo"
    / "mate_reconstruction_experiments"
    / "project02_mate_reconstruction_A_source_pose_v6.result.json"
)
DEFAULT_WIDTH_RESULT = DIAGNOSTICS / "project02_A600_A700_without_width10_stage2_v1.result.json"
DEFAULT_BOTH_RESULT = (
    DIAGNOSTICS / "project02_A600_A700_without_width10_distance29_stage2_v1.result.json"
)
DEFAULT_OUTPUT = DIAGNOSTICS / "project02_A600_A700_overconstraint_stage2_v1.json"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-result", type=Path, default=DEFAULT_SOURCE_RESULT)
    parser.add_argument("--without-width-result", type=Path, default=DEFAULT_WIDTH_RESULT)
    parser.add_argument("--without-both-result", type=Path, default=DEFAULT_BOTH_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing report: {output}")
    report = analyze_mate_overconstraint_isolation_results(
        _read(args.source_result.resolve()),
        [
            {
                "id": "A700-without-width10",
                "removedMateNames": ["宽度10"],
                "result": _read(args.without_width_result.resolve()),
            },
            {
                "id": "A700-without-width10-and-distance29",
                "removedMateNames": ["宽度10", "距离29"],
                "result": _read(args.without_both_result.resolve()),
            },
        ],
    )
    report["sourceResultPath"] = str(args.source_result.resolve())
    report["isolationResultPaths"] = [
        str(args.without_width_result.resolve()),
        str(args.without_both_result.resolve()),
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"output": str(output), "findings": report["findings"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
