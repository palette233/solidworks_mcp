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
from demo_backend.semantic_assembly_collision_gate import canonical_pair, live_pair_local_collision_hard_gate, module_token
from demo_backend.semantic_assembly_jobs import AssemblyJobExecutor, DurableAssemblyJobStore


TOKENS = ["AE00", "AD00", "AI00", "AG00", "AH00", "AJ00", "AB00"]


def baseline_map(cache_path: Path) -> dict[tuple[str, str], Path]:
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    result: dict[tuple[str, str], Path] = {}
    for row in payload.get("entries") or []:
        baseline = row.get("baselinePath")
        sources = row.get("sources") or []
        if not baseline or len(sources) != 2:
            continue
        path = Path(str(baseline))
        names = [str(item.get("componentName") or "") for item in sources]
        result[canonical_pair(*names)] = path
        tokens = [module_token(name) for name in names]
        if all(tokens):
            result[canonical_pair(str(tokens[0]), str(tokens[1]))] = path
    return result


def main() -> int:
    store = DurableAssemblyJobStore(
        WORKSPACE / "demo/semantic_ports/project03_live_adapter_full_jobs"
    )
    plan = {
        "schemaVersion": "ordered-assembly-plan/v2",
        "projectId": "project03",
        "steps": [
            {"stepId": f"step-{index:02d}-{token.lower()}", "moduleToken": token}
            for index, token in enumerate(TOKENS, start=1)
        ],
    }
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    job = store.create(
        plan,
        execution_mode="live_cad",
        idempotency_key=f"project03-full-live-{stamp}",
    )
    cache = WORKSPACE / "demo/semantic_ports/project03_live_adapter_four_step_jobs/pair_brep_cache_manifest_v3.json"
    executable = WORKSPACE / "artifacts/solidworks-mcp-current/SolidWorksMcpApp.exe"
    contacts = {
        canonical_pair("AA00", token)
        for token in ("AE00", "AD00", "AI00", "AG00", "AH00", "AJ00")
    }
    gate = live_pair_local_collision_hard_gate(
        store=store,
        workspace=WORKSPACE,
        executable=executable,
        cache_manifest_path=cache,
        accepted_baselines=baseline_map(cache),
        step_member_tokens={
            "AE00": {"AE00"},
            "AD00": {"AD00"},
            "AI00": {"AI00"},
            "AG00": {"AG00"},
            "AH00": {"AH00"},
            "AJ00": {"AJ00"},
            "AB00": {"AB00", "AC00"},
        },
        accepted_contact_token_pairs=contacts,
        timeout_seconds=3600.0,
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
        "schemaVersion": "project03-uninterrupted-full-live-adapter/v1",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "jobId": job["jobId"],
        "status": result["status"],
        "tokens": TOKENS,
        "committedStepCount": sum(step.get("status") == "succeeded" for step in result.get("steps") or []),
        "executionDurationSeconds": result.get("executionDurationSeconds"),
        "lastCommittedCheckpoint": result.get("lastCommittedCheckpoint"),
        "rollback": result.get("rollback"),
        "error": result.get("error"),
        "jobPath": str(store.root / job["jobId"] / "job.json"),
        "evidenceManifestPath": str(store.root / job["jobId"] / "evidence-manifest.json"),
        "productionReady": False,
        "scopeBoundary": {
            "singleUninterruptedJob": True,
            "ac00StaticHybridSnapshot": True,
            "dynamicMotionValidated": False,
        },
    }
    target = store.root / "latest_uninterrupted.json"
    target.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "succeeded" else 2


if __name__ == "__main__":
    raise SystemExit(main())
