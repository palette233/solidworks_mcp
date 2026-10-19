from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
BACKEND_SRC = WORKSPACE / "apps" / "demo-backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.ordered_assembly_planner import preview_ordered_assembly
from demo_backend.project_assembly_profile import load_project_assembly_profile
from demo_backend.semantic_assembly_jobs import (
    AssemblyJobExecutor,
    DurableAssemblyJobStore,
    validated_artifact_step_runner,
)


REQUIREMENTS = {
    "project01": "项目01：先添加SS00，再添加FF00，然后添加SM00，接着添加GN00，再添加BD00，然后添加GJ00，最后添加LM00。",
    "project03": "项目03：先添加AE00，再添加AD00，然后添加AI00，接着添加AG00，再添加AH00，然后添加AJ00，最后添加AB00。",
    "project05": "项目05：先添加D000，再添加K000，然后添加F000，接着添加M000，再添加G000，然后添加N000，接着添加P000，最后添加B000。",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    root = WORKSPACE / "demo" / "semantic_ports" / "cross_project_artifact_replay" / stamp
    rows = []
    for project_id, requirement in REQUIREMENTS.items():
        profile = load_project_assembly_profile(project_id)
        closure_path = (WORKSPACE / profile["artifacts"]["orderedClosure"]).resolve()
        closure = json.loads(closure_path.read_text(encoding="utf-8-sig"))
        plan = preview_ordered_assembly(project_id, requirement)["plan"]
        store = DurableAssemblyJobStore(root / project_id)
        job = store.create(
            plan,
            execution_mode="validated_artifact_replay",
            idempotency_key=f"{project_id}-cross-project-{stamp}",
        )
        result = AssemblyJobExecutor(
            store, validated_artifact_step_runner(closure, WORKSPACE)
        ).run(job["jobId"])
        rows.append(
            {
                "projectId": project_id,
                "success": result["status"] == "succeeded",
                "jobId": job["jobId"],
                "stepCount": len(result["steps"]),
                "committedStepCount": sum(
                    step["status"] == "succeeded" for step in result["steps"]
                ),
                "finalModuleToken": result["lastCommittedCheckpoint"]["moduleToken"],
                "finalAssemblyPath": result["lastCommittedCheckpoint"]["assemblyPath"],
                "jobPath": str(store.root / job["jobId"] / "job.json"),
                "evidenceManifestPath": str(
                    store.root / job["jobId"] / "evidence-manifest.json"
                ),
                "sourceClosurePath": str(closure_path),
            }
        )
    report = {
        "schemaVersion": "cross-project-validated-artifact-replay/v1",
        "generatedAt": utc_now(),
        "success": all(row["success"] for row in rows),
        "projectCount": len(rows),
        "projects": rows,
        "realCadRerunPerformed": False,
        "boundary": (
            "Every committed step references a previously accepted cumulative CAD artifact and evidence file. "
            "This validates cross-project job semantics, not a new SolidWorks run."
        ),
    }
    output = root / "cross_project_artifact_replay_closure.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    latest = output.parent.parent / "latest.json"
    latest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"success": report["success"], "output": str(output)}, ensure_ascii=False))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
