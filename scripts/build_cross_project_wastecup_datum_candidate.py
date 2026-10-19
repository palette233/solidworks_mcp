#!/usr/bin/env python3
"""Build the Project05 P000 -> Project02 A600 datum-placement candidate."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.cross_project_wastecup_datum_candidate import (  # noqa: E402
    build_project05_p000_to_project02_a600_datum_candidate,
)


P02 = ROOT / (
    "demo/global_assembly_catalog/v1/combination-v1-preview/"
    "project02-seven-addon-driving-v6/A300"
)
P05 = ROOT / (
    "demo/global_assembly_catalog/v1/combination-v1-preview/"
    "project05-nonanchor-driving-v6/P000"
)
OUTPUT = ROOT / "demo/cross_project_substitution/wastecup-project05-to-project02-v1"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    package = build_project05_p000_to_project02_a600_datum_candidate(
        a300_graph=_read(P02 / "assembly_plan_effective.json"),
        a300_semantic_catalog=_read(P02 / "semantic_port_catalog.json"),
        a300_endpoint_catalog=_read(P02 / "face_endpoint_catalog.json"),
        p000_graph=_read(P05 / "assembly_plan_effective.json"),
        p000_semantic_catalog=_read(P05 / "semantic_port_catalog.json"),
        p000_endpoint_catalog=_read(P05 / "face_endpoint_catalog.json"),
    )
    graph_path = OUTPUT / "candidate_effective_mate_graph.json"
    audit_path = OUTPUT / "candidate_audit.json"
    _write(graph_path, package["effectiveGraph"])
    _write(audit_path, package["audit"])
    print(
        json.dumps(
            {
                "success": True,
                "status": package["audit"]["status"],
                "cadLaunchAllowed": package["audit"]["cadLaunchAllowed"],
                "graphPath": str(graph_path),
                "auditPath": str(audit_path),
                "effectiveGraphDigest": package["audit"]["effectiveGraphDigest"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
