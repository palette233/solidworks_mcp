#!/usr/bin/env python3
"""Run the complete Project02 natural-language ordered assembly as one durable job."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.assembly_pipeline_audit import audit_project02_assembly_pipeline
from demo_backend.assembly_timing_report import write_assembly_timing_report
from demo_backend.assembly_job_closure import write_assembly_job_static_closure
from demo_backend.assembly_evidence_manifest import write_job_evidence_manifest
from demo_backend.semantic_assembly_cad_runner import live_cad_step_runner
from demo_backend.semantic_assembly_collision_gate import canonical_pair, live_pair_local_collision_hard_gate
from demo_backend.semantic_assembly_jobs import AssemblyJobExecutor, DurableAssemblyJobStore
from demo_backend.semantic_assembly_sequence import (
    load_project02_ordered_assembly_closure,
    preview_project02_ordered_assembly,
)


DEFAULT_REQUIREMENT = (
    "项目02：以A600为基座，先添加A800，再添加A180，然后添加A700，接着添加A300，"
    "再添加A500，然后添加A100，再添加A200，最后添加T401。"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _baseline_map(cache_path: Path) -> dict[tuple[str, str], Path]:
    result: dict[tuple[str, str], Path] = {}
    for row in _load(cache_path).get("entries") or []:
        sources = row.get("sources") or []
        baseline = row.get("baselinePath")
        if baseline and len(sources) == 2:
            pair = canonical_pair(
                str(sources[0]["componentName"]), str(sources[1]["componentName"])
            )
            result[pair] = Path(str(baseline))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requirement", default=DEFAULT_REQUIREMENT)
    parser.add_argument("--timeout", type=float, default=1800.0)
    parser.add_argument("--idempotency-key")
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()

    audit = audit_project02_assembly_pipeline(ROOT)
    if not audit.get("readyForLiveCadExecution"):
        print(json.dumps(audit, ensure_ascii=False, indent=2))
        return 2
    preview = preview_project02_ordered_assembly(args.requirement)
    if not preview["plan"]["executionBoundary"]["safeToStartCad"]:
        print(json.dumps(preview, ensure_ascii=False, indent=2))
        return 2
    if args.preflight_only:
        print(
            json.dumps(
                {
                    "success": True,
                    "mode": "preflight-only",
                    "audit": audit,
                    "intentDigest": preview["intent"]["intentDigest"],
                    "planDigest": preview["plan"]["planDigest"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    store = DurableAssemblyJobStore(ROOT / "demo/semantic_ports/project02_ordered_jobs")
    key = args.idempotency_key or (
        "project02-full-natural-language-live-"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )
    job = store.create(preview["plan"], execution_mode="live_cad", idempotency_key=key)
    job_directory = store.root / job["jobId"]
    preflight_path = job_directory / "preflight.json"
    preflight_path.write_text(
        json.dumps(
            {
                "schemaVersion": "assembly-job-preflight/v1",
                "pipelineAudit": audit,
                "previewAudit": preview["audit"],
                "projectProfile": preview["intent"]["projectProfile"],
                "intentDigest": preview["intent"]["intentDigest"],
                "planDigest": preview["plan"]["planDigest"],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    closure = load_project02_ordered_assembly_closure(ROOT)
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
        accepted_baselines=_baseline_map(cache_path),
        timeout_seconds=args.timeout,
    )
    requested = {str(step["moduleToken"]) for step in preview["plan"]["steps"]}
    runner = live_cad_step_runner(
        store=store,
        closure=closure,
        workspace=ROOT,
        executable=executable,
        hard_gate=gate,
        timeout_seconds=args.timeout,
        required_tokens=requested,
    )
    result = AssemblyJobExecutor(store, runner).run(job["jobId"])
    write_job_evidence_manifest(result, job_directory)
    timing_path = write_assembly_timing_report(job_directory)
    closure_path = write_assembly_job_static_closure(
        job_directory,
        expected_top_level_object_count=10,
        expected_cad_action_count=10,
    )
    static_closure = _load(closure_path)
    summary = {
        "jobId": job["jobId"],
        "jobPath": str(job_directory / "job.json"),
        "evidenceManifestPath": str(job_directory / "evidence-manifest.json"),
        "preflightEvidencePath": str(preflight_path),
        "timingReportPath": str(timing_path),
        "staticClosurePath": str(closure_path),
        "status": result["status"],
        "durationSeconds": result.get("executionDurationSeconds"),
        "lastCommittedCheckpoint": result.get("lastCommittedCheckpoint"),
        "rollback": result.get("rollback"),
        "error": result.get("error"),
    }
    summary_path = job_directory / "full-chain-summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if static_closure.get("staticFullChainAccepted") is True:
        latest_path = ROOT / (
            "demo/semantic_ports/project02_full_machine_increment_v1/"
            "latest_live_full_chain.json"
        )
        latest_path.write_text(
            json.dumps(
                {
                    "schemaVersion": "latest-live-full-chain/v1",
                    "projectId": "project02",
                    "jobId": job["jobId"],
                    "projectProfile": preview["intent"]["projectProfile"],
                    "intentDigest": preview["intent"]["intentDigest"],
                    "planDigest": preview["plan"]["planDigest"],
                    "finalAssemblyPath": static_closure["finalAssemblyPath"],
                    "staticClosurePath": str(closure_path),
                    "evidenceManifestPath": str(job_directory / "evidence-manifest.json"),
                    "timingReportPath": str(timing_path),
                    "productionDynamicReleaseAllowed": False,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "succeeded" else 2


if __name__ == "__main__":
    raise SystemExit(main())
