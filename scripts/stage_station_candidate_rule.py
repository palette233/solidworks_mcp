#!/usr/bin/env python3
"""Stage one configured station candidate in a new registry without CAD authority."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.station_rule_registry import (  # noqa: E402
    read,
    sha,
    stage_candidate_rule,
)


def write_new(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-registry", required=True, type=Path)
    parser.add_argument("--candidate-registry", required=True, type=Path)
    parser.add_argument("--rule-id", required=True)
    parser.add_argument("--output-registry", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    base_path = args.base_registry.resolve()
    candidate_path = args.candidate_registry.resolve()
    output_path = args.output_registry.resolve()
    report_path = args.report.resolve()
    for path in (output_path, report_path):
        if path.exists():
            raise FileExistsError(path)
    merged, result = stage_candidate_rule(
        ROOT,
        read(base_path),
        read(candidate_path),
        rule_id=args.rule_id,
    )
    write_new(output_path, merged)
    report = {
        "schemaVersion": "station-candidate-staging/v1",
        **result,
        "baseRegistryPath": str(base_path),
        "baseRegistrySha256": sha(base_path),
        "candidateRegistryPath": str(candidate_path),
        "candidateRegistrySha256": sha(candidate_path),
        "outputRegistryPath": str(output_path),
        "outputRegistrySha256": sha(output_path),
        "newCadExecuted": False,
        "validatedStationRuleAdded": False,
        "boundary": (
            "The rule is configured and remains a candidate. Fresh non-prototype "
            "CAD, save/reopen and current station postcheck are still required."
        ),
    }
    write_new(report_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
