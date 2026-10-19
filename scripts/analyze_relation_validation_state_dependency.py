from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.relation_validation_state_audit import (  # noqa: E402
    analyze_relation_validation_state_dependency,
)


def _read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validation-graph", required=True, type=Path)
    parser.add_argument("--verification-result", required=True, type=Path)
    parser.add_argument(
        "--installation-graph",
        action="append",
        default=[],
        metavar="MODULE=PATH",
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    installations = {}
    for item in args.installation_graph:
        module, separator, value = item.partition("=")
        if not separator or not module.strip() or not value.strip():
            raise ValueError("--installation-graph must use MODULE=PATH")
        installations[module.strip().upper()] = _read(Path(value))
    report = analyze_relation_validation_state_dependency(
        _read(args.validation_graph),
        _read(args.verification_result),
        installation_graphs=installations,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "output": str(args.output),
        "success": report["success"],
        "diagnosedExternalPoseFailureCount": report[
            "diagnosedExternalPoseFailureCount"
        ],
        "diagnosedFlexibleStateFailureCount": report[
            "diagnosedFlexibleStateFailureCount"
        ],
    }, ensure_ascii=False))
    return 0 if report["success"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
