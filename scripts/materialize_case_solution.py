#!/usr/bin/env python3
"""Materialize one persisted Top-K candidate without replacing the default selection."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.layout_preview import _materialize_solution  # noqa: E402


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=("project01", "project03", "project05"), required=True)
    parser.add_argument("--rank", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reviewer-note", required=True)
    args = parser.parse_args()
    if args.rank < 1:
        parser.error("--rank must be positive")

    solution_path = ROOT / f"demo/layout_previews/{args.case}_solution.json"
    preview_path = ROOT / f"demo/layout_previews/{args.case}_preview.json"
    output_path = args.output if args.output.is_absolute() else ROOT / args.output
    generated = read(solution_path)
    preview = read(preview_path)
    selected = next(
        (
            item
            for item in (generated.get("constraintPlan") or {})
            .get("jointSearch", {})
            .get("solutions", [])
            if int(item.get("rank") or 0) == args.rank
        ),
        None,
    )
    if selected is None:
        raise SystemExit(f"Solution rank {args.rank} is absent from {solution_path}.")
    materialized = _materialize_solution(generated, selected)
    materialized["visualApproval"] = {
        "approved": True,
        "approvedAt": datetime.now(timezone.utc).isoformat(),
        "selectedSolutionRank": args.rank,
        "reviewerNote": args.reviewer_note,
        "sourcePreviewGeneratedAt": preview.get("generatedAt"),
        "requiresReplayBeforeBroadPhase": True,
        "allowsBrepNow": False,
    }
    materialized["message"] = (
        f"Top-K solution {args.rank} was explicitly requested and materialized "
        "to an isolated artifact for CAD Replay."
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        raise SystemExit(f"Output already exists; refusing to overwrite: {output_path}")
    output_path.write_text(
        json.dumps(materialized, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "success": True,
                "caseId": args.case,
                "selectedSolutionRank": args.rank,
                "score": selected.get("score"),
                "output": str(output_path.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
