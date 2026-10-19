#!/usr/bin/env python3
"""Assess persisted full-context B-rep evidence against a selected direct-context baseline."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "demo-backend" / "src"))

from demo_backend.project03_full_context_dynamic_assessment import assess_against_prototype_baseline


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--construction-closure", type=Path)
    parser.add_argument("--require-exact-baseline", action="store_true")
    args = parser.parse_args()
    evidence = json.loads(args.evidence.resolve().read_text(encoding="utf-8-sig"))
    baseline = json.loads(args.baseline.resolve().read_text(encoding="utf-8-sig"))
    actual = evidence.get("exactInterference", evidence)
    assessment = assess_against_prototype_baseline(
        actual,
        baseline,
        require_exact_baseline=args.require_exact_baseline,
    )
    payload = {
        "schemaVersion": "project03-ad00-full-context-assessment/v1",
        "createdAtUtc": datetime.now(timezone.utc).isoformat(),
        "evidence": str(args.evidence.resolve()),
        "baseline": str(args.baseline.resolve()),
        **assessment,
    }
    if args.construction_closure is not None:
        construction_path = args.construction_closure.resolve()
        construction = json.loads(construction_path.read_text(encoding="utf-8-sig"))
        payload["constructionClosure"] = str(construction_path)
        payload["constructionStatus"] = construction.get("status")
        payload["sourceFilesUnchanged"] = bool(construction.get("sourceFilesUnchanged"))
        payload["passed"] = bool(payload["passed"] and payload["sourceFilesUnchanged"])
        if not payload["passed"]:
            payload["status"] = "FAILED_FULL_CONTEXT_STATE_AND_SOURCE_INTEGRITY_GATE"
    args.output.resolve().write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(args.output.resolve())
    return 0 if assessment["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
