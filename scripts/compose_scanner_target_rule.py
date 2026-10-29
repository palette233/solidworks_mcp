"""Compose one cross-project scanner rule candidate without starting CAD."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.scanner_target_rule_composition import (  # noqa: E402
    compose_scanner_target_rule,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-rule", required=True, type=Path)
    parser.add_argument("--target-rule", required=True, type=Path)
    parser.add_argument("--rule-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.relative_to(ROOT.resolve())
    if output.exists():
        raise FileExistsError(output)
    result = compose_scanner_target_rule(
        repository_root=ROOT,
        source_rule_path=(ROOT / args.source_rule).resolve(),
        target_rule_path=(ROOT / args.target_rule).resolve(),
        rule_id=args.rule_id,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            {
                "output": str(output),
                "ruleId": result["ruleId"],
                "status": result["status"],
                "cadStarted": False,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
