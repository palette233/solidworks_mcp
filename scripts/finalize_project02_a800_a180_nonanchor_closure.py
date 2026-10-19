from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.project02_a800_a180_nonanchor_closure import (  # noqa: E402
    build_project02_a800_a180_nonanchor_closure,
)


RUN_ROOT = ROOT / "demo/semantic_ports/project02_a800_a180_dof_audit_v1"


def main() -> int:
    parser = argparse.ArgumentParser(description="Finalize Project02 A800/A180 non-anchor CAD closure.")
    parser.add_argument("--a800", type=Path, default=RUN_ROOT / "project02-a600-a800-nonanchor-v1.result.json")
    parser.add_argument("--a180", type=Path, default=RUN_ROOT / "project02-a600-a800-a180-source-slot-v2.result.json")
    parser.add_argument("--rejected", type=Path, default=RUN_ROOT / "project02-a600-a800-a180-nonanchor-v1.result.json")
    parser.add_argument("--output", type=Path, default=RUN_ROOT / "project02-a800-a180-nonanchor-closure.json")
    args = parser.parse_args()
    report = build_project02_a800_a180_nonanchor_closure(args.a800, args.a180, args.rejected)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "output": str(output)}, ensure_ascii=False))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
