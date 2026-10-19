from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
BACKEND_SRC = WORKSPACE / "apps" / "demo-backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.assembly_timing_report import write_assembly_timing_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an auditable timing report for an assembly job.")
    parser.add_argument("job_directory", type=Path)
    args = parser.parse_args()
    output = write_assembly_timing_report(args.job_directory)
    payload = json.loads(output.read_text(encoding="utf-8"))
    print(
        json.dumps(
            {
                "jobId": payload["jobId"],
                "status": payload["status"],
                "totalDurationSeconds": payload["totalDurationSeconds"],
                "cadActionDurationSeconds": payload["cadActionDurationSeconds"],
                "collisionGateDurationSeconds": payload["collisionGateDurationSeconds"],
                "output": str(output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
