#!/usr/bin/env python3
"""Build AC00 diagnostic/final static-snapshot effective graphs.

The diagnostic graph fixes only the AC00 top-level source pose.  The final
graph additionally restores the smallest useful set of parent-context subtree
poses selected from a prototype/candidate comparison.  This is a transparent
static-demo fallback for a flexible subtree, not a claim that the four source
mates are sufficient or production-ready.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path


def load(path: Path) -> dict:
    return json.loads(path.resolve().read_text(encoding="utf-8-sig"))


def write(path: Path, value: dict) -> None:
    path.resolve().parent.mkdir(parents=True, exist_ok=True)
    path.resolve().write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def select_pose_anchors(reference: dict, comparison: dict) -> list[dict]:
    """Select unstable assembly nodes while avoiding redundant descendants.

    A parent-context transform is enough when every unstable descendant moves
    by the same rigid transform.  A nested assembly is retained only when its
    displacement differs materially from its nearest already selected parent.
    Leaf parts are used only when no assembly node can represent that branch.
    """

    reference_by_path = {
        row["relativeHierarchyPath"]: row for row in reference["components"]
    }
    unstable = {
        row["relativeHierarchyPath"]: row
        for row in comparison["comparisons"]
        if not row["stable"]
        and row["presentInReference"]
        and row["presentInCandidate"]
        and row["relativeHierarchyPath"] != "@root"
    }
    selected: list[str] = []
    for path in sorted(unstable, key=lambda item: (item.count("/"), item.casefold())):
        row = reference_by_path[path]
        is_assembly = str(row.get("path") or "").lower().endswith(".sldasm")
        selected_parent = next(
            (
                parent
                for parent in reversed(selected)
                if path.startswith(parent + "/")
            ),
            None,
        )
        if selected_parent is None:
            # Prefer the first unstable assembly in each branch.  A direct leaf
            # still has to be retained when the branch has no assembly node.
            if is_assembly or "/" not in path:
                selected.append(path)
            continue
        parent_error = unstable[selected_parent].get("translationDistanceMeters")
        current_error = unstable[path].get("translationDistanceMeters")
        if is_assembly and parent_error is not None and current_error is not None:
            if abs(float(current_error) - float(parent_error)) > 1e-6:
                selected.append(path)

    # Cover any still-unrepresented unstable branch with its shallowest node.
    for path in sorted(unstable, key=lambda item: (item.count("/"), item.casefold())):
        if not any(path == parent or path.startswith(parent + "/") for parent in selected):
            selected.append(path)

    anchors = []
    for path in sorted(set(selected), key=lambda item: (item.count("/"), item.casefold())):
        row = reference_by_path[path]
        resolver_path = path.split("/@module/")[-1]
        anchors.append(
            {
                "relativeLeafHierarchyPath": resolver_path,
                "transform": row["transform"],
                "evidence": (
                    "project03 prototype parent-context Transform2; "
                    f"canonicalSnapshotPath={path}"
                ),
            }
        )
    return anchors


def build(
    source_effective: dict,
    reference: dict | None = None,
    comparison: dict | None = None,
) -> dict:
    graph = copy.deepcopy(source_effective)
    graph["Mates"] = []
    graph["InterModuleMateCount"] = 0
    policy = graph.setdefault("EditPolicy", {})
    policy["caseAnchoredModuleTokens"] = ["FL9A24D063AC00"]
    anchors = (
        select_pose_anchors(reference, comparison)
        if reference is not None and comparison is not None
        else []
    )
    policy["targetLeafPoseAnchors"] = anchors
    if anchors:
        target = next(
            module
            for module in graph["Modules"]
            if module["ModuleToken"] == "FL9A24D063AC00"
        )
        target["SolvingState"] = 0
        target["SolvingStateName"] = "swComponentRigidSolving"
    audit = graph.setdefault("SemanticAssemblyPlanAudit", {})
    audit["staticSnapshotPolicy"] = {
        "status": "project03-provisional-static-demo",
        "sourceDrivingMatesApplied": [],
        "sourceDrivingMatesRetainedAsEvidence": [
            "重合26",
            "同心34",
            "同心35",
            "重合29",
        ],
        "reason": (
            "Three source mates leave a 54.300553 mm top-level residual, while "
            "all four over-define the assembly.  The static branch therefore "
            "uses the calibrated top-level source pose and explicit parent-context "
            "subtree poses for the flexible AC00 state."
        ),
        "motionSemanticsPreserved": False,
        "sourceSolvingState": "swComponentFlexibleSolving",
        "staticDemoSolvingState": (
            "swComponentRigidSolving" if anchors else "swComponentFlexibleSolving"
        ),
        "leafPoseAnchorCount": len(anchors),
        "requiresEngineerApprovalForProduction": True,
    }
    audit["failedRelationTrials"] = [
        {
            "trial": "three-driving-mates",
            "result": "CAD solve clean but top-level Z residual is 0.0543005534 m",
        },
        {
            "trial": "four-driving-mates",
            "result": "重合29 returned swAddMateError_OverDefinedAssembly",
        },
        {
            "trial": "three-driving-mates-plus-top-level-anchor",
            "result": "mate solution conflicts with the calibrated top-level source pose",
        },
    ]
    return graph


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-effective", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--comparison", type=Path)
    args = parser.parse_args()
    if bool(args.reference) != bool(args.comparison):
        parser.error("--reference and --comparison must be supplied together")
    graph = build(
        load(args.source_effective),
        load(args.reference) if args.reference else None,
        load(args.comparison) if args.comparison else None,
    )
    write(args.output, graph)
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "mateCount": len(graph["Mates"]),
                "leafPoseAnchorCount": len(
                    graph["EditPolicy"]["targetLeafPoseAnchors"]
                ),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
