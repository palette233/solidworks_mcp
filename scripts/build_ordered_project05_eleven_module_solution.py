#!/usr/bin/env python3
"""Build Project 05 as ordered, independently saved cumulative CAD checkpoints."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_direct_project02_nine_module_solution import (  # noqa: E402
    McpClient,
    audit_poses,
    audit_top_level_components,
    call_and_record,
    call_text_and_record,
    insertion_components,
    load_direct_manifest,
    movement_deltas,
    resolved,
    utc_now_iso,
    write_json,
)


DEFAULT_LAYOUT = ROOT / "demo/layout_previews/project05_selected_solution_replay.json"
DEFAULT_POSES = ROOT / "demo/layout_previews/project05_selected_solution_direct_poses.json"
DEFAULT_OUTPUT_ROOT = ROOT / "demo/semantic_ports/project05_ordered_direct_rank1_v1"
DEFAULT_MCP = ROOT / "artifacts/solidworks-mcp-current/SolidWorksMcpApp.exe"

STAGES = (
    ("step00", "A000", ("A000", "E000")),
    ("step01", "D000", ("D000",)),
    ("step02", "K000", ("K000",)),
    ("step03", "F000", ("F000",)),
    ("step04", "M000", ("M000",)),
    ("step05", "G000", ("G000",)),
    ("step06", "N000", ("N000",)),
    ("step07", "P000", ("P000",)),
    ("step08", "B000", ("B000", "Z000")),
)


def build_plan(
    layout_path: Path,
    pose_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    manifest = load_direct_manifest(
        layout_path,
        pose_path,
        expected_module_count=11,
        fixed_environment_code="A000",
    )
    by_code = {row["componentCode"]: row for row in manifest}
    expected_codes = {code for _, _, codes in STAGES for code in codes}
    if set(by_code) != expected_codes:
        raise ValueError(
            f"Project 05 ordered plan coverage mismatch; missing={sorted(expected_codes-set(by_code))}, "
            f"extra={sorted(set(by_code)-expected_codes)}."
        )

    stages = []
    installed: list[str] = []
    previous_path: str | None = None
    for stage_id, token, codes in STAGES:
        installed.extend(codes)
        target = (output_root / f"{stage_id}_{token}_cumulative.SLDASM").resolve()
        if target.exists():
            raise FileExistsError(f"Checkpoint already exists; refusing to overwrite: {target}")
        rows = [by_code[code] for code in codes]
        stages.append(
            {
                "stageId": stage_id,
                "moduleToken": token,
                "addedCodes": list(codes),
                "addedComponents": [row["componentName"] for row in rows],
                "sourceModulePaths": [row["filePath"] for row in rows],
                "installedCodesAfterStage": list(installed),
                "expectedTopLevelCountAfterStage": len(installed),
                "sourceCheckpointPath": previous_path,
                "targetCheckpointPath": str(target),
                "poseAuditRequired": True,
                "saveReopenRequired": True,
                "collisionGate": (
                    "base-whitelist-and-pose"
                    if stage_id == "step00"
                    else "strict-leaf-aabb-before-conditional-brep"
                ),
            }
        )
        previous_path = str(target)
    return {
        "schemaVersion": "project05-ordered-direct-plan/v1",
        "projectId": "project05",
        "selectedSolutionRank": 1,
        "prototypeAssemblyCopied": False,
        "layoutPath": str(layout_path.resolve()),
        "posePath": str(pose_path.resolve()),
        "outputRoot": str(output_root.resolve()),
        "moduleCount": len(manifest),
        "stageCount": len(stages),
        "stages": stages,
        "manifest": manifest,
        "productionReleased": False,
    }


def _rows_for_codes(manifest: list[dict[str, Any]], codes: list[str]) -> list[dict[str, Any]]:
    wanted = set(codes)
    return [row for row in manifest if row["componentCode"] in wanted]


def _rows_with_runtime_component_names(
    actual_components: list[dict[str, Any]],
    expected_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Resolve SolidWorks-assigned instance suffixes from the authoritative file path."""
    by_path: dict[str, list[str]] = {}
    for actual in actual_components:
        path = str(actual.get("Path", actual.get("path", ""))).casefold()
        name = str(actual.get("Name", actual.get("name", "")))
        if path and name:
            by_path.setdefault(path, []).append(name)
    resolved_rows = []
    aliases = []
    for expected in expected_rows:
        matches = by_path.get(str(expected["filePath"]).casefold(), [])
        if len(matches) != 1:
            raise RuntimeError(
                f"Expected exactly one runtime instance for {expected['componentCode']} at "
                f"{expected['filePath']}, found {matches}."
            )
        runtime_name = matches[0]
        row = dict(expected)
        row["componentName"] = runtime_name
        resolved_rows.append(row)
        aliases.append(
            {
                "componentCode": str(expected["componentCode"]),
                "plannedComponentName": str(expected["componentName"]),
                "runtimeComponentName": runtime_name,
                "filePath": str(expected["filePath"]),
            }
        )
    return resolved_rows, aliases


