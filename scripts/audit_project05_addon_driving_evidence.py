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
from demo_backend.global_module_catalog import (  # noqa: E402
    validate_global_module_catalog,
)
from demo_backend.mate_dof_analysis import analyze_target_mate_dof  # noqa: E402
from demo_backend.global_relation_semantics import (  # noqa: E402
    normalize_template_relation_profile,
)


DEFAULT_CATALOG = ROOT / (
    "demo/global_assembly_catalog/v1/"
    "global_module_catalog.combination-v1-preview.json"
)
DEFAULT_EVIDENCE_ROOT = ROOT / "demo/global_assembly_contexts/manifest_jobs"
DEFAULT_CHECKPOINT_ROOT = ROOT / (
    "demo/global_assembly_catalog/v1/combination-v1-preview"
)
DEFAULT_OUTPUT = ROOT / (
    "demo/global_assembly_catalog/v1/combination-v1-preview/"
    "project05-addon-driving-evidence-audit.json"
)
TARGETS = {
    "M000": "M000_to_A000_source_installation",
    "F000": "F000_to_A000_source_installation",
    "P000": "P000_to_A000_source_installation",
    "G000": "G000_to_A000_source_installation",
}
EFFECTIVE_GRAPHS = {
    token: ROOT
    / "demo/semantic_ports/project05_global_installation_ports_v1"
    / token
    / "assembly_plan_effective.json"
    for token in TARGETS
}


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON根节点必须为对象：{path}")
    return value


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _target_token(payload: dict[str, Any]) -> str:
    return str(
        payload.get("targetModuleToken")
        or (payload.get("toolResult") or {}).get("TargetModuleToken")
        or ""
    ).upper()


def build_audit(
    catalog: dict[str, Any],
    evidence_paths: list[Path],
) -> dict[str, Any]:
    validate_global_module_catalog(catalog)
    templates = {
        str(row.get("legacyTemplateId") or ""): row
        for row in catalog.get("connectionTemplates") or []
        if (row.get("provenance") or {}).get("projectId") == "project05"
    }
    rows = []
    for token, legacy_id in TARGETS.items():
        template = templates.get(legacy_id)
        if template is None:
            raise ValueError(f"目录缺少Project05模板：{legacy_id}")
        profile = normalize_template_relation_profile(template)
        expected = int(profile.get("drivingMateStepCount") or 0)
        evidence = []
        for path in evidence_paths:
            try:
                payload = _read(path)
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            if not _target_token(payload).endswith(token):
                continue
            assessment = assess_driving_insert_evidence(
                payload,
                expected_mate_count=expected,
            )
            evidence.append(
                {
                    "path": _relative(path),
                    "assessment": assessment,
                }
            )
        release_candidate = next(
            (
                row
                for row in evidence
                if row["assessment"].get("checkpointPassed") is True
            ),
            None,
        )
        anchored_checkpoint = next(
            (
                row
                for row in evidence
                if row["assessment"].get("checkpointChecks", {}).get(
                    "checkpointEnvelope"
                )
                is True
                and row["assessment"].get("semanticChecks", {}).get(
                    "casePoseAnchorNotUsed"
                )
                is False
            ),
            None,
        )
        explanation = profile.get("constraintExplanation") or {}
        graph_path = EFFECTIVE_GRAPHS[token]
        dof_analysis = analyze_target_mate_dof(_read(graph_path), token)
        declared_closed = bool(
            explanation.get("state") == "declared_closed"
            and explanation.get("expectedResidualDof") == 0
        )
        if release_candidate and declared_closed:
            state = "release_candidate"
        elif release_candidate:
            state = "semantic_upgrade_required_with_nonanchor_checkpoint"
        elif anchored_checkpoint:
            state = "case_anchor_dependency_blocks_release"
        elif evidence:
            state = "cad_evidence_blocked"
        else:
            state = "strict_checkpoint_missing"
        blockers = []
        if not declared_closed:
            blockers.append("TEMPLATE_NOT_DECLARED_CLOSED_WITHOUT_CASE_ANCHOR")
        if release_candidate is None:
            blockers.append("NONPROTOTYPE_INITIAL_POSE_CHECKPOINT_MISSING")
        if anchored_checkpoint:
            blockers.append("TARGET_CASE_ANCHOR_USED")
        if token == "P000" and expected < 3:
            blockers.append("TWO_MATE_BUNDLE_REQUIRES_INDEPENDENT_DOF_PROOF")
        if not dof_analysis["closed"]:
            blockers.append("RIGID_BODY_DOF_NOT_CLOSED")
        rows.append(
            {
                "moduleToken": token,
                "legacyTemplateId": legacy_id,
                "globalTemplateId": template.get("globalTemplateId"),
                "drivingMateStepCount": expected,
                "constraintState": explanation.get("state"),
                "residualDofPolicy": explanation.get("residualDofPolicy"),
                "dofAnalysisPath": _relative(graph_path),
                "dofAnalysis": dof_analysis,
                "state": state,
                "releaseEligible": state == "release_candidate",
                "selectedEvidencePath": (
                    release_candidate or anchored_checkpoint or {"path": None}
                )["path"],
                "blockers": blockers,
                "evidence": evidence,
            }
        )
    eligible = [row for row in rows if row["releaseEligible"]]
    return {
        "schemaVersion": "project05-addon-driving-evidence-audit/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "projectId": "project05",
        "catalogDigest": catalog.get("catalogDigest"),
        "status": "release_candidates_available" if eligible else "blocked",
        "targetCount": len(rows),
        "releaseCandidateCount": len(eligible),
        "targets": rows,
        "nextAction": (
            "Create deterministic displaced-pose checkpoints with TargetCaseAnchored=false, "
            "then promote only mechanically closed templates to declared_closed."
        ),
        "collisionStatus": "not_evaluated",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="审计Project05 M000/F000/P000/G000的独立驱动发布证据。"
    )
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--evidence-root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    evidence_paths = sorted(
        {
            *(
                path.resolve()
                for path in args.evidence_root.resolve().glob(
                    "project05-job-*/packet-runs/packet-*/cad-result.json"
                )
                if path.is_file()
            ),
            *(
                path.resolve()
                for directory in DEFAULT_CHECKPOINT_ROOT.glob(
                    "project05-*-checkpoint-v1"
                )
                for path in directory.glob("*.result.json")
                if path.is_file()
            ),
        }
    )
    report = build_audit(_read(args.catalog.resolve()), evidence_paths)
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
