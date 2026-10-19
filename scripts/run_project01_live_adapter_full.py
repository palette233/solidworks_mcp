from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
BACKEND_SRC = WORKSPACE / "apps/demo-backend/src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.main import _project01_static_baselines
from demo_backend.project01_semantic_assembly_cad_runner import (
    project01_live_cad_step_runner,
)
from demo_backend.semantic_assembly_collision_gate import (
    canonical_pair,
    live_pair_local_collision_hard_gate,
)
from demo_backend.semantic_assembly_jobs import AssemblyJobExecutor, DurableAssemblyJobStore


TOKENS = ["SS00", "FF00", "SM00", "GN00", "BD00", "GJ00", "LM00"]


def main() -> int:
    root = WORKSPACE / "demo/semantic_ports/project01_live_adapter_full_jobs"
    store = DurableAssemblyJobStore(root)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    plan = {
        "schemaVersion": "ordered-assembly-plan/v2",
        "projectId": "project01",
        "steps": [
            {"stepId": f"step-{index:02d}-{token.lower()}", "moduleToken": token}
            for index, token in enumerate(TOKENS, start=1)
        ],
    }
    job = store.create(
        plan,
        execution_mode="live_cad",
        idempotency_key=f"project01-full-live-{stamp}",
    )
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
    result = AssemblyJobExecutor(store, runner).run(job["jobId"])
    summary = {
        "schemaVersion": "project01-uninterrupted-full-live-adapter/v1",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "jobId": job["jobId"],
        "status": result["status"],
        "tokens": TOKENS,
        "singleDurableJob": True,
        "singleUninterruptedJob": True,
        "controlledResume": False,
        "committedStepCount": sum(
            step.get("status") == "succeeded" for step in result.get("steps") or []
        ),
        "executionDurationSeconds": result.get("executionDurationSeconds"),
        "lastCommittedCheckpoint": result.get("lastCommittedCheckpoint"),
        "rollback": result.get("rollback"),
        "error": result.get("error"),
        "jobPath": str(root / job["jobId"] / "job.json"),
        "evidenceManifestPath": str(root / job["jobId"] / "evidence-manifest.json"),
        "productionReady": False,
        "scopeBoundary": {
            "staticAssemblyOnly": True,
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
