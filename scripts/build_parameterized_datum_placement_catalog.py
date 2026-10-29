from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.parameterized_datum_placement import (  # noqa: E402
    build_parameterized_datum_placement_catalog,
)


DEFAULT_OUTPUT = (
    ROOT
    / "demo/cross_project_substitution/parameterized-datum-placement-v1"
    / "interface-contract-catalog.json"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build the bounded scanner/cleaning datum-placement fallback catalog."
        )
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = build_parameterized_datum_placement_catalog(ROOT)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "output": str(output),
                "summary": report["summary"],
                "catalogDigest": report["catalogDigest"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
