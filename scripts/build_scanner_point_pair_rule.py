"""Bind a reusable scanner point-pair profile to one exact target base."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.scanner_point_pair_profile import (  # noqa: E402
    build_scanner_point_pair_rule,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--target-base", required=True)
    parser.add_argument("--rule-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.relative_to(ROOT.resolve())
    if output.exists():
        raise FileExistsError(output)
    result = build_scanner_point_pair_rule(
        repository_root=ROOT,
        profile_path=(ROOT / args.profile).resolve(),
        module_catalog_path=ROOT / "demo/global_assembly_catalog/v1/global_module_catalog.json",
        target_base_definition_id=args.target_base,
        rule_id=args.rule_id,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "ruleId": result["ruleId"], "cadStarted": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
