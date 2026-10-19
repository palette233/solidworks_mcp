from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.global_assembly_workbench import compile_transaction_dag  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compile a global assembly context into a project-independent transaction DAG."
    )
    parser.add_argument("context_id")
    parser.add_argument("--base-instance-id")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = compile_transaction_dag(
        ROOT,
        args.context_id,
        base_instance_id=args.base_instance_id,
    )
    output = args.output or (
        ROOT / "demo" / "global_assembly_contexts" / f"{args.context_id}.transaction-dag.json"
    )
    if not output.is_absolute():
        output = ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(output), "status": result["status"], "transactionCount": result["transactionCount"], "blockerCount": len(result["blockers"])}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
