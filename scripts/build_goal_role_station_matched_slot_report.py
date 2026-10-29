from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.goal_role_station_matched_slot_report import write_goal_artifacts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "demo" / "goal_role_station_and_matched_slot_cases_20261028" / "report-v2-station-audit",
    )
    parser.add_argument(
        "--station-witness", type=Path, action="append", default=[],
        help="Hash-bound role-station-witness/v1 JSON; repeat for multiple cases.",
    )
    args = parser.parse_args()
    witnesses: dict[str, Path] = {}
    for path in args.station_witness:
        payload = json.loads(path.read_text(encoding="utf-8"))
        case_id = payload.get("caseId")
        if not isinstance(case_id, str) or not case_id or case_id in witnesses:
            parser.error("station witnesses require unique nonempty caseId values")
        witnesses[case_id] = path.resolve()
    paths = write_goal_artifacts(ROOT, args.output_dir.resolve(), station_witness_paths=witnesses)
    print(json.dumps({key: str(value) for key, value in paths.items()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
