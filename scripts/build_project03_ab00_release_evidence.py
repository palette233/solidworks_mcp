#!/usr/bin/env python3
"""Build immutable-release evidence for the completed Project03 AB00 port."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.project03_ab00_port_completion import (  # noqa: E402
    validate_project03_ab00_live_result,
)


DEFAULT_CATALOG = (
    ROOT
    / "demo/global_assembly_catalog/v1/"
    "global_module_catalog.ab00-complete-preview.json"
)
DEFAULT_RESULT = (
    ROOT
    / "demo/semantic_ports/project03_AB00_complete_port_candidate_v1/cad/"
    "project03_AB00_complete_nonanchor_v1.result.json"
)
DEFAULT_OUTPUT = (
    ROOT
    / "demo/semantic_ports/project03_AB00_complete_port_candidate_v1/"
    "driving_release_evidence.json"
)
LEGACY_TEMPLATE_ID = "AB00_to_AA00_complete_three_relation_installation"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--live-result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    catalog_path = args.catalog.resolve()
    result_path = args.live_result.resolve()
    catalog = _read_json(catalog_path)
    live_result = _read_json(result_path)
    validation = validate_project03_ab00_live_result(live_result)
    matches = [
        row
        for row in catalog.get("connectionTemplates") or []
        if row.get("legacyTemplateId") == LEGACY_TEMPLATE_ID
    ]
    if len(matches) != 1:
        raise SystemExit(
            f"Expected one {LEGACY_TEMPLATE_ID} template, found {len(matches)}."
        )
    template = matches[0]
    effect = template.get("constraintEffect") or {}
    global_id = str(template.get("globalTemplateId") or "")
    checks = {
        f"{LEGACY_TEMPLATE_ID}:drivesPlacement": (
            effect.get("fullyLocatesAddedComponent") is True
        ),
        f"{LEGACY_TEMPLATE_ID}:declaredClosed": (
            int(effect.get("expectedResidualDof", -1)) == 0
        ),
        f"{LEGACY_TEMPLATE_ID}:liveCadPassed": validation.get("success") is True,
        f"{LEGACY_TEMPLATE_ID}:nonPrototypeInitialPose": (
            live_result.get("toolResult", {}).get("TargetCaseAnchored") is False
        ),
    }
    if not all(checks.values()):
        raise SystemExit("AB00 release checks did not all pass.")

    payload = {
        "schemaVersion": "generic-driving-candidate-evidence/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": "ready",
        "projectId": "project03",
        "drivingScope": "project03_AA00_with_AB00_complete_port",
        "sourceCatalogPath": catalog_path.relative_to(ROOT).as_posix(),
        "outputCatalogDigest": catalog.get("catalogDigest"),
        "authorizedDrivingTemplateIds": [global_id],
        "authorizedTemplateCombinationIds": [],
        "checks": checks,
        "derivations": [
            {
                "entry": {
                    "mode": "register_scoped_driving_bundle",
                    "sourceProjectId": "project03",
                    "legacyTemplateId": LEGACY_TEMPLATE_ID,
                },
                "result": {
                    "derivedGlobalTemplateId": global_id,
                    "drivingScope": "project03_AA00_with_AB00_complete_port",
                },
            }
        ],
        "sourceEvidence": {
            "semanticPortCatalogPath": (
                "demo/semantic_ports/project03_AB00_complete_port_candidate_v1/"
                "semantic_port_catalog.json"
            ),
            "liveCadResultPath": result_path.relative_to(ROOT).as_posix(),
        },
        "cadAssessment": validation,
        "solidWorksExecutedInThisPublish": False,
        "collisionStatus": "not_evaluated",
        "statement": (
            "发布原型配合图恢复出的重合、宽度与距离完整安装束；"
            "已通过独立插入、非原型初始位姿、完全约束及保存重开复核。"
        ),
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "success": True,
                "templateId": global_id,
                "catalogDigest": catalog.get("catalogDigest"),
                "output": str(output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
