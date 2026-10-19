#!/usr/bin/env python3
"""Resume a failed Project01 full-chain live CAD job from its last checkpoint."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
BACKEND_SRC = WORKSPACE / "apps/demo-backend/src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))
if str(WORKSPACE / "scripts") not in sys.path:
    sys.path.insert(0, str(WORKSPACE / "scripts"))

from demo_backend.main import _project01_static_baselines  # noqa: E402
from demo_backend.project01_semantic_assembly_cad_runner import (  # noqa: E402
    project01_live_cad_step_runner,
)
from demo_backend.semantic_assembly_collision_gate import (  # noqa: E402
    canonical_pair,
    live_pair_local_collision_hard_gate,
)
from demo_backend.semantic_assembly_jobs import (  # noqa: E402
    AssemblyJobExecutor,
    DurableAssemblyJobStore,
)
from run_project01_live_adapter_full import TOKENS  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job-id", required=True)
    args = parser.parse_args()

    root = WORKSPACE / "demo/semantic_ports/project01_live_adapter_full_jobs"
    store = DurableAssemblyJobStore(root)
    before = store.load(args.job_id)
    if before.get("status") not in {"failed", "cancelled", "paused"}:
        raise ValueError(
            f"Job {args.job_id} is not resumable from {before.get('status')}"
        )
    prior_error = before.get("error")
    prior_rollback = before.get("rollback")
    prior_duration = float(before.get("executionDurationSeconds") or 0.0)
    store.prepare_resume(args.job_id)

    cache = root / "pair_brep_cache_manifest_v1.json"
    executable = WORKSPACE / "artifacts/solidworks-mcp-current/SolidWorksMcpApp.exe"
    gate = live_pair_local_collision_hard_gate(
        store=store,
        workspace=WORKSPACE,
        executable=executable,
        cache_manifest_path=cache,
        accepted_baselines=_project01_static_baselines(WORKSPACE),
        step_member_tokens={
            "SS00": {"SS00"},
            "FF00": {"FF00"},
            "SM00": {"SM00"},
            "GN00": {"GN00"},
            "BD00": {"BD00"},
            "GJ00": {"GJ00"},
            "LM00": {"LM00", "ZZ00"},
        },
        accepted_contact_token_pairs={
            canonical_pair("JJ00", "SS00"),
            canonical_pair("JJ00", "FF00"),
        },
        timeout_seconds=1800.0,
    )
    runner = project01_live_cad_step_runner(
        store=store,
        workspace=WORKSPACE,
        executable=executable,
        hard_gate=gate,
        timeout_seconds=1800.0,
    )
    result = AssemblyJobExecutor(store, runner).run(args.job_id)
    total_duration = float(result.get("executionDurationSeconds") or 0.0)
    summary = {
        "schemaVersion": "project01-uninterrupted-full-live-adapter/v2",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "jobId": args.job_id,
        "status": result["status"],
        "tokens": TOKENS,
        "singleDurableJob": True,
        "singleUninterruptedJob": False,
        "controlledResume": True,
        "committedStepCount": sum(
            step.get("status") == "succeeded" for step in result.get("steps") or []
        ),
        "attemptCounts": {
            str(step.get("moduleToken")): int(step.get("attemptCount") or 0)
            for step in result.get("steps") or []
        },
        "executionDurationSeconds": result.get("executionDurationSeconds"),
        "durationBeforeResumeSeconds": prior_duration,
        "resumeDurationSeconds": round(total_duration - prior_duration, 6),
        "lastCommittedCheckpoint": result.get("lastCommittedCheckpoint"),
        "priorFailure": {"error": prior_error, "rollback": prior_rollback},
        "rollback": result.get("rollback"),
        "error": result.get("error"),
        "jobPath": str(root / args.job_id / "job.json"),
        "evidenceManifestPath": str(root / args.job_id / "evidence-manifest.json"),
        "productionReady": False,
        "scopeBoundary": {
            "staticAssemblyOnly": True,
            "resumedFromCommittedBd00Checkpoint": True,
            "lm00Zz00RigidSnapshot": True,
            "dynamicMotionValidated": False,
        },
    }
    latest = root / "latest_uninterrupted.json"
    latest.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "succeeded" else 2


if __name__ == "__main__":
    raise SystemExit(main())
