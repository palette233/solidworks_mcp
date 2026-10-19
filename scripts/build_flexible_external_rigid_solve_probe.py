from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create a diagnostic graph that solves one flexible target as rigid. "
            "The output is an experiment and is not a released driving graph."
        )
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    graph = json.loads(args.input.read_text(encoding="utf-8-sig"))
    target = args.target.strip().upper()
    matches = [
        row
        for row in graph.get("Modules") or []
        if str(row.get("ModuleToken") or "").strip().upper() == target
    ]
    if len(matches) != 1:
        raise ValueError(f"Target {target} resolved to {len(matches)} modules")
    module = matches[0]
    original = {
        "solvingState": module.get("SolvingState"),
        "solvingStateName": module.get("SolvingStateName"),
    }
    module["SolvingState"] = 0
    module["SolvingStateName"] = "swComponentRigidSolving"
    graph["FlexibleExternalPlacementProbe"] = {
        "probeKind": "solve_external_installation_as_rigid",
        "targetModuleToken": target,
        "originalTargetSemantics": original,
        "releasedForPlacement": False,
        "purpose": (
            "Determine whether flexible internal endpoints allow a top-level "
            "gauge/branch drift during external installation."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(graph, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "output": str(args.output),
        "target": target,
        "originalSolvingState": original["solvingState"],
        "probeSolvingState": 0,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
