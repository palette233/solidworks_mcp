"""Classify missing scanner contexts and materialize safe rule candidates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.scanner_target_rule_composition import (  # noqa: E402
    _digest,
    build_scanner_rule_composition_batch,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binding-queue", required=True, type=Path)
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--target-candidate-catalog", type=Path)
    parser.add_argument("--source-candidate-catalog", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.relative_to(ROOT.resolve())
    if output.exists():
        raise FileExistsError(output)
    report = build_scanner_rule_composition_batch(
        repository_root=ROOT,
        binding_queue_path=(ROOT / args.binding_queue).resolve(),
        registry_path=(ROOT / args.registry).resolve(),
        target_candidate_catalog_path=(
            (ROOT / args.target_candidate_catalog).resolve()
            if args.target_candidate_catalog is not None
            else None
        ),
        source_candidate_catalog_path=(
            (ROOT / args.source_candidate_catalog).resolve()
            if args.source_candidate_catalog is not None
            else None
        ),
    )
    output.mkdir(parents=True)
    for row in report["rows"]:
        candidate = row.get("candidateRule")
        if candidate is None:
            continue
        path = output / "candidates" / f"{candidate['ruleId']}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(candidate, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        row["candidatePath"] = path.relative_to(ROOT).as_posix()
    report.pop("batchDigest", None)
    report["batchDigest"] = _digest(report)
    report_path = output / "batch-report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "report": str(report_path),
                "summary": report["summary"],
                "cadStarted": False,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
