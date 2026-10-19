#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.project02_prototype_dynamic_closure import (  # noqa: E402
    build_closure_report,
    compare_candidate_to_reference,
    recover_reference_layout,
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    root = ROOT / "demo"
    artifacts = root / "semantic_ports/project02_full_machine_increment_v1"
    source_capture_path = root / "FL9A24D062A000_8components_real_geometry.json"
    reference_path = root / "layout_previews/project02_selected_solution_reopened_v52.json"
    solution_path = root / "layout_previews/project02_solution.json"
    selected_solution_path = root / "layout_previews/project02_selected_solution.json"
    preview_path = root / "layout_previews/project02_preview.json"
    estimate_path = artifacts / "prototype_dynamic_estimates.json"
    audit_path = artifacts / "prototype_dynamic_profile_audit.json"
    reference_layout = recover_reference_layout(
        load(source_capture_path), load(reference_path)
    )
    preview = load(preview_path)
    comparison_source = load(solution_path)
    comparison_source_path = solution_path
    if selected_solution_path.exists():
        selected = load(selected_solution_path)
        approval = selected.get("visualApproval") or {}
        if (
            selected.get("components")
            and approval.get("sourcePreviewGeneratedAt") == preview.get("generatedAt")
        ):
            comparison_source = selected
            comparison_source_path = selected_solution_path
    comparison = compare_candidate_to_reference(comparison_source, reference_layout)
    report = build_closure_report(
        load(estimate_path),
        load(audit_path),
        preview,
        comparison,
    )
    report["generatedAt"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    report["sources"] = {
        "sourceGeometry": str(source_capture_path),
        "acceptedReferencePose": str(reference_path),
        "candidateSolution": str(comparison_source_path),
        "candidatePreview": str(preview_path),
        "dynamicEstimate": str(estimate_path),
        "dynamicProfileAudit": str(audit_path),
    }
    output = artifacts / "prototype_estimated_closure.json"
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(output),
                "status": report["status"],
                "estimatedProfilePassed": report["estimatedProfilePassed"],
                "solverHardConstraintsPassed": report["solverHardConstraintsPassed"],
                "cadReplayRequired": report["cadReplayRequired"],
                "changedComponentCount": comparison["changedComponentCount"],
                "maximumTranslationDeltaMeters": comparison["maximumTranslationDeltaMeters"],
                "productionDynamicReleaseAllowed": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["estimatedProfilePassed"] and report["solverHardConstraintsPassed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
