#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.project03_deprototype_closure import (  # noqa: E402
    build_project03_deprototype_closure,
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    root = ROOT / "demo/semantic_ports/project03_deprototype_ablation_v1"
    result = build_project03_deprototype_closure(
        load(root / "project03_pose_anchor_ablation.json"),
        ROOT / "demo/semantic_ports/project03_calibrated_parameters_v1.json",
        load(root / "live-cad/step04_AG00_calibrated_v2.result.json"),
        load(root / "live-cad/step07a_AB00_calibrated_v2.result.json"),
    )
    output = root / "project03_deprototype_closure.json"
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["success"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
