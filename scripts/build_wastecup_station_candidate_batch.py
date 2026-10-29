"""Prepare all mapped WasteCup station candidates from one inspection batch."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.wastecup_station_candidate import (  # noqa: E402
    build_wastecup_station_candidate_batch,
)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mapping-config", type=Path, required=True)
    parser.add_argument("--mapping-report", type=Path, required=True)
    parser.add_argument("--inspection-batch", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output_dir = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    report_path = output_dir / "batch-report.json"
    if output_dir.exists():
        raise FileExistsError(f"candidate batch output already exists: {output_dir}")
    result = build_wastecup_station_candidate_batch(
        ROOT,
        mapping_config_path=args.mapping_config,
        mapping_report_path=args.mapping_report,
        inspection_batch_path=args.inspection_batch,
    )
    output_dir.mkdir(parents=True)
    for row in result["rows"]:
        # Keep the payload (including explicit null while pending) in the batch
        # report so its precomputed candidateDigest remains verifiable.  A ready
        # payload is also written separately for convenient downstream binding.
        payload = row.get("candidatePayload")
        if payload is None:
            row["candidatePath"] = None
            row["candidateSha256"] = None
            continue
        pair_dir = output_dir / (
            _slug(row["sourceModuleDefinitionId"])
            + "--"
            + _slug(row["targetBaseDefinitionId"])
        )
        pair_dir.mkdir()
        candidate_path = pair_dir / "candidate.json"
        candidate_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        row["candidatePath"] = str(candidate_path.resolve())
        row["candidateSha256"] = _sha(candidate_path)
    # Materialization adds immutable output bindings that are not present in the
    # pure planner result.  Recompute the digest over the exact report payload.
    result.pop("candidateDigest", None)
    result["candidateDigest"] = hashlib.sha256(
        json.dumps(
            result,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    report_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "success": True,
        "report": str(report_path.resolve()),
        **result["summary"],
        "cadStarted": False,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
