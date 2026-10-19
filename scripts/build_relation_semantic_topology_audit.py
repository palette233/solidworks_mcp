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

from demo_backend.relation_topology_audit import annotate_relation_topology_with_catalog


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--topology-audit",
        type=Path,
        default=ROOT / "demo/global_assembly_catalog/relation-topology-audit-v1.json",
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=ROOT
        / "demo/global_assembly_catalog/releases/"
        "relation-v36-project02-nine-addon-portable-driving-20261011/"
        "global_module_catalog.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "demo/global_assembly_catalog/relation-semantic-topology-audit-v2.json",
    )
    args = parser.parse_args()
    topology_path = args.topology_audit if args.topology_audit.is_absolute() else ROOT / args.topology_audit
    catalog_path = args.catalog if args.catalog.is_absolute() else ROOT / args.catalog
    output = args.output if args.output.is_absolute() else ROOT / args.output
    topology = _read(topology_path)
    catalog = _read(catalog_path)
    projects = [
        annotate_relation_topology_with_catalog(row, catalog)
        for row in topology.get("projects") or []
    ]
    result = {
        "schemaVersion": "cross-project-relation-semantic-topology-audit/v2",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sourceTopologyAuditPath": str(topology_path.resolve()),
        "catalogPath": str(catalog_path.resolve()),
        "catalogDigest": catalog.get("catalogDigest"),
        "projects": projects,
        "summary": {
            "projectCount": len(projects),
            "drivingMechanicalEdgeCount": sum(
                1
                for project in projects
                for edge in project.get("mechanicalEdges") or []
                if (edge.get("catalogRelationSemantics") or {}).get("classification")
                == "has_driving_template"
            ),
            "validationOnlyMechanicalEdgeCount": sum(
                1
                for project in projects
                for edge in project.get("mechanicalEdges") or []
                if (edge.get("catalogRelationSemantics") or {}).get("classification")
                == "validation_only"
            ),
            "incompleteDrivingOnlyMechanicalEdgeCount": sum(
                1
                for project in projects
                for edge in project.get("mechanicalEdges") or []
                if (edge.get("catalogRelationSemantics") or {}).get("classification")
                == "incomplete_driving_only"
            ),
            "collectivelyClosedBundleMemberEdgeCount": sum(
                1
                for project in projects
                for edge in project.get("mechanicalEdges") or []
                if (edge.get("catalogRelationSemantics") or {}).get("classification")
                == "collectively_closed_bundle_member"
            ),
            "legacyIncompleteDrivingTemplateCount": sum(
                int(
                    (edge.get("catalogRelationSemantics") or {}).get(
                        "incompleteDrivingTemplateCount"
                    )
                    or 0
                )
                for project in projects
                for edge in project.get("mechanicalEdges") or []
            ),
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
