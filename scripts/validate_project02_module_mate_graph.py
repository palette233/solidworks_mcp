#!/usr/bin/env python3
"""Validate the Project 02 module mate graph and record semantic gaps explicitly."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GRAPH = ROOT / "demo/layout_previews/project02_module_mate_graph_v4_semantics.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def pick(item: dict[str, Any], name: str, default: Any = None) -> Any:
    return item.get(name, item.get(name[0].lower() + name[1:], default))


def canonical_pair(first: str, second: str) -> tuple[str, str]:
    return tuple(sorted((first, second), key=str.casefold))  # type: ignore[return-value]


def main() -> int:
    args = parse_args()
    graph_path = args.graph.resolve()
    output_path = (args.output or graph_path.with_suffix(".validation.json")).resolve()
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    modules = pick(graph, "Modules", []) or []
    mates = pick(graph, "Mates", []) or []
    bundles = pick(graph, "MateBundles", []) or []
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, evidence: Any) -> None:
        checks.append({"name": name, "passed": bool(passed), "evidence": evidence})

    required = {"A100", "A180", "A200", "A300", "A500", "A600", "A700", "A800", "T401"}
    actual_tokens = {str(pick(module, "ModuleToken", "")) for module in modules}
    hierarchy_paths = [str(pick(module, "HierarchyPath", "")) for module in modules]
    check("all_project02_module_tokens_resolved", required <= actual_tokens, sorted(actual_tokens))
    check("module_instance_paths_are_unique", len(hierarchy_paths) == len(set(hierarchy_paths)), hierarchy_paths)
    check("a600_resolves_to_one_instance", sum(1 for module in modules if pick(module, "ModuleToken") == "A600") == 1, hierarchy_paths)
    check("t401_duplicate_instances_are_preserved", sum(1 for module in modules if pick(module, "ModuleToken") == "T401") == 2, hierarchy_paths)
    check("no_known_module_is_suppressed", not any(bool(pick(module, "IsSuppressed", False)) for module in modules), [pick(module, "SuppressionStateName") for module in modules])
    check(
        "mate_endpoint_geometry_schema_v1_2",
        str(pick(graph, "SchemaVersion", "")) in {"solidworks-module-mate-graph/v1.2", "solidworks-module-mate-graph/v1.3", "solidworks-module-mate-graph/v1.4"},
        pick(graph, "SchemaVersion"),
    )

    bundle_by_pair = {
        canonical_pair(str(pick(bundle, "FirstModuleToken", "")), str(pick(bundle, "SecondModuleToken", ""))): bundle
        for bundle in bundles
    }
    a600_a800 = bundle_by_pair.get(canonical_pair("A600", "A800"))
    check(
        "a600_a800_installation_bundle_exists",
        bool(a600_a800) and pick(a600_a800, "InstallationRelationAssessment") == "POSITION_AND_ORIENTATION_BUNDLE_CANDIDATE",
        a600_a800,
    )
    check("a600_a180_installation_bundle_exists", canonical_pair("A600", "A180") in bundle_by_pair, bundle_by_pair.get(canonical_pair("A600", "A180")))
    check("a600_a100_installation_bundle_exists", canonical_pair("A600", "A100") in bundle_by_pair, bundle_by_pair.get(canonical_pair("A600", "A100")))

    contact35 = next((mate for mate in mates if str(pick(mate, "MateName", "")) == "重合35"), None)
    contact_a600 = next(
        (
            endpoint
            for endpoint in (pick(contact35 or {}, "Endpoints", []) or [])
            if pick(endpoint, "ModuleToken") == "A600"
        ),
        None,
    )
    check(
        "a600_a800_support_surface_geometry_available",
        contact_a600 is not None
        and float(pick(contact_a600, "FaceArea", 0.0)) > 0.5
        and len(pick(contact_a600, "FaceCenterWorld", []) or []) == 3
        and len(pick(contact_a600, "FaceNormalWorld", []) or []) == 3,
        contact_a600,
    )

    width9 = next((mate for mate in mates if str(pick(mate, "MateName", "")) == "宽度9"), None)
    width_a600 = [
        endpoint
        for endpoint in (pick(width9 or {}, "Endpoints", []) or [])
        if pick(endpoint, "ModuleToken") == "A600"
    ]
    check(
        "a600_a800_width_center_references_available",
        len(width_a600) == 2
        and all(len(pick(endpoint, "FaceCenterWorld", []) or []) == 3 for endpoint in width_a600),
        width_a600,
    )

    distance8 = next((mate for mate in mates if str(pick(mate, "MateName", "")) == "距离8"), None)
    distance8_value = None if distance8 is None else pick(distance8, "Distance")
    check(
        "a500_a700_distance8_is_50mm",
        distance8 is not None
        and set(pick(distance8, "ModuleTokens", []) or []) == {"A500", "A700"}
        and abs(float(distance8_value) - 0.05) <= 1e-9,
        distance8,
    )

    semantic_gaps = {
        "a180_a800_direct_mateAbsent": canonical_pair("A180", "A800") not in bundle_by_pair,
        "operationFaceNotEncoded": True,
        "barcodeAndScannerFieldNotEncoded": True,
        "workPositionsAndServicePointsNotEncoded": True,
        "dualValveTravelEnvelopeNotEncoded": True,
        "assemblyPrecedenceNotEncodedByUndirectedMateGraph": True,
    }
    success = all(item["passed"] for item in checks)
    result = {
        "status": "PASS_READ_ONLY_GRAPH_EXPORT_SEMANTIC_CONSTRAINTS_PENDING" if success else "FAIL_GRAPH_INVARIANT",
        "success": success,
        "graph": str(graph_path),
        "moduleInstanceCount": len(modules),
        "interModuleMateCount": int(pick(graph, "InterModuleMateCount", len(mates))),
        "mateBundleCount": len(bundles),
        "checks": checks,
        "semanticGaps": semantic_gaps,
        "nextGate": "Use the recorded operation face plus A600-A800 support/width endpoint geometry to anchor the staged A600→A800→A180→functional modules→A100 solver.",
    }
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"success": success, "status": result["status"], "output": str(output_path)}, ensure_ascii=False))
    return 0 if success else 2


if __name__ == "__main__":
    raise SystemExit(main())
