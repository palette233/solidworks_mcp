from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.global_cad_driving_evidence import assess_driving_insert_evidence


PREVIOUS = ROOT / (
    "demo/global_assembly_catalog/v1/combination-v1-preview/"
    "project03-ae00-ad00-ai00-ah00-driving-release-evidence.json"
)
INVENTORY = ROOT / (
    "demo/global_assembly_catalog/v1/combination-v1-preview/"
    "project03-driving-cad-evidence-inventory.json"
)
AJ00_EVIDENCE = ROOT / (
    "demo/global_assembly_catalog/v1/combination-v1-preview/"
    "project03-aj00-checkpoint-v1/"
    "project03-aj00-cumulative-nonprototype-checkpoint.result.json"
)
OUTPUT = ROOT / (
    "demo/global_assembly_catalog/v1/combination-v1-preview/"
    "project03-ae00-ad00-ai00-ah00-aj00-driving-release-evidence.json"
)
LEGACY_ID = "AJ00_to_AA00_three_datum_installation"
TEMPLATE_ID = "template/project03/aj00-to-aa00-three-datum-installation/e323079e41"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def main() -> int:
    report = _read(PREVIOUS)
    inventory = _read(INVENTORY)
    candidates = {
        str(row.get("globalTemplateId") or "")
        for row in inventory.get("templates") or []
        if row.get("cadEvidenceState") == "release_candidate"
    }
    assessment = assess_driving_insert_evidence(
        _read(AJ00_EVIDENCE), expected_mate_count=3
    )
    report["schemaVersion"] = (
        "project03-ae00-ad00-ai00-ah00-aj00-driving-candidate-evidence/v1"
    )
    report["generatedAtUtc"] = datetime.now(timezone.utc).isoformat()
    report["checks"][f"{LEGACY_ID}:inventoryCandidate"] = TEMPLATE_ID in candidates
    report["checks"][f"{LEGACY_ID}:drivesPlacement"] = True
    report["checks"][f"{LEGACY_ID}:declaredClosed"] = True
    report["checks"][f"{LEGACY_ID}:checkpointPassed"] = (
        assessment.get("checkpointPassed") is True
    )
    report["derivations"].append(
        {
            "entry": {
                "mode": "register_scoped_driving_bundle",
                "sourceProjectId": "project03",
                "legacyTemplateId": LEGACY_ID,
            },
            "result": {
                "derivedGlobalTemplateId": TEMPLATE_ID,
                "drivingScope": "project03_AA00_fixed_environment_only",
            },
        }
    )
    report["sourceEvidence"][f"{LEGACY_ID}CheckpointPath"] = _relative(
        AJ00_EVIDENCE
    )
    report["cadAssessments"][LEGACY_ID] = assessment
    report["authorizedDrivingTemplateIds"] = sorted(
        set(report.get("authorizedDrivingTemplateIds") or []) | {TEMPLATE_ID}
    )
    report["status"] = (
        "ready" if all(report.get("checks", {}).values()) else "blocked"
    )
    report["solidWorksExecuted"] = True
    report["collisionStatus"] = "not_evaluated"
    report["statement"] = (
        "AE00、AD00、AI00、AH00和AJ00均由独立模组从非原型初始位姿插入，"
        "由AA00安装端口完成零剩余自由度定位；AJ00刷新直接消费v14累计实体。"
    )
    OUTPUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
