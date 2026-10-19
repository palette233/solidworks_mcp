#!/usr/bin/env python3
"""Clone an assembly, replace one top-level component, set it rigid, and verify reopen."""

from __future__ import annotations

import argparse
from collections import Counter
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter


sys.path.insert(0, str(Path(__file__).resolve().parent))
from capture_assembly_entity_annotations import McpClient


def open_needs_regen(payload: dict) -> bool:
    """Return whether an open-document result contains SolidWorks' NeedsRegen warning."""
    diagnostics = payload.get("Diagnostics", payload.get("diagnostics", {}))
    if not isinstance(diagnostics, dict):
        return False
    warnings = diagnostics.get("Warnings", diagnostics.get("warnings", []))
    return any(
        isinstance(item, dict)
        and str(item.get("Name", item.get("name", ""))).casefold()
        == "swfileloadwarning_needsregen"
        for item in warnings
    )


def rebuild_state_is_healthy(payload: dict) -> bool:
    needs_rebuild = payload.get("NeedsRebuild", payload.get("needsRebuild"))
    summary = str(payload.get("Summary", payload.get("summary", ""))).casefold()
    return needs_rebuild is not True and "error" not in summary and "failed" not in summary


def health_issue_counts(payload: dict) -> Counter[tuple[int, str, bool]]:
    health = payload.get("health", payload)
    actionable = health.get("ActionableDiagnostics", health.get("actionableDiagnostics", {}))
    issues = actionable.get("CurrentIssues", actionable.get("currentIssues", []))
    return Counter(
        (
            int(item.get("ErrorCode", item.get("errorCode", -1))),
            str(item.get("ErrorName", item.get("errorName", ""))),
            bool(item.get("IsWarning", item.get("isWarning", False))),
        )
        for item in issues
        if isinstance(item, dict)
    )


def baseline_health_allows(candidate: dict, baseline: dict) -> bool:
    candidate_health = candidate.get("health", candidate)
    baseline_health = baseline.get("health", baseline)
    candidate_rebuild = candidate_health.get("Rebuild", candidate_health.get("rebuild", {}))
    candidate_after = candidate_rebuild.get("StatusAfter", candidate_rebuild.get("statusAfter", {}))
    candidate_ready = candidate_health.get(
        "ReadyForVerificationGate", candidate_health.get("readyForVerificationGate")
    )
    candidate_blocking = candidate_health.get(
        "HasBlockingIssues", candidate_health.get("hasBlockingIssues")
    )
    baseline_ready = baseline_health.get(
        "ReadyForVerificationGate", baseline_health.get("readyForVerificationGate")
    )
    baseline_blocking = baseline_health.get(
        "HasBlockingIssues", baseline_health.get("hasBlockingIssues")
    )
    candidate_counts = health_issue_counts(candidate_health)
    baseline_counts = health_issue_counts(baseline_health)
    issues_are_baseline_subset = all(
        count <= baseline_counts[signature]
        for signature, count in candidate_counts.items()
    )
    return bool(
        candidate_ready is True
        and candidate_blocking is False
        and baseline_ready is True
        and baseline_blocking is False
        and rebuild_state_is_healthy(candidate_after)
        and issues_are_baseline_subset
    )


