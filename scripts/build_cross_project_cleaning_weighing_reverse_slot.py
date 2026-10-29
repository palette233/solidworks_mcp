#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.cross_project_cleaning_weighing_reverse_slot import (  # noqa: E402
    build_cleaning_weighing_reverse_slot_discovery,
)


PACKAGE = ROOT / (
    "demo/cross_project_substitution/cleaning-weighing-base-only-v1/"
    "project01_GN00_project03_AG00"
)


def main() -> int:
    catalog = json.loads(
        (
            ROOT
            / "demo/cross_project_substitution/scanner-slot-discovery-v1/"
            "project01_JJ00_project03_AI00/"
            "jj00-scanner-support-leaf-face-catalog.json"
        ).read_text(encoding="utf-8-sig")
    )
    report = build_cleaning_weighing_reverse_slot_discovery(
        target_leaf_catalog=catalog
    )
    output = PACKAGE / "cleaning_weighing_reverse_slot_discovery.json"
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "strictCandidateCount": report["strictCandidateCount"],
                "relaxedNearMatchCount": report["relaxedNearMatchCount"],
                "toleranceRelaxationAccepted": report[
                    "toleranceRelaxationAccepted"
                ],
                "cadLaunchAllowed": report["cadLaunchAllowed"],
                "output": str(output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
