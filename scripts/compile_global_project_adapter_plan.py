from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
BACKEND = WORKSPACE / "apps" / "demo-backend" / "src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.global_assembly_workbench import compile_project_adapter_plan


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compile a global context into a fail-closed project adapter plan."
    )
    parser.add_argument("context_id")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    plan = compile_project_adapter_plan(WORKSPACE, args.context_id)
    output = args.output or (
        WORKSPACE
        / "demo"
        / "global_assembly_contexts"
        / f"{args.context_id}.project-adapter-plan.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "status": plan["status"], "blockers": plan["blockers"]}, ensure_ascii=False, indent=2))
    return 0 if plan.get("safeToCreateDurableJob") else 2


if __name__ == "__main__":
    raise SystemExit(main())
