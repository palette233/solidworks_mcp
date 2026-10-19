#!/usr/bin/env python3
"""Create the Project 02 A600/A700 full-semantics baseline audit."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "apps" / "demo-backend" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from demo_backend.mate_overconstraint_audit import analyze_full_semantics_baseline


DIAGNOSTICS = ROOT / "demo" / "mate_graph_edit" / "diagnostics"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--prior",
        type=Path,
        default=ROOT / "demo/mate_reconstruction_experiments/project02_mate_reconstruction_A_source_pose_v6.result.json",
    )
    parser.add_argument(
        "--graph",
        type=Path,
        default=ROOT / "demo/layout_previews/project02_A600_A700_module_mate_graph_semantics_v1.json",
    )
    parser.add_argument(
        "--run",
        type=Path,
        default=DIAGNOSTICS / "project02_A600_A700_full_semantics_baseline_v1.result.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DIAGNOSTICS / "project02_A600_A700_full_semantics_audit_v1.json",
    )
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing report: {output}")
    report = analyze_full_semantics_baseline(
        _read(args.prior.resolve()),
        _read(args.graph.resolve()),
        _read(args.run.resolve()),
    )
    report["priorResultPath"] = str(args.prior.resolve())
    report["semanticGraphPath"] = str(args.graph.resolve())
    report["semanticRunPath"] = str(args.run.resolve())
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"output": str(output), "finding": report["finding"]}, ensure_ascii=False))
    return 0 if report["finding"]["confirmed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
