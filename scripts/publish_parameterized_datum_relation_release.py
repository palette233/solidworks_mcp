"""Publish a validated exact-pair datum recipe for the existing cumulative executor."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))
from demo_backend.parameterized_datum_relation_release import publish_parameterized_datum_relation_release


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validation-dir", required=True, type=Path)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--base-catalog", type=Path, default=ROOT / "demo/cross_project_substitution/expanded-project03-v1/relation-v62-project03-expanded-cross-project-chain-driving-20261014.catalog-preview.json")
    args = parser.parse_args()
    result = publish_parameterized_datum_relation_release(ROOT, args.validation_dir.resolve(), args.release_id, args.base_catalog.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
