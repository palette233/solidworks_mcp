from __future__ import annotations

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


CATALOG = ROOT / (
    "demo/global_assembly_catalog/v1/"
    "global_module_catalog.combination-v1-preview.json"
)
INVENTORY = ROOT / (
    "demo/global_assembly_catalog/v1/combination-v1-preview/"
    "project03-driving-cad-evidence-inventory.json"
)
EVIDENCE = {
    "AE00_to_AA00_three_datum_installation": {
        "templateId": "template/project03/ae00-to-aa00-three-datum-installation/3665a437a8",
        "path": ROOT
        / "demo/global_assembly_catalog/v1/combination-v1-preview/"
        "project03-ae00-checkpoint-v1/project03-ae00-nonprototype-checkpoint.result.json",
    },
    "AD00_to_AA00_three_datum_installation": {
        "templateId": "template/project03/ad00-to-aa00-three-datum-installation/357acee2ce",
        "path": ROOT
        / "demo/global_assembly_catalog/v1/combination-v1-preview/"
        "project03-ad00-checkpoint-v1/project03-ad00-cumulative-nonprototype-checkpoint.result.json",
    },
    "AI00_to_AA00_five_mate_installation": {
        "templateId": "template/project03/ai00-to-aa00-five-mate-installation/0b1374c7f5",
        "path": ROOT
        / "demo/global_assembly_catalog/v1/combination-v1-preview/"
        "project03-ai00-checkpoint-v1/project03-ai00-cumulative-nonprototype-checkpoint.result.json",
    },
}
OUTPUT = ROOT / (
    "demo/global_assembly_catalog/v1/combination-v1-preview/"
    "project03-ae00-ad00-ai00-driving-release-evidence.json"
)


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON根节点必须是对象：{path}")
    return value


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def main() -> int:
    catalog = _read(CATALOG)
    inventory = _read(INVENTORY)
    validate_global_module_catalog(catalog)
    template_by_id = {
        str(row.get("globalTemplateId") or ""): row
        for row in catalog.get("connectionTemplates") or []
    }
    inventory_candidates = {
        str(row.get("globalTemplateId") or "")
        for row in inventory.get("templates") or []
        if row.get("cadEvidenceState") == "release_candidate"
    }
    assessments: dict[str, dict[str, Any]] = {}
    checks = {
        "catalogDigestMatchesInventory": (
            inventory.get("catalogDigest") == catalog.get("catalogDigest")
        )
    }
    derivations = []
    source_evidence = {"inventoryPath": _relative(INVENTORY)}
    for legacy_id, definition in EVIDENCE.items():
        template_id = definition["templateId"]
        template = template_by_id.get(template_id)
        if template is None:
            raise ValueError(f"候选目录缺少模板：{template_id}")
        assessment = assess_driving_insert_evidence(
            _read(definition["path"]), expected_mate_count=3
        )
        assessments[legacy_id] = assessment
        profile = normalize_template_relation_profile(template)
        checks[f"{legacy_id}:inventoryCandidate"] = template_id in inventory_candidates
        checks[f"{legacy_id}:drivesPlacement"] = profile.get("drivesPlacement") is True
        explanation = profile.get("constraintExplanation") or {}
        checks[f"{legacy_id}:declaredClosed"] = (
            explanation.get("state") == "declared_closed"
            and explanation.get("expectedResidualDof") == 0
        )
        checks[f"{legacy_id}:checkpointPassed"] = (
            assessment.get("checkpointPassed") is True
        )
        derivations.append(
            {
                "entry": {
                    "mode": "register_scoped_driving_bundle",
                    "sourceProjectId": "project03",
                    "legacyTemplateId": legacy_id,
                },
                "result": {
                    "derivedGlobalTemplateId": template_id,
                    "drivingScope": "project03_AA00_fixed_environment_only",
                },
            }
        )
        source_evidence[f"{legacy_id}CheckpointPath"] = _relative(definition["path"])

    report = {
        "schemaVersion": "project03-ae00-ad00-ai00-driving-candidate-evidence/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": "ready" if all(checks.values()) else "blocked",
        "sourceCatalogPath": _relative(CATALOG),
        "outputCatalogDigest": catalog["catalogDigest"],
        "authorizedDrivingTemplateIds": sorted(
            definition["templateId"] for definition in EVIDENCE.values()
        ),
        "checks": checks,
        "derivations": derivations,
        "sourceEvidence": source_evidence,
        "cadAssessments": assessments,
        "solidWorksExecuted": True,
        "collisionStatus": "not_evaluated",
        "statement": (
            "AE00、AD00和AI00均由独立模块从非原型初始位姿插入，"
            "并由AA00安装端口完成零剩余自由度定位；后续证据逐级消费前序累计检查点。"
        ),
    }
    OUTPUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
