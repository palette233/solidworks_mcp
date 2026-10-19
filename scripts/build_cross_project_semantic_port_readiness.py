#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "demo-backend" / "src"))

from demo_backend.cross_project_port_readiness import audit_cross_project_port_readiness
from demo_backend.global_module_catalog import build_global_module_catalog


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--projects", nargs="+",
        default=["project01", "project02", "project03", "project05", "project06"],
    )
    parser.add_argument(
        "--output", type=Path,
        default=ROOT / "demo" / "global_assembly_catalog" / "v1" / "cross_project_port_readiness.json",
    )
    args = parser.parse_args()
    catalog = build_global_module_catalog(ROOT, project_ids=tuple(args.projects))
    report = audit_cross_project_port_readiness(catalog, args.projects)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "readyProjectIds": report["readyProjectIds"],
        "blockedProjectIds": report["blockedProjectIds"],
        "output": str(output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
