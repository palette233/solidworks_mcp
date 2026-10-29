#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.cross_project_wastecup_interface_gap import (  # noqa: E402
    build_wastecup_mechanical_interface_gap_audit,
)


PACKAGE = ROOT / "demo/cross_project_substitution/wastecup-project05-to-project02-v1"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    report = build_wastecup_mechanical_interface_gap_audit(
        catalog=_read(
            ROOT / "demo/global_assembly_catalog/v1/global_module_catalog.json"
        ),
        datum_closure=_read(PACKAGE / "datum-placement-demo-closure.json"),
        datum_effective_graph=_read(PACKAGE / "candidate_effective_mate_graph.json"),
        physical_attachment_candidate=_read(
            PACKAGE / "p000_physical_attachment_candidate.json"
        ),
    )
    output = PACKAGE / "mechanical_interface_gap_audit.json"
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "missingEvidenceCount": len(report["missingEvidence"]),
                "cadLaunchAllowed": report["cadLaunchAllowed"],
                "nextAction": report["nextAction"],
                "output": str(output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
