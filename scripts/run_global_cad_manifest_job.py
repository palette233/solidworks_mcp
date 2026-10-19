from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.global_cad_manifest_orchestrator import (  # noqa: E402
    build_manifest_job_plan,
    manifest_cad_step_runner,
    run_manifest_job,
    validate_seed_evidence,
    write_manifest_job_artifacts,
)
from demo_backend.semantic_assembly_jobs import (  # noqa: E402
    AssemblyJobExecutor,
    DurableAssemblyJobStore,
)


DEFAULT_ROOT = ROOT / "demo" / "global_assembly_contexts" / "manifest_jobs"


def _print(value) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create and operate durable jobs for a generic CAD transaction manifest."
    )
    parser.add_argument("--jobs-root", type=Path, default=DEFAULT_ROOT)
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create")
    create.add_argument("manifest", type=Path)
    create.add_argument("--start-order", type=int, default=1)
    create.add_argument("--packet-limit", type=int)
    create.add_argument("--idempotency-key")
    create.add_argument("--seed-assembly", type=Path)
    create.add_argument("--seed-evidence", type=Path)

    for name in ("run", "resume"):
        action = sub.add_parser(name)
        action.add_argument("job_id")
        action.add_argument("--pause-after-packet")
        action.add_argument("--inject-failure-before-packet")
        action.add_argument("--timeout-seconds", type=int, default=2400)

    pause = sub.add_parser("pause")
    pause.add_argument("job_id")
    status = sub.add_parser("status")
    status.add_argument("job_id")

    args = parser.parse_args()
    store = DurableAssemblyJobStore(args.jobs_root.resolve())
    if args.command == "create":
        plan = build_manifest_job_plan(
            ROOT,
            args.manifest,
            start_order=args.start_order,
            packet_limit=args.packet_limit,
        )
        job = store.create(
            plan,
            execution_mode="generic_cad_manifest",
            idempotency_key=args.idempotency_key,
        )
        if plan.get("requiresSeedCheckpoint") and not job.get("lastCommittedCheckpoint"):
            if not args.seed_assembly or not args.seed_evidence:
                raise ValueError("非首包任务必须同时提供--seed-assembly和--seed-evidence。")
            seed = validate_seed_evidence(plan, args.seed_assembly, args.seed_evidence)
            job = store.seed_verified_checkpoint(
                job["jobId"],
                step_id=seed["packetId"],
                module_token=seed["moduleToken"],
                assembly_path=args.seed_assembly,
                evidence_path=args.seed_evidence,
            )
            job["initialCommittedCheckpoint"].update(seed)
            job["lastCommittedCheckpoint"].update(seed)
            job["demoCheckpoint"].update(seed)
            store.save(job)
        write_manifest_job_artifacts(store, job["jobId"])
        _print(job)
        return 0
    if args.command == "status":
        _print(store.load(args.job_id))
        return 0
    if args.command == "pause":
        _print(store.request_pause(args.job_id))
        return 0

    if args.command == "resume":
        store.prepare_resume(args.job_id)
    runner = manifest_cad_step_runner(
        ROOT,
        store,
        timeout_seconds=args.timeout_seconds,
        pause_after_packet=args.pause_after_packet,
        fail_before_packet=args.inject_failure_before_packet,
    )
    result = run_manifest_job(store, args.job_id, runner)
    _print(result)
    return 0 if result.get("status") in {"succeeded", "paused"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
