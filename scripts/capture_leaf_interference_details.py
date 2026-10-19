#!/usr/bin/env python3
"""Capture detailed leaf-body B-Rep interference records for selected module pairs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

from capture_assembly_entity_annotations import McpClient


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.pipeline_timing import PipelineTiming, utc_now_iso  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", required=True, type=Path)
    parser.add_argument("--assembly", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--pair", action="append", nargs=2, metavar=("FIRST", "SECOND"), required=True)
    parser.add_argument("--timeout", type=float, default=1800.0)
    parser.add_argument("--force-new-instance", action="store_true")
    parser.add_argument(
        "--reuse-existing",
        action="store_true",
        help="Reuse complete per-pair JSON files and only recheck missing or incomplete pairs.",
    )
    parser.add_argument(
        "--direct-stdio",
        action="store_true",
        help="Run the MCP app directly instead of routing through the background Hub proxy.",
    )
    parser.add_argument(
        "--stop-on-first-interference",
        action="store_true",
        help=(
            "Stop after the first pair that fails its acceptance policy. A pair with an "
            "accepted baseline continues when it introduces no new leaf-body interference."
        ),
    )
    parser.add_argument(
        "--accepted-baseline",
        action="append",
        nargs=3,
        metavar=("FIRST", "SECOND", "BASELINE_JSON"),
        default=[],
        help=(
            "Accept prototype-existing contact for one module pair. The candidate must have "
            "a complete exact check and may not add a leaf-body interference outside BASELINE_JSON."
        ),
    )
    parser.add_argument(
        "--exit-solidworks-after-check",
        action="store_true",
        help=(
            "After durable results are written, call the MCP lifecycle tool to "
            "exit the SolidWorks instance used by this isolated batch."
        ),
    )
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def component_code(hierarchy_path: str) -> str:
    name = hierarchy_path.split("/")[0]
    marker = "D062A"
    if marker in name:
        suffix = name.split(marker, 1)[1]
        return "A" + suffix.split(".", 1)[0]
    # Non-A-series components can have multiple top-level occurrences. Keep
    # the occurrence suffix (for example T401...-1 versus T401...-2), otherwise
    # per-pair evidence files collide and --reuse-existing can silently reuse
    # the wrong instance's result.
    return name.replace(".001-1", "")


def pair_output_path(
    output_dir: Path,
    assembly_stem: str,
    first: str,
    second: str,
    *,
    max_path_chars: int = 240,
) -> Path:
    """Return a deterministic evidence path that remains usable on Windows.

    Most existing module names are short enough to keep the historical,
    human-readable file name.  Static replacement assemblies can have much
    longer occurrence names, however, and the full output path can exceed the
    traditional Windows path limit only *after* an expensive CAD check has
    completed.  In that case use compact readable prefixes plus a hash of the
    complete pair identity.  The hash keeps two long names from silently
    colliding while preserving the old names for all current short paths.
    """

    first_code = component_code(first)
    second_code = component_code(second)
    readable = output_dir / (
        f"{assembly_stem}_leaf_details_{first_code}_{second_code}.json"
    )
    if len(str(readable)) <= max_path_chars:
        return readable

    digest = hashlib.sha256(
        json.dumps(
            [assembly_stem, first, second],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:12]
    compact_first = first_code[:16]
    compact_second = second_code[:16]
    return output_dir / (
        f"pair_{compact_first}_{compact_second}_{digest}.json"
    )


def module_pair_key(first: str, second: str) -> tuple[str, str]:
    return tuple(sorted((str(first), str(second))))


def component_interference_identity(component: dict[str, object]) -> str:
    """Build a copy-location-stable identity for one interfering leaf occurrence.

    Replacing or saving a parent subassembly changes every hierarchy prefix even
    when the physical leaf part and its occurrence suffix are unchanged.  The
    B-rep baseline therefore keys a leaf by the source *file name* plus terminal
    occurrence name.  The same vendor part may be copied under two project
    directories or resolved through a shared-library location; an absolute path
    would turn an unchanged logical contact into a false added/missing pair.
    Geometry revisions are guarded separately by the pair-cache source hashes.
    The full hierarchy is used only when the bridge provides no source path.
    """

    full_name = str(component.get("Name", component.get("name", "")))
    leaf_name = full_name.rsplit("/", 1)[-1].casefold()
    source_path = str(component.get("Path", component.get("path", ""))).strip()
    if source_path:
        source_file = source_path.replace("/", "\\").rsplit("\\", 1)[-1].casefold()
        return f"{source_file}|{leaf_name}"
    return full_name.casefold()


def interfering_leaf_pair_set(payload: dict[str, object]) -> set[tuple[str, str]]:
    result: set[tuple[str, str]] = set()
    raw_pairs = payload.get("InterferingBodyPairs", payload.get("interferingBodyPairs", []))
    for item in raw_pairs if isinstance(raw_pairs, list) else []:
        if not isinstance(item, dict):
            continue
        first = item.get("FirstComponent", item.get("firstComponent"))
        second = item.get("SecondComponent", item.get("secondComponent"))
        if not isinstance(first, dict) or not isinstance(second, dict):
            continue
        first_name = component_interference_identity(first)
        second_name = component_interference_identity(second)
        if first_name and second_name:
            result.add(tuple(sorted((first_name, second_name))))
    return result


def _terminal_leaf_pair(first: str, second: str) -> tuple[str, str]:
    return tuple(sorted((first.rsplit("/", 1)[-1].casefold(), second.rsplit("/", 1)[-1].casefold())))


def failed_leaf_pair_set(payload: dict[str, object]) -> set[tuple[str, str]]:
    result: set[tuple[str, str]] = set()
    failures = payload.get("Failures", payload.get("failures", []))
    for raw in failures if isinstance(failures, list) else []:
        pair_text = str(raw).rsplit(": ", 1)[0]
        parts = pair_text.split(" <-> ")
        if len(parts) == 2 and all(part.strip() for part in parts):
            result.add(_terminal_leaf_pair(parts[0].strip(), parts[1].strip()))
    return result


def fallback_leaf_pair_set(payload: dict[str, object]) -> set[tuple[str, str]]:
    result: set[tuple[str, str]] = set()
    rows = payload.get("results", payload.get("Results", []))
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        paths = row.get("hierarchyPaths", row.get("HierarchyPaths", []))
        if isinstance(paths, list) and len(paths) == 2:
            result.add(_terminal_leaf_pair(str(paths[0]), str(paths[1])))
    return result


def fallback_interfering_leaf_pair_set(
    payload: dict[str, object],
) -> set[tuple[str, str]]:
    """Return failed leaf pairs that the official fallback found interfering.

    The low-level B-rep runner records a failed leaf pair by hierarchy path but
    cannot provide the usual source-file identity.  The official SolidWorks
    fallback checks that exact pair and therefore uses the terminal occurrence
    names as the common identity shared by both records.
    """

    result: set[tuple[str, str]] = set()
    rows = payload.get("results", payload.get("Results", []))
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        success = row.get("success", row.get("Success")) is True
        interferes = row.get("hasInterference", row.get("HasInterference")) is True
        paths = row.get("hierarchyPaths", row.get("HierarchyPaths", []))
        if success and interferes and isinstance(paths, list) and len(paths) == 2:
            result.add(_terminal_leaf_pair(str(paths[0]), str(paths[1])))
    return result


def _identity_pair_to_terminal_pair(pair: tuple[str, str]) -> tuple[str, str]:
    terminals = []
    for identity in pair:
        occurrence = identity.rsplit("|", 1)[-1]
        terminals.append(occurrence.rsplit("/", 1)[-1].casefold())
    return tuple(sorted(terminals))


def fallback_resolves_all_failures(
    exact_result: dict[str, object], fallback_result: dict[str, object] | None
) -> dict[str, object]:
    failed_pairs = failed_leaf_pair_set(exact_result)
    if not failed_pairs:
        return {
            "required": False,
            "resolved": True,
            "failedPairCount": 0,
            "fallbackPairCount": 0,
        }
    rows = []
    if isinstance(fallback_result, dict):
        raw_rows = fallback_result.get("results", fallback_result.get("Results", []))
        rows = raw_rows if isinstance(raw_rows, list) else []
    fallback_pairs = fallback_leaf_pair_set(fallback_result or {})
    all_rows_successful = bool(rows) and all(
        isinstance(row, dict)
        and row.get("success", row.get("Success")) is True
        for row in rows
    )
    resolved = (
        isinstance(fallback_result, dict)
        and fallback_result.get("success", fallback_result.get("Success")) is True
        and all_rows_successful
        and fallback_pairs == failed_pairs
    )
    interfering_pairs = fallback_interfering_leaf_pair_set(fallback_result or {})
    return {
        "required": True,
        "resolved": resolved,
        "failedPairCount": len(failed_pairs),
        "fallbackPairCount": len(fallback_pairs),
        "failedPairs": sorted(failed_pairs),
        "fallbackPairs": sorted(fallback_pairs),
        "fallbackInterferingPairs": sorted(interfering_pairs),
        "fallbackClearPairCount": len(fallback_pairs - interfering_pairs),
        "fallbackInterferingPairCount": len(interfering_pairs),
    }


def baseline_acceptance(
    candidate: dict[str, object],
    baseline: dict[str, object] | None,
    *,
    candidate_fallback: dict[str, object] | None = None,
    baseline_fallback: dict[str, object] | None = None,
) -> dict[str, object]:
    exact_complete = candidate.get(
        "ExactCheckComplete", candidate.get("exactCheckComplete")
    ) is True
    failed_count = int(
        candidate.get("FailedBodyPairCount", candidate.get("failedBodyPairCount", 0))
        or 0
    )
    candidate_fallback_status = fallback_resolves_all_failures(candidate, candidate_fallback)
    candidate_effectively_complete = exact_complete or (
        failed_count > 0 and candidate_fallback_status["resolved"] is True
    )
    candidate_pairs = interfering_leaf_pair_set(candidate)
    candidate_fallback_positive = fallback_interfering_leaf_pair_set(
        candidate_fallback or {}
    )
    if baseline is None:
        accepted = (
            candidate_effectively_complete
            and not candidate_pairs
            and not candidate_fallback_positive
        )
        return {
            "policy": (
                "zeroInterferenceWithOfficialFallback"
                if failed_count
                else "zeroInterference"
            ),
            "accepted": accepted,
            "rawExactCheckComplete": exact_complete,
            "effectiveExactCheckComplete": candidate_effectively_complete,
            "candidateFailureFallback": candidate_fallback_status,
            "candidateInterferingPairCount": len(candidate_pairs),
            "addedInterferingPairs": sorted(candidate_pairs),
            "candidateFallbackInterferingPairs": sorted(
                candidate_fallback_positive
            ),
        }

    baseline_exact_complete = baseline.get(
        "ExactCheckComplete", baseline.get("exactCheckComplete")
    ) is True
    baseline_failed_count = int(
        baseline.get("FailedBodyPairCount", baseline.get("failedBodyPairCount", 0))
        or 0
    )
    baseline_fallback_status = fallback_resolves_all_failures(baseline, baseline_fallback)
    baseline_effectively_complete = baseline_exact_complete or (
        baseline_failed_count > 0 and baseline_fallback_status["resolved"] is True
    )
    baseline_pairs = interfering_leaf_pair_set(baseline)
    baseline_fallback_positive = fallback_interfering_leaf_pair_set(
        baseline_fallback or {}
    )
    candidate_exact_terminals = {
        _identity_pair_to_terminal_pair(pair) for pair in candidate_pairs
    }
    baseline_exact_terminals = {
        _identity_pair_to_terminal_pair(pair) for pair in baseline_pairs
    }
    added_exact = {
        pair
        for pair in candidate_pairs - baseline_pairs
        if _identity_pair_to_terminal_pair(pair) not in baseline_fallback_positive
    }
    missing_exact = {
        pair
        for pair in baseline_pairs - candidate_pairs
        if _identity_pair_to_terminal_pair(pair) not in candidate_fallback_positive
    }
    added_fallback = candidate_fallback_positive - (
        baseline_exact_terminals | baseline_fallback_positive
    )
    missing_fallback = baseline_fallback_positive - (
        candidate_exact_terminals | candidate_fallback_positive
    )
    added = sorted(added_exact) + [
        (f"fallback-terminal:{first}", f"fallback-terminal:{second}")
        for first, second in sorted(added_fallback)
    ]
    missing = sorted(missing_exact) + [
        (f"fallback-terminal:{first}", f"fallback-terminal:{second}")
        for first, second in sorted(missing_fallback)
    ]
    accepted = (
        candidate_effectively_complete
        and baseline_effectively_complete
        and not added
    )
    return {
        "policy": (
            "noNewInterferenceOverAcceptedBaselineWithOfficialFallback"
            if failed_count or baseline_failed_count
            else "noNewInterferenceOverAcceptedBaseline"
        ),
        "accepted": accepted,
        "rawExactCheckComplete": exact_complete,
        "effectiveExactCheckComplete": candidate_effectively_complete,
        "candidateFailureFallback": candidate_fallback_status,
        "baselineExactCheckComplete": baseline_exact_complete,
        "baselineEffectiveExactCheckComplete": baseline_effectively_complete,
        "baselineFailedBodyPairCount": baseline_failed_count,
        "baselineFailureFallback": baseline_fallback_status,
        "baselineInterferingPairCount": len(baseline_pairs),
        "candidateInterferingPairCount": len(candidate_pairs),
        "candidateFallbackInterferingPairs": sorted(
            candidate_fallback_positive
        ),
        "baselineFallbackInterferingPairs": sorted(
            baseline_fallback_positive
        ),
        "addedInterferingPairs": added,
        "missingBaselinePairs": missing,
    }


def batch_exit_code(payload: dict[str, object]) -> int:
    """Return a process status that agrees with the durable gate result.

    The JSON batch remains the source of detailed evidence, while the exit code
    lets shell pipelines stop immediately instead of treating a rejected CAD
    candidate as a successful zero-interference check.
    """

    return 0 if int(payload.get("hardFailureCount") or 0) == 0 else 2


def main() -> int:
    timing = PipelineTiming("project02.conditional-leaf-brep")
    args = parse_args()
    exe = args.exe.resolve()
    assembly = args.assembly.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    assembly_sha256_before = sha256_file(assembly)

    accepted_baselines: dict[tuple[str, str], tuple[Path, dict[str, object]]] = {}
    for first, second, raw_path in args.accepted_baseline:
        baseline_path = Path(raw_path)
        if not baseline_path.is_absolute():
            baseline_path = ROOT / baseline_path
        baseline_path = baseline_path.resolve()
        if not baseline_path.exists():
            raise FileNotFoundError(f"Accepted interference baseline does not exist: {baseline_path}")
        accepted_baselines[module_pair_key(first, second)] = (
            baseline_path,
            json.loads(baseline_path.read_text(encoding="utf-8")),
        )

    if args.force_new_instance:
        os.environ["SOLIDWORKS_MCP_FORCE_NEW_INSTANCE"] = "1"

    batch: list[dict[str, object]] = []
    with McpClient(
        exe,
        "CodexLeafInterferenceDetails",
        args.timeout,
        "newline" if args.direct_stdio else "content-length",
        direct_stdio=args.direct_stdio,
    ) as client:
        try:
            active = client.call_tool("get_active_document", {})
        except RuntimeError:
            active = None
        active_path = (
            active.get("Path", active.get("path"))
            if isinstance(active, dict)
            else None
        )
        target_was_active = bool(
            active_path and Path(str(active_path)).resolve() == assembly
        )
        if target_was_active:
            opened = {
                "reusedAlreadyOpenDocument": True,
                "document": active,
            }
        else:
            opened = client.call_tool("open_document", {"path": str(assembly)})
        # SolidWorks may leave a leaf document active when the same parent assembly is
        # already open in an in-context edit session.  Leaf hierarchy resolution must run
        # against the parent assembly.  Some validated MCP builds do not expose the
        # optional activate_document_by_title tool, so avoid calling it when the target
        # was already active and fall back to a path verification after OpenDocument.
        if not target_was_active:
            try:
                client.call_tool(
                    "activate_document_by_title", {"title": assembly.stem}
                )
            except RuntimeError as exc:
                if "Unknown tool" not in str(exc):
                    raise
                current = client.call_tool("get_active_document", {})
                current_path = (
                    current.get("Path", current.get("path"))
                    if isinstance(current, dict)
                    else None
                )
                if not current_path or Path(str(current_path)).resolve() != assembly:
                    raise RuntimeError(
                        "The MCP build has no activate_document_by_title tool and "
                        "OpenDocument did not leave the requested assembly active."
                    ) from exc
        for first, second in args.pair:
            pair_started_at = utc_now_iso()
            pair_started = time.perf_counter()
            output_path = pair_output_path(
                output_dir,
                assembly.stem,
                first,
                second,
            )
            result: dict[str, object] | None = None
            reused_existing_result = False
            if args.reuse_existing and output_path.exists():
                candidate = json.loads(output_path.read_text(encoding="utf-8"))
                if candidate.get("ExactCheckComplete", candidate.get("exactCheckComplete")) is True:
                    result = candidate
                    reused_existing_result = True
            if result is None:
                result = client.call_tool(
                    "check_interference_by_leaf_bodies",
                    {
                        "hierarchyPaths": [first, second],
                        "treatCoincidenceAsInterference": False,
                    },
                )
                result["timing"] = {
                    "startedAtUtc": pair_started_at,
                    "finishedAtUtc": utc_now_iso(),
                    "durationSeconds": round(time.perf_counter() - pair_started, 6),
                    "reusedExistingResult": False,
                }
                output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            pair_timing = {
                "startedAtUtc": pair_started_at,
                "finishedAtUtc": utc_now_iso(),
                "durationSeconds": round(time.perf_counter() - pair_started, 6),
                "reusedExistingResult": reused_existing_result,
            }
            baseline_entry = accepted_baselines.get(module_pair_key(first, second))
            acceptance = baseline_acceptance(
                result,
                baseline_entry[1] if baseline_entry else None,
            )
            if baseline_entry:
                acceptance["baselinePath"] = str(baseline_entry[0])
            batch.append(
                {
                    "pair": [first, second],
                    "outputPath": str(output_path),
                    "hasInterference": result.get("HasInterference", result.get("hasInterference")),
                    "interferingBodyPairCount": result.get(
                        "InterferingBodyPairCount", result.get("interferingBodyPairCount")
                    ),
                    "failedBodyPairCount": result.get(
                        "FailedBodyPairCount", result.get("failedBodyPairCount", 0)
                    ),
                    "exactCheckComplete": result.get("ExactCheckComplete", result.get("exactCheckComplete")),
                    "acceptance": acceptance,
                    "timing": pair_timing,
                }
            )
            if args.stop_on_first_interference and acceptance["accepted"] is not True:
                break
        batch_path = output_dir / f"{assembly.stem}_leaf_details_batch.json"
        stopped_early = len(batch) < len(args.pair)
        assembly_sha256_after = sha256_file(assembly)
        assembly_changed_during_check = assembly_sha256_before != assembly_sha256_after
        payload: dict[str, object] = {
            "assemblyPath": str(assembly),
            "assemblySha256Before": assembly_sha256_before,
            "assemblySha256After": assembly_sha256_after,
            "assemblyChangedDuringCheck": assembly_changed_during_check,
            "opened": opened,
            "pairs": batch,
            "requestedPairCount": len(args.pair),
            "completedPairCount": len(batch),
            "stopOnFirstInterference": args.stop_on_first_interference,
            "stoppedEarly": stopped_early,
            "acceptedPairCount": sum(
                item.get("acceptance", {}).get("accepted") is True for item in batch
            ),
            "hardFailureCount": sum(
                item.get("acceptance", {}).get("accepted") is not True for item in batch
            ) + (1 if assembly_changed_during_check else 0),
        }
        batch_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            client.call_tool_text("close_document", {"path": str(assembly)})
        except RuntimeError as exc:
            # The diagnostic results are already durable. A read-only/sharing-violation
            # close failure must not turn a completed interference check into a failure.
            payload["closeWarning"] = str(exc)
            batch_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        if args.exit_solidworks_after_check:
            exit_result = client.call_tool(
                "exit_solid_works",
                {"confirmAllDocumentsSaved": True},
            )
            payload["solidWorksExit"] = exit_result
            batch_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        payload["timing"] = timing.finish()
        batch_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    print(batch_path)
    return batch_exit_code(payload)


if __name__ == "__main__":
    raise SystemExit(main())
