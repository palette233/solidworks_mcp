from __future__ import annotations

import json
import sys
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
BACKEND_SRC = WORKSPACE / "apps/demo-backend/src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.project03_live_adapter_closure import (
    write_project03_ae00_ad00_ai00_live_adapter_closure,
)


def main() -> int:
    root = WORKSPACE / "demo/semantic_ports/project03_live_adapter_three_step_jobs"
    output = root / "project03_ae00_ad00_ai00_live_adapter_closure.json"
    write_project03_ae00_ad00_ai00_live_adapter_closure(
        root / "latest_ae00_ad00_ai00_pilot.json", output
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    print(
        json.dumps(
            {
                "status": payload["status"],
                "success": payload["success"],
                "assemblyPath": payload["assemblyPath"],
                "output": str(output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if payload["success"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
