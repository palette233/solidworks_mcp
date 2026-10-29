#!/usr/bin/env python3
"""Read-only six-role scope/authority/station report; no SolidWorks calls."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"apps/demo-backend/src"))

from demo_backend.six_role_station_coverage import (  # noqa: E402
    build_six_role_station_coverage, render_station_coverage_markdown,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=ROOT)
    parser.add_argument("--scope", type=Path)
    parser.add_argument("--station-rules", type=Path, action="append", default=[],
                        help="One rule, a rule list or a registry with rules[]; repeatable.")
    parser.add_argument("--output", type=Path,
                        default=Path("demo/unified_six_role_goal_20261028/scope-v1"))
    args = parser.parse_args(argv)
    workspace = args.workspace.resolve()
    output = (workspace/args.output).resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to replace existing report: {output}")
    rules, source_files = [], []
    for value in args.station_rules:
        path = (workspace/value).resolve()
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8-sig"))
        rules.extend(payload if isinstance(payload, list) else payload.get("rules", [payload]))
        source_files.append({"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(), "sizeBytes": len(raw)})
    # Existing registry owns rule evidence/identity checks. Do not reinterpret
    # a status label as current CAD or station validation in this report.
    from demo_backend.station_rule_registry import validate_rule
    report = build_six_role_station_coverage(workspace, scope_path=args.scope,
        station_rules=rules, station_rule_validator=validate_rule)
    report["sources"] = sorted({row["path"]: row for row in report["sources"]+source_files}.values(), key=lambda r: r["path"])
    output.mkdir(parents=True, exist_ok=False)
    for name, value in (("scope.json", report["scope"]), ("coverage.json", report)):
        (output/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    (output/"coverage-gaps-CN.md").write_text(render_station_coverage_markdown(report), encoding="utf-8")
    print(json.dumps({"output": str(output), "summary": report["summary"],
                      "durationSeconds": report["durationSeconds"], "cadExecuted": False}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
