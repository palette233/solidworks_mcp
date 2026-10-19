#!/usr/bin/env python3
"""Run a verified Project02 live-CAD tail from an explicit accepted checkpoint."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.semantic_assembly_cad_runner import live_cad_step_runner
from demo_backend.semantic_assembly_collision_gate import canonical_pair, live_pair_local_collision_hard_gate
from demo_backend.semantic_assembly_jobs import AssemblyJobExecutor, DurableAssemblyJobStore
from demo_backend.semantic_assembly_sequence import load_project02_ordered_assembly_closure


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def baseline_map(cache_path: Path) -> dict[tuple[str, str], Path]:
    result: dict[tuple[str, str], Path] = {}
    for row in load(cache_path).get("entries") or []:
        sources = row.get("sources") or []
        baseline = row.get("baselinePath")
        if baseline and len(sources) == 2:
            result[canonical_pair(str(sources[0]["componentName"]), str(sources[1]["componentName"]))] = Path(str(baseline))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-assembly", required=True, type=Path)
    parser.add_argument("--seed-evidence", required=True, type=Path)
    parser.add_argument("--seed-step", required=True)
    parser.add_argument("--seed-token", required=True)
    parser.add_argument("--tokens", nargs="+", required=True)
    parser.add_argument("--timeout", type=float, default=1800.0)
    parser.add_argument("--idempotency-key")
    parser.add_argument(
        "--validation-profile",
        choices=("demo", "engineering"),
        default="demo",
        help="demo commits after CAD save/reopen; engineering also runs the collision hard gate",
    )
    args = parser.parse_args()
    closure = load_project02_ordered_assembly_closure(ROOT)
    store = DurableAssemblyJobStore(ROOT / "demo/semantic_ports/project02_ordered_jobs")
    plan = {
        "schemaVersion": "project02-live-tail-plan/v1",
        "projectId": "project02",
        "validationProfile": args.validation_profile,
        "steps": [
            {"stepId": f"tail-{index:02d}-{token.lower()}", "moduleToken": token}
            for index, token in enumerate(args.tokens, start=1)
        ],
        "seed": {"moduleToken": args.seed_token, "assemblyPath": str(args.seed_assembly.resolve())},
    }
    key = args.idempotency_key or "project02-live-tail-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    job = store.create(plan, execution_mode="live_cad", idempotency_key=key)
    if not job.get("initialCommittedCheckpoint"):
        store.seed_verified_checkpoint(
            job["jobId"],
            step_id=args.seed_step,
            module_token=args.seed_token,
            assembly_path=args.seed_assembly,
            evidence_path=args.seed_evidence,
        )
    cache_path = ROOT / "demo/semantic_ports/project02_full_machine_increment_v1/pair_brep_cache_manifest_v3.json"
    executable = ROOT / "demo/runtime/project02_full_machine_20260930_v2/SolidWorksMcpApp.exe"
    gate = live_pair_local_collision_hard_gate(
        store=store,
        workspace=ROOT,
        executable=executable,
        cache_manifest_path=cache_path,
        accepted_baselines=baseline_map(cache_path),
        timeout_seconds=args.timeout,
    )
    runner = live_cad_step_runner(
        store=store,
        closure=closure,
        workspace=ROOT,
        executable=executable,
        hard_gate=gate,
        timeout_seconds=args.timeout,
        required_tokens=set(args.tokens),
    )
    result = AssemblyJobExecutor(store, runner).run(job["jobId"])
    print(json.dumps({
        "jobId": job["jobId"],
        "jobPath": str(store.root / job["jobId"] / "job.json"),
        "status": result["status"],
        "validationProfile": result.get("validationProfile"),
        "assemblyStatus": result.get("assemblyStatus"),
        "collisionStatus": result.get("collisionStatus"),
        "durationSeconds": result.get("executionDurationSeconds"),
        "checkpoint": result.get("lastCommittedCheckpoint"),
        "error": result.get("error"),
    }, ensure_ascii=False))
    return 0 if result["status"] == "succeeded" else 2


if __name__ == "__main__":
    raise SystemExit(main())
