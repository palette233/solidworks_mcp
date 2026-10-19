from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE / "apps/demo-backend/src"))

from demo_backend.semantic_assembly_collision_gate import (
    canonical_pair,
    evaluate_pair_local_collision_gate,
)


MODULES = ["A800", "A180", "A700", "A300", "A500", "A100", "A200", "T401"]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit whether the final Project02 pair cache closes every live step."
    )
    root = WORKSPACE / "demo/semantic_ports/project02_full_machine_increment_v1"
    parser.add_argument("--poses", type=Path, default=root / "step09_V2_top_level_poses.json")
    parser.add_argument("--cache", type=Path, default=root / "pair_brep_cache_manifest_v3.json")
    parser.add_argument("--output", type=Path, default=root / "pair_brep_cache_coverage.json")
    args = parser.parse_args()

    poses = load(args.poses)
    cache = load(args.cache)
    baselines = {}
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

    rows = []
    for token in MODULES:
        gate = evaluate_pair_local_collision_gate(
            poses,
            token,
            cache_manifest=cache,
            accepted_baselines=baselines,
        )
        rows.append(
            {
                "moduleToken": token,
                "pairCount": gate["pairCount"],
                "strictAabbAcceptedCount": gate["strictAabbAcceptedCount"],
                "cacheAcceptedCount": gate["cacheAcceptedCount"],
                "unresolvedExactPairCount": gate["unresolvedExactPairCount"],
                "accepted": gate["accepted"],
            }
        )

    payload = {
        "schemaVersion": "project02-pair-brep-cache-coverage/v1",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "poseCatalogPath": str(args.poses.resolve()),
        "cacheManifestPath": str(args.cache.resolve()),
        "cacheEntryCount": int(cache.get("entryCount") or 0),
        "moduleGates": rows,
        "summary": {
            "moduleGateCount": len(rows),
            "acceptedModuleGateCount": sum(1 for row in rows if row["accepted"]),
            "allCurrentFinalPosesClosedByAabbOrCache": all(row["accepted"] for row in rows),
            "unresolvedExactPairCount": sum(row["unresolvedExactPairCount"] for row in rows),
        },
        "invalidationBoundary": (
            "This audit is valid only while source CAD hashes, configurations, pair-relative "
            "poses, policies, baseline hashes, checker version and evidence hashes remain unchanged."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), **payload["summary"]}, ensure_ascii=False))
    return 0 if payload["summary"]["allCurrentFinalPosesClosedByAabbOrCache"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
