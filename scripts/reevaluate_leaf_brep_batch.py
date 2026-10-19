from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from capture_leaf_interference_details import baseline_acceptance, module_pair_key


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Re-evaluate durable exact B-rep details without reopening SolidWorks."
    )
    parser.add_argument("--batch", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--accepted-baseline",
        action="append",
        nargs=3,
        metavar=("FIRST", "SECOND", "BASELINE_JSON"),
        default=[],
    )
    args = parser.parse_args()
    batch = load(args.batch)
    baseline_paths = {
        module_pair_key(first, second): Path(path).resolve()
        for first, second, path in args.accepted_baseline
    }
    accepted = 0
    for row in batch.get("pairs") or []:
        pair = [str(value) for value in row.get("pair") or []]
        detail_path = Path(str(row.get("outputPath") or ""))
        if len(pair) != 2 or not detail_path.is_file():
            row["acceptance"] = {"policy": "missingExactDetail", "accepted": False}
            continue
        baseline_path = baseline_paths.get(module_pair_key(pair[0], pair[1]))
        baseline = load(baseline_path) if baseline_path else None
        row["acceptance"] = baseline_acceptance(load(detail_path), baseline)
        if baseline_path:
            row["acceptance"]["baselinePath"] = str(baseline_path)
        if row["acceptance"]["accepted"] is True:
            accepted += 1
    batch["acceptedPairCount"] = accepted
    batch["hardFailureCount"] = len(batch.get("pairs") or []) - accepted
    batch["reevaluation"] = {
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sourceBatchPath": str(args.batch.resolve()),
        "solidWorksReopened": False,
        "reason": "Acceptance policy/baseline identity changed; exact candidate geometry was reused.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(batch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "acceptedPairCount": accepted,
                "hardFailureCount": batch["hardFailureCount"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if batch["hardFailureCount"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
