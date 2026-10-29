#!/usr/bin/env python3
"""Inspect or advance the bounded SS00/AE00 datum-port acquisition workflow."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "apps/demo-backend/src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.transport_datum_port_acquisition_execution import (  # noqa: E402
    inspect_transport_datum_port_acquisition,
    materialize_next_transport_datum_review,
)
from run_global_cad_transaction_packet import (  # noqa: E402
    capture_open_document_baseline,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action", choices=["status", "plan-next", "scan-next", "review-next"]
    )
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--session-check-timeout", type=float, default=120.0)
    args = parser.parse_args()
    if args.action == "scan-next":
        status = inspect_transport_datum_port_acquisition(
            ROOT, plan_path=args.plan
        )
        action = status["nextAction"]
        if action.get("action") != "run_bounded_leaf_scan":
            raise RuntimeError(
                f"next acquisition action is not a leaf scan: {action.get('action')}"
            )
        baseline = capture_open_document_baseline(
            timeout=args.session_check_timeout
        )
        if int(baseline.get("openDocumentCount") or 0) != 0:
            raise RuntimeError(
                "Transport datum scan requires an empty SolidWorks document "
                f"session; observed {baseline.get('openDocumentCount')} open documents."
            )
        command = list(action["command"])
        command[0] = sys.executable
        completed = subprocess.run(command, cwd=ROOT, check=False)
        if completed.returncode != 0:
            raise RuntimeError(
                f"bounded leaf scan failed with return code {completed.returncode}"
            )
        result = {
            "action": "bounded_leaf_scan_completed",
            "moduleDefinitionId": action["moduleDefinitionId"],
            "solidWorksBaseline": baseline,
            "returnCode": completed.returncode,
            "nextState": inspect_transport_datum_port_acquisition(
                ROOT, plan_path=args.plan
            )["nextAction"],
        }
    elif args.action == "review-next":
        result = materialize_next_transport_datum_review(
            ROOT, plan_path=args.plan
        )
    else:
        status = inspect_transport_datum_port_acquisition(
            ROOT, plan_path=args.plan
        )
        result = status if args.action == "status" else status["nextAction"]
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
