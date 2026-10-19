#!/usr/bin/env python3
"""Extend the latest Project02 release lineage with the validated A600 slot."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.cross_project_slot_release import (  # noqa: E402
    augment_project02_release_catalog_with_a600_ah00_slot,
)


BASE = (
    ROOT
    / "demo/global_assembly_catalog/releases/"
    "relation-v36-project02-nine-addon-portable-driving-20261011/"
    "global_module_catalog.json"
)
SLOT = (
    ROOT
    / "demo/global_assembly_catalog/v1/"
    "global_module_catalog.a600-ah00-cross-project-preview.json"
)
OUTPUT = (
    ROOT
    / "demo/global_assembly_catalog/v1/"
    "global_module_catalog.a600-ah00-project02-lineage-preview.json"
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=BASE)
    parser.add_argument("--slot", type=Path, default=SLOT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() and not args.overwrite:
        raise FileExistsError(f"拒绝覆盖候选目录：{output}")
    catalog = augment_project02_release_catalog_with_a600_ah00_slot(
        _read(args.base.resolve()), _read(args.slot.resolve())
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    summary = {
        "success": True,
        "baseCatalogPath": str(args.base.resolve()),
        "slotCatalogPath": str(args.slot.resolve()),
        "outputCatalogPath": str(output),
        "catalogDigest": catalog["catalogDigest"],
        "summary": catalog["summary"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
