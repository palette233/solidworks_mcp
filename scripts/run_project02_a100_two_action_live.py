#!/usr/bin/env python3
"""Run the Project02 A100 two-action adapter from the accepted A500 checkpoint."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.semantic_assembly_cad_runner import live_cad_step_runner
from demo_backend.semantic_assembly_collision_gate import (
    canonical_pair,
    live_pair_local_collision_hard_gate,
)
from demo_backend.semantic_assembly_jobs import (
    AssemblyJobExecutor,
    DurableAssemblyJobStore,
)
from demo_backend.semantic_assembly_sequence import load_project02_ordered_assembly_closure


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def baseline_map(cache_path: Path) -> dict[tuple[str, str], Path]:
    result: dict[tuple[str, str], Path] = {}
    for row in load(cache_path).get("entries") or []:
        sources = row.get("sources") or []
        baseline = row.get("baselinePath")
        if baseline and len(sources) == 2:
            result[
                canonical_pair(
                    str(sources[0]["componentName"]),
                    str(sources[1]["componentName"]),
                )
            ] = Path(str(baseline))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=1800.0)
    parser.add_argument("--idempotency-key")
    args = parser.parse_args()

    closure = load_project02_ordered_assembly_closure(ROOT)
    rows = {str(row.get("moduleToken")): row for row in closure.get("steps") or []}
    seed = rows["A500"]
    seed_assembly = Path(str(seed["assemblyPath"])).resolve()
    seed_evidence = Path(str(seed.get("evidencePath") or "")).resolve()
    if not seed_evidence.is_file():
        candidates = [Path(str(value)).resolve() for value in seed.get("evidencePaths") or []]
        seed_evidence = next((path for path in candidates if path.is_file()), seed_evidence)

    jobs_root = ROOT / "demo/semantic_ports/project02_ordered_jobs"
    store = DurableAssemblyJobStore(jobs_root)
    plan = {
        "schemaVersion": "project02-a100-two-action-live-plan/v1",
        "steps": [{"stepId": "step-06-a100", "moduleToken": "A100"}],
        "seed": {"moduleToken": "A500", "assemblyPath": str(seed_assembly)},
    }
    key = args.idempotency_key or (
        "project02-a100-two-action-live-"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    )
    job = store.create(plan, execution_mode="live_cad", idempotency_key=key)
    if not job.get("initialCommittedCheckpoint"):
        job = store.seed_verified_checkpoint(
            job["jobId"],
            step_id="step-05-a500",
            module_token="A500",
            assembly_path=seed_assembly,
            evidence_path=seed_evidence,
        )

    cache_path = ROOT / (
        "demo/semantic_ports/project02_full_machine_increment_v1/"
        "pair_brep_cache_manifest_v3.json"
    )
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
        required_tokens={"A100"},
    )
    result = AssemblyJobExecutor(store, runner).run(job["jobId"])
    print(
        json.dumps(
            {
                "jobId": job["jobId"],
                "jobPath": str(jobs_root / job["jobId"] / "job.json"),
                "status": result["status"],
                "durationSeconds": result.get("executionDurationSeconds"),
                "checkpoint": result.get("lastCommittedCheckpoint"),
                "error": result.get("error"),
            },
            ensure_ascii=False,
        )
    )
    return 0 if result["status"] == "succeeded" else 2


if __name__ == "__main__":
    raise SystemExit(main())
