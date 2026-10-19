from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
BACKEND_SRC = WORKSPACE / "apps" / "demo-backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.constraint_layout import ConstraintLayoutOptions, generate_constraint_layout  # noqa: E402


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else WORKSPACE / path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a provisional process-aware Layout2D document without changing SolidWorks CAD."
    )
    parser.add_argument(
        "request",
        nargs="?",
        default="demo/FL9A24D062A000_coarse_process_request.json",
        help="Coarse-layout request JSON, absolute or relative to the workspace.",
    )
    args = parser.parse_args()

    request_path = resolve_path(args.request).resolve()
    request = json.loads(request_path.read_text(encoding="utf-8"))
    geometry_path = resolve_path(request["geometryCapturePath"]).resolve()
    output_path = resolve_path(request["outputPath"]).resolve()
    capture = json.loads(geometry_path.read_text(encoding="utf-8"))

    generated = generate_constraint_layout(
        capture,
        ConstraintLayoutOptions(
            role_overrides=request.get("roleOverrides") or {},
            margin_ratios=tuple(request.get("marginRatios") or [0.05, 0.03, 0.01, 0.0]),
            minimum_clearance_meters=float(request.get("minimumClearanceMeters") or 0.0),
            glue_distance_meters=float(request.get("glueDistanceMeters") or 0.0),
            allow_rotation=bool(request.get("allowRotation", False)),
            portal_pass_through={
                name: tuple(component_names)
                for name, component_names in (request.get("portalPassThrough") or {}).items()
            },
            portal_opening_width_ratio=float(request.get("portalOpeningWidthRatio") or 0.8),
            portal_opening_height_ratio=float(request.get("portalOpeningHeightRatio") or 0.75),
            module_semantics=request.get("moduleSemantics") or {},
            process_constraints=tuple(request.get("processConstraints") or []),
            auto_generate_process_constraints=bool(request.get("autoGenerateProcessConstraints", True)),
            provisional_components=tuple(request.get("provisionalComponents") or []),
            prefer_source_layout=bool(request.get("preferSourceLayout", False)),
            source_position_independent=bool(
                request.get("sourcePositionIndependent", False)
            ),
        ),
    )
    generated["outputPath"] = str(output_path)
    generated["coarseRequestPath"] = str(request_path)
    generated["knownCoverageGap"] = request.get("knownCoverageGap")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(generated, ensure_ascii=False, indent=2), encoding="utf-8")

    plan = generated["constraintPlan"]
    summary = {
        "success": generated["success"],
        "outputPath": str(output_path),
        "componentCount": len(generated["components"]),
        "processPassed": plan["processValidation"]["passedCount"],
        "processTotal": plan["processValidation"]["constraintCount"],
        "nonAllowedOverlapCount": len(plan["validation"]["overlapPairs"]),
        "allowedProjectedOverlapCount": len(plan["validation"]["allowedAabbOverlapPairs"]),
        "productionReady": plan["validation"]["productionReady"],
        "assumptionWarnings": plan["assumptionWarnings"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
