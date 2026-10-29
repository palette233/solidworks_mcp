#!/usr/bin/env python3
"""Plan or run a read-only station recheck for an existing CAD pair release."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))
sys.path.insert(0, str(ROOT / "scripts"))

from demo_backend.saved_output_station_inspection import (  # noqa: E402
    build_saved_output_station_inspection_plan,
)
from run_global_cad_transaction_packet import (  # noqa: E402
    capture_open_document_baseline,
)


def _write_once(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("plan", "run"))
    parser.add_argument("request", type=Path)
    parser.add_argument("--session-check-timeout", type=float, default=20.0)
    args = parser.parse_args()
    plan = build_saved_output_station_inspection_plan(ROOT, args.request)
    if args.action == "plan":
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    baseline = capture_open_document_baseline(timeout=args.session_check_timeout)
    if baseline.get("openDocumentCount") != 0:
        print(
            json.dumps(
                {
                    "success": False,
                    "reason": "solidworks_session_not_clean",
                    "baseline": baseline,
                    "cadStarted": False,
                },
                ensure_ascii=False,
            )
        )
        return 2
    started = datetime.now(timezone.utc).isoformat()
    clock = perf_counter()
    command = [sys.executable, *plan["command"][1:]]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, check=False)
    process = {
        "schemaVersion": "saved-output-station-inspection-process/v1",
        "startedAtUtc": started,
        "finishedAtUtc": datetime.now(timezone.utc).isoformat(),
        "durationSeconds": perf_counter() - clock,
        "requestPath": plan["requestPath"],
        "requestDigest": plan["requestDigest"],
        "command": command,
        "returnCode": completed.returncode,
        "stdout": completed.stdout.decode("utf-8", errors="replace"),
        "stderr": completed.stderr.decode("utf-8", errors="replace"),
        "cadReexecuted": False,
        "readOnly": True,
        "referenceResolutionMappings": plan["referenceResolutionMappings"],
        "referenceSearchFolders": plan["referenceSearchFolders"],
    }
    _write_once(Path(plan["processReportPath"]), process)
    if completed.returncode != 0:
        print(json.dumps(process, ensure_ascii=False))
        return completed.returncode
    state = json.loads(Path(plan["outputStatePath"]).read_text(encoding="utf-8-sig"))
    if (
        state.get("success") is not True
        or state.get("observed", {}).get("readOnly") is not True
        or not state.get("checks")
        or not all(value is True for value in state["checks"].values())
    ):
        raise RuntimeError("Read-only saved-output inspection did not pass")
    print(
        json.dumps(
            {
                "success": True,
                "statePath": plan["outputStatePath"],
                "processReportPath": plan["processReportPath"],
                "cadReexecuted": False,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
