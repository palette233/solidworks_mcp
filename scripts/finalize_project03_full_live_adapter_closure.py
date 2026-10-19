#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
BACKEND_SRC = WORKSPACE / "apps/demo-backend/src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.project03_full_live_adapter_closure import (  # noqa: E402
    write_project03_full_live_adapter_closure,
)


def main() -> int:
    root = WORKSPACE / "demo/semantic_ports/project03_live_adapter_full_jobs"
    output = root / "project03_full_live_adapter_closure.json"
    write_project03_full_live_adapter_closure(
        root / "latest_uninterrupted.json", output
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    print(
        json.dumps(
            {
                "status": payload["status"],
                "success": payload["success"],
                "allActionsLiveCadValidated": payload[
                    "allActionsLiveCadValidated"
                ],
                "liveCadApiMayStartForTokens": payload[
                    "liveCadApiMayStartForTokens"
                ],
                "totalMeasuredDurationSeconds": payload[
                    "totalMeasuredDurationSeconds"
                ],
                "failedAttemptDurationSeconds": payload[
                    "failedAttemptDurationSeconds"
                ],
                "finalAssemblyPath": payload["finalAssemblyPath"],
                "output": str(output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if payload["success"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
