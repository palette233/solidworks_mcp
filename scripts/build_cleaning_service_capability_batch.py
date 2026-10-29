#!/usr/bin/env python3
"""Build reusable cleaning capability audits for exact source/base pairs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.cleaning_service_region import (  # noqa: E402
    build_discovered_cleaning_service_capability_audit,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pair",
        action="append",
        required=True,
        help="Exact SOURCE,TARGET pair; repeat for a batch.",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--index-output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    index_output = args.index_output.resolve()
    if output.exists() or index_output.exists():
        raise FileExistsError("Refusing to overwrite capability batch evidence")
    pairs: list[tuple[str, str]] = []
    for raw in args.pair:
        values = [value.strip() for value in raw.split(",")]
        if len(values) != 2 or not all(values):
            parser.error(f"invalid --pair: {raw}")
        pairs.append((values[0], values[1]))
    if len(pairs) != len(set(pairs)):
        parser.error("duplicate --pair")

    output.mkdir(parents=True)
    entries = []
    for source, target in pairs:
        report = build_discovered_cleaning_service_capability_audit(
            ROOT, source, target
        )
        path = output / f"{_slug(source)}-to-{_slug(target)}.json"
        path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        coverage = report["capabilityCoverage"]
        near_match_required = sorted(
            {
                capability
                for provider in report["providerDiscovery"][
                    "nearMatchProvidersRequiringEngineeringDecision"
                ]
                for capability in provider["reviewForRequiredCapabilities"]
            }
        )
        entries.append(
            {
                "sourceModuleDefinitionId": source,
                "targetBaseDefinitionId": target,
                "role": "CleaningWeighing",
                "reportPath": str(path.relative_to(ROOT)).replace("\\", "/"),
                "reportSha256": _sha(path),
                "auditDigest": report["auditDigest"],
                "passed": coverage["passed"],
                "missingCapabilities": coverage["missingCapabilities"],
                "classification": (
                    "target_service_capability_complete"
                    if coverage["passed"]
                    else "target_service_capability_incomplete"
                ),
                "boundary": report["providerDiscovery"]["boundary"],
                "nearMatchProviderCount": len(
                    report["providerDiscovery"][
                        "nearMatchProvidersRequiringEngineeringDecision"
                    ]
                ),
                "nearMatchRequiredCapabilities": near_match_required,
            }
        )
    index = {
        "schemaVersion": "cleaning-service-capability-coverage-index/v1",
        "entries": entries,
        "summary": {
            "pairCount": len(entries),
            "passedCount": sum(row["passed"] is True for row in entries),
            "incompleteCount": sum(row["passed"] is False for row in entries),
            "nearMatchDecisionPairCount": sum(
                row["nearMatchProviderCount"] > 0 for row in entries
            ),
        },
        "cadStarted": False,
        "boundary": (
            "Exact reviewed capability labels only. Near matches remain explicit "
            "engineering decisions and do not authorize station CAD."
        ),
    }
    index_output.parent.mkdir(parents=True, exist_ok=True)
    index_output.write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(index["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
