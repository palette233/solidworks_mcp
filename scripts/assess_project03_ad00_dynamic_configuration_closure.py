#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.project03_dynamic_configuration_assessment import (  # noqa: E402
    assess_project03_dynamic_configuration_closure,
    default_baseline_path,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--closure",
        type=Path,
        default=ROOT / "demo/semantic_ports/project03_ad00_dynamic_configuration_closure_v4/project03_ad00_dynamic_configuration_closure.json",
    )
    parser.add_argument("--baseline", type=Path, default=default_baseline_path(ROOT))
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "demo/semantic_ports/project03_ad00_dynamic_configuration_closure_v4/project03_ad00_dynamic_configuration_assessment.json",
    )
    args = parser.parse_args()
    closure = json.loads(args.closure.read_text(encoding="utf-8-sig"))
    baseline = json.loads(args.baseline.read_text(encoding="utf-8-sig"))
    result = assess_project03_dynamic_configuration_closure(closure, baseline)
    result["closureEvidencePath"] = str(args.closure.resolve())
    result["prototypeBaselinePath"] = str(args.baseline.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
