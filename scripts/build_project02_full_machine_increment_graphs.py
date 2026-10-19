#!/usr/bin/env python3
"""Build target-specific effective mate graphs for A200 and both T401 instances.

The source 27-mate graph already contains stable face selectors.  This script
does not rescan the whole assembly.  It extracts only the modules and driving
mates required by each cumulative insertion step and records the explicit
Project02 source-pose anchor needed to close residual slot/distance degrees of
freedom.  The anchors are intentionally labelled case calibration, not vendor
installation data.
"""

from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = (
    ROOT
    / "demo/mate_reconstruction_pipeline/project02_full27_source_pose_v1.effective.json"
)
DEFAULT_OUTPUT = ROOT / "demo/semantic_ports/project02_full_machine_increment_v1"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def module_by_hierarchy(graph: dict[str, Any], hierarchy: str) -> dict[str, Any]:
    matches = [
        item for item in graph["Modules"] if item.get("HierarchyPath") == hierarchy
    ]
    if len(matches) != 1:
        raise ValueError(f"Expected one module '{hierarchy}', found {len(matches)}")
    return matches[0]


def mate_endpoint_hierarchies(mate: dict[str, Any]) -> set[str]:
    return {
        str(item.get("ModuleHierarchyPath") or "")
        for item in mate.get("Endpoints") or []
        if item.get("ModuleHierarchyPath")
    }


def build_increment_graph(
    source: dict[str, Any],
    *,
    target_hierarchy: str,
    context_hierarchies: list[str],
    base_hierarchy: str,
    step_id: str,
    engineering_ports: list[dict[str, Any]],
) -> dict[str, Any]:
    selected_hierarchies = {target_hierarchy, *context_hierarchies}
    modules = [
        copy.deepcopy(module_by_hierarchy(source, hierarchy))
        for hierarchy in [*context_hierarchies, target_hierarchy]
    ]
    mates = []
    for mate in source.get("Mates") or []:
        endpoint_hierarchies = mate_endpoint_hierarchies(mate)
        if (
            target_hierarchy in endpoint_hierarchies
            and endpoint_hierarchies
            and endpoint_hierarchies.issubset(selected_hierarchies)
        ):
            mates.append(copy.deepcopy(mate))
    if not mates:
        raise ValueError(f"No driving mates found for {target_hierarchy}")
    if any(target_hierarchy not in mate_endpoint_hierarchies(item) for item in mates):
        raise AssertionError("Every extracted driving mate must reference the target")

    target = module_by_hierarchy(source, target_hierarchy)
    base = module_by_hierarchy(source, base_hierarchy)
    graph = {
        "SchemaVersion": "editable-module-mate-graph/v1",
        "SourceAssemblyPath": source.get("SourceAssemblyPath"),
        "RequestedModuleTokens": [item.get("ModuleToken") for item in modules],
        "ModuleCount": len(modules),
        "InterModuleMateCount": len(mates),
        "MateBundleCount": 0,
        "IgnoredIntraModuleMateCount": 0,
        "IgnoredUnresolvedMateCount": 0,
        "Modules": modules,
        "Mates": mates,
        "MateBundles": [],
        "SavedJsonPath": None,
        "Diagnostics": [
            "Extracted from the recovered 27/27 Project02 mate graph; no full-tree face rescan.",
            "The target starts from its calibrated Project02 source pose because the available mate bundle leaves residual degrees of freedom.",
        ],
        "SourceGraphProvenance": {
            "sourceSchemaVersion": source.get("SchemaVersion"),
            "sourceAssemblyPath": source.get("SourceAssemblyPath"),
            "extractionMode": "target-specific-driving-mate-subgraph",
        },
        "EditPolicy": {
            "baseModuleToken": base.get("ModuleToken"),
            "initialPlacementMode": "project02_source_pose_case_anchor",
            "sourceGraphImmutable": True,
            "fixedModuleTokens": [base_hierarchy],
            "caseAnchoredModuleTokens": [target_hierarchy],
            "targetLeafPoseAnchors": [],
        },
        "SemanticAssemblyPlanAudit": {
            "stepId": step_id,
            "targetHierarchyPath": target_hierarchy,
            "targetModuleToken": target.get("ModuleToken"),
            "baseHierarchyPath": base_hierarchy,
            "drivingMateNames": [item.get("MateName") for item in mates],
            "caseAnchorEvidence": {
                "scope": "project02_static_demo_only",
                "source": "recovered prototype top-level SourceTransform",
                "reason": (
                    "The recovered slot/distance bundle does not uniquely locate all six rigid-body degrees of freedom. "
                    "The source pose selects the intended Project02 branch until vendor datums are available."
                ),
                "notVendorDatum": True,
            },
            "engineeringPorts": copy.deepcopy(engineering_ports),
        },
    }
    return graph


def build_all(source: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        "A200": build_increment_graph(
            source,
            target_hierarchy="FL9A24D062A200.001-1",
            context_hierarchies=["FL9A24D062A600.001-1"],
            base_hierarchy="FL9A24D062A600.001-1",
            step_id="step07-add-a200",
            engineering_ports=[
                {
                    "portId": "A200.ccd_optical_work_envelope",
                    "category": "optical",
                    "status": "prototype-baseline-coarse",
                    "checks": ["A800工作位1/2覆盖", "结构通道", "工作距离", "维护空间"],
                }
            ],
        ),
        "T401-1": build_increment_graph(
            source,
            target_hierarchy="T401AA-07388-0-1",
            context_hierarchies=["FL9A24D062A600.001-1"],
            base_hierarchy="FL9A24D062A600.001-1",
            step_id="step08-add-t401-1",
            engineering_ports=[
                {
                    "portId": "T401-1.glue_supply_mount",
                    "category": "fluid-supply",
                    "status": "prototype-baseline-coarse",
                    "checks": ["箱体安装面", "维护空间", "运动区隔离"],
                }
            ],
        ),
        "T401-2": build_increment_graph(
            source,
            target_hierarchy="T401AA-07388-0-2",
            context_hierarchies=["FL9A24D062A200.001-1"],
            base_hierarchy="FL9A24D062A200.001-1",
            step_id="step09-add-t401-2",
            engineering_ports=[
                {
                    "portId": "T401-2.glue_supply_spacing",
                    "category": "fluid-supply",
                    "status": "prototype-baseline-coarse",
                    "checks": ["与A200间距59 mm", "软管接口方向", "维护空间"],
                }
            ],
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    source_path = args.source.resolve()
    output_root = args.output.resolve()
    source = read_json(source_path)
    graphs = build_all(source)
    outputs: dict[str, str] = {}
    for name, graph in graphs.items():
        path = output_root / f"{name.lower()}_increment_effective.json"
        graph["SavedJsonPath"] = str(path)
        write_json(path, graph)
        outputs[name] = str(path)
    manifest = {
        "schemaVersion": "project02-full-machine-increment-plan/v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sourceGraphPath": str(source_path),
        "sequence": ["A200", "T401-1", "T401-2"],
        "graphs": outputs,
        "status": "OFFLINE_INCREMENT_GRAPHS_READY",
        "knownLimitations": [
            "All three targets use explicit Project02 source-pose branch anchors.",
            "A200 optical coverage and T401 hose/maintenance semantics require post-insert validation.",
            "CAD save/reopen and 45-pair interference closure have not yet been claimed by this builder.",
        ],
    }
    write_json(output_root / "full_machine_increment_manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
