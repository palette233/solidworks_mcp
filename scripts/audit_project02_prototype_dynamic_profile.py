#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.project02_prototype_dynamic_estimates import (
    evaluate_vertical_stroke_scenarios,
    validate_solver_binding,
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    request_path = ROOT / "demo/FL9A24D062A000_real_process_request.json"
    estimate_path = ROOT / "demo/semantic_ports/project02_full_machine_increment_v1/prototype_dynamic_estimates.json"
    estimate = load(estimate_path)
    binding = validate_solver_binding(load(request_path), estimate)
    sensitivity = evaluate_vertical_stroke_scenarios(estimate, [0.2, 0.2455, 0.2655, 0.3])
    nominal = next(row for row in sensitivity["scenarios"] if abs(row["strokeMeters"] - 0.2655) < 1e-9)
    report = {
        "schemaVersion": "project02-prototype-dynamic-profile-audit/v1",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "projectId": "project02",
        "solverBinding": binding,
        "verticalStrokeSensitivity": sensitivity,
        "estimatedProfilePassed": bool(
            binding["passed"]
            and nominal["accepted"]
            and estimate["gate"]["prototypeEstimatedDynamicDemoPassed"]
        ),
        "productionDynamicReleaseAllowed": False,
        "sources": {"request": str(request_path), "estimate": str(estimate_path)},
    }
    output = ROOT / "demo/semantic_ports/project02_full_machine_increment_v1/prototype_dynamic_profile_audit.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "bindingPassed": binding["passed"], "estimatedProfilePassed": report["estimatedProfilePassed"], "productionDynamicReleaseAllowed": False}, ensure_ascii=False))
    return 0 if report["estimatedProfilePassed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
