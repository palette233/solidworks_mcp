#!/usr/bin/env python3
"""Merge Project02 broad-phase, exact B-rep and cache evidence into one gate."""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.semantic_assembly_collision_gate import (  # noqa: E402
    canonical_pair,
    evaluate_pair_local_collision_gate,
)


def load(path: Path) -> dict[str, Any] | list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def pose_rows(payload: object) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("components"), list):
        return [item for item in payload["components"] if isinstance(item, dict)]
    raise ValueError("Pose evidence must be a list or contain a components list.")


def module_token(name: str) -> str:
    upper = str(name).upper()
    marker = "D062A"
    if marker in upper:
        suffix = upper.split(marker, 1)[1]
        return "A" + suffix.split(".", 1)[0]
    for token in ("A100", "A180", "A200", "A300", "A500", "A600", "A700", "A800"):
        if upper.startswith(token):
            return token
    if upper.startswith("T401"):
        return "T401"
    return upper


def token_pair(first: str, second: str) -> tuple[str, str]:
    return tuple(sorted((module_token(first), module_token(second))))


def pose_map(payload: object) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for item in pose_rows(payload):
        token = module_token(str(item.get("Name") or ""))
        if token in rows:
            raise ValueError(f"Pose catalog contains multiple top-level {token} objects.")
        rows[token] = item
    return rows


def unchanged_tokens(
    current: object,
    reference: object,
    *,
    tolerance: float = 1e-9,
) -> set[str]:
    current_rows = pose_map(current)
    reference_rows = pose_map(reference)
    result: set[str] = set()
    for token in set(current_rows) & set(reference_rows):
        current_transform = current_rows[token].get("Transform") or []
        reference_transform = reference_rows[token].get("Transform") or []
        if len(current_transform) != 16 or len(reference_transform) != 16:
            continue
        if max(
            abs(float(first) - float(second))
            for first, second in zip(current_transform, reference_transform, strict=True)
        ) <= tolerance:
            result.add(token)
    return result


def accepted_exact_pairs(
    paths: list[Path],
    *,
    allowed_tokens: set[str] | None = None,
) -> dict[tuple[str, str], dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for path in paths:
        payload = load(path)
        if not isinstance(payload, dict):
            continue
        if payload.get("assemblyChangedDuringCheck") is True:
            continue
        for item in payload.get("pairs") or []:
            pair = item.get("pair") or []
            acceptance = item.get("acceptance") or {}
            if len(pair) != 2 or acceptance.get("accepted") is not True:
                continue
            key = token_pair(str(pair[0]), str(pair[1]))
            if allowed_tokens is not None and not set(key) <= allowed_tokens:
                continue
            result[key] = {
                "method": "exact-brep",
                "evidencePath": str(path.resolve()),
                "pairEvidencePath": item.get("outputPath"),
                "interferingBodyPairCount": item.get("interferingBodyPairCount"),
                "exactCheckComplete": item.get("exactCheckComplete"),
            }
    return result


def accepted_cache_pairs(
    poses: dict[str, Any], cache: dict[str, Any]
) -> dict[tuple[str, str], dict[str, Any]]:
    baselines: dict[tuple[str, str], Path] = {}
    for entry in cache.get("entries") or []:
        sources = entry.get("sources") or []
        baseline = entry.get("baselinePath")
        if len(sources) == 2 and baseline:
            baselines[
                canonical_pair(
                    str(sources[0]["componentName"]),
                    str(sources[1]["componentName"]),
                )
            ] = Path(str(baseline))

    result: dict[tuple[str, str], dict[str, Any]] = {}
    tokens = sorted(pose_map(poses))
    for token in tokens:
        gate = evaluate_pair_local_collision_gate(
            poses,
            token,
            cache_manifest=cache,
            accepted_baselines=baselines,
        )
        for item in gate.get("pairs") or []:
            if item.get("accepted") is not True or item.get("method") != "pair-brep-cache":
                continue
            pair = item.get("pair") or []
            if len(pair) != 2:
                continue
            result[token_pair(str(pair[0]), str(pair[1]))] = {
                "method": "pair-brep-cache",
                "cacheKey": item.get("cacheKey"),
                "policy": item.get("policy"),
            }
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screening", required=True, type=Path)
    parser.add_argument("--current-poses", required=True, type=Path)
    parser.add_argument("--reference-poses", required=True, type=Path)
    parser.add_argument("--cache", required=True, type=Path)
    parser.add_argument("--current-exact-batch", action="append", type=Path, default=[])
    parser.add_argument("--reused-exact-batch", action="append", type=Path, default=[])
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    screening = load(args.screening.resolve())
    current_poses = load(args.current_poses.resolve())
    reference_poses = load(args.reference_poses.resolve())
    cache = load(args.cache.resolve())
    if not all(isinstance(item, dict) for item in (screening, current_poses, cache)):
        raise ValueError("Screening, current pose and cache evidence must be objects.")

    unchanged = unchanged_tokens(current_poses, reference_poses)
    current_exact = accepted_exact_pairs([path.resolve() for path in args.current_exact_batch])
    reused_exact = accepted_exact_pairs(
        [path.resolve() for path in args.reused_exact_batch],
        allowed_tokens=unchanged,
    )
    cache_pairs = accepted_cache_pairs(current_poses, cache)

    rows: list[dict[str, Any]] = []
    for item in screening.get("diagnostics") or []:
        pair = item.get("components") or []
        if len(pair) != 2:
            continue
        key = token_pair(str(pair[0]), str(pair[1]))
        status = str(item.get("status") or "")
        evidence: dict[str, Any] | None = None
        if status.startswith("passed_"):
            evidence = {"method": "world-aabb", "screeningStatus": status}
        elif key in current_exact:
            evidence = {**current_exact[key], "method": "current-exact-brep"}
        elif key in cache_pairs:
            evidence = cache_pairs[key]
        elif key in reused_exact:
            evidence = {**reused_exact[key], "method": "reused-exact-brep"}
        rows.append(
            {
                "pair": list(key),
                "collisionPolicy": item.get("collisionPolicy"),
                "screeningStatus": status,
                "accepted": evidence is not None,
                "evidence": evidence,
            }
        )

    unresolved = [item for item in rows if item["accepted"] is not True]
    payload = {
        "schemaVersion": "project02-feedback-layout-closure/v1",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "assemblyPath": screening.get("assemblyPath"),
        "screeningPath": str(args.screening.resolve()),
        "currentPosePath": str(args.current_poses.resolve()),
        "referencePosePath": str(args.reference_poses.resolve()),
        "unchangedFromReferenceTokens": sorted(unchanged),
        "pairCount": len(rows),
        "acceptedPairCount": sum(item["accepted"] is True for item in rows),
        "unresolvedPairCount": len(unresolved),
        "staticCollisionReady": not unresolved and len(rows) == math.comb(len(pose_map(current_poses)), 2),
        "pairs": rows,
        "unresolvedPairs": unresolved,
        "releaseBoundary": (
            "A saved assembly is not publishable until every world-AABB, conditional B-rep "
            "and installation-contact pair has accepted evidence."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "pairCount": payload["pairCount"],
                "acceptedPairCount": payload["acceptedPairCount"],
                "unresolvedPairCount": payload["unresolvedPairCount"],
                "staticCollisionReady": payload["staticCollisionReady"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if payload["staticCollisionReady"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
