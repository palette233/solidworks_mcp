#!/usr/bin/env python3
"""Publish the evidence-backed Project01 GN00 base-only installation port."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.driving_relation_release_publisher import (  # noqa: E402
    publish_driving_relation_release,
)


PACKAGE = ROOT / (
    "demo/cross_project_substitution/cleaning-weighing-base-only-v1/"
    "project01_GN00_project03_AG00/two-hole-candidate-v1"
)
LEGACY_TEMPLATE_ID = "GN00_to_JJ00_plane_two_hole_installation_v1"
RELEASE_ID = "relation-v65-project01-gn00-base-only-two-hole-driving-20261022"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    catalog_path = PACKAGE / "global_module_catalog.candidate.json"
    catalog = _read(catalog_path)
    templates = [
        row
        for row in catalog.get("connectionTemplates") or []
        if row.get("legacyTemplateId") == LEGACY_TEMPLATE_ID
    ]
    if len(templates) != 1:
        raise RuntimeError("candidate catalog has no unique GN00 two-hole template")
    spec = {
        "schemaVersion": "driving-relation-release-spec/v1",
        "releaseId": RELEASE_ID,
        "projectId": "project01",
        "drivingScope": "project01_JJ00_then_GN00_base_only_plane_two_hole",
        "catalogPath": catalog_path.relative_to(ROOT).as_posix(),
        "templates": [
            {
                "legacyTemplateId": LEGACY_TEMPLATE_ID,
                "globalTemplateId": templates[0]["globalTemplateId"],
                "evidencePath": (
                    PACKAGE
                    / "project01_GN00_base_only_two_hole_checkpoint_v1.result.json"
                ).relative_to(ROOT).as_posix(),
                "expectedMateCount": 3,
                "requireDeclaredClosed": True,
            }
        ],
    }
    (PACKAGE / "driving_release_spec.json").write_text(
        json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report = publish_driving_relation_release(ROOT, spec)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
