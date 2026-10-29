#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.project05_p000_physical_attachment_candidate import (  # noqa: E402
    build_project05_p000_physical_attachment_candidate,
    validate_project05_p000_physical_attachment_candidate,
)


PACKAGE = ROOT / "demo/cross_project_substitution/wastecup-project05-to-project02-v1"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    report = build_project05_p000_physical_attachment_candidate(
        catalog=_json(ROOT / "demo/global_assembly_catalog/v1/global_module_catalog.json"),
        face_catalog=_json(
            ROOT
            / "demo/semantic_ports/project05_p000_locator_discovery_v1/"
            "p000-mount-leaf-face-catalog-attempt02.json"
        ),
        source_graph=_json(
            ROOT / "demo/layout_previews/project05_module_mate_graph_v2_axes.json"
        ),
        base_face_catalog=_json(
            ROOT / "demo/semantic_ports/project05_p000_locator_discovery_v1/"
            "a000-p000-support-leaf-face-catalog.json"
        ),
    )
    validate_project05_p000_physical_attachment_candidate(report)
    output = PACKAGE / "p000_physical_attachment_candidate.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "slotCenterlineSpacingMeters": report["candidateInterfaceSignature"][
                    "slotCenterlineSpacingMeters"
                ],
                "mechanicalMeaningConfirmed": report["candidateInterfaceSignature"][
                    "mechanicalMeaningConfirmed"
                ],
                "semanticPortPublished": report["semanticPortPublished"],
                "cadLaunchAllowed": report["cadLaunchAllowed"],
                "output": str(output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
