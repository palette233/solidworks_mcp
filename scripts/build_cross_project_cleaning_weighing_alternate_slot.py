#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.cross_project_cleaning_weighing_alternate_slot import (  # noqa: E402
    build_cleaning_weighing_alternate_slot_discovery,
)


PACKAGE = ROOT / (
    "demo/cross_project_substitution/cleaning-weighing-base-only-v1/"
    "project01_GN00_project03_AG00"
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    report = build_cleaning_weighing_alternate_slot_discovery(
        route_report=_read(PACKAGE / "cleaning_weighing_cross_project_route.json"),
        target_leaf_catalog=_read(
            ROOT
            / "demo/global_assembly_catalog/coverage-v2/"
            "ag00-datum-discovery-v1/aa00_ag00_mount_leaf_faces.json"
        ),
        native_primary_target_endpoint_id=(
            "face:fl9a24d063aa00:81af5e2652843d2e"
        ),
        native_secondary_target_endpoint_id=(
            "face:fl9a24d063aa00:9218e31bdc9fd1db"
        ),
    )
    output = PACKAGE / "cleaning_weighing_alternate_slot_discovery.json"
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "candidateCount": report["candidateCount"],
                "exactSpacingCandidateCount": report[
                    "exactSpacingCandidateCount"
                ],
                "preferredDistanceFromNativeSlotMeters": (
                    report.get("preferredForMechanicalReview") or {}
                ).get("distanceFromNativeAg00SlotMeters"),
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
