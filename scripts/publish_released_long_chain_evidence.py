from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.released_long_chain_evidence import (
    build_released_long_chain_closure,
    write_released_long_chain_closure,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Publish machine-verifiable evidence for one released long CAD chain."
    )
    parser.add_argument("job_id")
    parser.add_argument("--expected-order", required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    order = [value.strip().upper() for value in args.expected_order.split(",") if value.strip()]
    if not order:
        raise ValueError("--expected-order must contain at least one module token")
    job_directory = ROOT / "demo/global_assembly_contexts/manifest_jobs" / args.job_id
    output = write_released_long_chain_closure(
        job_directory,
        args.output,
        expected_order=order,
        expected_release_id=args.release_id,
    )
    report = build_released_long_chain_closure(
        job_directory,
        expected_order=order,
        expected_release_id=args.release_id,
    )
    print(json.dumps({"status": report["status"], "output": str(output)}, ensure_ascii=False))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
