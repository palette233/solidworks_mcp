#!/usr/bin/env python3
"""Build an AC00 graph that fixes the target root before all four source mates.

This variant tests the actual flexible-subassembly semantics: the calibrated
AC00 root remains fixed while AB00/AC00 parent-context mates drive AC00's
internal leaves.  It is intentionally separate from the static leaf-anchor
fallback so the two hypotheses remain auditable.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.project03_incremental_work_packet import (  # noqa: E402
    _endpoint,
    _pair_mates,
    normalize_project03_paths,
)


TOKENS = {
    "FL9A24D063AA00",
    "FL9A24D063AF00",
    "FL9A24D063AE00",
    "FL9A24D063AD00",
    "FL9A24D063AI00",
    "FL9A24D063AG00",
    "FL9A24D063AH00",
    "FL9A24D063AJ00",
    "FL9A24D063AB00",
    "FL9A24D063AC00",
}


def load(path: Path) -> dict:
    return json.loads(path.resolve().read_text(encoding="utf-8-sig"))


def build(effective: dict, source_graph: dict, prototype: Path) -> dict:
    normalized, audit = normalize_project03_paths(
        source_graph, prototype.resolve(), selected_tokens=TOKENS
    )
    pair = _pair_mates(normalized, "FL9A24D063AB00", "FL9A24D063AC00")
    if len(pair) != 4:
        raise ValueError(f"Expected four AB00/AC00 source mates, got {len(pair)}")
    existing_types = [mate["MateTypeName"] for mate in effective["Mates"]]
    if existing_types.count("swMateCOINCIDENT") != 1 or existing_types.count("swMateCONCENTRIC") != 2:
        raise ValueError("Expected the three-mate AC00 base graph")
    used_leaf_paths = {
        endpoint["LeafHierarchyPath"]
        for mate in effective["Mates"]
        for endpoint in mate["Endpoints"]
        if endpoint["ModuleToken"] == "FL9A24D063AC00"
    }
    candidates = [
        mate
        for mate in pair
        if mate["MateTypeName"] == "swMateCOINCIDENT"
        and _endpoint(mate, "FL9A24D063AC00")["LeafHierarchyPath"] not in used_leaf_paths
    ]
    if len(candidates) != 1:
        raise ValueError(f"Could not identify one redundant AC30 coincident: {len(candidates)}")
    redundant = copy.deepcopy(candidates[0])
    redundant["MateName"] = "重合29"

    graph = copy.deepcopy(effective)
    graph["Mates"].append(redundant)
    graph["InterModuleMateCount"] = len(graph["Mates"])
    graph["EditPolicy"]["caseAnchoredModuleTokens"] = ["FL9A24D063AC00"]
    graph["EditPolicy"]["fixCaseAnchorBeforeMates"] = True
    graph["EditPolicy"]["targetLeafPoseAnchors"] = []
    target = next(
        module
        for module in graph["Modules"]
        if module["ModuleToken"] == "FL9A24D063AC00"
    )
    target["SolvingState"] = 1
    target["SolvingStateName"] = "swComponentFlexibleSolving"
    plan = graph.setdefault("SemanticAssemblyPlanAudit", {})
    plan["preFixedFlexibleTargetPolicy"] = {
        "status": "project03-cad-hypothesis-under-test",
        "fixCaseAnchorBeforeMates": True,
        "targetRootPoseSource": "prototype calibrated top-level transform",
        "sourceMateNames": [mate["MateName"] for mate in graph["Mates"]],
        "purpose": (
            "Keep the AC00 root fixed while parent-context AB00/AC00 mates drive "
            "the flexible AC00 internal leaves."
        ),
        "pathRecoveryPassed": audit["allResolved"],
        "requiresSubtreePoseComparison": True,
    }
    return graph


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--effective", required=True, type=Path)
    parser.add_argument("--source-graph", required=True, type=Path)
    parser.add_argument("--prototype", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    graph = build(load(args.effective), load(args.source_graph), args.prototype)
    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.output.resolve().write_text(
        json.dumps(graph, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "mateNames": [mate["MateName"] for mate in graph["Mates"]],
                "fixCaseAnchorBeforeMates": graph["EditPolicy"]["fixCaseAnchorBeforeMates"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
