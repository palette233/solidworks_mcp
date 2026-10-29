"""Normalize a scanner rule and direct transport target into a local point pair."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.scanner_point_pair_profile import (  # noqa: E402
    build_point_pair_profile_from_scanner_rule_and_direct_target,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scanner-rule", required=True, type=Path)
    parser.add_argument("--target-measurement", required=True, type=Path)
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    output.relative_to(ROOT.resolve())
    if output.exists():
        raise FileExistsError(output)
    result = build_point_pair_profile_from_scanner_rule_and_direct_target(
        repository_root=ROOT,
        scanner_rule_path=(ROOT / args.scanner_rule).resolve(),
        target_measurement_path=(ROOT / args.target_measurement).resolve(),
        profile_id=args.profile_id,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"output": str(output), "profileId": result["profileId"], "cadStarted": False},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
