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
    seed_root = WORKSPACE / "demo/semantic_ports/project03_live_adapter_ah00_tail_jobs"
    seed_summary = json.loads((seed_root / "latest_ah00_tail.json").read_text(encoding="utf-8"))
    checkpoint = seed_summary["lastCommittedCheckpoint"]
    store = DurableAssemblyJobStore(
        WORKSPACE / "demo/semantic_ports/project03_live_adapter_aj00_tail_jobs"
    )
    plan = {
        "schemaVersion": "ordered-assembly-plan/v2",
        "projectId": "project03",
        "steps": [{"stepId": "step-06-aj00", "moduleToken": "AJ00"}],
    }
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    job = store.create(plan, execution_mode="live_cad", idempotency_key=f"project03-aj00-live-tail-{stamp}")
    store.seed_verified_checkpoint(
        job["jobId"],
        step_id=str(checkpoint["stepId"]),
        module_token=str(checkpoint["moduleToken"]),
        assembly_path=Path(str(checkpoint["assemblyPath"])),
        evidence_path=Path(str(checkpoint["evidencePath"])),
    )
    cache = WORKSPACE / "demo/semantic_ports/project03_live_adapter_four_step_jobs/pair_brep_cache_manifest_v3.json"
    executable = WORKSPACE / "artifacts/solidworks-mcp-current/SolidWorksMcpApp.exe"
    gate = live_pair_local_collision_hard_gate(
        store=store,
        workspace=WORKSPACE,
        executable=executable,
        cache_manifest_path=cache,
        accepted_baselines={},
        step_member_tokens={"AJ00": {"AJ00"}},
        accepted_contact_token_pairs={canonical_pair("AA00", "AJ00")},
        timeout_seconds=1800.0,
    )
    runner = project03_live_cad_step_runner(
        store=store, workspace=WORKSPACE, executable=executable, hard_gate=gate, timeout_seconds=1800.0
    )
    result = AssemblyJobExecutor(store, runner).run(job["jobId"])
    summary = {
        "schemaVersion": "project03-aj00-live-adapter-tail/v1",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "jobId": job["jobId"],
        "status": result["status"],
        "seedCheckpoint": result.get("initialCommittedCheckpoint"),
        "lastCommittedCheckpoint": result.get("lastCommittedCheckpoint"),
        "rollback": result.get("rollback"),
        "error": result.get("error"),
        "jobPath": str(store.root / job["jobId"] / "job.json"),
        "evidenceManifestPath": str(store.root / job["jobId"] / "evidence-manifest.json"),
        "productionReady": False,
    }
    target = store.root / "latest_aj00_tail.json"
    target.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "succeeded" else 2


if __name__ == "__main__":
    raise SystemExit(main())
