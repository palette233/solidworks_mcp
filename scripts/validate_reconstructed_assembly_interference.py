#!/usr/bin/env python3
"""Independently validate interference in a reconstructed SolidWorks assembly.

Every top-level module pair is first screened by its saved world AABB.  A pair
whose AABBs are strictly separated cannot contain intersecting solids.  Only
the remaining broad-phase candidates are submitted to the SolidWorks modeler
for transformed leaf-body B-rep checks.  Progress is persisted after every
pair so an interrupted, expensive CAD run can be resumed.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import itertools
import json
import math
import os
from pathlib import Path
import time

from capture_assembly_entity_annotations import McpClient


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", required=True, type=Path)
    parser.add_argument("--assembly", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=3600.0)
    parser.add_argument("--direct-stdio", action="store_true")
    parser.add_argument("--force-new-instance", action="store_true")
    parser.add_argument("--broad-phase-only", action="store_true")
    parser.add_argument("--reuse-existing", action="store_true")
    parser.add_argument(
        "--aabb-tolerance-meters",
        type=float,
        default=1e-8,
        help="Positive overlap no larger than this tolerance is treated as contact, not penetration.",
    )
    return parser.parse_args()


def get_value(item: dict, pascal: str, camel: str):
    return item.get(pascal, item.get(camel))


def component_name(item: dict) -> str:
    return str(get_value(item, "HierarchyPath", "hierarchyPath") or get_value(item, "Name", "name") or "")


def component_box(item: dict) -> list[float]:
    raw = get_value(item, "BoundingBoxWorld", "boundingBoxWorld")
    if not isinstance(raw, list) or len(raw) != 6:
        raise ValueError(f"Component '{component_name(item)}' has no six-value BoundingBoxWorld")
    return [float(value) for value in raw]


def pair_key(first: str, second: str) -> str:
    return "||".join(sorted((first, second), key=str.casefold))


def broad_phase(first_name: str, first: list[float], second_name: str, second: list[float], tolerance: float) -> dict:
    signed_overlaps = [
        min(first[axis + 3], second[axis + 3]) - max(first[axis], second[axis])
        for axis in range(3)
    ]
    gaps = [max(first[axis] - second[axis + 3], second[axis] - first[axis + 3], 0.0) for axis in range(3)]
    candidate = all(value > tolerance for value in signed_overlaps)
    return {
        "pair": [first_name, second_name],
        "pairKey": pair_key(first_name, second_name),
        "axisSignedOverlapMeters": signed_overlaps,
        "axisGapMeters": gaps,
        "minimumAabbDistanceMeters": math.sqrt(sum(value * value for value in gaps)),
        "intersectionBoxVolumeCubicMeters": math.prod(signed_overlaps) if candidate else 0.0,
        "requiresExactLeafBrep": candidate,
        "broadPhaseStatus": "CANDIDATE_FOR_EXACT_BREP" if candidate else "PROVEN_SEPARATED_OR_CONTACT_ONLY",
    }


def exact_complete(result: dict) -> bool:
    return get_value(result, "ExactCheckComplete", "exactCheckComplete") is True


def interference_count(result: dict) -> int:
    return int(get_value(result, "InterferingBodyPairCount", "interferingBodyPairCount") or 0)


def failed_count(result: dict) -> int:
    return int(get_value(result, "FailedBodyPairCount", "failedBodyPairCount") or 0)


def persist(output: Path, payload: dict) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    exe = args.exe.resolve()
    assembly = args.assembly.resolve()
    output = args.output.resolve()
    if args.force_new_instance:
        os.environ["SOLIDWORKS_MCP_FORCE_NEW_INSTANCE"] = "1"

    started_at = utc_now()
    started = time.perf_counter()
    previous_exact: dict[str, dict] = {}
    if args.reuse_existing and output.exists():
        previous = json.loads(output.read_text(encoding="utf-8-sig"))
        for row in previous.get("exactChecks") or []:
            if isinstance(row, dict) and row.get("pairKey") and row.get("result") and exact_complete(row["result"]):
                previous_exact[str(row["pairKey"])] = row

    opened_by_script = False
    close_warning = None
    with McpClient(
        exe,
        "CodexReconstructedAssemblyInterferenceValidation",
        args.timeout,
        "newline" if args.direct_stdio else "content-length",
        direct_stdio=args.direct_stdio,
    ) as client:
        active = None
        try:
            active = client.call_tool("get_active_document", {})
        except RuntimeError:
            pass
        active_path = str(get_value(active, "Path", "path") or "") if isinstance(active, dict) else ""
        if active_path and Path(active_path).resolve() == assembly:
            opened = {"reusedAlreadyOpenDocument": True, "document": active}
        else:
            opened = client.call_tool("open_document", {"path": str(assembly)})
            opened_by_script = True

        poses_started = time.perf_counter()
        poses = client.call_tool("list_component_poses", {"topLevelOnly": True})
        pose_duration = time.perf_counter() - poses_started
        if not isinstance(poses, list):
            raise RuntimeError("list_component_poses did not return an array")
        boxes = {component_name(item): component_box(item) for item in poses}
        if not boxes or any(not name for name in boxes):
            raise RuntimeError("Could not resolve every top-level component name")

        broad_started = time.perf_counter()
        broad = [
            broad_phase(first_name, boxes[first_name], second_name, boxes[second_name], args.aabb_tolerance_meters)
            for first_name, second_name in itertools.combinations(sorted(boxes, key=str.casefold), 2)
        ]
        candidates = sorted(
            (row for row in broad if row["requiresExactLeafBrep"]),
            key=lambda row: (
                float(row["intersectionBoxVolumeCubicMeters"]),
                row["pairKey"],
            ),
        )
        broad_duration = time.perf_counter() - broad_started
        exact_rows: list[dict] = []
        payload = {
            "schemaVersion": "project02-reconstructed-interference-validation/v1",
            "status": "BROAD_PHASE_COMPLETE" if args.broad_phase_only else "EXACT_CHECK_IN_PROGRESS",
            "success": None,
            "assemblyPath": str(assembly),
            "opened": opened,
            "componentCount": len(boxes),
            "allTopLevelPairCount": len(broad),
            "aabbToleranceMeters": args.aabb_tolerance_meters,
            "aabbProvenPairCount": len(broad) - len(candidates),
            "exactCandidatePairCount": len(candidates),
            "broadPhase": broad,
            "exactChecks": exact_rows,
            "timing": {
                "startedAtUtc": started_at,
                "poseCaptureSeconds": round(pose_duration, 6),
                "broadPhaseSeconds": round(broad_duration, 6),
            },
        }
        persist(output, payload)

        if not args.broad_phase_only:
            for index, candidate in enumerate(candidates, start=1):
                key = candidate["pairKey"]
                reused = key in previous_exact
                print(
                    json.dumps(
                        {
                            "event": "exact_pair_started",
                            "candidateIndex": index,
                            "candidateCount": len(candidates),
                            "pair": candidate["pair"],
                            "reusedExistingResult": reused,
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
                if reused:
                    row = previous_exact[key]
                else:
                    pair_started_at = utc_now()
                    pair_started = time.perf_counter()
                    result = client.call_tool(
                        "check_interference_by_leaf_bodies",
                        {
                            "hierarchyPaths": candidate["pair"],
                            "treatCoincidenceAsInterference": False,
                        },
                    )
                    row = {
                        "pair": candidate["pair"],
                        "pairKey": key,
                        "candidateIndex": index,
                        "result": result,
                        "timing": {
                            "startedAtUtc": pair_started_at,
                            "finishedAtUtc": utc_now(),
                            "durationSeconds": round(time.perf_counter() - pair_started, 6),
                            "reusedExistingResult": False,
                        },
                    }
                if reused:
                    row = dict(row)
                    row["candidateIndex"] = index
                    row["timing"] = dict(row.get("timing") or {}, reusedExistingResult=True)
                exact_rows.append(row)
                print(
                    json.dumps(
                        {
                            "event": "exact_pair_finished",
                            "candidateIndex": index,
                            "candidateCount": len(candidates),
                            "pair": candidate["pair"],
                            "exactCheckComplete": exact_complete(row["result"]),
                            "failedBodyPairCount": failed_count(row["result"]),
                            "interferingBodyPairCount": interference_count(row["result"]),
                            "durationSeconds": (row.get("timing") or {}).get("durationSeconds"),
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
                payload["exactChecks"] = exact_rows
                payload["completedExactPairCount"] = len(exact_rows)
                payload["remainingExactPairCount"] = len(candidates) - len(exact_rows)
                persist(output, payload)

        incomplete = [row for row in exact_rows if not exact_complete(row["result"])]
        failed_kernel = [row for row in exact_rows if failed_count(row["result"]) > 0]
        interfering = [row for row in exact_rows if interference_count(row["result"]) > 0]
        complete = args.broad_phase_only or len(exact_rows) == len(candidates)
        success = complete and not incomplete and not failed_kernel and not interfering
        payload.update(
            {
                "status": (
                    "BROAD_PHASE_COMPLETE"
                    if args.broad_phase_only
                    else "PASSED_ZERO_INTERFERENCE"
                    if success
                    else "FAILED_INTERFERENCE_OR_INCOMPLETE"
                ),
                "success": success if not args.broad_phase_only else None,
                "completedExactPairCount": len(exact_rows),
                "remainingExactPairCount": len(candidates) - len(exact_rows),
                "incompleteExactPairCount": len(incomplete),
                "kernelFailurePairCount": len(failed_kernel),
                "interferingModulePairCount": len(interfering),
                "interferingModulePairs": [row["pair"] for row in interfering],
            }
        )
        if opened_by_script:
            try:
                client.call_tool_text("close_document", {"path": str(assembly)})
            except RuntimeError as exc:
                close_warning = str(exc)

    payload["closeWarning"] = close_warning
    payload["timing"].update(
        {
            "finishedAtUtc": utc_now(),
            "totalDurationSeconds": round(time.perf_counter() - started, 6),
            "exactDurationSeconds": round(
                sum(float((row.get("timing") or {}).get("durationSeconds") or 0.0) for row in exact_rows),
                6,
            ),
        }
    )
    persist(output, payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "output": str(output),
                "componentCount": payload["componentCount"],
                "allTopLevelPairCount": payload["allTopLevelPairCount"],
                "aabbProvenPairCount": payload["aabbProvenPairCount"],
                "exactCandidatePairCount": payload["exactCandidatePairCount"],
                "interferingModulePairCount": payload["interferingModulePairCount"],
                "totalDurationSeconds": payload["timing"]["totalDurationSeconds"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if args.broad_phase_only or success else 2


if __name__ == "__main__":
    raise SystemExit(main())
