#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "demo-backend" / "src"))

from demo_backend.constraint_layout import generate_constraint_layout
from demo_backend.layout_preview import build_source_independent_options
from demo_backend.project02_robustness import (
    compare_signatures,
    placement_signature,
    with_service_component_scale,
)


COMPONENTS = {
    "A500": "FL9A24D062A500.001-1",
    "A700": "FL9A24D062A700.001-1",
    "A300": "FL9A24D062A300.001-1",
}


def solve(capture: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    return generate_constraint_layout(
        capture, build_source_independent_options(request, ROOT)
    )


def main() -> int:
    request_path = ROOT / "demo/FL9A24D062A000_real_process_request.json"
    request = json.loads(request_path.read_text(encoding="utf-8-sig"))
    capture = json.loads(
        (ROOT / request["geometryCapturePath"]).read_text(encoding="utf-8-sig")
    )
    baseline = solve(capture, request)
    baseline_signature = placement_signature(baseline)
    if not baseline_signature:
        raise RuntimeError("Baseline Project02 solve has no rank-1 placement")

    scenarios: list[dict[str, Any]] = []
    for code, component in COMPONENTS.items():
        for factor in (1.0, 1.25, 1.5):
            started = time.perf_counter()
            try:
                generated = solve(
                    capture,
                    with_service_component_scale(request, component, factor),
                )
                signature = placement_signature(generated)
                comparison = compare_signatures(baseline_signature, signature)
                scenarios.append(
                    {
                        "moduleCode": code,
                        "componentName": component,
                        "scaleFactor": factor,
                        "feasible": bool(generated.get("success")) and bool(signature),
                        "layoutComparison": comparison,
                        "replayRequiredIfApplied": bool(signature)
                        and not comparison["equivalent"],
                        "elapsedSeconds": time.perf_counter() - started,
                    }
                )
            except Exception as exc:
                scenarios.append(
                    {
                        "moduleCode": code,
                        "componentName": component,
                        "scaleFactor": factor,
                        "feasible": False,
                        "layoutComparison": None,
                        "replayRequiredIfApplied": False,
                        "error": f"{type(exc).__name__}: {exc}",
                        "elapsedSeconds": time.perf_counter() - started,
                    }
                )

    module_summary = {}
    for code in COMPONENTS:
        rows = [row for row in scenarios if row["moduleCode"] == code]
        feasible = [row for row in rows if row["feasible"]]
        preserved = [
            row
            for row in feasible
            if (row.get("layoutComparison") or {}).get("equivalent")
        ]
        module_summary[code] = {
            "testedScaleFactors": [row["scaleFactor"] for row in rows],
            "feasibleScaleFactors": [row["scaleFactor"] for row in feasible],
            "layoutPreservingScaleFactors": [
                row["scaleFactor"] for row in preserved
            ],
            "maximumTestedLayoutPreservingScaleFactor": max(
                (row["scaleFactor"] for row in preserved), default=None
            ),
        }

    success = all(
        row["feasible"]
        and (row.get("layoutComparison") or {}).get("equivalent")
        for row in scenarios
        if row["scaleFactor"] == 1.0
    )
    report = {
        "schemaVersion": "project02-service-component-robustness/v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "success": success,
        "status": "SERVICE_COMPONENT_PROTECTED_SPACE_SENSITIVITY_AUDITED",
        "authority": "prototypeBaselineAcceptedForCoarseLayout",
        "vendorConfirmed": False,
        "scope": "project02-only",
        "scenarioCount": len(scenarios),
        "scenarios": scenarios,
        "summary": module_summary,
        "decision": {
            "promoteScaledEnvelopeToFormalBaseline": False,
            "reason": (
                "Per-module scale factors are sensitivity probes, not measured tool or "
                "operator envelopes. Keep the purpose-specific Project02 baseline until "
                "maintenance actions and access directions are measured."
            ),
        },
    }
    output = (
        ROOT
        / "demo/layout_previews/project02_service_component_robustness.json"
    )
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
