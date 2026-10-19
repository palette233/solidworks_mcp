#!/usr/bin/env python3
"""Resume full-context reopen and B-rep validation after a clean SolidWorks restart."""

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
from demo_backend.project03_full_context_dynamic_assessment import assess_against_prototype_baseline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, default=ROOT / "artifacts/solidworks-mcp-current/SolidWorksMcpApp.exe")
    parser.add_argument("--closure", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--require-exact-baseline", action="store_true")
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


def unique(rows: list[dict[str, Any]], token: str) -> dict[str, Any]:
    matches = [row for row in rows if token.casefold() in str(pick(row, "Name", "")).casefold()]
    if len(matches) != 1:
        raise RuntimeError(f"Selector {token!r} resolved to {len(matches)} components.")
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
    closure_path = args.closure.resolve()
    output_path = args.output.resolve()
    exe = args.exe.resolve()
    if not closure_path.is_file() or not exe.is_file():
        raise FileNotFoundError(closure_path if not closure_path.is_file() else exe)
    if output_path.exists():
        raise FileExistsError(output_path)
    source = json.loads(closure_path.read_text(encoding="utf-8"))
    full_context = Path(source["copies"]["fullContext"]).resolve()
    state_ad00 = Path(source["copies"]["stateAd00"]).resolve()
    baseline_path = (args.baseline or Path(source["sourceFiles"]["prototypeBaseline"])).resolve()
    if not full_context.is_file() or not baseline_path.is_file():
        raise FileNotFoundError(full_context if not full_context.is_file() else baseline_path)

    payload: dict[str, Any] = {
        "schemaVersion": "project03-ad00-full-context-resume/v1",
        "sourceClosure": str(closure_path),
        "fullContextAssembly": str(full_context),
        "status": "RUNNING",
        "startedAtUtc": datetime.now(timezone.utc).isoformat(),
        "operations": [],
        "problems": [],
    }
    write(output_path, payload)

    def operation(name: str, action: Callable[[], Any]) -> Any:
        started = time.perf_counter()
        row: dict[str, Any] = {"operation": name, "startedAtUtc": datetime.now(timezone.utc).isoformat()}
        payload["operations"].append(row)
        write(output_path, payload)
        try:
            value = action()
        except BaseException as exc:
            row.update(success=False, error=str(exc), durationSeconds=round(time.perf_counter() - started, 6))
            payload["problems"].append(f"{name}: {exc}")
            write(output_path, payload)
            raise
        row.update(success=True, durationSeconds=round(time.perf_counter() - started, 6))
        write(output_path, payload)
        return value

    total_started = time.perf_counter()
    try:
        with McpClient(exe, "Project03AD00FullContextResume", args.timeout, "newline", direct_stdio=True) as client:
            operation("connect-clean-session", lambda: client.call_tool("solid_works_connect", {}))
            payload["opened"] = operation("open-full-context", lambda: client.call_tool("open_document", {"path": str(full_context)}))
            rows = operation("list-reopened-top-level", lambda: client.call_tool("list_component_poses", {"topLevelOnly": True}))
            ad00 = unique(rows, state_ad00.stem)
            ae00 = unique(rows, "FL9A24D063AE00")
            payload["reopenedTopLevel"] = {"ad00": ad00, "ae00": ae00}
            expected_top_level = list(source.get("expectedTopLevelAd00Transform", []))
            payload["topLevelAd00TransformError"] = (
                max_transform_error(list(pick(ad00, "Transform", [])), expected_top_level)
                if expected_top_level
                else None
            )
            if payload["topLevelAd00TransformError"] is not None and payload["topLevelAd00TransformError"] > 1e-9:
                raise RuntimeError(
                    "Top-level AD00 pose drifted after replacement: "
                    f"max Transform2 element error={payload['topLevelAd00TransformError']}."
                )
            payload["exactInterference"] = operation(
                "brep-ad00-ae00-full-context",
                lambda: client.call_tool(
                    "check_interference_by_leaf_bodies",
                    {
                        "hierarchyPaths": [pick(ad00, "HierarchyPath", ""), pick(ae00, "HierarchyPath", "")],
                        "treatCoincidenceAsInterference": False,
                    },
                ),
            )
            try:
                operation("close-full-context", lambda: client.call_tool_text("close_document", {"path": str(full_context)}))
            except BaseException as exc:
                # The exact B-rep result is already durable.  SolidWorks can reject
                # CloseDoc after a large leaf-body check while it unwinds background
                # state; record this as cleanup debt without discarding geometry proof.
                payload.setdefault("warnings", []).append(f"close-full-context: {exc}")
                payload["cleanupComplete"] = False
            else:
                payload["cleanupComplete"] = True

        baseline_document = json.loads(baseline_path.read_text(encoding="utf-8-sig"))
        # Accept either a raw B-rep result or a durable resume-assessment document
        # that embeds the exact result. This lets later dynamic states compare
        # against the validated rigid 0-degree baseline rather than a different
        # flexible prototype context.
        baseline = pick(baseline_document, "exactInterference", baseline_document)
        payload["baselineAssessment"] = assess_against_prototype_baseline(
            payload["exactInterference"],
            baseline,
            require_exact_baseline=args.require_exact_baseline,
        )
        protected = {Path(path): expected for path, expected in source.get("sourceHashesBefore", {}).items()}
        payload["sourceHashesAfter"] = {str(path): sha256(path) for path in protected}
        payload["sourceFilesUnchanged"] = all(payload["sourceHashesAfter"][str(path)] == expected for path, expected in protected.items())
        payload["status"] = (
            "PASSED_FULL_CONTEXT_BASELINE_REPRODUCTION_AFTER_CLEAN_RESTART"
            if payload["baselineAssessment"]["passed"] and payload["sourceFilesUnchanged"]
            else "FAILED_FULL_CONTEXT_BASELINE_REPRODUCTION_AFTER_CLEAN_RESTART"
        )
    except BaseException as exc:
        payload["status"] = "ERROR"
        payload["error"] = str(exc)
    finally:
        payload["completedAtUtc"] = datetime.now(timezone.utc).isoformat()
        payload["durationSeconds"] = round(time.perf_counter() - total_started, 6)
        write(output_path, payload)

    print(output_path)
    return 0 if payload["status"].startswith("PASSED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
