"""Run a repeatable FL9A layout test without using prototype component positions."""

from __future__ import annotations

import copy
import json
import math
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "apps" / "demo-backend" / "src"
REQUEST = ROOT / "demo" / "FL9A24D062A000_real_process_request.json"
OUTPUT = ROOT / "demo" / "FL9A24D062A000_source_independent_layout2d.json"
VALIDATION = ROOT / "demo" / "FL9A24D062A000_source_independent_validation.json"
GANTRY = "FL9A24D062A100.001-1"

sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.constraint_layout import generate_constraint_layout  # noqa: E402
from demo_backend.layout_preview import build_source_independent_options  # noqa: E402


def resolve(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def translated_capture(source: dict, variant: int) -> tuple[dict, dict[str, list[float]]]:
    """Move every captured component independently while preserving its geometry."""
    result = copy.deepcopy(source)
    frame = result["baseFrame"]
    u_axis = frame["uAxis"]
    v_axis = frame["vAxis"]
    applied: dict[str, list[float]] = {}
    for index, item in enumerate(result["components"], start=1):
        if variant == 1:
            du = 0.43 * index - 1.31
            dv = 0.29 * ((index * 3) % 7) - 0.86
        else:
            du = -0.37 * index + 1.74
            dv = 0.31 * ((index * 5) % 9) - 1.12
        world_delta = [
            du * u_axis[axis] + dv * v_axis[axis]
            for axis in range(3)
        ]
        item["layout2d"]["x"] += du
        item["layout2d"]["y"] += dv
        for key in ("bottomCenterWorld", "componentTranslation"):
            values = item.get(key)
            if isinstance(values, list) and len(values) >= 3:
                for axis in range(3):
                    values[axis] += world_delta[axis]
        transform = item.get("sourceTransform")
        if isinstance(transform, list) and len(transform) >= 12:
            for axis in range(3):
                transform[9 + axis] += world_delta[axis]
        box = item["boundingBoxWorld"]
        for axis in range(3):
            box[axis] += world_delta[axis]
            box[axis + 3] += world_delta[axis]
        applied[item["componentName"]] = [du, dv]
    return result, applied


def layouts(result: dict) -> dict[str, dict]:
    return {item["componentName"]: item["layout2d"] for item in result["components"]}


def relative(layout: dict[str, dict], name: str) -> tuple[float, float]:
    return (
        layout[name]["x"] - layout[GANTRY]["x"],
        layout[name]["y"] - layout[GANTRY]["y"],
    )


def main() -> None:
    request = json.loads(REQUEST.read_text(encoding="utf-8"))
    capture = json.loads(resolve(request["geometryCapturePath"]).read_text(encoding="utf-8"))
    first_capture, first_perturbation = translated_capture(capture, 1)
    second_capture, second_perturbation = translated_capture(capture, 2)
    first = generate_constraint_layout(first_capture, build_source_independent_options(request))
    second = generate_constraint_layout(second_capture, build_source_independent_options(request))

    first_layout = layouts(first)
    second_layout = layouts(second)
    prototype_layout = layouts(capture)
    stability: list[dict] = []
    prototype_comparison: list[dict] = []
    for name in first_layout:
        first_relative = relative(first_layout, name)
        second_relative = relative(second_layout, name)
        prototype_relative = relative(prototype_layout, name)
        stability.append(
            {
                "componentName": name,
                "relativeLayoutDeltaBetweenPerturbationsMeters": math.dist(
                    first_relative, second_relative
                ),
                "absoluteLayoutDeltaBetweenPerturbationsMeters": math.dist(
                    (first_layout[name]["x"], first_layout[name]["y"]),
                    (second_layout[name]["x"], second_layout[name]["y"]),
                ),
            }
        )
        prototype_comparison.append(
            {
                "componentName": name,
                "prototypeRelativeToGantry": list(prototype_relative),
                "sourceIndependentRelativeToGantry": list(first_relative),
                "distanceFromPrototypeMeters": math.dist(first_relative, prototype_relative),
            }
        )

    plan = first["constraintPlan"]
    process = plan["processValidation"]
    spatial = plan["spatialValidation"]
    interaction = plan["interactionValidation"]
    reach = plan["reachValidation"]
    max_stability_delta = max(
        item["relativeLayoutDeltaBetweenPerturbationsMeters"] for item in stability
    )
    max_absolute_stability_delta = max(
        item["absoluteLayoutDeltaBetweenPerturbationsMeters"] for item in stability
    )
    max_prototype_distance = max(
        item["distanceFromPrototypeMeters"] for item in prototype_comparison
    )
    changed_count = sum(
        item["distanceFromPrototypeMeters"] > 0.01 for item in prototype_comparison
    )
    case_anchor = plan.get("caseAnchor") or {}
    explicit_installation_anchor = bool(case_anchor) and not bool(
        case_anchor.get("sourceCapturePoseReadForAnchor", True)
    )
    success = (
        plan["sourcePositionIndependent"]
        and not plan["preferSourceLayout"]
        and max_stability_delta <= 1e-9
        and (not explicit_installation_anchor or max_absolute_stability_delta <= 1e-9)
        and process["hardFeasible"]
        and spatial["hardFeasible"]
        and interaction["hardFeasible"]
        and reach["hardFeasible"]
        and not plan["validation"]["overlapPairs"]
        and not plan["containmentRelaxedComponents"]
    )

    first["sourceIndependentTest"] = {
        "sourceCoordinatesUsedAsCandidates": False,
        "sourceAnchorTieBreakersUsed": False,
        "gantryNormalizedToOrigin": True,
        "replayApplied": False,
        "note": "This is an offline layout-generation test; anchor translation is required before CAD Replay.",
    }
    first["constraintPlan"]["sourceIndependentPolicy"] = request.get(
        "sourceIndependentPolicy", {}
    )
    OUTPUT.write_text(json.dumps(first, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    validation = {
        "success": success,
        "testKind": "source-position-independent-two-perturbation",
        "baseRequest": str(REQUEST),
        "sourcePositionIndependent": plan["sourcePositionIndependent"],
        "preferSourceLayout": plan["preferSourceLayout"],
        "firstSourcePerturbations": first_perturbation,
        "secondSourcePerturbations": second_perturbation,
        "maxRelativeLayoutDeltaBetweenPerturbationsMeters": max_stability_delta,
        "maxAbsoluteLayoutDeltaBetweenPerturbationsMeters": max_absolute_stability_delta,
        "explicitInstallationAnchorUsed": explicit_installation_anchor,
        "sourceCapturePoseReadForAnchor": case_anchor.get(
            "sourceCapturePoseReadForAnchor"
        ),
        "maxDistanceFromPrototypeMeters": max_prototype_distance,
        "componentCountDifferentFromPrototypeByMoreThan10mm": changed_count,
        "processConstraints": f"{process['passedCount']}/{process['constraintCount']}",
        "spatialConstraints": f"{spatial['passedCount']}/{spatial['constraintCount']}",
        "interactionConstraints": f"{interaction['passedCount']}/{interaction['constraintCount']}",
        "reachContained": reach["hardFeasible"],
        "unallowedOverlapPairCount": len(plan["validation"]["overlapPairs"]),
        "containmentRelaxedComponents": plan["containmentRelaxedComponents"],
        "productionReady": plan["validation"]["productionReady"],
        "sourceIndependentPolicy": request.get("sourceIndependentPolicy", {}),
        "stabilityDiagnostics": stability,
        "prototypeComparison": prototype_comparison,
        "limitations": [
            "Uses CAD-captured projected footprints and source orientation axes, but not source component positions.",
            "The current Project02 installation-frame anchor parameter is still prototype-calibrated until the vendor longitudinal datum is confirmed.",
            "Process points, valve reach, scanner distance, and CCD coverage still contain documented provisional estimates.",
            "This stability test does not execute SolidWorks Replay or B-Rep checking; use the separately anchor-translated Replay input for CAD closure.",
        ],
        "layoutOutput": str(OUTPUT),
    }
    VALIDATION.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(validation, ensure_ascii=False, indent=2))
    if not success:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
