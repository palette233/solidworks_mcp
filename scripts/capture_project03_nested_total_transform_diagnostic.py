#!/usr/bin/env python3
"""Capture local and SolidWorks total transforms for the Project03 AD10/AD20 nested chain."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from capture_assembly_entity_annotations import McpClient


def pick(value: dict[str, Any], name: str, default: Any = None) -> Any:
    return value.get(name, value.get(name[0].lower() + name[1:], default))


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def max_delta(first: Any, second: Any) -> float | None:
    if not isinstance(first, list) or not isinstance(second, list) or len(first) != len(second):
        return None
    return max((abs(float(a) - float(b)) for a, b in zip(first, second)), default=0.0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, default=ROOT / "artifacts/solidworks-mcp-current/SolidWorksMcpApp.exe")
    parser.add_argument(
        "--baseline",
        type=Path,
        default=ROOT
        / "demo/semantic_ports/project03_live_adapter_full_jobs/project03-job-acc1cd320f35/cad-working/step-07-ab00-attempt2/step07b_project03_full_10_object_hybrid_static.SLDASM",
    )
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=1200.0)
    args = parser.parse_args()
    exe, baseline, candidate, output = (
        args.exe.resolve(), args.baseline.resolve(), args.candidate.resolve(), args.output.resolve()
    )
    for path in (exe, baseline, candidate):
        if not path.is_file():
            raise FileNotFoundError(path)
    if output.exists():
        raise FileExistsError(output)

    payload: dict[str, Any] = {
        "schemaVersion": "project03-nested-total-transform-diagnostic/v1",
        "status": "RUNNING",
        "startedAtUtc": datetime.now(timezone.utc).isoformat(),
        "assemblies": [],
        "operations": [],
        "productionReady": False,
    }
    atomic_write(output, payload)

    def operation(name: str, action: Callable[[], Any]) -> Any:
        started = time.perf_counter()
        row: dict[str, Any] = {"operation": name}
        payload["operations"].append(row)
        atomic_write(output, payload)
        try:
            value = action()
        except BaseException as exc:
            row.update(success=False, durationSeconds=round(time.perf_counter() - started, 6), error=str(exc))
            atomic_write(output, payload)
            raise
        row.update(success=True, durationSeconds=round(time.perf_counter() - started, 6))
        atomic_write(output, payload)
        return value

    def select_ad00(top_rows: list[dict[str, Any]]) -> dict[str, Any]:
        matches = [
            row
            for row in top_rows
            if "AD00" in Path(str(pick(row, "Path", ""))).stem.upper()
            and "AE00" not in Path(str(pick(row, "Path", ""))).stem.upper()
        ]
        if len(matches) != 1:
            raise RuntimeError(f"AD00 top-level root resolved to {len(matches)} rows.")
        return matches[0]

    def relevant(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result = []
        for row in rows:
            path = Path(str(pick(row, "Path", ""))).name.upper()
            if (
                "AD10" in path
                or "AD20" in path
                or "FL5A24D063AD20001.01" in path
                or "PROJECT03_AD20_STATIC_" in str(pick(row, "Name", "")).upper()
                or "PROJECT03_AD20_STATIC_" in str(pick(row, "HierarchyPath", "")).upper()
            ):
                result.append(row)
        return result

    started = time.perf_counter()
    try:
        with McpClient(exe, "Project03NestedTotalTransformDiagnostic", args.timeout, "newline", direct_stdio=True) as client:
            operation("connect", lambda: client.call_tool("solid_works_connect", {}))
            for label, path in (("baseline", baseline), ("candidate", candidate)):
                operation(f"open-{label}", lambda path=path: client.call_tool("open_document", {"path": str(path)}))
                top_rows = operation(
                    f"list-top-level-{label}",
                    lambda: client.call_tool("list_component_poses", {"topLevelOnly": True}),
                )
                ad00 = select_ad00(top_rows)
                hierarchy = str(pick(ad00, "HierarchyPath", pick(ad00, "Name", "")))
                subtree = operation(
                    f"list-ad00-subtree-{label}",
                    lambda hierarchy=hierarchy: client.call_tool(
                        "list_top_level_component_subtree_poses", {"hierarchyPath": hierarchy}
                    ),
                )
                selected = relevant(subtree)
                payload["assemblies"].append(
                    {
                        "label": label,
                        "path": str(path),
                        "ad00Root": ad00,
                        "subtreePoseCount": len(subtree),
                        "selectedPoseCount": len(selected),
                        "selectedPoses": selected,
                    }
                )
                atomic_write(output, payload)
                operation(f"close-{label}", lambda path=path: client.call_tool_text("close_document", {"path": str(path)}))

        baseline_rows = payload["assemblies"][0]["selectedPoses"]
        candidate_rows = payload["assemblies"][1]["selectedPoses"]
        baseline_ad20001 = [
            row for row in baseline_rows if "FL5A24D063AD20001.01" in str(pick(row, "Path", "")).upper()
        ]
        candidate_ad20001 = [
            row for row in candidate_rows if "FL5A24D063AD20001.01" in str(pick(row, "Path", "")).upper()
        ]
        comparisons: list[dict[str, Any]] = []
        if baseline_ad20001 and candidate_ad20001:
            for candidate_row in candidate_ad20001:
                reference = min(
                    baseline_ad20001,
                    key=lambda row: max_delta(
                        pick(row, "BoundingBoxWorld"), pick(candidate_row, "BoundingBoxWorld")
                    )
                    or float("inf"),
                )
                comparisons.append(
                    {
                        "candidateHierarchyPath": pick(candidate_row, "HierarchyPath"),
                        "baselineHierarchyPath": pick(reference, "HierarchyPath"),
                        "transformDelta": max_delta(pick(reference, "Transform"), pick(candidate_row, "Transform")),
                        "totalTransformDelta": max_delta(
                            pick(reference, "TotalTransform"), pick(candidate_row, "TotalTransform")
                        ),
                        "boundingBoxWorldDelta": max_delta(
                            pick(reference, "BoundingBoxWorld"), pick(candidate_row, "BoundingBoxWorld")
                        ),
                    }
                )
        payload["ad20001Comparisons"] = comparisons
        total_transforms_present = all(
            isinstance(pick(row, "TotalTransform"), list)
            for assembly in payload["assemblies"]
            for row in assembly["selectedPoses"]
        )
        payload["status"] = (
            "PASSED_NESTED_TOTAL_TRANSFORM_DIAGNOSTIC"
            if total_transforms_present and comparisons
            else "FAILED_NESTED_TOTAL_TRANSFORM_DIAGNOSTIC"
        )
        if not total_transforms_present:
            payload["blocker"] = "At least one selected nested component did not expose GetTotalTransform(true)."
        elif not comparisons:
            payload["blocker"] = "AD20001 could not be matched in both assemblies."
    except BaseException as exc:
        payload["status"] = "ERROR"
        payload["error"] = str(exc)
    finally:
        payload["completedAtUtc"] = datetime.now(timezone.utc).isoformat()
        payload["durationSeconds"] = round(time.perf_counter() - started, 6)
        atomic_write(output, payload)
    print(output)
    return 0 if payload["status"].startswith("PASSED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