def _apply_target_poses(
    client: McpClient,
    steps: list[dict[str, Any]],
    installed: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    for row in installed:
        if row["fixedEnvironment"]:
            continue
        call_and_record(
            client,
            steps,
            "set_component_orientation",
            {
                "componentName": row["componentName"],
                "xAxis": row["xAxis"],
                "yAxis": row["yAxis"],
                "zAxis": row["zAxis"],
                "rebuild": False,
            },
        )
    current = call_and_record(client, steps, "list_component_poses", {"topLevelOnly": True})
    moves = movement_deltas(current, installed)
    for move in moves:
        if not move["requiresMove"]:
            continue
        call_and_record(
            client,
            steps,
            "move_component",
            {
                "componentName": move["componentName"],
                "deltaX": move["delta"][0],
                "deltaY": move["delta"][1],
                "deltaZ": move["delta"][2],
            },
        )
    return moves


def _document_path(row: dict[str, Any]) -> str:
    return str(
        row.get("Path")
        or row.get("path")
        or row.get("FullPath")
        or row.get("fullPath")
        or ""
    )


def _target_is_open(documents: Any, target: Path) -> bool:
    normalized = str(target.resolve()).casefold()
    return any(_document_path(row).casefold() == normalized for row in (documents or []))


def _close_and_verify(
    client: McpClient,
    steps: list[dict[str, Any]],
    target: Path,
) -> None:
    candidates = (str(target), target.name, target.stem)
    documents = call_and_record(client, steps, "list_documents")
    for candidate in candidates:
        if not _target_is_open(documents, target):
            return
        call_text_and_record(client, steps, "close_document", {"path": candidate})
        documents = call_and_record(client, steps, "list_documents")
    if _target_is_open(documents, target):
        raise RuntimeError(f"SolidWorks document remained open after verified close: {target}")


def _union_boxes(boxes: list[list[float]]) -> list[float]:
    if not boxes:
        raise ValueError("Cannot build a leaf-body union from an empty capture.")
    return [
        min(box[index] for box in boxes) if index < 3 else max(box[index] for box in boxes)
        for index in range(6)
    ]


def _capture_leaf_union_and_record(
    client: McpClient,
    steps: list[dict[str, Any]],
    component_name: str,
) -> dict[str, Any]:
    """Capture exact leaf-body occupancy without storing thousands of bodies in the stage log."""
    started_at = utc_now_iso()
    started = time.perf_counter()
    try:
        payload = client.call_tool(
            "capture_leaf_body_envelopes",
            {"hierarchyPath": component_name},
        )
        bodies = payload.get("Bodies", payload.get("bodies", [])) if isinstance(payload, dict) else []
        boxes = []
        for body in bodies or []:
            raw = body.get("BoundingBoxWorld", body.get("boundingBoxWorld", []))
            if len(raw) == 6:
                boxes.append([float(value) for value in raw])
        coverage_complete = bool(
            payload.get("CoverageComplete", payload.get("coverageComplete", False))
        ) if isinstance(payload, dict) else False
        summary = {
            "componentName": component_name,
            "coverageComplete": coverage_complete,
            "leafComponentCount": int(
                payload.get("LeafComponentCount", payload.get("leafComponentCount", 0))
            ) if isinstance(payload, dict) else 0,
            "bodyCount": len(boxes),
            "boundingBoxWorld": _union_boxes(boxes),
        }
        failed = not coverage_complete or not boxes
        steps.append(
            {
                "tool": "capture_leaf_body_envelopes",
                "businessFailed": failed,
                "arguments": {"hierarchyPath": component_name},
                "timing": {
                    "startedAtUtc": started_at,
                    "finishedAtUtc": utc_now_iso(),
                    "durationSeconds": round(time.perf_counter() - started, 6),
                },
                "payloadSummary": summary,
            }
        )
        if failed:
            raise RuntimeError(f"Incomplete leaf-body capture for {component_name}.")
        return summary
    except Exception as exc:
        if not steps or steps[-1].get("tool") != "capture_leaf_body_envelopes":
            steps.append(
                {
                    "tool": "capture_leaf_body_envelopes",
                    "businessFailed": True,
                    "invocationFailed": True,
                    "arguments": {"hierarchyPath": component_name},
                    "timing": {
                        "startedAtUtc": started_at,
                        "finishedAtUtc": utc_now_iso(),
                        "durationSeconds": round(time.perf_counter() - started, 6),
                    },
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
        raise


def _audit_leaf_body_extents(
    captures: list[dict[str, Any]],
    expected_manifest: list[dict[str, Any]],
    *,
    extent_tolerance_meters: float = 0.005,
) -> dict[str, Any]:
    actual_by_name = {item["componentName"]: item for item in captures}
    rows = []
    for expected in expected_manifest:
        name = expected["componentName"]
        actual = actual_by_name.get(name, {})
        actual_box = actual.get("boundingBoxWorld") or []
        expected_box = expected.get("boundingBoxWorld") or []
        if len(actual_box) != 6 or len(expected_box) != 6:
            rows.append({"componentName": name, "success": False, "reason": "missingLeafBodyBoundingBox"})
            continue
        actual_extents = [float(actual_box[index + 3]) - float(actual_box[index]) for index in range(3)]
        expected_extents = [float(expected_box[index + 3]) - float(expected_box[index]) for index in range(3)]
        errors = [abs(actual_extents[index] - expected_extents[index]) for index in range(3)]
        rows.append(
            {
                "componentName": name,
                "success": max(errors) <= extent_tolerance_meters,
                "expectedExtentsMeters": expected_extents,
                "actualExtentsMeters": actual_extents,
                "extentErrorsMeters": errors,
                "maximumExtentErrorMeters": max(errors),
                "bodyCount": actual.get("bodyCount"),
                "coverageComplete": actual.get("coverageComplete"),
                "fixedEnvironment": expected["fixedEnvironment"],
            }
        )
    return {
        "success": len(rows) == len(expected_manifest) and all(row["success"] for row in rows),
        "method": "complete-leaf-body-union-v1",
        "extentToleranceMeters": extent_tolerance_meters,
        "mismatchComponents": [row["componentName"] for row in rows if not row["success"]],
        "components": rows,
    }


def execute_plan(
    plan: dict[str, Any],
    *,
    mcp: Path,
    request_timeout: float,
    start_stage_index: int = 0,
    end_stage_index_exclusive: int | None = None,
    resume_checkpoint: Path | None = None,
) -> dict[str, Any]:
    manifest = list(plan["manifest"])
    completed_stages: list[dict[str, Any]] = []
    started = time.perf_counter()
    with McpClient(
        mcp,
        client_name="CodexProject05OrderedDirectBuilder",
        request_timeout=request_timeout,
        framing="newline",
        direct_stdio=True,
    ) as client:
        connection_steps: list[dict[str, Any]] = []
        call_and_record(client, connection_steps, "solid_works_connect")
        stages_to_run = list(plan["stages"])[
            start_stage_index:end_stage_index_exclusive
        ]
        for relative_index, stage in enumerate(stages_to_run):
            index = start_stage_index + relative_index
            stage_started = time.perf_counter()
            steps: list[dict[str, Any]] = []
            target = Path(stage["targetCheckpointPath"])
            target.parent.mkdir(parents=True, exist_ok=True)
            added = _rows_for_codes(manifest, stage["addedCodes"])
            installed = _rows_for_codes(manifest, stage["installedCodesAfterStage"])
            if index == 0:
                call_and_record(
                    client,
                    steps,
                    "initialize_common_base_assembly",
                    {
                        "components": insertion_components(added),
                        "outputAssemblyPath": str(target),
                        "screenshotPath": None,
                        "includeScreenshotBase64Data": False,
                    },
                )
            else:
                previous = (
                    resume_checkpoint
                    if relative_index == 0 and resume_checkpoint is not None
                    else Path(str(stage["sourceCheckpointPath"]))
                )
                call_and_record(client, steps, "open_document", {"path": str(previous)})
                call_and_record(
                    client,
                    steps,
                    "save_document_as",
                    {
                        "outputPath": str(target),
                        "sourcePath": str(previous),
                        "saveAsCopy": False,
                    },
                )
                # SaveAs makes the target the active document.  Calling the
                # batch append helper here would try OpenDoc6 on that same path
                # and SolidWorks rejects it as swFileWithSameTitleAlreadyOpen.
                # Insert directly into the already-active cumulative checkpoint.
                for component in insertion_components(added):
                    call_and_record(
                        client,
                        steps,
                        "insert_component",
                        {
                            "filePath": component["filePath"],
                            "x": component["x"],
                            "y": component["y"],
                            "z": component["z"],
                        },
                    )
            runtime_components = call_and_record(client, steps, "list_components")
            installed_runtime, runtime_aliases = _rows_with_runtime_component_names(
                runtime_components, installed
            )
            added_codes = set(stage["addedCodes"])
            added_runtime = [
                row for row in installed_runtime if row["componentCode"] in added_codes
            ]
            moves = _apply_target_poses(client, steps, installed_runtime)
            call_and_record(client, steps, "force_rebuild_active_document", {"topOnly": False})
            call_and_record(client, steps, "save_document", {"path": str(target)})
            _close_and_verify(client, steps, target)
            call_and_record(client, steps, "open_document", {"path": str(target)})
            actual_components = call_and_record(client, steps, "list_components")
            actual_poses = call_and_record(
                client, steps, "list_component_poses", {"topLevelOnly": True}
            )
            # A resumed chain must establish a complete leaf-body baseline at
            # its first executed stage.  Intermediate stages only add one
            # module, so recapturing every unchanged subtree is redundant;
            # the final stage performs a complete 11-module revalidation.
            full_leaf_audit = relative_index == 0 or index == len(plan["stages"]) - 1
            leaf_audit_rows = installed_runtime if full_leaf_audit else added_runtime
            actual_leaf_captures = [
                _capture_leaf_union_and_record(client, steps, row["componentName"])
                for row in leaf_audit_rows
            ]
            count = int(stage["expectedTopLevelCountAfterStage"])
            whitelist = audit_top_level_components(
                actual_components, installed_runtime, expected_module_count=count
            )
            pose_audit = audit_poses(
                actual_poses, installed_runtime, expected_module_count=count
            )
            extent_audit = _audit_leaf_body_extents(actual_leaf_captures, leaf_audit_rows)
            extent_audit["scope"] = "all-installed" if full_leaf_audit else "newly-added"
            extent_audit["auditedComponents"] = [row["componentName"] for row in leaf_audit_rows]
            accepted = whitelist["success"] and pose_audit["success"] and extent_audit["success"]
            stage_result = {
                **stage,
                "accepted": accepted,
                "durationSeconds": round(time.perf_counter() - stage_started, 6),
                "directTranslationCorrections": moves,
                "runtimeComponentAliases": runtime_aliases,
                "topLevelAudit": whitelist,
                "poseAudit": pose_audit,
                "boundingBoxExtentAudit": extent_audit,
                "steps": steps,
            }
            write_json(target.with_suffix(".stage-result.json"), stage_result)
            completed_stages.append(stage_result)
            if not accepted:
                raise RuntimeError(f"{stage['stageId']} failed save/reopen CAD gate.")

    return {
        "schemaVersion": "project05-ordered-direct-execution/v1",
        "success": len(completed_stages) == len(stages_to_run),
        "projectId": "project05",
        "selectedSolutionRank": 1,
        "durationSeconds": round(time.perf_counter() - started, 6),
        "connectionSteps": connection_steps,
        "stages": completed_stages,
        "startStageIndex": start_stage_index,
        "endStageIndexExclusive": end_stage_index_exclusive,
        "resumeCheckpoint": str(resume_checkpoint) if resume_checkpoint else None,
        "finalAssemblyPath": completed_stages[-1]["targetCheckpointPath"] if completed_stages else None,
        "collisionClosurePending": True,
        "productionReleased": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layout", default=str(DEFAULT_LAYOUT))
    parser.add_argument("--poses", default=str(DEFAULT_POSES))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--mcp", default=str(DEFAULT_MCP))
    parser.add_argument("--request-timeout", type=float, default=1200.0)
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--start-stage", type=int, default=0)
    parser.add_argument("--end-stage", type=int, default=None)
    parser.add_argument("--resume-checkpoint", default=None)
    args = parser.parse_args()

    layout = resolved(args.layout)
    poses = resolved(args.poses)
    output_root = resolved(args.output_root)
    for required in (layout, poses):
        if not required.is_file():
            raise SystemExit(f"Required input does not exist: {required}")
    output_root.mkdir(parents=True, exist_ok=True)
    plan = build_plan(layout, poses, output_root)
    plan_path = output_root / "project05_ordered_direct_plan.json"
    write_json(plan_path, plan)
    if args.plan_only:
        print(json.dumps({
            "success": True,
            "mode": "plan-only",
            "planPath": str(plan_path),
            "stageCount": plan["stageCount"],
            "moduleCount": plan["moduleCount"],
        }, ensure_ascii=False, indent=2))
        return 0

    mcp = resolved(args.mcp)
    if not mcp.is_file():
        raise SystemExit(f"MCP executable does not exist: {mcp}")
    if args.start_stage < 0 or args.start_stage >= len(plan["stages"]):
        raise SystemExit("--start-stage is outside the ordered plan.")
    if args.end_stage is not None and not (
        args.start_stage < args.end_stage <= len(plan["stages"])
    ):
        raise SystemExit("--end-stage must be greater than --start-stage and within the ordered plan.")
    resume_checkpoint = resolved(args.resume_checkpoint) if args.resume_checkpoint else None
    if args.start_stage > 0 and (resume_checkpoint is None or not resume_checkpoint.is_file()):
        raise SystemExit("A valid --resume-checkpoint is required when --start-stage > 0.")
    result = execute_plan(
        plan,
        mcp=mcp,
        request_timeout=args.request_timeout,
        start_stage_index=args.start_stage,
        end_stage_index_exclusive=args.end_stage,
        resume_checkpoint=resume_checkpoint,
    )
    result_path = output_root / "project05_ordered_direct_execution.json"
    write_json(result_path, result)
    print(json.dumps({
        "success": result["success"],
        "resultPath": str(result_path),
        "finalAssemblyPath": result["finalAssemblyPath"],
        "durationSeconds": result["durationSeconds"],
    }, ensure_ascii=False, indent=2))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
