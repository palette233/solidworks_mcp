from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.parameter_authority_registry import audit_parameter_authorities


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Audit project-scoped parameter authority and replacement readiness."
    )
    parser.add_argument("--project", default="project02")
    parser.add_argument("--registry", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "demo/semantic_ports/project02_full_machine_increment_v1/"
        "parameter_authority_audit.json",
    )
    parser.add_argument(
        "--require-production-authority",
        action="store_true",
        help="Return exit code 3 while any production parameter remains unsigned.",
    )
    args = parser.parse_args()
    result = audit_parameter_authorities(
        ROOT,
        args.project,
        path=args.registry.resolve() if args.registry else None,
    )
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["staticDemoParameterEvidenceAccepted"]:
        return 2
    if args.require_production_authority and not result[
        "productionParameterAuthorityAccepted"
    ]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
