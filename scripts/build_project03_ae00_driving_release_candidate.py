from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.global_cad_driving_evidence import (  # noqa: E402
    assess_driving_insert_evidence,
)
from demo_backend.global_module_catalog import validate_global_module_catalog  # noqa: E402
from demo_backend.global_relation_semantics import (  # noqa: E402
    normalize_template_relation_profile,
)


TEMPLATE_ID = "template/project03/ae00-to-aa00-three-datum-installation/3665a437a8"
LEGACY_ID = "AE00_to_AA00_three_datum_installation"
DEFAULT_CATALOG = ROOT / (
    "demo/global_assembly_catalog/v1/"
    "global_module_catalog.combination-v1-preview.json"
)
DEFAULT_INVENTORY = ROOT / (
    "demo/global_assembly_catalog/v1/combination-v1-preview/"
    "project03-driving-cad-evidence-inventory.json"
)
DEFAULT_CAD_RESULT = ROOT / (
    "demo/global_assembly_catalog/v1/combination-v1-preview/"
    "project03-ae00-checkpoint-v1/"
    "project03-ae00-nonprototype-checkpoint.result.json"
)
DEFAULT_OUTPUT = ROOT / (
    "demo/global_assembly_catalog/v1/combination-v1-preview/"
    "project03-ae00-driving-release-evidence.json"
)


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.resolve().read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON根节点必须是对象：{path}")
    return value


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def build_evidence(
    catalog: dict[str, Any],
    inventory: dict[str, Any],
    cad_result: dict[str, Any],
) -> dict[str, Any]:
    validate_global_module_catalog(catalog)
    template = next(
        (
            row
            for row in catalog.get("connectionTemplates") or []
            if row.get("globalTemplateId") == TEMPLATE_ID
        ),
        None,
    )
    if template is None:
        raise ValueError("候选目录缺少AE00驱动模板。")
    profile = normalize_template_relation_profile(template)
    assessment = assess_driving_insert_evidence(
        cad_result,
        expected_mate_count=3,
    )
    selected = inventory.get("selectedReleaseCandidate") or {}
    checks = {
        "catalogDigestMatchesInventory": (
            inventory.get("catalogDigest") == catalog.get("catalogDigest")
        ),
        "inventorySelectedAe00": (
            selected.get("globalTemplateId") == TEMPLATE_ID
        ),
        "templateDrivesPlacement": profile.get("drivesPlacement") is True,
        "templateDeclaredClosed": (
            (profile.get("constraintExplanation") or {}).get("state")
            == "declared_closed"
            and (profile.get("constraintExplanation") or {}).get(
                "expectedResidualDof"
            )
            == 0
        ),
        "checkpointCadEvidencePassed": assessment.get("checkpointPassed") is True,
        "caseAndLeafAnchorsAbsent": (
            assessment.get("semanticChecks", {}).get("casePoseAnchorNotUsed") is True
            and assessment.get("semanticChecks", {}).get("leafPoseAnchorNotUsed")
            is True
        ),
    }
    return {
        "schemaVersion": "project03-ae00-scoped-driving-candidate-evidence/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": "ready" if all(checks.values()) else "blocked",
        "sourceCatalogPath": _relative(DEFAULT_CATALOG),
        "outputCatalogDigest": catalog["catalogDigest"],
        "authorizedDrivingTemplateIds": [TEMPLATE_ID],
        "checks": checks,
        "derivations": [
            {
                "entry": {
                    "mode": "register_scoped_driving_bundle",
                    "sourceProjectId": "project03",
                    "legacyTemplateId": LEGACY_ID,
                },
                "result": {
                    "derivedGlobalTemplateId": TEMPLATE_ID,
                    "drivingScope": (
                        "project03_AA00_frame_to_AE00_transport_three_datum_only"
                    ),
                },
            }
        ],
        "sourceEvidence": {
            "inventoryPath": _relative(DEFAULT_INVENTORY),
            "checkpointCadInsertPath": _relative(DEFAULT_CAD_RESULT),
        },
        "cadAssessment": assessment,
        "solidWorksExecuted": True,
        "collisionStatus": "not_evaluated",
        "statement": (
            "AE00由独立子装配体从确定性的非原型位姿插入，仅凭支承面与双定位孔"
            "三条驱动配合完成定位；保存、关闭、重开及会话清洁均已复核。"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the Project03 AE00 scoped driving release evidence."
    )
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--cad-result", type=Path, default=DEFAULT_CAD_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    evidence = build_evidence(
        _read(args.catalog),
        _read(args.inventory),
        _read(args.cad_result),
    )
    evidence["sourceCatalogPath"] = _relative(args.catalog)
    evidence["sourceEvidence"] = {
        "inventoryPath": _relative(args.inventory),
        "checkpointCadInsertPath": _relative(args.cad_result),
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0 if evidence["status"] == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
