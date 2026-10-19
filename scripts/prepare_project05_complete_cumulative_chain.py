#!/usr/bin/env python3
"""Prepare and optionally publish the Project05 seven-addon cumulative chain."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.driving_relation_release_publisher import (  # noqa: E402
    publish_driving_relation_release,
)
from demo_backend.project05_complete_cumulative_chain import (  # noqa: E402
    DEFAULT_RELEASE_ID,
    build_candidate_catalog,
    build_release_spec,
    build_scenario,
)


def _write_new(path: Path, value: dict) -> None:
    if path.exists():
        raise FileExistsError(f"拒绝覆盖已有完整链输入：{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-id", default=DEFAULT_RELEASE_ID)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "demo/global_assembly_catalog/coverage-v2/project05-complete-chain-v2",
    )
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve() if args.output.is_absolute() else (ROOT / args.output).resolve()
    candidate, provenance = build_candidate_catalog(ROOT)
    catalog_path = output / "global_module_catalog.candidate.json"
    spec_path = output / "driving_release_spec.json"
    scenario_path = output / "natural_language_scenario.json"
    _write_new(catalog_path, candidate)
    spec = build_release_spec(
        ROOT,
        release_id=args.release_id,
        candidate_catalog_path=catalog_path,
    )
    _write_new(spec_path, spec)
    _write_new(output / "preparation_report.json", provenance)
    _write_new(scenario_path, build_scenario(args.release_id))
    report: dict = {
        "success": True,
        "status": "prepared_not_published",
        "releaseId": args.release_id,
        "catalogPath": str(catalog_path),
        "releaseSpecPath": str(spec_path),
        "scenarioPath": str(scenario_path),
        "candidateCatalogDigest": candidate["catalogDigest"],
    }
    if args.publish:
        publication = publish_driving_relation_release(ROOT, spec)
        report.update(
            {
                "status": "published",
                "publication": publication,
                "releaseManifestPath": publication["manifestPath"],
            }
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
