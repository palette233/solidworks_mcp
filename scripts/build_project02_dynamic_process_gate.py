from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE / "apps/demo-backend/src"))

from demo_backend.dynamic_process_gate import evaluate_project02_discrete_process_gate


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=WORKSPACE / "demo/semantic_ports/project02_full_machine_increment_v1/dynamic_process_gate.json",
    )
    parser.add_argument("--a700-evidence", type=Path)
    parser.add_argument("--a100-limits", type=Path)
    args = parser.parse_args()
    result = evaluate_project02_discrete_process_gate(
        load(WORKSPACE / "demo/layout_previews/project02_dual_valve_reach_audit.json"),
        load(WORKSPACE / "demo/layout_previews/project02_service_access_audit.json"),
        a700_swept_envelope_evidence=(load(args.a700_evidence) if args.a700_evidence else None),
        a100_axis_limit_evidence=(load(args.a100_limits) if args.a100_limits else None),
    )
    result["generatedAt"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), **result["summary"]}, ensure_ascii=False))
    return 0 if result["summary"]["coarseProcessGatePassed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
