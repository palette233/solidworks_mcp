from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
BACKEND_SRC = WORKSPACE / "apps" / "demo-backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.project05_semantic_assembly_cad_runner import (
    project05_live_cad_step_runner,
)
from demo_backend.semantic_assembly_collision_gate import (
    canonical_pair,
    live_pair_local_collision_hard_gate,
    module_token,
)
from demo_backend.semantic_assembly_jobs import (
    AssemblyJobExecutor,
    DurableAssemblyJobStore,
)


TOKENS = ["K000", "F000", "M000", "G000", "N000", "P000", "B000"]
STEP_MEMBERS = {
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


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def baseline_map(cache_path: Path) -> dict[tuple[str, str], Path]:
    result: dict[tuple[str, str], Path] = {}
    for row in load(cache_path).get("entries") or []:
        baseline = row.get("baselinePath")
        sources = row.get("sources") or []
        if baseline and len(sources) == 2:
            first_name = str(sources[0]["componentName"])
            second_name = str(sources[1]["componentName"])
            baseline_path = Path(str(baseline))
            result[canonical_pair(first_name, second_name)] = baseline_path
            first_token = module_token(first_name)
            second_token = module_token(second_name)
            if first_token and second_token:
                token_pair = canonical_pair(first_token, second_token)
                existing = result.get(token_pair)
                if existing is None or existing == baseline_path:
                    result[token_pair] = baseline_path
    return result


def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    store = DurableAssemblyJobStore(
        WORKSPACE / "demo" / "semantic_ports" / "project05_live_adapter_jobs"
    )
    plan = {
        "schemaVersion": "ordered-assembly-plan/v2",
        "projectId": "project05",
        "steps": [
            {
                "stepId": f"step-{index:02d}-{token.lower()}",
                "moduleToken": token,
            }
            for index, token in enumerate(TOKENS, start=2)
        ],
    }
    job = store.create(
        plan,
        execution_mode="live_cad",
        idempotency_key=f"project05-live-tail-{stamp}",
    )
    seed_assembly = (
        WORKSPACE
        / "demo"
        / "semantic_ports"
        / "project05_live_adapter_pilot_v1"
        / "step01_D000_cumulative.SLDASM"
    )
    seed_evidence = seed_assembly.with_suffix(".stage-result.json")
    store.seed_verified_checkpoint(
        job["jobId"],
        step_id="step-01-d000",
        module_token="D000",
        assembly_path=seed_assembly,
        evidence_path=seed_evidence,
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
        accepted_baselines=baseline_map(cache_path),
        step_member_tokens=STEP_MEMBERS,
        accepted_contact_token_pairs=CONTACTS,
        timeout_seconds=1800.0,
    )
    runner = project05_live_cad_step_runner(
        store=store,
        closure=load(closure_path),
        workspace=WORKSPACE,
        executable=executable,
        hard_gate=gate,
        timeout_seconds=1800.0,
    )
    result = AssemblyJobExecutor(store, runner).run(job["jobId"])
    latest = store.root / "latest_live_tail.json"
    summary = {
        "schemaVersion": "project05-live-adapter-tail/v1",
        "jobId": job["jobId"],
        "status": result["status"],
        "seedCheckpoint": result.get("initialCommittedCheckpoint"),
        "stepCount": len(result["steps"]),
        "committedStepCount": sum(
            step["status"] == "succeeded" for step in result["steps"]
        ),
        "lastCommittedCheckpoint": result.get("lastCommittedCheckpoint"),
        "rollback": result.get("rollback"),
        "error": result.get("error"),
        "jobPath": str(store.root / job["jobId"] / "job.json"),
        "eventPath": str(store.root / job["jobId"] / "events.jsonl"),
        "evidenceManifestPath": str(
            store.root / job["jobId"] / "evidence-manifest.json"
        ),
        "productionReleased": False,
    }
    latest.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "succeeded" else 2


if __name__ == "__main__":
    raise SystemExit(main())
