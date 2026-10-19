#!/usr/bin/env python3
"""Build and validate three real AD20 configuration states against broad-phase candidates."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from capture_assembly_entity_annotations import McpClient


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXE = ROOT / "vendor/solidworks-mcp/app/SolidWorksMcpApp/bin/Release/net8.0-windows/win-x64/SolidWorksMcpApp.exe"
DEFAULT_POSES = ROOT / "demo/semantic_ports/project03_live_adapter_full_jobs/project03-job-acc1cd320f35/collision-gates/step-07-ab00/attempt2-poses.json"
DEFAULT_AD00_GRAPH = ROOT / "demo/layout_previews/project03_ad00_internal_mate_graph.json"
DEFAULT_AD10_GRAPH = ROOT / "demo/layout_previews/project03_ad10_internal_mate_graph.json"
DEFAULT_OUTPUT = ROOT / "demo/semantic_ports/project03_ad00_dynamic_configuration_closure_v1"

STATE_CONFIGURATIONS = {
    "both-0deg": ("0度", "0度"),
    "left-25deg": ("25度", "0度"),
    "right-25deg": ("0度", "25度"),
}
CANDIDATE_TOKENS = ("AA00", "AE00", "AB00", "AI00")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path, default=DEFAULT_EXE)
    parser.add_argument("--poses", type=Path, default=DEFAULT_POSES)
    parser.add_argument("--ad00-graph", type=Path, default=DEFAULT_AD00_GRAPH)
    parser.add_argument("--ad10-graph", type=Path, default=DEFAULT_AD10_GRAPH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--timeout", type=float, default=1800.0)
    return parser.parse_args()


def pick(value: dict[str, Any], name: str, default: Any = None) -> Any:
    return value.get(name, value.get(name[0].lower() + name[1:], default))


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def modules(graph: dict[str, Any]) -> list[dict[str, Any]]:
    return list(pick(graph, "Modules", []) or [])


def aabb_overlap(first: list[float], second: list[float], tolerance: float = 1e-9) -> bool:
    return all(
        min(first[axis + 3], second[axis + 3]) - max(first[axis], second[axis]) > tolerance
        for axis in range(3)
    )


def record_call(
    timings: list[dict[str, Any]],
    name: str,
    action: Callable[[], Any],
    *,
    on_update: Callable[[], None] | None = None,
) -> Any:
    started = time.perf_counter()
    try:
        result = action()
    except BaseException as exc:
        timings.append({"operation": name, "durationSeconds": round(time.perf_counter() - started, 6), "success": False, "error": str(exc)})
        if on_update is not None:
            on_update()
        raise
    timings.append({"operation": name, "durationSeconds": round(time.perf_counter() - started, 6), "success": True})
    if on_update is not None:
        on_update()
    return result


def find_unique(rows: list[dict[str, Any]], token: str) -> dict[str, Any]:
    matches = [row for row in rows if token.casefold() in str(pick(row, "Name", "")).casefold()]
    if len(matches) != 1:
        raise RuntimeError(f"Token {token!r} resolved to {len(matches)} rows.")
    return matches[0]


def write_progress(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    exe = args.exe.resolve()
    pose_path = args.poses.resolve()
    ad00_graph_path = args.ad00_graph.resolve()
    ad10_graph_path = args.ad10_graph.resolve()
    output_dir = args.output_dir.resolve()
    for required in (exe, pose_path, ad00_graph_path, ad10_graph_path):
        if not required.exists():
            raise FileNotFoundError(required)
    output_dir.mkdir(parents=True, exist_ok=True)

    pose_rows = list(load(pose_path).get("components") or [])
    ad00_rows = modules(load(ad00_graph_path))
    ad10_rows = modules(load(ad10_graph_path))
    ad10_instances = [row for row in ad00_rows if "AD10" in str(pick(row, "ModuleToken", ""))]
    if len(ad10_instances) != 2:
        raise RuntimeError(f"Expected two AD10 instances, found {len(ad10_instances)}.")
    ad10_instances.sort(key=lambda row: str(pick(row, "Name", "")))
    ad20_source = find_unique(
        [row for row in ad10_rows if str(pick(row, "Path", "")).lower().endswith(".sldasm")],
        "AD20",
    )
    candidates = {token: find_unique(pose_rows, token) for token in CANDIDATE_TOKENS}

    manifest_path = output_dir / "project03_ad00_dynamic_configuration_closure.json"
    payload: dict[str, Any] = {
        "schemaVersion": "project03-ad00-dynamic-configuration-closure-v1",
        "startedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": "RUNNING",
        "sourceEvidence": {
            "finalPoseCatalog": str(pose_path),
            "ad00InternalMateGraph": str(ad00_graph_path),
            "ad10InternalMateGraph": str(ad10_graph_path),
            "ad20Source": str(pick(ad20_source, "Path", "")),
        },
        "stateDefinitions": [
            {"state": name, "leftConfiguration": configs[0], "rightConfiguration": configs[1]}
            for name, configs in STATE_CONFIGURATIONS.items()
        ],
        "states": [],
        "timings": [],
        "problems": [],
        "blockers": [],
    }
    write_progress(manifest_path, payload)

    def run_call(timings: list[dict[str, Any]], name: str, action: Callable[[], Any]) -> Any:
        return record_call(
            timings,
            name,
            action,
            on_update=lambda: write_progress(manifest_path, payload),
        )

    with McpClient(exe, "Project03AD00ConfigurationStateClosure", args.timeout, "newline", direct_stdio=True) as client:
        run_call(payload["timings"], "connect", lambda: client.call_tool("solid_works_connect", {}))
        for state_name, (left_config, right_config) in STATE_CONFIGURATIONS.items():
            state_started = time.perf_counter()
            state_timings: list[dict[str, Any]] = []
            assembly_path = output_dir / f"{output_dir.name}_{state_name}.SLDASM"
            if assembly_path.exists():
                raise FileExistsError(f"Refusing to overwrite evidence assembly: {assembly_path}")
            state: dict[str, Any] = {
                "state": state_name,
                "assemblyPath": str(assembly_path),
                "leftConfiguration": left_config,
                "rightConfiguration": right_config,
                "timings": state_timings,
                "pairChecks": [],
                "status": "RUNNING",
            }
            payload["states"].append(state)
            write_progress(manifest_path, payload)
            try:
                run_call(state_timings, "new-assembly", lambda: client.call_tool("new_document", {"type": "Assembly"}))
                run_call(
                    state_timings,
                    "save-empty-context",
                    lambda: client.call_tool("save_document_as", {"outputPath": str(assembly_path), "saveAsCopy": False}),
                )

                insert_specs = [
                    ("AD20_LEFT", str(pick(ad20_source, "Path", "")), list(pick(ad10_instances[0], "SourceTransform", []))),
                    ("AD20_RIGHT", str(pick(ad20_source, "Path", "")), list(pick(ad10_instances[1], "SourceTransform", []))),
                ]
                insert_specs.extend(
                    (token, str(pick(row, "Path", "")), list(pick(row, "Transform", [])))
                    for token, row in candidates.items()
                )
                alias_to_name: dict[str, str] = {}
                for alias, source_path, transform in insert_specs:
                    run_call(
                        state_timings,
                        f"activate-before-insert-{alias}",
                        lambda: client.call_tool(
                            "activate_document_by_title", {"title": assembly_path.stem}
                        ),
                    )
                    poses_before_insert = client.call_tool("list_component_poses", {"topLevelOnly": True})
                    names_before_insert = {str(pick(row, "Name", "")) for row in poses_before_insert}
                    inserted = run_call(
                        state_timings,
                        f"insert-{alias}",
                        lambda source_path=source_path: client.call_tool(
                            "insert_component", {"filePath": source_path, "x": 0, "y": 0, "z": 0}
                        ),
                    )
                    run_call(
                        state_timings,
                        f"reactivate-after-insert-{alias}",
                        lambda: client.call_tool(
                            "activate_document_by_title", {"title": assembly_path.stem}
                        ),
                    )
                    poses_after_insert = run_call(
                        state_timings,
                        f"resolve-inserted-{alias}",
                        lambda: client.call_tool(
                            "list_component_poses", {"topLevelOnly": True}
                        ),
                    )
                    added = [row for row in poses_after_insert if str(pick(row, "Name", "")) not in names_before_insert]
                    if len(added) != 1:
                        raise RuntimeError(
                            f"Insertion of {alias} produced {len(added)} new top-level instances; "
                            f"suggestedName={pick(inserted, 'Name', '')!r}."
                        )
                    actual_name = str(pick(added[0], "Name", ""))
                    alias_to_name[alias] = actual_name
                    run_call(
                        state_timings,
                        f"transform-{alias}",
                        lambda actual_name=actual_name, transform=transform: client.call_tool(
                            "set_component_transform",
                            {"componentName": actual_name, "transform": transform, "rebuild": False},
                        ),
                    )

                state["componentAliases"] = alias_to_name

                run_call(
                    state_timings,
                    "activate-before-configuration",
                    lambda: client.call_tool(
                        "activate_document_by_title", {"title": assembly_path.stem}
                    ),
                )

                state["configurationResults"] = [
                    run_call(
                        state_timings,
                        "configure-left",
                        lambda: client.call_tool(
                            "set_component_referenced_configuration",
                            {"componentName": alias_to_name["AD20_LEFT"], "configurationName": left_config, "rebuild": False},
                        ),
                    ),
                    run_call(
                        state_timings,
                        "configure-right",
                        lambda: client.call_tool(
                            "set_component_referenced_configuration",
                            {"componentName": alias_to_name["AD20_RIGHT"], "configurationName": right_config, "rebuild": True},
                        ),
                    ),
                ]
                state["save"] = run_call(
                    state_timings,
                    "save-state",
                    lambda: client.call_tool("save_document", {"path": str(assembly_path)}),
                )
                state["poses"] = run_call(
                    state_timings,
                    "capture-poses",
                    lambda: client.call_tool("list_component_poses", {"topLevelOnly": True}),
                )
                poses_by_name = {str(pick(row, "Name", "")): row for row in state["poses"]}
                for dynamic_alias in ("AD20_LEFT", "AD20_RIGHT"):
                    dynamic_pose = find_unique(list(poses_by_name.values()), alias_to_name[dynamic_alias])
                    dynamic_box = list(pick(dynamic_pose, "BoundingBoxWorld", []) or [])
                    for candidate_alias in CANDIDATE_TOKENS:
                        candidate_pose = find_unique(list(poses_by_name.values()), alias_to_name[candidate_alias])
                        candidate_box = list(pick(candidate_pose, "BoundingBoxWorld", []) or [])
                        pair = [str(pick(dynamic_pose, "HierarchyPath", "")), str(pick(candidate_pose, "HierarchyPath", ""))]
                        pair_result: dict[str, Any] = {
                            "dynamicComponent": dynamic_alias,
                            "candidateComponent": candidate_alias,
                            "hierarchyPaths": pair,
                            "broadPhaseOverlap": bool(len(dynamic_box) >= 6 and len(candidate_box) >= 6 and aabb_overlap(dynamic_box, candidate_box)),
                        }
                        if pair_result["broadPhaseOverlap"]:
                            pair_result["exactResult"] = run_call(
                                state_timings,
                                f"brep-{dynamic_alias}-{candidate_alias}",
                                lambda pair=pair: client.call_tool(
                                    "check_interference_by_leaf_bodies",
                                    {"hierarchyPaths": pair, "treatCoincidenceAsInterference": False},
                                ),
                            )
                            pair_result["gate"] = "PASSED_EXACT" if not bool(pick(pair_result["exactResult"], "HasInterference", True)) else "FAILED_INTERFERENCE"
                        else:
                            pair_result["gate"] = "PASSED_AABB_SEPARATED"
                        state["pairChecks"].append(pair_result)
                        write_progress(manifest_path, payload)

                state["status"] = (
                    "PASSED_STATE_COLLISION_GATE"
                    if all(item["gate"].startswith("PASSED") for item in state["pairChecks"])
                    else "FAILED_STATE_COLLISION_GATE"
                )
                state["durationSeconds"] = round(time.perf_counter() - state_started, 6)
                run_call(
                    state_timings,
                    "close-state",
                    lambda: client.call_tool_text("close_document", {"path": str(assembly_path)}),
                )
            except BaseException as exc:
                state["status"] = "ERROR"
                state["error"] = str(exc)
                state["durationSeconds"] = round(time.perf_counter() - state_started, 6)
                payload["problems"].append(f"{state_name}: {exc}")
                write_progress(manifest_path, payload)
                raise
            write_progress(manifest_path, payload)

    payload["completedAtUtc"] = datetime.now(timezone.utc).isoformat()
    payload["status"] = (
        "PASSED_THREE_REAL_CONFIGURATION_STATES_STATIC_COLLISION_GATE"
        if all(state["status"] == "PASSED_STATE_COLLISION_GATE" for state in payload["states"])
        else "FAILED_DYNAMIC_CONFIGURATION_COLLISION_GATE"
    )
    payload["productionReady"] = payload["status"].startswith("PASSED")
    payload["limitations"] = [
        "The three states validate two AD20 configuration placements against the four conservative candidate modules; they do not reconstruct continuous motion between 0度 and 25度.",
        "AD10 placement transforms are recovered from the source AD00 mate graph; vendor axis limits remain unconfirmed.",
    ]
    write_progress(manifest_path, payload)
    print(manifest_path)
    return 0 if payload["productionReady"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
