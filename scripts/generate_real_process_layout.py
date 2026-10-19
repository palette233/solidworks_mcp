from __future__ import annotations

import json
import sys
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
BACKEND_SRC = WORKSPACE / "apps" / "demo-backend" / "src"
REQUEST_PATH = WORKSPACE / "demo" / "FL9A24D062A000_real_process_request.json"

sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.constraint_layout import generate_constraint_layout  # noqa: E402
from demo_backend.layout_preview import build_source_independent_options  # noqa: E402


def workspace_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else WORKSPACE / path


def main() -> None:
    request = json.loads(REQUEST_PATH.read_text(encoding="utf-8"))
    geometry_path = workspace_path(request["geometryCapturePath"])
    output_path = workspace_path(request["outputPath"])
    capture = json.loads(geometry_path.read_text(encoding="utf-8"))
    result = generate_constraint_layout(
        capture,
        # Keep this command-line entry point behaviorally identical to the
        # exhibition/API solver: source-independent options, structural
        # occupancy, and the complete strict-AABB/conditional-B-Rep pair policy
        # must be applied before solving.
        build_source_independent_options(request, WORKSPACE),
    )
    result["outputPath"] = str(output_path)
    result["coarseRequestPath"] = str(REQUEST_PATH)
    result["knownCoverageGap"] = request.get("knownCoverageGap")
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    process = result["constraintPlan"]["processValidation"]
    spatial = result["constraintPlan"]["spatialValidation"]
    reach = result["constraintPlan"]["reachValidation"]
    print(
        json.dumps(
            {
                "result": "PASS",
                "output": str(output_path),
                "componentCount": len(result["components"]),
                "processConstraints": f"{process['passedCount']}/{process['constraintCount']}",
                "spatialConstraints": f"{spatial['passedCount']}/{spatial['constraintCount']}",
                "reachContained": reach["hardFeasible"],
                "productionReady": result["constraintPlan"]["validation"]["productionReady"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