def select_unique(rows: list[dict], selector: str) -> dict:
    matches = [row for row in rows if selector.casefold() in str(row.get("Name", "")).casefold()]
    if len(matches) != 1:
        raise RuntimeError(f"Selector {selector!r} resolved to {len(matches)} top-level components")
    return matches[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--component", required=True)
    parser.add_argument("--replacement", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--baseline-health", type=Path)
    parser.add_argument("--timeout", type=float, default=1800.0)
    args = parser.parse_args()

    source = args.source.resolve()
    output = args.output.resolve()
    replacement = args.replacement.resolve()
    result_path = args.result.resolve()
    baseline_health_path = args.baseline_health.resolve() if args.baseline_health else None
    required_paths = [args.exe.resolve(), source, replacement]
    if baseline_health_path is not None:
        required_paths.append(baseline_health_path)
    for required in required_paths:
        if not required.is_file():
            raise FileNotFoundError(required)
    if output.exists() or result_path.exists():
        raise FileExistsError(f"Refusing to overwrite: {output} | {result_path}")
    output.parent.mkdir(parents=True, exist_ok=True)
    result_path.parent.mkdir(parents=True, exist_ok=True)

    started = perf_counter()
    payload: dict = {
        "schemaVersion": "top-level-component-replacement-run/v1",
        "success": False,
        "startedAtUtc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sourceAssemblyPath": str(source),
        "outputAssemblyPath": str(output),
        "componentSelector": args.component,
        "replacementFilePath": str(replacement),
        "phaseDurationsSeconds": {},
    }
    phases: dict[str, float] = payload["phaseDurationsSeconds"]

    def timed(name: str, call):
        phase_started = perf_counter()
        try:
            return call()
        finally:
            phases[name] = round(perf_counter() - phase_started, 6)

    with McpClient(
        args.exe.resolve(),
        "ReplaceTopLevelAndSetRigid",
        args.timeout,
        "newline",
        direct_stdio=True,
    ) as client:
        timed("connect", lambda: client.call_tool("solid_works_connect", {}))
        payload["opened"] = timed(
            "open-source", lambda: client.call_tool("open_document", {"path": str(source)})
        )
        payload["savedCopy"] = timed(
            "save-working-copy",
            lambda: client.call_tool(
                "save_document_as", {"outputPath": str(output), "saveAsCopy": False}
            ),
        )
        before = timed(
            "capture-before",
            lambda: select_unique(
                client.call_tool("list_component_poses", {"topLevelOnly": True}),
                args.component,
            ),
        )
        payload["before"] = before
        payload["replacement"] = timed(
            "replace-component",
            lambda: client.call_tool(
                "replace_component",
                {
                    "hierarchyPath": before["HierarchyPath"],
                    "replacementFilePath": str(replacement),
                    "replaceAllInstances": False,
                    "reattachMates": True,
                },
            ),
        )
        after_replace = timed(
            "capture-after-replace",
            lambda: select_unique(
                client.call_tool("list_component_poses", {"topLevelOnly": True}),
                replacement.stem,
            ),
        )
        payload["solveAsRigid"] = timed(
            "set-rigid-and-rebuild",
            lambda: client.call_tool(
                "set_top_level_component_solving_state",
                {
                    "hierarchyPath": after_replace["HierarchyPath"],
                    "solvingState": 0,
                    "rebuild": True,
                },
            ),
        )
        payload["saved"] = timed(
            "save", lambda: client.call_tool("save_document", {"path": str(output)})
        )
        timed("close-before-reopen", lambda: client.call_tool_text("close_document", {"path": str(output)}))
        payload["reopened"] = timed(
            "reopen", lambda: client.call_tool("open_document", {"path": str(output)})
        )
        payload["initialReopenNeedsRegen"] = open_needs_regen(payload["reopened"])
        payload["rebuildStateAfterInitialReopen"] = timed(
            "rebuild-state-after-initial-reopen",
            lambda: client.call_tool("get_active_document_rebuild_state", {}),
        )
        payload["repairNeedsRegenApplied"] = False
        if payload["initialReopenNeedsRegen"] or not rebuild_state_is_healthy(
            payload["rebuildStateAfterInitialReopen"]
        ):
            payload["repairNeedsRegenApplied"] = True
            payload["repairForceRebuild"] = timed(
                "repair-force-rebuild",
                lambda: client.call_tool(
                    "force_rebuild_active_document", {"topOnly": False}
                ),
            )
            payload["repairRebuildStateBeforeSave"] = timed(
                "repair-rebuild-state-before-save",
                lambda: client.call_tool("get_active_document_rebuild_state", {}),
            )
            payload["repairSaved"] = timed(
                "repair-save",
                lambda: client.call_tool("save_document", {"path": str(output)}),
            )
            timed(
                "repair-close-before-second-reopen",
                lambda: client.call_tool_text("close_document", {"path": str(output)}),
            )
            payload["reopenedAfterRepair"] = timed(
                "repair-second-reopen",
                lambda: client.call_tool("open_document", {"path": str(output)}),
            )
            payload["finalOpen"] = payload["reopenedAfterRepair"]
        else:
            payload["finalOpen"] = payload["reopened"]
        payload["finalOpenNeedsRegen"] = open_needs_regen(payload["finalOpen"])
        payload["finalRebuildState"] = timed(
            "final-rebuild-state",
            lambda: client.call_tool("get_active_document_rebuild_state", {}),
        )
        payload["healthAcceptance"] = {
            "policy": "absolute_clean_reopen",
            "accepted": (
                payload["finalOpenNeedsRegen"] is False
                and rebuild_state_is_healthy(payload["finalRebuildState"])
            ),
            "baselineHealthPath": str(baseline_health_path) if baseline_health_path else None,
        }
        if not payload["healthAcceptance"]["accepted"] and baseline_health_path:
            payload["candidateHealthDiagnostics"] = timed(
                "baseline-relative-health-diagnostics",
                lambda: client.call_tool(
                    "diagnose_active_document_health",
                    {"forceRebuild": True, "topOnly": False, "saveDocument": False},
                ),
            )
            baseline_health = json.loads(
                baseline_health_path.read_text(encoding="utf-8-sig")
            )
            payload["healthAcceptance"] = {
                "policy": "baseline_equivalent_nonblocking_health",
                "accepted": baseline_health_allows(
                    payload["candidateHealthDiagnostics"], baseline_health
                ),
                "baselineHealthPath": str(baseline_health_path),
                "candidateIssueCounts": [
                    {"signature": list(signature), "count": count}
                    for signature, count in sorted(
                        health_issue_counts(payload["candidateHealthDiagnostics"]).items()
                    )
                ],
                "baselineIssueCounts": [
                    {"signature": list(signature), "count": count}
                    for signature, count in sorted(health_issue_counts(baseline_health).items())
                ],
            }
        reopened = timed(
            "verify-reopened-component",
            lambda: select_unique(
                client.call_tool("list_component_poses", {"topLevelOnly": True}),
                replacement.stem,
            ),
        )
        payload["reopenedComponent"] = reopened
        timed("close-final", lambda: client.call_tool_text("close_document", {"path": str(output)}))

    payload["success"] = bool(
        payload["replacement"].get("Success") is True
        and payload["solveAsRigid"].get("Success") is True
        and int(reopened.get("SolvingState", -1)) == 0
        and Path(str(reopened.get("Path") or "")).resolve() == replacement
        and payload["healthAcceptance"]["accepted"] is True
    )
    payload["durationSeconds"] = round(perf_counter() - started, 6)
    payload["completedAtUtc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    result_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"success": payload["success"], "result": str(result_path)}, ensure_ascii=False))
    return 0 if payload["success"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
