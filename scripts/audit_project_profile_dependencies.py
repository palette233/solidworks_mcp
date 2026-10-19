from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.prototype_dependency_audit import audit_project_profile_dependencies


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Audit prototype dependence in a project profile.")
    parser.add_argument("--project", default="project02")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "demo/semantic_ports/project02_full_machine_increment_v1/"
        "prototype_dependency_audit.json",
    )
    args = parser.parse_args()
    result = audit_project_profile_dependencies(args.project)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["staticDemoProfileAccepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
