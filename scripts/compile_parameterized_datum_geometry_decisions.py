#!/usr/bin/env python3
"""Build or compile reviewed datum geometry decision requests."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "apps/demo-backend/src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.parameterized_datum_geometry_decisions import (  # noqa: E402
    build_geometry_decision_request_template,
    compile_geometry_decision_requests,
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["template", "compile"])
    parser.add_argument("--review", required=True, type=Path)
    parser.add_argument("--requests", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite geometry evidence: {output}")
    review = _read(args.review.resolve())
    if args.action == "template":
        output.parent.mkdir(parents=True, exist_ok=True)
        result = build_geometry_decision_request_template(review)
        _write(output, result)
    else:
        if args.requests is None:
            parser.error("compile requires --requests")
        result = compile_geometry_decision_requests(
            ROOT, review, _read(args.requests.resolve())
        )
        output.mkdir(parents=True)
        _write(output / "geometry-decision-evidence-bundle.json", result)
        _write(output / "axis-selection-evidence.json", result["axisSelections"])
        _write(
            output / "axis-pair-selection-evidence.json",
            result["axisPairSelections"],
        )
        _write(
            output / "flexible-slot-selection-evidence.json",
            result["flexibleSlotSelections"],
        )
    print(
        json.dumps(
            {
                "success": True,
                "output": str(output),
                "requestCount": len(result.get("requests") or []),
                "confirmedDecisionCount": result.get("confirmedDecisionCount", 0),
                "confirmedAxisSelectionCount": result.get(
                    "confirmedAxisSelectionCount", 0
                ),
                "confirmedAxisPairSelectionCount": result.get(
                    "confirmedAxisPairSelectionCount", 0
                ),
                "confirmedFlexibleSlotSelectionCount": result.get(
                    "confirmedFlexibleSlotSelectionCount", 0
                ),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
