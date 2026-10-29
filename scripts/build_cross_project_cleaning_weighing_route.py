#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.cross_project_cleaning_weighing_route import (  # noqa: E402
    build_cross_project_cleaning_weighing_route,
)


GN00 = ROOT / (
    "demo/cross_project_substitution/cleaning-weighing-base-only-v1/"
    "project01_GN00_project03_AG00/two-hole-candidate-v1"
)
AG00 = ROOT / "demo/global_assembly_catalog/coverage-v2/ag00-three-datum-candidate-v1"
GN00_RELEASE = ROOT / (
    "demo/global_assembly_catalog/releases/"
    "relation-v65-project01-gn00-base-only-two-hole-driving-20261022"
)
AG00_RELEASE = ROOT / (
    "demo/global_assembly_catalog/releases/"
    "relation-v54-project03-ag00-three-datum-driving-20261014"
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    report = build_cross_project_cleaning_weighing_route(
        gn00_summary=_read(GN00 / "candidate_summary.json"),
        gn00_checkpoint=_read(
            GN00 / "project01_GN00_base_only_two_hole_checkpoint_v1.result.json"
        ),
        gn00_release_manifest=_read(GN00_RELEASE / "release-manifest.json"),
        ag00_summary=_read(AG00 / "candidate_summary.json"),
        ag00_checkpoint=_read(
            AG00 / "project03_AG00_three_datum_checkpoint_v2.result.json"
        ),
        ag00_release_manifest=_read(AG00_RELEASE / "release-manifest.json"),
    )
    output = GN00.parent / "cleaning_weighing_cross_project_route.json"
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "nativeSlotCompatible": report["nativeSlotCompatible"],
                "spacingDifferenceMeters": report["interfaceComparison"][
                    "spacingDifferenceMeters"
                ],
                "nextAction": report["nextAction"],
                "output": str(output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
