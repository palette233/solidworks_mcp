#!/usr/bin/env python3
"""Publish one successful parameterized-datum CAD validation as pair evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.parameterized_datum_placement import (  # noqa: E402
    publish_parameterized_datum_pair_release,
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validation-dir", required=True, type=Path)
    args = parser.parse_args()
    root = args.validation_dir.resolve()
    output = root / "pair-release.json"
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite pair release: {output}")
    release = publish_parameterized_datum_pair_release(
        _read(root / "validation-package.json"),
        _read(root / "cad-result.json"),
    )
    output.write_text(
        json.dumps(release, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(release, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
