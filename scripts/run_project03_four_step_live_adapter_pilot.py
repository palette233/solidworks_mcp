from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
BACKEND_SRC = WORKSPACE / "apps/demo-backend/src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.project03_semantic_assembly_cad_runner import project03_live_cad_step_runner
from demo_backend.semantic_assembly_collision_gate import canonical_pair, live_pair_local_collision_hard_gate
from demo_backend.semantic_assembly_jobs import AssemblyJobExecutor, DurableAssemblyJobStore


def main() -> int:
    store = DurableAssemblyJobStore(
        WORKSPACE / "demo/semantic_ports/project03_live_adapter_four_step_jobs"
    )
    tokens = ["AE00", "AD00", "AI00", "AG00"]
    plan = {
        "schemaVersion": "ordered-assembly-plan/v2",
        "projectId": "project03",
        "steps": [
            {"stepId": f"step-{index:02d}-{token.lower()}", "moduleToken": token}
            for index, token in enumerate(tokens, start=1)
        ],
    }
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    job = store.create(
        plan,
        execution_mode="live_cad",
        idempotency_key=f"project03-four-step-live-pilot-{stamp}",
    )
    prototype_root = WORKSPACE / "demo/interference_project03_prototype/conditional_hits"
    baselines = {
        canonical_pair("AE00", "AD00"): prototype_root
        / "FL9A24D063A000.001_leaf_details_FL9A24D063AE00_FL9A24D063AD00.json",
        canonical_pair("AE00", "AI00"): prototype_root
        / "FL9A24D063A000.001_leaf_details_FL9A24D063AE00_FL9A24D063AI00.json",
    }
    for baseline in baselines.values():
        if not baseline.is_file():
            raise FileNotFoundError(baseline)
    cache = store.root / "pair_brep_cache_manifest_v3.json"
    executable = WORKSPACE / "artifacts/solidworks-mcp-current/SolidWorksMcpApp.exe"
    gate = live_pair_local_collision_hard_gate(
        store=store,
        workspace=WORKSPACE,
        executable=executable,
        cache_manifest_path=cache,
        accepted_baselines=baselines,
        step_member_tokens={token: {token} for token in tokens},
        accepted_contact_token_pairs={
            canonical_pair("AA00", token) for token in tokens
        },
        timeout_seconds=1800.0,
    )
    runner = project03_live_cad_step_runner(
        store=store,
        workspace=WORKSPACE,
        executable=executable,
        hard_gate=gate,
        timeout_seconds=1800.0,
    )
    result = AssemblyJobExecutor(store, runner).run(job["jobId"])
    summary = {
        "schemaVersion": "project03-four-step-live-adapter-pilot/v1",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "jobId": job["jobId"],
        "status": result["status"],
        "tokens": tokens,
        "committedStepCount": sum(
            step.get("status") == "succeeded" for step in result.get("steps") or []
        ),
        "executionDurationSeconds": result.get("executionDurationSeconds"),
        "lastCommittedCheckpoint": result.get("lastCommittedCheckpoint"),
        "rollback": result.get("rollback"),
        "error": result.get("error"),
        "jobPath": str(store.root / job["jobId"] / "job.json"),
        "evidenceManifestPath": str(store.root / job["jobId"] / "evidence-manifest.json"),
        "productionReady": False,
        "knownLimitation": "AG00 uses an explicit prototype residual pose anchor to close the sixth static degree of freedom.",
    }
    target = store.root / "latest_four_step_pilot.json"
    target.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "succeeded" else 2


if __name__ == "__main__":
    raise SystemExit(main())
