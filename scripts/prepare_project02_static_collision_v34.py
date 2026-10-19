#!/usr/bin/env python3
"""Prepare the v34 staged static-collision execution plan for Project 02."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "apps" / "demo-backend" / "src"
sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.static_collision_closure import (  # noqa: E402
    build_execution_plan,
    component_code,
    component_files_older_than_evidence,
    evidence_is_complete_and_clear,
    relative_pose_matches,
)


DEFAULT_PREVIEW = ROOT / "demo/layout_previews/project02_preview.json"
DEFAULT_CURRENT_LAYOUT = ROOT / "demo/layout_previews/project02_solution.json"
DEFAULT_V33_LAYOUT = ROOT / "demo/layout_previews/project02_selected_solution_replay_v33.json"
DEFAULT_V33_EVIDENCE = ROOT / (
    "demo/interference_8modules_clean_solved_v33/priority_a300_a700/"
    "FL9A24D062A000_8modules_clean_solved_v33_leaf_details_A300_A700.json"
)
DEFAULT_LOCKFIX_LAYOUT = ROOT / (
    "demo/layout_previews/project02_v34_coordinated_transport_lock_fix/"
    "candidate_02_solution.json"
)
DEFAULT_REUSABLE_EVIDENCE_SPECS = (
    (
        "A300",
        "A700",
        DEFAULT_V33_EVIDENCE,
        DEFAULT_V33_LAYOUT,
    ),
    (
        "A100",
        "A200",
        ROOT / (
            "demo/interference_8modules_clean_solved_v33/v34_priority_p0/"
            "FL9A24D062A000_8modules_clean_solved_v34_coordinated_lockfix_"
            "candidate02_leaf_details_A100_A200.json"
        ),
        DEFAULT_LOCKFIX_LAYOUT,
    ),
    (
        "A200",
        "A700",
        ROOT / (
            "demo/interference_8modules_clean_solved_v33/v34_priority_p1/"
            "FL9A24D062A000_8modules_clean_solved_v34_coordinated_lockfix_"
            "candidate02_leaf_details_A200_A700.json"
        ),
        DEFAULT_LOCKFIX_LAYOUT,
    ),
    (
        "A200",
        "A800",
        ROOT / (
            "demo/interference_8modules_clean_solved_v33/v34_priority_p1/"
            "FL9A24D062A000_8modules_clean_solved_v34_coordinated_lockfix_"
            "candidate02_leaf_details_A200_A800.json"
        ),
        DEFAULT_LOCKFIX_LAYOUT,
    ),
    (
        "A100",
        "A180",
        ROOT / (
            "demo/interference_8modules_clean_solved_v33/v34_priority_p2/"
            "FL9A24D062A000_8modules_clean_solved_v34_coordinated_lockfix_"
            "candidate02_leaf_details_A100_A180.json"
        ),
        DEFAULT_LOCKFIX_LAYOUT,
    ),
    (
        "A180",
        "A800",
        ROOT / (
            "demo/interference_8modules_clean_solved_v33/v34_priority_p2/"
            "FL9A24D062A000_8modules_clean_solved_v34_coordinated_lockfix_"
            "candidate02_leaf_details_A180_A800.json"
        ),
        DEFAULT_LOCKFIX_LAYOUT,
    ),
)
DEFAULT_PROJECT_CONFIG = ROOT / "demo/FL9A24D062A000_8components_real_project_config.json"
DEFAULT_V33_REPLAY_RESULT = ROOT / "demo/layout_previews/project02_8modules_clean_solved_v33_result.json"
DEFAULT_OUTPUT = ROOT / "demo/layout_previews/project02_v34_static_collision_execution_plan.json"


def resolved(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_evidence_spec(value: str) -> tuple[str, str, Path, Path]:
    parts = value.split(",", 3)
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(
            "Evidence spec must use CODE1,CODE2,EVIDENCE_JSON,LAYOUT_JSON syntax."
        )
    first_code, second_code, evidence, layout = parts
    return first_code.strip(), second_code.strip(), resolved(evidence), resolved(layout)


def solidworks_process_count() -> int:
    if sys.platform != "win32":
        return 0
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            "@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count",
        ],
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        return -1
    try:
        return int(completed.stdout.strip())
    except ValueError:
        return -1


def saved_world_aabbs(result: dict[str, Any]) -> dict[str, list[float]]:
    for step in result.get("steps") or []:
        if step.get("tool") != "list_component_poses":
            continue
        payload = step.get("payload") or []
        return {
            str(item["Name"]): [float(value) for value in item["BoundingBoxWorld"]]
            for item in payload
            if item.get("Name") and len(item.get("BoundingBoxWorld") or []) == 6
        }
    return {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", default=str(DEFAULT_PREVIEW))
    parser.add_argument("--current-layout", default=str(DEFAULT_CURRENT_LAYOUT))
    parser.add_argument(
        "--world-aabb-result",
        default=str(DEFAULT_V33_REPLAY_RESULT),
        help=(
            "Replay result whose list_component_poses payload supplies world AABBs. "
            "Pass the candidate Replay result when auditing a repaired layout."
        ),
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument(
        "--evidence-spec",
        action="append",
        type=parse_evidence_spec,
        default=[],
        help=(
            "Additional durable exact-clear evidence as "
            "CODE1,CODE2,EVIDENCE_JSON,LAYOUT_JSON. The pair is reused only "
            "when its relative pose and source geometry are unchanged."
        ),
    )
    args = parser.parse_args()

    preview_path = resolved(args.preview)
    current_layout_path = resolved(args.current_layout)
    world_aabb_result_path = resolved(args.world_aabb_result)
    output_path = resolved(args.output)
    preview = read_json(preview_path)
    current_layout = read_json(current_layout_path)
    world_aabb_result = read_json(world_aabb_result_path)
    config = read_json(DEFAULT_PROJECT_CONFIG)
    component_paths = {
        item["componentName"]: Path(item["filePath"])
        for item in config.get("components") or []
    }
    component_name_by_code = {
        component_code(name): name for name in component_paths
    }
    reusable_evidence: list[dict[str, Any]] = []
    evidence_specs = (*DEFAULT_REUSABLE_EVIDENCE_SPECS, *args.evidence_spec)
    for first_code, second_code, evidence_path, evidence_layout_path in evidence_specs:
        evidence = read_json(evidence_path) if evidence_path.exists() else {}
        evidence_layout = (
            read_json(evidence_layout_path) if evidence_layout_path.exists() else {}
        )
        try:
            pose_match = relative_pose_matches(
                current_layout,
                evidence_layout,
                first_code,
                second_code,
            )
        except (KeyError, TypeError, ValueError):
            pose_match = False
        evidence_component_paths = [
            component_paths[component_name_by_code[code]]
            for code in (first_code, second_code)
            if code in component_name_by_code
        ]
        geometry_unchanged = component_files_older_than_evidence(
            evidence_path,
            evidence_component_paths,
        )
        complete_and_clear = evidence_is_complete_and_clear(evidence)
        reusable_evidence.append(
            {
                "codes": [first_code, second_code],
                "evidencePath": str(evidence_path),
                "sourceLayoutPath": str(evidence_layout_path),
                "exactCheckCompleteAndClear": complete_and_clear,
                "relativePoseMatches": pose_match,
                "sourceGeometryUnchanged": geometry_unchanged,
                "reusable": bool(
                    complete_and_clear and pose_match and geometry_unchanged
                ),
            }
        )
    plan = build_execution_plan(
        preview=preview,
        current_layout=current_layout,
        reusable_evidence=reusable_evidence,
        world_aabbs_by_component=saved_world_aabbs(world_aabb_result),
    )
    process_count = solidworks_process_count()
    plan["inputs"] = {
        "previewPath": str(preview_path),
        "currentLayoutPath": str(current_layout_path),
        "v33EvidenceLayoutPath": str(DEFAULT_V33_LAYOUT),
        "savedWorldAabbPath": str(world_aabb_result_path),
        "projectConfigPath": str(DEFAULT_PROJECT_CONFIG),
    }
    plan["evidenceAudit"] = reusable_evidence
    plan["cadPreflight"] = {
        "solidworksProcessCount": process_count,
        "ready": process_count in {0, 1},
        "required": "Use one clean SolidWorks session before running the priority B-Rep gate.",
        "reason": (
            "Clean process state."
            if process_count in {0, 1}
            else "Multiple SolidWorks processes make COM/MCP document binding ambiguous."
        ),
    }
    if not plan["cadPreflight"]["ready"]:
        plan["status"] = "PRIORITY_BREP_READY_CAD_SESSION_CLEANUP_REQUIRED"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": plan["status"],
                "strictAabb": plan["strictAabb"],
                "conditionalBrep": {
                    "policyPairCount": plan["conditionalBrep"]["policyPairCount"],
                    "worldAabbClearPairCount": plan["conditionalBrep"]["worldAabbClearPairCount"],
                    "reusedClearPairCount": plan["conditionalBrep"]["reusedClearPairCount"],
                    "pendingPairCount": plan["conditionalBrep"]["pendingPairCount"],
                    "batches": [
                        {
                            "priority": batch["priority"],
                            "codes": [item["codes"] for item in batch["pairs"]],
                        }
                        for batch in plan["conditionalBrep"]["batches"]
                    ],
                },
                "cadPreflight": plan["cadPreflight"],
                "output": str(output_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
