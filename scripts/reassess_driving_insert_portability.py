from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.global_cad_driving_evidence import (  # noqa: E402
    assess_driving_insert_evidence,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reassess whether a CAD insert proves portable external placement."
    )
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--expected-mate-count", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    payload = json.loads(args.evidence.read_text(encoding="utf-8-sig"))
    assessment = assess_driving_insert_evidence(
        payload, expected_mate_count=args.expected_mate_count
    )
    report = {
        "schemaVersion": "driving-insert-portability-reassessment/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "evidencePath": str(args.evidence),
        "assessment": assessment,
        "conclusion": (
            "portable_external_placement_proven"
            if assessment["portablePlacementProven"]
            else "checkpoint_passed_but_portable_external_placement_not_proven"
            if assessment["checkpointPassed"]
            else "checkpoint_not_accepted"
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "conclusion": report["conclusion"],
                "checkpointPassed": assessment["checkpointPassed"],
                "portablePlacementProven": assessment["portablePlacementProven"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if assessment["portablePlacementProven"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
