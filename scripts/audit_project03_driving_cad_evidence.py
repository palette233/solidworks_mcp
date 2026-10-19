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
from demo_backend.global_template_combination_readiness import (  # noqa: E402
    assess_template_combination_readiness,
)


DEFAULT_CATALOG = ROOT / (
    "demo/global_assembly_catalog/v1/"
    "global_module_catalog.combination-v1-preview.json"
)
DEFAULT_OUTPUT = ROOT / (
    "demo/global_assembly_catalog/v1/combination-v1-preview/"
    "project03-driving-cad-evidence-inventory.json"
)

# Prefer the first independent increment: its source context does not contain
# any of the later AG00/AB00/AC00 anchor-dependent links.
PORTABLE_PRIORITY = (
    "AE00_to_AA00_three_datum_installation",
    "AD00_to_AA00_three_datum_installation",
    "AI00_to_AA00_five_mate_installation",
    "AH00_to_AA00_three_datum_installation",
    "AJ00_to_AA00_three_datum_installation",
)


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON根节点必须是对象：{path}")
    return value


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _target_suffix(template: dict[str, Any]) -> str:
    legacy = str(template.get("legacyTemplateId") or "")
    return legacy.split("_to_", 1)[0].strip().upper()


def build_inventory(catalog: dict[str, Any]) -> dict[str, Any]:
    readiness = assess_template_combination_readiness(
        catalog,
        project_id="project03",
    )
    rows = []
    shared_evidence_paths = [
        path
        for directory in DEFAULT_OUTPUT.parent.glob("project03-*-checkpoint-v1")
        for path in directory.glob("*.result.json")
    ]
    for template in readiness["templates"]:
        source = ROOT / str(template.get("semanticCatalogPath") or "")
        expected_mates = int(template.get("drivingMateStepCount") or 0)
        evidence_rows = []
        candidate_paths: set[Path] = set(shared_evidence_paths)
        if source.parent.is_dir():
            candidate_paths.update(source.parent.glob("*.result.json"))
        target_suffix = _target_suffix(template)
        for path in sorted(candidate_paths):
            try:
                payload = _read(path)
                target = str(
                    payload.get("targetModuleToken")
                    or (payload.get("toolResult") or {}).get("TargetModuleToken")
                    or ""
                ).upper()
                if target_suffix and not target.endswith(target_suffix):
                    continue
                assessment = assess_driving_insert_evidence(
                    payload,
                    expected_mate_count=expected_mates,
                )
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                assessment = {
                    "status": "blocked",
                    "checkpointPassed": False,
                    "semanticPassed": False,
                    "blockers": [f"EVIDENCE_READ_FAILED: {exc}"],
                }
            evidence_rows.append(
                {
                    "path": _relative(path),
                    "assessment": assessment,
                }
            )
        checkpoint = next(
            (
                row
                for row in evidence_rows
                if row["assessment"].get("status") == "release_candidate"
            ),
            None,
        )
        legacy = next(
            (
                row
                for row in evidence_rows
                if row["assessment"].get("status")
                == "checkpoint_refresh_required"
            ),
            None,
        )
        if template["state"] != "declared_atomic_closed":
            state = "semantic_completion_required"
        elif checkpoint:
            state = "release_candidate"
        elif legacy:
            state = "checkpoint_refresh_required"
        else:
            state = "cad_evidence_missing_or_blocked"
        rows.append(
            {
                **template,
                "cadEvidenceState": state,
                "selectedEvidencePath": (
                    checkpoint or legacy or {"path": None}
                )["path"],
                "evidence": evidence_rows,
            }
        )

    priority = {value: index for index, value in enumerate(PORTABLE_PRIORITY)}
    release_candidates = sorted(
        (row for row in rows if row["cadEvidenceState"] == "release_candidate"),
        key=lambda row: priority.get(str(row.get("legacyTemplateId")), 999),
    )
    refresh_candidates = sorted(
        (
            row
            for row in rows
            if row["cadEvidenceState"] == "checkpoint_refresh_required"
        ),
        key=lambda row: priority.get(str(row.get("legacyTemplateId")), 999),
    )
    selected = release_candidates[0] if release_candidates else None
    recommended_refresh = refresh_candidates[0] if refresh_candidates else None
    return {
        "schemaVersion": "project03-driving-cad-evidence-inventory/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "projectId": "project03",
        "catalogDigest": catalog.get("catalogDigest"),
        "status": "candidate_selected" if selected else "checkpoint_refresh_required",
        "templateCount": len(rows),
        "releaseCandidateCount": len(release_candidates),
        "checkpointRefreshRequiredCount": len(refresh_candidates),
        "selectedReleaseCandidate": (
            {
                "globalTemplateId": selected["globalTemplateId"],
                "legacyTemplateId": selected["legacyTemplateId"],
                "evidencePath": selected["selectedEvidencePath"],
            }
            if selected
            else None
        ),
        "recommendedCheckpointRefresh": (
            {
                "globalTemplateId": recommended_refresh["globalTemplateId"],
                "legacyTemplateId": recommended_refresh["legacyTemplateId"],
                "legacyEvidencePath": recommended_refresh["selectedEvidencePath"],
            }
            if recommended_refresh
            else None
        ),
        "templates": rows,
        "policy": {
            "legacyEnvelopeMayAuthorizeRelease": False,
            "prototypeOrCaseAnchorMayAuthorizeRelease": False,
            "targetMustStartFromDeterministicNonSourcePose": True,
            "sourceAndOutputDocumentCheckpointRequired": True,
            "collisionOrBrepEvaluated": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="盘点Project03驱动模板的真实CAD与checkpoint证据。"
    )
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = build_inventory(_read(args.catalog.resolve()))
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
