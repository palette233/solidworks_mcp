from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
BACKEND_SRC = WORKSPACE / "apps" / "demo-backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.project02_positioning_standard import (  # noqa: E402
    audit_project02_positioning_standard,
)


DEFAULT_OUTPUT = (
    WORKSPACE
    / "demo"
    / "positioning_standards"
    / "project02_positioning_standard_v1.audit.json"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit the inferred Project02 A800/A180 positioning standard."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    result = audit_project02_positioning_standard(WORKSPACE)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "output": str(output),
        "resultStatus": result["resultStatus"],
        "coarseLayoutReady": result["coarseLayoutReady"],
        "productionReady": result["productionReady"],
        "provisionalItems": result["provisionalItems"],
    }, ensure_ascii=False, indent=2))
    return 0 if result["coarseLayoutReady"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
