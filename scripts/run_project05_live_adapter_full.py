from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
BACKEND_SRC = WORKSPACE / "apps" / "demo-backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.main import _baseline_map_from_cache
from demo_backend.project05_semantic_assembly_cad_runner import (
    project05_live_cad_step_runner,
)
from demo_backend.semantic_assembly_collision_gate import (
    live_pair_local_collision_hard_gate,
)
from demo_backend.semantic_assembly_jobs import (
    AssemblyJobExecutor,
    DurableAssemblyJobStore,
)


TOKENS = ["D000", "K000", "F000", "M000", "G000", "N000", "P000", "B000"]
STEP_MEMBERS = {
    "D000": {"D000"},
    "K000": {"K000"},
    "F000": {"F000"},
    "M000": {"M000"},
    "G000": {"G000"},
    "N000": {"N000"},
    "P000": {"P000"},
    "B000": {"B000", "Z000"},
}
CONTACTS = {
    tuple(sorted((frame, module)))
    for frame in ("A000", "E000")
    for module in ("D000", "K000", "F000", "M000", "G000", "N000", "P000", "B000", "Z000")
}
CONTACTS.add(tuple(sorted(("B000", "Z000"))))


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    store = DurableAssemblyJobStore(
        WORKSPACE / "demo" / "semantic_ports" / "project05_live_adapter_full_jobs"
    )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    plan = {
        "schemaVersion": "ordered-assembly-plan/v2",
        "projectId": "project05",
        "steps": [
            {
                "stepId": f"step-{index:02d}-{token.lower()}",
                "moduleToken": token,
            }
            for index, token in enumerate(TOKENS, start=1)
        ],
    }
    job = store.create(
        plan,
        execution_mode="live_cad",
        idempotency_key=f"project05-live-uninterrupted-{stamp}",
    )
    closure_path = (
        WORKSPACE
        / "demo"
        / "semantic_ports"
        / "project05_ordered_jobs"
        / "latest_ordered_closure.json"
    )
    cache_path = (
        WORKSPACE
        / "demo"
        / "semantic_ports"
        / "project05_ordered_jobs"
        / "pair_brep_cache_manifest_v3.json"
    )
    executable = WORKSPACE / "artifacts" / "solidworks-mcp-current" / "SolidWorksMcpApp.exe"
    gate = live_pair_local_collision_hard_gate(
        store=store,
        workspace=WORKSPACE,
        executable=executable,
        cache_manifest_path=cache_path,
        accepted_baselines=_baseline_map_from_cache(cache_path),
        step_member_tokens=STEP_MEMBERS,
        accepted_contact_token_pairs=CONTACTS,
        timeout_seconds=1800.0,
    )
    runner = project05_live_cad_step_runner(
        store=store,
        closure=_load(closure_path),
        workspace=WORKSPACE,
        executable=executable,
        hard_gate=gate,
        timeout_seconds=1800.0,
    )
    result = AssemblyJobExecutor(store, runner).run(job["jobId"])
    summary = {
        "schemaVersion": "project05-live-adapter-uninterrupted/v1",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "jobId": job["jobId"],
        "status": result["status"],
        "singleUninterruptedJob": True,
        "stepCount": len(result.get("steps") or []),
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
    }
    latest = store.root / "latest_uninterrupted.json"
    latest.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "succeeded" else 2


if __name__ == "__main__":
    raise SystemExit(main())
