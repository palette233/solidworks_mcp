from __future__ import annotations

import json
import sys
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
BACKEND_SRC = WORKSPACE / "apps" / "demo-backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.project05_live_adapter_closure import (
    write_project05_live_adapter_closure,
)


def main() -> int:
    output = (
        WORKSPACE
        / "demo"
        / "semantic_ports"
        / "project05_live_adapter_jobs"
        / "project05_live_adapter_closure.json"
    )
    write_project05_live_adapter_closure(
        pilot_stage_path=(
            WORKSPACE
            / "demo"
            / "semantic_ports"
            / "project05_live_adapter_pilot_v1"
            / "step01_D000_cumulative.stage-result.json"
        ),
        tail_summary_path=(
            WORKSPACE
            / "demo"
            / "semantic_ports"
            / "project05_live_adapter_jobs"
            / "latest_live_tail.json"
        ),
        output_path=output,
        uninterrupted_summary_path=(
            WORKSPACE
            / "demo"
            / "semantic_ports"
            / "project05_live_adapter_full_jobs"
            / "latest_uninterrupted.json"
        ),
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    print(
        json.dumps(
            {
                "status": payload["status"],
                "allActionsLiveCadValidated": payload["allActionsLiveCadValidated"],
                "liveCadApiMayStart": payload["liveCadApiMayStart"],
                "totalMeasuredDurationMinutes": payload["totalMeasuredDurationMinutes"],
                "finalAssemblyPath": payload["finalAssemblyPath"],
                "output": str(output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if payload["allActionsLiveCadValidated"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
