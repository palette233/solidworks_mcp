#!/usr/bin/env python3
"""Build one AD00 configuration state through copied parents and validate it in full context."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "demo-backend" / "src"))

from capture_assembly_entity_annotations import McpClient
from demo_backend.project03_full_context_dynamic_assessment import assess_against_prototype_baseline


DEFAULT_EXE = ROOT / "artifacts/solidworks-mcp-current/SolidWorksMcpApp.exe"
DEFAULT_PROJECT_ROOT = Path(
    r"D:\zengshuang\workspace\cuhksz\cad_data\001-给港中文AI训练用资料_20260624"
    r"\项目03\01-项目3D图纸\FL9A24D063A000.001-0415"
)
DEFAULT_FINAL = ROOT / (
    "demo/semantic_ports/project03_live_adapter_full_jobs/project03-job-acc1cd320f35/"
    "cad-working/step-07-ab00-attempt2/step07b_project03_full_10_object_hybrid_static.SLDASM"
)
DEFAULT_BASELINE = ROOT / (
    "demo/interference_project03_prototype/conditional_hits/"
    "FL9A24D063A000.001_leaf_details_FL9A24D063AE00_FL9A24D063AD00.json"
)
DEFAULT_OUTPUT = ROOT / "demo/semantic_ports/project03_ad00_full_context_baseline_v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, default=DEFAULT_EXE)
    parser.add_argument("--project-root", type=Path, default=DEFAULT_PROJECT_ROOT)
    parser.add_argument("--final-assembly", type=Path, default=DEFAULT_FINAL)
    parser.add_argument("--prototype-baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--state", default="both-0deg")
    parser.add_argument("--left-configuration", default="0度")
    parser.add_argument("--right-configuration", default="0度")
    parser.add_argument(
        "--left-ad10-override",
        type=Path,
        help="Optional prebuilt AD10 static-state assembly. When supplied, it is copied and not reconfigured.",
    )
    parser.add_argument(
        "--right-ad10-override",
        type=Path,
        help="Optional prebuilt AD10 static-state assembly. When supplied, it is copied and not reconfigured.",
    )
    parser.add_argument(
        "--left-override-solving-state",
        choices=("preserve", "rigid"),
        default="preserve",
        help="Whether a prebuilt left AD10 remains in the source flexible state or is forced rigid.",
    )
    parser.add_argument(
        "--right-override-solving-state",
        choices=("preserve", "rigid"),
        default="preserve",
        help="Whether a prebuilt right AD10 remains in the source flexible state or is forced rigid.",
    )
    parser.add_argument(
        "--left-nested-rigid-token",
        help="Optional unique nested subassembly token inside the left AD10 that must remain rigid in AD00/full context.",
    )
    parser.add_argument(
        "--right-nested-rigid-token",
        help="Optional unique nested subassembly token inside the right AD10 that must remain rigid in AD00/full context.",
    )
    parser.add_argument("--require-exact-baseline", action="store_true")
    parser.add_argument(
        "--defer-clean-reopen",
        action="store_true",
        help="Stop after the durable full-context copy is saved and closed; validate it in a new process with the resume script.",
    )
    parser.add_argument("--timeout", type=float, default=1800.0)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pick(value: dict[str, Any], name: str, default: Any = None) -> Any:
    return value.get(name, value.get(name[0].lower() + name[1:], default))


def select(rows: list[dict[str, Any]], token: str) -> list[dict[str, Any]]:
    return [row for row in rows if token.casefold() in str(pick(row, "Name", "")).casefold()]


def unique(rows: list[dict[str, Any]], token: str) -> dict[str, Any]:
    matches = select(rows, token)
    if len(matches) != 1:
        raise RuntimeError(f"Selector {token!r} resolved to {len(matches)} components.")
    return matches[0]


def unique_source_stem(rows: list[dict[str, Any]], token: str) -> dict[str, Any]:
    normalized = token.casefold()
    matches = [
        row
        for row in rows
        if Path(str(pick(row, "Path", ""))).stem.casefold() == normalized
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Source stem selector {token!r} resolved to {len(matches)} components.")
    return matches[0]


def write(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def max_transform_error(first: list[float], second: list[float]) -> float:
    if len(first) != 16 or len(second) != 16:
        return float("inf")
    return max(abs(float(a) - float(b)) for a, b in zip(first, second))


def main() -> int:
    args = parse_args()
    exe = args.exe.resolve()
    project_root = args.project_root.resolve()
    final_source = args.final_assembly.resolve()
    baseline_path = args.prototype_baseline.resolve()
    output_dir = args.output_dir.resolve()
    left_override = args.left_ad10_override.resolve() if args.left_ad10_override else None
    right_override = args.right_ad10_override.resolve() if args.right_ad10_override else None
    ad10_source = project_root / "FL9A24D063AD10.001.SLDASM"
    ad00_source = project_root / "FL9A24D063AD00.001.SLDASM"
    required = tuple(
        path
        for path in (exe, ad10_source, ad00_source, final_source, baseline_path, left_override, right_override)
        if path is not None
    )
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(path)
    output_dir.mkdir(parents=True, exist_ok=True)

    copies = {
        "leftAd10": output_dir / f"AD10_LEFT_{args.state}.SLDASM",
        "rightAd10": output_dir / f"AD10_RIGHT_{args.state}.SLDASM",
        "stateAd00": output_dir / f"AD00_{args.state}.SLDASM",
        "fullContext": output_dir / f"project03_full_context_{args.state}.SLDASM",
    }
    manifest_path = output_dir / f"project03_full_context_{args.state}_closure.json"
    if manifest_path.exists() or any(path.exists() for path in copies.values()):
        raise FileExistsError(f"Refusing to overwrite evidence in {output_dir}")

    protected = list(dict.fromkeys(
        path for path in (ad10_source, ad00_source, final_source, left_override, right_override) if path is not None
    ))
    source_hashes_before = {str(path): sha256(path) for path in protected}
    payload: dict[str, Any] = {
        "schemaVersion": "project03-ad00-full-context-state/v1",
        "state": args.state,
        "requestedConfigurations": {
            "left": args.left_configuration,
            "right": args.right_configuration,
        },
        "ad10Overrides": {
            "left": str(left_override) if left_override else None,
            "right": str(right_override) if right_override else None,
        },
        "status": "RUNNING",
        "startedAtUtc": datetime.now(timezone.utc).isoformat(),
        "sourceFiles": {
            "ad10": str(ad10_source),
            "ad00": str(ad00_source),
            "finalAssembly": str(final_source),
            "prototypeBaseline": str(baseline_path),
        },
        "copies": {key: str(path) for key, path in copies.items()},
        "sourceHashesBefore": source_hashes_before,
        "operations": [],
        "problems": [],
    }
    write(manifest_path, payload)

    def operation(name: str, action: Callable[[], Any]) -> Any:
        started = time.perf_counter()
        row: dict[str, Any] = {"operation": name, "startedAtUtc": datetime.now(timezone.utc).isoformat()}
        payload["operations"].append(row)
        write(manifest_path, payload)
        try:
            value = action()
        except BaseException as exc:
            row.update(success=False, error=str(exc), durationSeconds=round(time.perf_counter() - started, 6))
            payload["problems"].append(f"{name}: {exc}")
            write(manifest_path, payload)
            raise
        row.update(success=True, durationSeconds=round(time.perf_counter() - started, 6))
        write(manifest_path, payload)
        return value

    total_started = time.perf_counter()
    try:
        for target, source in (
            (copies["leftAd10"], left_override or ad10_source),
            (copies["rightAd10"], right_override or ad10_source),
            (copies["stateAd00"], ad00_source),
            (copies["fullContext"], final_source),
        ):
            operation(f"copy-{target.stem}", lambda target=target, source=source: shutil.copy2(source, target))

        with McpClient(exe, "Project03AD00FullContextState", args.timeout, "newline", direct_stdio=True) as client:
            operation("connect", lambda: client.call_tool("solid_works_connect", {}))

            for side, copy_path, configuration, override in (
                ("left", copies["leftAd10"], args.left_configuration, left_override),
                ("right", copies["rightAd10"], args.right_configuration, right_override),
            ):
                if override is not None:
                    payload[f"{side}Configuration"] = {
                        "mode": "prebuilt-ad10-override",
                        "source": str(override),
                        "requestedLabel": configuration,
                    }
                    write(manifest_path, payload)
                    continue
                operation(f"open-{side}-ad10", lambda copy_path=copy_path: client.call_tool("open_document", {"path": str(copy_path)}))
                poses = operation(f"list-{side}-ad10", lambda: client.call_tool("list_component_poses", {"topLevelOnly": True}))
                ad20 = unique(poses, "FL9A24D063AD20")
                payload[f"{side}Configuration"] = operation(
                    f"configure-{side}-ad20",
                    lambda ad20=ad20, configuration=configuration: client.call_tool(
                        "set_component_referenced_configuration",
                        {"componentName": pick(ad20, "Name", ""), "configurationName": configuration, "rebuild": True},
                    ),
                )
                operation(f"save-{side}-ad10", lambda copy_path=copy_path: client.call_tool("save_document", {"path": str(copy_path)}))
                operation(f"close-{side}-ad10", lambda copy_path=copy_path: client.call_tool_text("close_document", {"path": str(copy_path)}))

            operation("open-state-ad00", lambda: client.call_tool("open_document", {"path": str(copies["stateAd00"])}))
            ad10_rows = select(operation("list-state-ad00", lambda: client.call_tool("list_component_poses", {"topLevelOnly": True})), "FL9A24D063AD10")
            if len(ad10_rows) != 2:
                raise RuntimeError(f"Expected two AD10 instances in AD00, found {len(ad10_rows)}.")
            ad10_rows.sort(key=lambda row: str(pick(row, "HierarchyPath", "")))
            payload["leftReplacement"] = operation(
                "replace-left-ad10",
                lambda: client.call_tool(
                    "replace_component",
                    {
                        "hierarchyPath": pick(ad10_rows[0], "HierarchyPath", ""),
                        "replacementFilePath": str(copies["leftAd10"]),
                        "replaceAllInstances": False,
                        "reattachMates": left_override is None and right_override is None,
                    },
                ),
            )
            after_left_rows = operation(
                "list-after-left-replacement",
                lambda: client.call_tool("list_component_poses", {"topLevelOnly": True}),
            )
            inserted_left = unique(after_left_rows, copies["leftAd10"].stem)
            if left_override is not None and args.left_override_solving_state == "rigid":
                payload["leftSolvingState"] = operation(
                    "set-left-ad10-rigid",
                    lambda: client.call_tool(
                        "set_top_level_component_solving_state",
                        {
                            "hierarchyPath": pick(inserted_left, "HierarchyPath", ""),
                            "solvingState": 0,
                            "rebuild": True,
                        },
                    ),
                )
            payload["leftTransformLock"] = operation(
                "lock-left-ad10-transform",
                lambda: client.call_tool(
                    "set_component_transform",
                    {
                        "componentName": pick(inserted_left, "Name", ""),
                        "transform": list(pick(ad10_rows[0], "Transform", [])),
                        "rebuild": False,
                    },
                ),
            )
            remaining = select(after_left_rows, "FL9A24D063AD10")
            # The source assembly retains a historical I:\ reference in this project even
            # when SolidWorks resolves it from the current D:\ data tree.  Instance identity,
            # not the stale stored path, is therefore the authoritative selector here.
            original_remaining = [
                row
                for row in remaining
                if "FL9A24D063AD10.001" in str(pick(row, "Name", "")).upper()
            ]
            if len(original_remaining) != 1:
                raise RuntimeError(f"Expected one original AD10 after left replacement, found {len(original_remaining)}.")
            payload["rightReplacement"] = operation(
                "replace-right-ad10",
                lambda: client.call_tool(
                    "replace_component",
                    {
                        "hierarchyPath": pick(original_remaining[0], "HierarchyPath", ""),
                        "replacementFilePath": str(copies["rightAd10"]),
                        "replaceAllInstances": False,
                        "reattachMates": left_override is None and right_override is None,
                    },
                ),
            )
            after_right_rows = operation(
                "list-after-right-replacement",
                lambda: client.call_tool("list_component_poses", {"topLevelOnly": True}),
            )
            inserted_right = unique(after_right_rows, copies["rightAd10"].stem)
            if right_override is not None and args.right_override_solving_state == "rigid":
                payload["rightSolvingState"] = operation(
                    "set-right-ad10-rigid",
                    lambda: client.call_tool(
                        "set_top_level_component_solving_state",
                        {
                            "hierarchyPath": pick(inserted_right, "HierarchyPath", ""),
                            "solvingState": 0,
                            "rebuild": True,
                        },
                    ),
                )
            payload["rightTransformLock"] = operation(
                "lock-right-ad10-transform",
                lambda: client.call_tool(
                    "set_component_transform",
                    {
                        "componentName": pick(inserted_right, "Name", ""),
                        "transform": list(pick(ad10_rows[1], "Transform", [])),
                        "rebuild": False,
                    },
                ),
            )
            locked_rows = operation(
                "verify-ad10-transform-locks",
                lambda: client.call_tool("list_component_poses", {"topLevelOnly": True}),
            )
            locked_left = unique(locked_rows, copies["leftAd10"].stem)
            locked_right = unique(locked_rows, copies["rightAd10"].stem)
            payload["ad10TransformLockErrors"] = {
                "left": max_transform_error(
                    list(pick(locked_left, "Transform", [])),
                    list(pick(ad10_rows[0], "Transform", [])),
                ),
                "right": max_transform_error(
                    list(pick(locked_right, "Transform", [])),
                    list(pick(ad10_rows[1], "Transform", [])),
                ),
            }
            payload["ad10SolvingStates"] = {
                "left": {
                    "actual": pick(locked_left, "SolvingState"),
                    "expected": (
                        0
                        if left_override is not None and args.left_override_solving_state == "rigid"
                        else pick(ad10_rows[0], "SolvingState")
                    ),
                },
                "right": {
                    "actual": pick(locked_right, "SolvingState"),
                    "expected": (
                        0
                        if right_override is not None and args.right_override_solving_state == "rigid"
                        else pick(ad10_rows[1], "SolvingState")
                    ),
                },
            }
            if max(payload["ad10TransformLockErrors"].values()) > 1e-9:
                raise RuntimeError(f"AD10 transform lock failed: {payload['ad10TransformLockErrors']}")
            if any(
                row["actual"] != row["expected"]
                for row in payload["ad10SolvingStates"].values()
            ):
                raise RuntimeError(f"AD10 solving-state gate failed: {payload['ad10SolvingStates']}")
            nested_rigid_specs = [
                ("left", args.left_nested_rigid_token, copies["leftAd10"].stem),
                ("right", args.right_nested_rigid_token, copies["rightAd10"].stem),
            ]
            nested_rigid_specs = [row for row in nested_rigid_specs if row[1]]
            if nested_rigid_specs:
                operation(
                    "save-state-ad00-before-nested-rigid-lock",
                    lambda: client.call_tool("save_document", {"path": str(copies["stateAd00"])}),
                )
                operation(
                    "close-state-ad00-before-nested-rigid-lock",
                    lambda: client.call_tool_text("close_document", {"path": str(copies["stateAd00"])}),
                )
                operation(
                    "reopen-state-ad00-for-nested-rigid-lock",
                    lambda: client.call_tool("open_document", {"path": str(copies["stateAd00"])}),
                )
                payload["resolveLightweightInAd00"] = operation(
                    "resolve-lightweight-components-in-ad00",
                    lambda: client.call_tool(
                        "resolve_all_lightweight_components",
                        {"warnIfNotResolved": False, "rebuild": True},
                    ),
                )
                reopened_ad10_rows = operation(
                    "list-reopened-state-ad00-for-nested-rigid-lock",
                    lambda: client.call_tool("list_component_poses", {"topLevelOnly": True}),
                )
                for side, nested_token, ad10_stem in nested_rigid_specs:
                    locked_ad10 = unique(reopened_ad10_rows, ad10_stem)
                    ad10_subtree = operation(
                        f"list-{side}-ad10-subtree-before-nested-rigid-lock",
                        lambda locked_ad10=locked_ad10: client.call_tool(
                            "list_top_level_component_subtree_poses",
                            {"hierarchyPath": pick(locked_ad10, "HierarchyPath", "")},
                        ),
                    )
                    nested = unique_source_stem(ad10_subtree, nested_token)
                    payload[f"{side}NestedRigidLockInAd00"] = operation(
                        f"set-{side}-nested-component-rigid-in-ad00",
                        lambda nested=nested: client.call_tool(
                            "set_component_solving_state",
                            {
                                "hierarchyPath": pick(nested, "HierarchyPath", ""),
                                "solvingState": 0,
                                "rebuild": True,
                            },
                        ),
                    )
                    ad10_subtree_after = operation(
                        f"verify-{side}-nested-component-rigid-in-ad00",
                        lambda locked_ad10=locked_ad10: client.call_tool(
                            "list_top_level_component_subtree_poses",
                            {"hierarchyPath": pick(locked_ad10, "HierarchyPath", "")},
                        ),
                    )
                    nested_after = unique_source_stem(ad10_subtree_after, nested_token)
                    state_key = f"{side}NestedRigidStateInAd00"
                    payload[state_key] = pick(nested_after, "SolvingState")
                    if payload[state_key] != 0:
                        raise RuntimeError(
                            f"Nested {side} component remained non-rigid in AD00: {payload[state_key]}"
                        )
            operation("save-state-ad00", lambda: client.call_tool("save_document", {"path": str(copies["stateAd00"])}))
            operation("close-state-ad00", lambda: client.call_tool_text("close_document", {"path": str(copies["stateAd00"])}))

            operation("open-full-context", lambda: client.call_tool("open_document", {"path": str(copies["fullContext"])}))
            full_rows = operation("list-full-context-before", lambda: client.call_tool("list_component_poses", {"topLevelOnly": True}))
            original_ad00 = unique(full_rows, "FL9A24D063AD00")
            payload["topLevelReplacement"] = operation(
                "replace-top-level-ad00",
                lambda: client.call_tool(
                    "replace_component",
                    {
                        "hierarchyPath": pick(original_ad00, "HierarchyPath", ""),
                        "replacementFilePath": str(copies["stateAd00"]),
                        "replaceAllInstances": False,
                        "reattachMates": not (left_override or right_override),
                    },
                ),
            )
            after_top_rows = operation(
                "list-full-context-after-replacement",
                lambda: client.call_tool("list_component_poses", {"topLevelOnly": True}),
            )
            inserted_ad00 = unique(after_top_rows, copies["stateAd00"].stem)
            payload["expectedTopLevelAd00Transform"] = list(pick(original_ad00, "Transform", []))
            payload["topLevelTransformLock"] = operation(
                "lock-top-level-ad00-transform",
                lambda: client.call_tool(
                    "set_component_transform",
                    {
                        "componentName": pick(inserted_ad00, "Name", ""),
                        "transform": payload["expectedTopLevelAd00Transform"],
                        "rebuild": False,
                    },
                ),
            )
            if nested_rigid_specs:
                operation(
                    "save-full-context-before-nested-rigid-lock",
                    lambda: client.call_tool("save_document", {"path": str(copies["fullContext"])}),
                )
                operation(
                    "close-full-context-before-nested-rigid-lock",
                    lambda: client.call_tool_text("close_document", {"path": str(copies["fullContext"])}),
                )
                operation(
                    "reopen-full-context-for-nested-rigid-lock",
                    lambda: client.call_tool("open_document", {"path": str(copies["fullContext"])}),
                )
                payload["resolveLightweightInFullContext"] = operation(
                    "resolve-lightweight-components-in-full-context",
                    lambda: client.call_tool(
                        "resolve_all_lightweight_components",
                        {"warnIfNotResolved": False, "rebuild": True},
                    ),
                )
                reopened_full_rows = operation(
                    "list-reopened-full-context-for-nested-rigid-lock",
                    lambda: client.call_tool("list_component_poses", {"topLevelOnly": True}),
                )
                inserted_ad00 = unique(reopened_full_rows, copies["stateAd00"].stem)
                ad00_subtree = operation(
                    "list-ad00-subtree-before-full-context-nested-rigid-lock",
                    lambda: client.call_tool(
                        "list_top_level_component_subtree_poses",
                        {"hierarchyPath": pick(inserted_ad00, "HierarchyPath", "")},
                    ),
                )
                for side, nested_token, ad10_stem in nested_rigid_specs:
                    full_ad10 = unique_source_stem(ad00_subtree, ad10_stem)
                    full_ad10_subtree = operation(
                        f"list-{side}-ad10-subtree-before-full-context-nested-rigid-lock",
                        lambda full_ad10=full_ad10: client.call_tool(
                            "list_top_level_component_subtree_poses",
                            {"hierarchyPath": pick(full_ad10, "HierarchyPath", "")},
                        ),
                    )
                    nested_full = unique_source_stem(full_ad10_subtree, nested_token)
                    payload[f"{side}NestedRigidLockInFullContext"] = operation(
                        f"set-{side}-nested-component-rigid-in-full-context",
                        lambda nested_full=nested_full: client.call_tool(
                            "set_component_solving_state",
                            {
                                "hierarchyPath": pick(nested_full, "HierarchyPath", ""),
                                "solvingState": 0,
                                "rebuild": True,
                            },
                        ),
                    )
                    full_ad10_subtree_after = operation(
                        f"verify-{side}-nested-component-rigid-in-full-context",
                        lambda full_ad10=full_ad10: client.call_tool(
                            "list_top_level_component_subtree_poses",
                            {"hierarchyPath": pick(full_ad10, "HierarchyPath", "")},
                        ),
                    )
                    nested_full_after = unique_source_stem(full_ad10_subtree_after, nested_token)
                    state_key = f"{side}NestedRigidStateInFullContext"
                    payload[state_key] = pick(nested_full_after, "SolvingState")
                    if payload[state_key] != 0:
                        raise RuntimeError(
                            f"Nested {side} component remained non-rigid in full context: {payload[state_key]}"
                        )
            operation("save-full-context", lambda: client.call_tool("save_document", {"path": str(copies["fullContext"])}))
            operation("close-full-context", lambda: client.call_tool_text("close_document", {"path": str(copies["fullContext"])}))
            if args.defer_clean_reopen:
                payload["sourceHashesAfter"] = {str(path): sha256(path) for path in protected}
                payload["sourceFilesUnchanged"] = payload["sourceHashesAfter"] == source_hashes_before
                payload["status"] = (
                    "READY_FOR_CLEAN_RESTART_VALIDATION"
                    if payload["sourceFilesUnchanged"]
                    else "FAILED_SOURCE_INTEGRITY_GATE"
                )
                payload["deferredValidation"] = {
                    "required": True,
                    "reason": "SolidWorks crashed reopening the first full-context copy after a long construction session.",
                }
                return 0 if payload["status"].startswith("READY") else 1
            operation("reopen-full-context", lambda: client.call_tool("open_document", {"path": str(copies["fullContext"])}))
            reopened_rows = operation("list-full-context-reopened", lambda: client.call_tool("list_component_poses", {"topLevelOnly": True}))
            state_ad00 = unique(reopened_rows, copies["stateAd00"].stem)
            ae00 = unique(reopened_rows, "FL9A24D063AE00")
            payload["reopenedTopLevel"] = {
                "ad00": state_ad00,
                "ae00": ae00,
            }
            payload["exactInterference"] = operation(
                "brep-ad00-ae00-full-context",
                lambda: client.call_tool(
                    "check_interference_by_leaf_bodies",
                    {
                        "hierarchyPaths": [pick(state_ad00, "HierarchyPath", ""), pick(ae00, "HierarchyPath", "")],
                        "treatCoincidenceAsInterference": False,
                    },
                ),
            )
            operation("close-full-context-final", lambda: client.call_tool_text("close_document", {"path": str(copies["fullContext"])}))

        baseline = json.loads(baseline_path.read_text(encoding="utf-8-sig"))
        payload["baselineAssessment"] = assess_against_prototype_baseline(
            payload["exactInterference"],
            baseline,
            require_exact_baseline=args.require_exact_baseline,
        )
        payload["sourceHashesAfter"] = {str(path): sha256(path) for path in protected}
        payload["sourceFilesUnchanged"] = payload["sourceHashesAfter"] == source_hashes_before
        payload["status"] = (
            "PASSED_FULL_CONTEXT_BASELINE_REPRODUCTION"
            if payload["baselineAssessment"]["passed"] and payload["sourceFilesUnchanged"]
            else "FAILED_FULL_CONTEXT_BASELINE_REPRODUCTION"
        )
    except BaseException as exc:
        payload["status"] = "ERROR"
        payload["error"] = str(exc)
        payload["sourceHashesAfter"] = {str(path): sha256(path) for path in protected}
        payload["sourceFilesUnchanged"] = payload["sourceHashesAfter"] == source_hashes_before
    finally:
        payload["completedAtUtc"] = datetime.now(timezone.utc).isoformat()
        payload["durationSeconds"] = round(time.perf_counter() - total_started, 6)
        write(manifest_path, payload)

    print(manifest_path)
    return 0 if payload["status"] == "PASSED_FULL_CONTEXT_BASELINE_REPRODUCTION" else 1


if __name__ == "__main__":
    raise SystemExit(main())
