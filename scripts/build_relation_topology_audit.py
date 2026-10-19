from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "apps/demo-backend/src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.project_assembly_profile import load_project_assembly_profile
from demo_backend.relation_topology_audit import audit_relation_topology


def _load_graphs(project_id: str) -> list[tuple[Path, dict]]:
    prefix = f"{project_id}_".casefold()
    records: list[tuple[Path, dict]] = []
    for path in (ROOT / "demo/semantic_ports").rglob("*.json"):
        if not path.parent.name.casefold().startswith(prefix) and not any(
            part.casefold().startswith(prefix) for part in path.parts
        ):
            continue
        if "effective" not in path.name.casefold():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        if payload.get("SchemaVersion") != "editable-module-mate-graph/v1" and payload.get(
            "schemaVersion"
        ) != "editable-module-mate-graph/v1":
            continue
        records.append((path.relative_to(ROOT), payload))
    return records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project_ids", nargs="+", help="例如 project01 project02 project03")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "demo/global_assembly_catalog/relation-topology-audit-v1.json",
    )
    args = parser.parse_args()
    projects = []
    for project_id in args.project_ids:
        profile = load_project_assembly_profile(project_id)
        records = _load_graphs(project_id)
        audit = audit_relation_topology(profile, records)
        audit["effectiveGraphFileCount"] = len(records)
        projects.append(audit)
    result = {
        "schemaVersion": "cross-project-relation-topology-audit/v1",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "projects": projects,
        "summary": {
            "projectCount": len(projects),
            "portableNonStarMechanicalEdgeCount": sum(
                row["portableNonStarMechanicalEdgeCount"] for row in projects
            ),
            "processOnlyDependencyCount": sum(
                len(row["processOnlyDependencies"]) for row in projects
            ),
        },
    }
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
