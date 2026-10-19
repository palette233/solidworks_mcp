#!/usr/bin/env python3
"""Close, reopen and verify the basic health of one saved SolidWorks assembly."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))
BACKEND_SRC = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from capture_assembly_entity_annotations import McpClient  # noqa: E402
from demo_backend.pipeline_timing import PipelineTiming  # noqa: E402


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def rebuild_is_healthy(payload: dict[str, object]) -> bool:
    needs_rebuild = payload.get("NeedsRebuild", payload.get("needsRebuild"))
    summary = str(payload.get("Summary", payload.get("summary", ""))).casefold()
    return needs_rebuild is not True and "error" not in summary and "failed" not in summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", required=True, type=Path)
    parser.add_argument("--assembly", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--screenshot", type=Path)
    parser.add_argument("--expected-component", action="append", default=[])
    parser.add_argument("--timeout", type=float, default=900.0)
    parser.add_argument("--exit-solidworks", action="store_true")
    parser.add_argument(
        "--repair-needs-rebuild",
        action="store_true",
        help="Force rebuild, save and reopen once when the first disk open reports NeedsRebuild.",
    )
    args = parser.parse_args()

    exe = args.exe.resolve()
    assembly = args.assembly.resolve()
    output = args.output.resolve()
    screenshot = args.screenshot.resolve() if args.screenshot else None
    if not exe.is_file() or not assembly.is_file():
        raise FileNotFoundError(exe if not exe.is_file() else assembly)
    output.parent.mkdir(parents=True, exist_ok=True)
    if screenshot:
        screenshot.parent.mkdir(parents=True, exist_ok=True)

    timing = PipelineTiming("solidworks.saved-assembly-reopen-verification")
    file_hash_before = sha256_file(assembly)
    saved_active_before_reopen_hash = None
    steps: dict[str, object] = {}
    with timing.stage("solidworks-reopen-session"):
        with McpClient(exe, "VerifySavedAssemblyReopen", args.timeout, "newline", direct_stdio=True) as client:
            try:
                active = client.call_tool("get_active_document", {})
            except RuntimeError:
                active = None
            steps["activeBefore"] = active
            active_path = (
                active.get("Path", active.get("path"))
                if isinstance(active, dict)
                else None
            )
            if active_path and Path(str(active_path)).resolve() == assembly:
                if args.repair_needs_rebuild:
                    steps["saveActiveBeforeReopen"] = client.call_tool(
                        "save_document", {"path": str(assembly)}
                    )
                    saved_active_before_reopen_hash = sha256_file(assembly)
                steps["closeBefore"] = client.call_tool_text(
                    "close_document", {"path": str(assembly)}
                )
            steps["opened"] = client.call_tool("open_document", {"path": str(assembly)})
            try:
                steps["activated"] = client.call_tool(
                    "activate_document_by_title", {"title": assembly.stem}
                )
            except RuntimeError as exc:
                if "Unknown tool" not in str(exc):
                    raise
                steps["activated"] = {"unsupported": True}
            poses = client.call_tool("list_component_poses", {"topLevelOnly": True})
            rebuild = client.call_tool("get_active_document_rebuild_state", {})
            steps["initialRebuildState"] = rebuild
            repair_applied = False
            saved_hash_after_repair = None
            if args.repair_needs_rebuild and rebuild.get(
                "NeedsRebuild", rebuild.get("needsRebuild")
            ) is True:
                repair_applied = True
                steps["forceRebuild"] = client.call_tool(
                    "force_rebuild_active_document", {"topOnly": False}
                )
                steps["rebuildStateAfterForce"] = client.call_tool(
                    "get_active_document_rebuild_state", {}
                )
                steps["saveAfterForce"] = client.call_tool(
                    "save_document", {"path": str(assembly)}
                )
                saved_hash_after_repair = sha256_file(assembly)
                steps["closeForSecondOpen"] = client.call_tool_text(
                    "close_document", {"path": str(assembly)}
                )
                steps["secondOpen"] = client.call_tool(
                    "open_document", {"path": str(assembly)}
                )
                try:
                    steps["secondActivate"] = client.call_tool(
                        "activate_document_by_title", {"title": assembly.stem}
                    )
                except RuntimeError as exc:
                    if "Unknown tool" not in str(exc):
                        raise
                    steps["secondActivate"] = {"unsupported": True}
                poses = client.call_tool("list_component_poses", {"topLevelOnly": True})
                rebuild = client.call_tool("get_active_document_rebuild_state", {})
            steps["rebuildState"] = rebuild
            if screenshot:
                steps["screenshot"] = client.call_tool(
                    "export_current_view_png",
                    {
                        "outputPath": str(screenshot),
                        "width": 1600,
                        "height": 900,
                        "includeBase64Data": False,
                    },
                )
            steps["closeAfter"] = client.call_tool_text(
                "close_document", {"path": str(assembly)}
            )
            if args.exit_solidworks:
                steps["exitSolidWorks"] = client.call_tool(
                    "exit_solid_works", {"confirmAllDocumentsSaved": True}
                )

    names = {
        str(item.get("Name", item.get("name", "")))
        for item in poses
        if isinstance(item, dict)
    }
    missing = sorted(set(args.expected_component) - names)
    file_hash_after = sha256_file(assembly)
    file_hash_stable = (
        file_hash_after == saved_hash_after_repair
        if repair_applied and saved_hash_after_repair
        else (
            file_hash_after == saved_active_before_reopen_hash
            if saved_active_before_reopen_hash
            else file_hash_before == file_hash_after
        )
    )
    success = (
        bool(poses)
        and not missing
        and rebuild_is_healthy(rebuild)
        and file_hash_stable
        and (screenshot is None or screenshot.is_file())
    )
    timing_payload = timing.finish(status="completed" if success else "failed")
    payload = {
        "schemaVersion": "saved-assembly-reopen-verification/v1",
        "success": success,
        "status": "PASS_FINAL_REOPENED_ASSEMBLY_HEALTH" if success else "FAIL_FINAL_REOPENED_ASSEMBLY_HEALTH",
        "assemblyPath": str(assembly),
        "assemblySha256Before": file_hash_before,
        "assemblySha256After": file_hash_after,
        "assemblyChangedDuringVerification": file_hash_before != file_hash_after,
        "fileHashStableAfterLastSave": file_hash_stable,
        "repairNeedsRebuildRequested": args.repair_needs_rebuild,
        "repairNeedsRebuildApplied": repair_applied,
        "assemblySha256AfterRepairSave": saved_hash_after_repair,
        "assemblySha256AfterActiveSave": saved_active_before_reopen_hash,
        "componentCount": len(poses),
        "expectedComponents": args.expected_component,
        "missingExpectedComponents": missing,
        "components": poses,
        "rebuildState": rebuild,
        "screenshotPath": str(screenshot) if screenshot else None,
        "steps": steps,
        "timing": timing_payload,
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: payload[key] for key in ("success", "status", "componentCount", "missingExpectedComponents", "screenshotPath", "timing")}, ensure_ascii=False, indent=2))
    return 0 if success else 2


if __name__ == "__main__":
    raise SystemExit(main())
