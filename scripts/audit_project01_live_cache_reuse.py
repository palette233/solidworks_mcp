#!/usr/bin/env python3
"""Audit Project01 final-step pair-cache reuse from a fresh pose capture."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter


WORKSPACE = Path(__file__).resolve().parents[1]
BACKEND_SRC = WORKSPACE / "apps/demo-backend/src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.main import _project01_static_baselines  # noqa: E402
from demo_backend.semantic_assembly_collision_gate import (  # noqa: E402
    evaluate_pair_local_collision_gate,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--poses", required=True)
    parser.add_argument("--cache", required=True)
    parser.add_argument("--prior-gate", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    poses_path = Path(args.poses).resolve()
    cache_path = Path(args.cache).resolve()
    prior_gate_path = Path(args.prior_gate).resolve()
    poses = json.loads(poses_path.read_text(encoding="utf-8-sig"))
    cache = json.loads(cache_path.read_text(encoding="utf-8-sig"))
    prior_gate = json.loads(prior_gate_path.read_text(encoding="utf-8-sig"))
    started = perf_counter()
    result = evaluate_pair_local_collision_gate(
        poses,
        "LM00",
        cache_manifest=cache,
        accepted_baselines=_project01_static_baselines(WORKSPACE),
        inserted_module_tokens={"LM00", "ZZ00"},
        accepted_contact_token_pairs=set(),
    )
    evaluation_duration = perf_counter() - started
    pose_duration = float(poses.get("durationSeconds") or 0.0)
    prior_total = float((prior_gate.get("timingSeconds") or {}).get("total") or 0.0)
    reused_total = pose_duration + evaluation_duration
    payload = {
        "schemaVersion": "project01-live-pair-cache-reuse-audit/v1",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "projectId": "project01",
        "assemblyPath": poses.get("assemblyPath"),
        "freshPoseCapturePath": str(poses_path),
        "cacheManifestPath": str(cache_path),
        "priorGatePath": str(prior_gate_path),
        "accepted": result.get("accepted") is True,
        "pairCount": result.get("pairCount"),
        "strictAabbAcceptedCount": result.get("strictAabbAcceptedCount"),
        "cacheAcceptedCount": result.get("cacheAcceptedCount"),
        "unresolvedExactPairCount": result.get("unresolvedExactPairCount"),
        "freshPoseCaptureDurationSeconds": round(pose_duration, 6),
        "cacheEvaluationDurationSeconds": round(evaluation_duration, 6),
        "totalReuseGateDurationSeconds": round(reused_total, 6),
        "priorExactGateDurationSeconds": round(prior_total, 6),
        "avoidedExactBrepSeconds": round(max(0.0, prior_total - reused_total), 6),
        "durationReductionPercent": round(
            (
                100.0 * max(0.0, prior_total - reused_total) / prior_total
                if prior_total
                else 0.0
            ),
            3,
        ),
        "pairs": result.get("pairs") or [],
        "invalidationRule": (
            "源文件哈希、组件相对位姿、检查策略或原型基线任一变化，"
            "对象对指纹变化并重新进入条件B-rep。"
        ),
        "scopeBoundary": {
            "freshTopLevelPoseCaptureUsed": True,
            "exactBrepRerun": False,
            "validOnlyForMatchingVersionedFingerprints": True,
            "doesNotReplaceFirstTimeExactVerification": True,
        },
    }
    target = Path(args.output).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
