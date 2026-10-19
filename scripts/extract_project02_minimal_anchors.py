#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def pick(item: dict, name: str, default=None):
    return item.get(name, item.get(name[0].lower() + name[1:], default))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", required=True, type=Path)
    parser.add_argument("--dof", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite anchor report: {output}")
    graph = json.loads(args.graph.resolve().read_text(encoding="utf-8-sig"))
    dof = json.loads(args.dof.resolve().read_text(encoding="utf-8-sig"))
    modules = {str(pick(item, "HierarchyPath", "")): item for item in pick(graph, "Modules", []) or []}
    scalar = []
    module_anchors = []
    for component in dof["components"]:
        path = component["hierarchyPath"]
        module = modules[path]
        transform = list(pick(module, "SourceTransform", []) or [])
        if len(transform) < 12:
            raise ValueError(f"Module '{path}' has no source transform for residual anchor extraction.")
        module_anchors.append(
            {
                "moduleToken": pick(module, "ModuleToken", ""),
                "hierarchyPath": path,
                "sourceTransformFallback": transform,
                "fallbackSemantics": "Conservative full-transform convergence anchor for the current SolidWorks executor.",
            }
        )
        translation = transform[9:12]
        for coordinate in component["freeCoordinates"]:
            axis = coordinate["axisWorld"]
            item = {**coordinate, "module": path}
            if coordinate["kind"] == "translation":
                item["target"] = sum(float(axis[index]) * float(translation[index]) for index in range(3))
                item["unit"] = "m"
            else:
                item["targetSourceRotationMatrix"] = transform[:9]
                item["unit"] = "rad-equivalent orientation constraint"
            scalar.append(item)
    result = {
        "schemaVersion": "project02-minimal-residual-anchors/v1",
        "sourceGraph": str(args.graph.resolve()),
        "sourceDofReport": str(args.dof.resolve()),
        "baseModule": "A600",
        "residualScalarDofCount": len(scalar),
        "minimumModuleAnchorCount": len(module_anchors),
        "scalarAnchors": scalar,
        "moduleAnchors": module_anchors,
        "executorPolicy": "Use sourceTransformFallback only for the three underconstrained modules; all other non-base modules must start from deterministic non-source poses.",
        "refinementBoundary": "The current executor applies one full transform per selected module. A later scalar-anchor executor can reduce 18 transform values to the five listed free coordinates.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"success": True, "scalarAnchors": len(scalar), "moduleAnchors": len(module_anchors), "output": str(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
