"""Create a machine-readable numerical gate for the Project 02 preview.

This audit deliberately does not claim visual approval.  It verifies the
source-independent hard constraints and reports top-level outline overflow and
conditional B-Rep candidates so a human can decide whether CAD Replay is worth
the cost.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PREVIEW = ROOT / "demo" / "layout_previews" / "project02_preview.json"
SOLUTION = ROOT / "demo" / "layout_previews" / "project02_solution.json"
OUTPUT = (
    ROOT
    / "demo"
    / "layout_previews"
    / "project02_v33_numerical_visual_gate.json"
)
FOCUSED_BREP = (
    ROOT
    / "demo"
    / "interference_8modules_clean_solved_v33"
    / "priority_a300_a700"
    / "FL9A24D062A000_8modules_clean_solved_v33_leaf_details_A300_A700.json"
)


def pair_key(first: str, second: str) -> frozenset[str]:
    return frozenset((first, second))


def overlaps(first: list[float], second: list[float]) -> bool:
    return not (
        first[2] < second[0]
        or second[2] < first[0]
        or first[3] < second[1]
        or second[3] < first[1]
    )


def outline_overflow(bounds: list[float], container: list[float]) -> dict[str, float]:
    return {
        "lowU": max(0.0, container[0] - bounds[0]),
        "lowV": max(0.0, container[1] - bounds[1]),
        "highU": max(0.0, bounds[2] - container[2]),
        "highV": max(0.0, bounds[3] - container[3]),
    }


def code(name: str) -> str:
    upper = name.upper()
    for value in ("A100", "A180", "A200", "A300", "A500", "A700", "A800", "T401"):
        if value in upper:
            return value
    return name


def main() -> None:
    preview = json.loads(PREVIEW.read_text(encoding="utf-8"))
    solution = json.loads(SOLUTION.read_text(encoding="utf-8"))
    modules = preview["modules"]
    by_name = {item["componentName"]: item for item in modules}
    by_code = {item["code"]: item for item in modules}
    gantry = by_code["A100"]
    policy = preview["staticCollisionPolicy"]

    conditional_pairs = [
        pair
        for pair in policy.get("brepOnAabbOverlapPairs", [])
        if overlaps(by_name[pair[0]]["bounds"], by_name[pair[1]]["bounds"])
    ]
    deferred = [
        item
        for item in preview["diagnostics"]
        if item.get("conditionalBrepPair")
        and (
            item.get("collisionDetected")
            or item.get("resolution") == "insufficientOccupancyCoverageDeferredToCad"
        )
    ]
    portal_pair = pair_key(
        by_code["A200"]["componentName"], by_code["A800"]["componentName"]
    )
    portal_diagnostics = [
        item
        for item in preview["diagnostics"]
        if pair_key(
            str(item.get("firstComponent")), str(item.get("secondComponent"))
        )
        == portal_pair
        and item.get("portalCheck")
    ]
    nested_pair = pair_key(
        by_code["A300"]["componentName"], by_code["A700"]["componentName"]
    )
    nested_diagnostics = [
        item
        for item in preview["diagnostics"]
        if pair_key(
            str(item.get("firstComponent")), str(item.get("secondComponent"))
        )
        == nested_pair
        and item.get("conditionalBrepPair")
    ]
    relative_anchor_diagnostics = [
        item
        for item in preview["diagnostics"]
        if item.get("type") == "relativeAnchorWindow"
        and item.get("id") == "a300-a700-service-cluster-relative-window"
    ]
    focused_brep = json.loads(FOCUSED_BREP.read_text(encoding="utf-8"))
    quarter_turns = all(
        math.isclose(float(item["thetaDegrees"]) / 90.0, round(float(item["thetaDegrees"]) / 90.0), abs_tol=1e-6)
        for item in modules
    )
    strict_diagnostics = [
        item
        for item in preview["diagnostics"]
        if item.get("type") == "strictInflatedAabbSeparation"
    ]
    gantry_functional = [
        item
        for item in preview["diagnostics"]
        if item.get("type")
        in {"functionalGantryOverlap", "functionalGantryBoundaryClearance"}
    ]
    checks = {
        # Project02 deliberately reuses only A800's absolute prototype anchor
        # after the relative solve.  The feasibility search itself must remain
        # source-independent; an output-frame case anchor is not a failed
        # no-prototype-dependency test.
        "relativeConstraintSolveSourceIndependent": bool(
            preview.get("relativeConstraintsSourceIndependent")
        )
        and bool(
            (preview.get("caseAnchor") or {}).get(
                "relativeConstraintsRemainSourceIndependent"
            )
        ),
        "exactEightModules": {item["code"] for item in modules}
        == {"A100", "A180", "A200", "A300", "A500", "A700", "A800", "T401"},
        "hardFeasible": bool(preview["metrics"]["hardFeasible"]),
        "processHardConstraints": preview["metrics"]["processPassed"]
        == preview["metrics"]["processTotal"],
        "spatialHardConstraints": preview["metrics"]["spatialPassed"]
        == preview["metrics"]["spatialTotal"],
        "interactionHardConstraints": preview["metrics"]["interactionPassed"]
        == preview["metrics"]["interactionTotal"],
        "transportCentered": float(preview["metrics"]["transportCenterOffsetMeters"])
        <= 0.05,
        "a200GantryOverlap": float(preview["metrics"]["portalGantryOverlapRatio"])
        >= 0.85,
        "a200GantryCenterline": float(preview["metrics"]["portalCenterOffsetMeters"])
        <= float(preview["metrics"].get("portalMaximumCenterOffsetMeters") or 0.03),
        "a200GantryBoundedOverhang": float(
            preview["metrics"]["portalMaximumOverhangMeters"]
        )
        <= 0.16,
        "quarterTurnOrientations": quarter_turns,
        "strictAabbPairsSeparated": bool(strict_diagnostics)
        and all(item.get("success") for item in strict_diagnostics),
        "functionalGantryRules": bool(gantry_functional)
        and all(item.get("success") for item in gantry_functional),
        "a200A800PortalOpening": bool(portal_diagnostics)
        and all(item.get("success") for item in portal_diagnostics),
        "a300A700RelativeWindow": bool(relative_anchor_diagnostics)
        and all(item.get("success") for item in relative_anchor_diagnostics),
        "a300A700FocusedBrepClear": bool(focused_brep.get("ExactCheckComplete"))
        and not bool(focused_brep.get("HasInterference"))
        and int(focused_brep.get("FailedBodyPairCount", 0)) == 0,
    }
    outlines: list[dict[str, Any]] = []
    for item in modules:
        if item["code"] == "A100":
            continue
        overflow = outline_overflow(item["bounds"], gantry["bounds"])
        outlines.append(
            {
                "component": item["componentName"],
                "code": item["code"],
                "topLevelBounds": item["bounds"],
                "gantryBounds": gantry["bounds"],
                "fullyInsideTopLevelGantryOutline": not any(overflow.values()),
                "overflowMeters": overflow,
                "fullContainmentRequired": False,
                "boundedOverhangHardConstraint": item["code"] == "A200",
                "interpretation": (
                    "A200 uses overlap, short-axis centerline and bounded one-sided overhang "
                    "instead of full top-level containment; other outlines remain visual-review "
                    "signals while process reach, spatial overlap and boundary-clearance diagnostics "
                    "remain authoritative hard gates."
                ),
            }
        )

    numerical_pass = all(checks.values())
    result = {
        "schemaVersion": 1,
        "caseId": "project02",
        "status": (
            "NUMERICAL_AND_A300_A700_FOCUSED_BREP_PASSED_REMAINING_REVIEW_REQUIRED"
            if numerical_pass
            else "NUMERICAL_GATE_FAILED"
        ),
        "numericalGatePassed": numerical_pass,
        "visualApprovalCompleted": False,
        "eligibleForReplay": numerical_pass,
        "productionReady": False,
        "checks": checks,
        "metrics": preview["metrics"],
        "topLevelOutlineReview": outlines,
        "predictedConditionalBrepPairs": [
            {"components": pair, "codes": [code(name) for name in pair]}
            for pair in conditional_pairs
        ],
        "predictedConditionalBrepPairCount": len(conditional_pairs),
        "nestedStructuralReview": {
            "codes": ["A300", "A700"],
            "topLevelAabbOverlapAllowed": True,
            "diagnostics": nested_diagnostics,
            "interpretation": (
                "A300/A700 is treated as a non-convex nested structural pair. Top-level AABB "
                "overlap is not an interference verdict; conditional leaf-level B-Rep remains "
                "the final CAD gate after Replay."
            ),
        },
        "focusedCadEvidence": {
            "codes": ["A300", "A700"],
            "assembly": "demo/FL9A24D062A000_8modules_clean_solved_v33.SLDASM",
            "leafBrepResult": str(FOCUSED_BREP),
            "exactCheckComplete": bool(focused_brep.get("ExactCheckComplete")),
            "hasInterference": bool(focused_brep.get("HasInterference")),
            "interferingBodyPairCount": int(
                focused_brep.get("InterferingBodyPairCount", 0)
            ),
            "failedBodyPairCount": int(focused_brep.get("FailedBodyPairCount", 0)),
            "interpretation": (
                "The v33 saved assembly passed the focused A300/A700 leaf-level CAD gate. "
                "This is not a full-assembly interference certificate."
            ),
        },
        "priorityBrepPairs": [
            {
                "components": [item["firstComponent"], item["secondComponent"]],
                "codes": [code(item["firstComponent"]), code(item["secondComponent"])],
                "reason": item.get("resolution"),
                "coarseCollisionDetected": bool(item.get("collisionDetected")),
                "coarseCollidingBoxPairCount": int(item.get("collidingBoxPairCount", 0)),
            }
            for item in deferred
        ],
        "nextGate": {
            "required": "remainingConditionalPairReview",
            "reviewItems": [
                "A200 one-sided support overhang after the centerline and overlap gates",
                "scanner and service-module facing directions",
                "obvious contact near A200/A700 and the transport corridor",
                "A300/A700 nested clearance rather than top-level AABB overlap alone",
                "glue-supply accessibility and hose-routing side",
            ],
            "afterApproval": "Run broad-phase AABB for the remaining conditional pairs, then exact B-Rep only for those that still overlap.",
        },
        "inputs": {
            "preview": str(PREVIEW),
            "solution": str(SOLUTION),
            "structuralOccupancy": "demo/FL9A24D062A000_structural_occupancy_v31.json",
            "focusedBrep": str(FOCUSED_BREP),
        },
    }
    OUTPUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "checks": checks,
                "predictedConditionalBrepPairCount": len(conditional_pairs),
                "priorityBrepPairs": result["priorityBrepPairs"],
                "output": str(OUTPUT),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
