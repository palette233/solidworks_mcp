from __future__ import annotations

import json
import sys
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
BACKEND_SRC = WORKSPACE / "apps/demo-backend/src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.project03_segmented_live_adapter_closure import (
    write_project03_segmented_full_live_adapter_closure,
)


def main() -> int:
    output = WORKSPACE / (
        "demo/semantic_ports/project03_live_adapter_ab00_tail_jobs/"
        "project03_segmented_full_live_adapter_closure.json"
    )
    write_project03_segmented_full_live_adapter_closure(
        output,
        four_step_closure_path=WORKSPACE / (
            "demo/semantic_ports/project03_live_adapter_four_step_jobs/"
            "project03_four_step_live_adapter_closure.json"
        ),
        ah00_summary_path=WORKSPACE / "demo/semantic_ports/project03_live_adapter_ah00_tail_jobs/latest_ah00_tail.json",
        aj00_summary_path=WORKSPACE / "demo/semantic_ports/project03_live_adapter_aj00_tail_jobs/latest_aj00_tail.json",
        ab00_summary_path=WORKSPACE / "demo/semantic_ports/project03_live_adapter_ab00_tail_jobs/latest_ab00_tail.json",
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    print(json.dumps({"status": payload["status"], "success": payload["success"], "assemblyPath": payload["assemblyPath"], "output": str(output)}, ensure_ascii=False, indent=2))
    return 0 if payload["success"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
