#!/usr/bin/env python3
"""Locate the first contact of the known Project03 AD20/AE00 leaf pair."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "demo-backend" / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from capture_assembly_entity_annotations import McpClient
from demo_backend.rigid_transform_interpolation import compose_transform


def pick(value: dict[str, Any], name: str, default: Any = None) -> Any:
    return value.get(name, value.get(name[0].lower() + name[1:], default))


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def unique(rows: list[dict[str, Any]], predicate: Callable[[dict[str, Any]], bool], label: str) -> dict[str, Any]:
    matches = [row for row in rows if predicate(row)]
    if len(matches) != 1:
        raise RuntimeError(f"{label} resolved to {len(matches)} components.")
    return matches[0]


def sample(component: dict[str, Any], angle: float) -> list[float]:
    row = unique(
        list(component.get("samples") or []),
        lambda item: abs(float(item.get("mechanismParameterDegrees") or 0.0) - angle) <= 1e-9,
        f"{angle:g}-degree interpolation sample",
    )
    return list(row["transform"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--exe", type=Path,
        default=ROOT / "artifacts/solidworks-mcp-current/SolidWorksMcpApp.exe",
    )
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--interpolation", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--start", type=float, default=15.0)
    parser.add_argument("--stop", type=float, default=16.0)
    parser.add_argument("--step", type=float, default=0.1)
    parser.add_argument("--timeout", type=float, default=1800.0)
    args = parser.parse_args()

    exe, context, interpolation_path, output_dir = (
        args.exe.resolve(), args.context.resolve(), args.interpolation.resolve(), args.output_dir.resolve()
    )
    for path in (exe, context, interpolation_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    if args.step <= 0 or args.stop <= args.start:
        raise ValueError("Refinement interval and step are invalid.")
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "project03_ad20_first_contact_pair_refinement.json"
    harness = output_dir / "project03_ad20_first_contact_pair_harness.SLDASM"
    if output.exists() or harness.exists():
        raise FileExistsError(output_dir)

    interpolation = json.loads(interpolation_path.read_text(encoding="utf-8-sig"))
    moving_component = unique(
        list(interpolation.get("components") or []),
        lambda row: Path(str(row.get("componentPath") or "")).name.casefold()
        == "fl5a24d063ad20002.01.sldprt"
        and str(row.get("componentName") or "").casefold().endswith("-1"),
        "moving AD20002 interpolation component",
    )
    moving_source = Path(str(moving_component["componentPath"])).resolve()
    fixed_source_name = "24d063电气-fl201ab-00181(2).sldprt"
    angles: list[float] = []
    value = args.start
    while value <= args.stop + 1e-9:
        angles.append(round(value, 9))
        value += args.step
    missing_samples = [angle for angle in angles if not any(
        abs(float(row.get("mechanismParameterDegrees") or 0.0) - angle) <= 1e-9
        for row in moving_component.get("samples") or []
    )]
    if missing_samples:
        raise ValueError(f"Interpolation is missing samples: {missing_samples}")

    payload: dict[str, Any] = {
        "schemaVersion": "project03-ad20-first-contact-pair-refinement/v1",
        "projectId": "project03",
        "status": "RUNNING",
        "startedAtUtc": datetime.now(timezone.utc).isoformat(),
        "sourceContext": str(context),
        "sourceInterpolation": str(interpolation_path),
        "sampleAnglesDegrees": angles,
        "harnessAssembly": str(harness),
        "operations": [],
        "samples": [],
        "scope": "known-leaf-pair-first-contact-only",
        "productionReady": False,
    }
    atomic_write(output, payload)

    def operation(name: str, action: Callable[[], Any]) -> Any:
        started = time.perf_counter()
        row: dict[str, Any] = {"operation": name}
        payload["operations"].append(row)
        atomic_write(output, payload)
        try:
            result = action()
        except BaseException as exc:
            row.update(success=False, error=str(exc), durationSeconds=round(time.perf_counter() - started, 6))
            atomic_write(output, payload)
            raise
        row.update(success=True, durationSeconds=round(time.perf_counter() - started, 6))
        atomic_write(output, payload)
        return result

    total_started = time.perf_counter()
    protected: dict[Path, str] = {context: sha256(context), moving_source: sha256(moving_source)}
    try:
        with McpClient(exe, "Project03AD20FirstContactPairRefinement", args.timeout, "newline", direct_stdio=True) as client:
            operation("connect", lambda: client.call_tool("solid_works_connect", {}))
            operation("open-context", lambda: client.call_tool("open_document", {"path": str(context)}))
            top = operation("list-context-top-level", lambda: client.call_tool("list_component_poses", {"topLevelOnly": True}))
            ae00 = unique(
                top,
                lambda row: Path(str(pick(row, "Path", ""))).stem.upper().endswith("AE00.001"),
                "top-level AE00",
            )
            ad00 = unique(
                top,
                lambda row: "AD00" in Path(str(pick(row, "Path", ""))).stem.upper()
                and "AE00" not in Path(str(pick(row, "Path", ""))).stem.upper(),
                "top-level AD00",
            )
            ae_subtree = operation(
                "capture-ae00-subtree",
                lambda: client.call_tool(
                    "list_top_level_component_subtree_poses",
                    {"hierarchyPath": str(pick(ae00, "HierarchyPath", pick(ae00, "Name", "")))},
                ),
            )
            ad_subtree = operation(
                "capture-ad00-subtree",
                lambda: client.call_tool(
                    "list_top_level_component_subtree_poses",
                    {"hierarchyPath": str(pick(ad00, "HierarchyPath", pick(ad00, "Name", "")))},
                ),
            )
            fixed = unique(
                ae_subtree,
                lambda row: (
                    Path(str(pick(row, "Path", ""))).name.casefold()
                    == fixed_source_name.casefold()
                    and "FL9A24D063AE43.001-2" in str(pick(row, "HierarchyPath", ""))
                    and str(pick(row, "Name", "")).replace("\\", "/").endswith(
                        "24D063电气-FL201AB-00181(2)-7"
                    )
                ),
                "fixed AE00 electrical leaf",
            )
            ad20_parent = unique(
                ad_subtree,
                lambda row: "PROJECT03_AD20_STATIC_16DEG" in str(pick(row, "Name", "")).upper(),
                "AD20 static parent",
            )
            fixed_source = Path(str(pick(fixed, "Path", ""))).resolve()
            protected[fixed_source] = sha256(fixed_source)
            fixed_world = list(pick(fixed, "TotalTransform", []))
            ad20_world = list(pick(ad20_parent, "TotalTransform", []))
            if len(fixed_world) != 16 or len(ad20_world) != 16:
                raise RuntimeError("Required SolidWorks total transforms are unavailable.")
            payload["sourceLeaves"] = {
                "fixed": {"path": str(fixed_source), "hierarchyPath": pick(fixed, "HierarchyPath")},
                "moving": {"path": str(moving_source), "sourceOccurrenceName": moving_component["componentName"]},
            }
            payload["contextTransforms"] = {"fixedWorld": fixed_world, "ad20ParentWorld": ad20_world}
            atomic_write(output, payload)
            operation("close-context", lambda: client.call_tool_text("close_document", {"path": str(context)}))

            operation("new-pair-harness", lambda: client.call_tool("new_document", {"type": "Assembly"}))
            operation(
                "save-empty-pair-harness",
                lambda: client.call_tool("save_document_as", {"outputPath": str(harness), "saveAsCopy": False}),
            )
            before = client.call_tool("list_component_poses", {"topLevelOnly": True})
            operation("insert-fixed-leaf", lambda: client.call_tool("insert_component", {"filePath": str(fixed_source), "x": 0, "y": 0, "z": 0}))
            after_fixed = client.call_tool("list_component_poses", {"topLevelOnly": True})
            fixed_instance = unique(after_fixed, lambda row: str(pick(row, "Name", "")) not in {str(pick(item, "Name", "")) for item in before}, "inserted fixed leaf")
            operation(
                "transform-fixed-leaf",
                lambda: client.call_tool("set_component_transform", {"componentName": pick(fixed_instance, "Name"), "transform": fixed_world, "rebuild": False}),
            )
            fixed_names = {str(pick(row, "Name", "")) for row in after_fixed}
            operation("insert-moving-leaf", lambda: client.call_tool("insert_component", {"filePath": str(moving_source), "x": 0, "y": 0, "z": 0}))
            after_moving = client.call_tool("list_component_poses", {"topLevelOnly": True})
            moving_instance = unique(after_moving, lambda row: str(pick(row, "Name", "")) not in fixed_names, "inserted moving leaf")
            fixed_path = str(pick(fixed_instance, "HierarchyPath", pick(fixed_instance, "Name", "")))
            moving_path = str(pick(moving_instance, "HierarchyPath", pick(moving_instance, "Name", "")))

            for angle in angles:
                world = compose_transform(ad20_world, sample(moving_component, angle))
                operation(
                    f"transform-moving-{angle:g}deg",
                    lambda world=world: client.call_tool(
                        "set_component_transform",
                        {"componentName": pick(moving_instance, "Name"), "transform": world, "rebuild": True},
                    ),
                )
                exact = operation(
                    f"brep-{angle:g}deg",
                    lambda: client.call_tool(
                        "check_interference_by_leaf_bodies",
                        {
                            "hierarchyPaths": [fixed_path, moving_path],
                            "treatCoincidenceAsInterference": False,
                        },
                    ),
                )
                payload["samples"].append(
                    {
                        "angleDegrees": angle,
                        "movingWorldTransform": world,
                        "exactCheckComplete": pick(exact, "ExactCheckComplete", False),
                        "failedBodyPairCount": int(pick(exact, "FailedBodyPairCount", 0) or 0),
                        "interferingBodyPairCount": int(pick(exact, "InterferingBodyPairCount", 0) or 0),
                        "hasInterference": int(pick(exact, "InterferingBodyPairCount", 0) or 0) > 0,
                    }
                )
                atomic_write(output, payload)
            operation("save-pair-harness", lambda: client.call_tool("save_document", {"path": str(harness)}))
            operation("close-pair-harness", lambda: client.call_tool_text("close_document", {"path": str(harness)}))

        first_collision = next((row for row in payload["samples"] if row["hasInterference"]), None)
        last_safe = None
        if first_collision is not None:
            last_safe = next(
                (row for row in reversed(payload["samples"]) if row["angleDegrees"] < first_collision["angleDegrees"] and not row["hasInterference"]),
                None,
            )
        payload["firstObservedCollisionAngleDegrees"] = (
            first_collision["angleDegrees"] if first_collision else None
        )
        payload["lastObservedSafeAngleDegrees"] = last_safe["angleDegrees"] if last_safe else None
        payload["firstObservedCollisionBracketDegrees"] = (
            [last_safe["angleDegrees"], first_collision["angleDegrees"]]
            if last_safe and first_collision
            else None
        )
        payload["sourceFilesUnchanged"] = all(sha256(path) == digest for path, digest in protected.items())
        checks_complete = all(
            row["exactCheckComplete"] and row["failedBodyPairCount"] == 0
            for row in payload["samples"]
        )
        payload["status"] = (
            "PASSED_PROJECT03_AD20_KNOWN_PAIR_FIRST_CONTACT_REFINEMENT"
            if checks_complete and first_collision and payload["sourceFilesUnchanged"]
            else "FAILED_PROJECT03_AD20_KNOWN_PAIR_FIRST_CONTACT_REFINEMENT"
        )
        payload["limitations"] = [
            "This evidence locates first contact only for the already identified AD20002/electrical-part pair.",
            "It does not prove the absence of collisions against every other machine leaf or validate vendor kinematics.",
        ]
    except BaseException as exc:
        payload["status"] = "ERROR"
        payload["error"] = str(exc)
    finally:
        payload["completedAtUtc"] = datetime.now(timezone.utc).isoformat()
        payload["durationSeconds"] = round(time.perf_counter() - total_started, 6)
        atomic_write(output, payload)

    print(output)
    return 0 if payload["status"].startswith("PASSED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
