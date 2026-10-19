from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JOB_ROOT = ROOT / (
    "demo/global_assembly_contexts/manifest_jobs/project03-job-d7ecc82db4f1"
)
CONTEXT_ROOT = ROOT / (
    "demo/global_assembly_contexts/project03-aa00-ae00-ad00-ai00-v13-driving-v1"
)
OUTPUT = CONTEXT_ROOT / "durable-executor-closure.json"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    job = _read(JOB_ROOT / "job.json")
    audit = _read(JOB_ROOT / "command-audit.json")
    timing = _read(JOB_ROOT / "timing-report.json")
    steps = list(job.get("steps") or [])
    cad_results = [
        _read(
            JOB_ROOT
            / "packet-runs"
            / f"packet-{index:03d}-attempt-{'02' if index == 3 else '01'}"
            / "cad-result.json"
        )
        for index in range(1, 4)
    ]
    checkpoints = [step.get("checkpoint") or {} for step in steps]
    final_path = Path(str((job.get("lastCommittedCheckpoint") or {}).get("assemblyPath") or ""))
    chain_ok = all(
        checkpoints[index].get("inputAssemblyPath")
        == checkpoints[index - 1].get("assemblyPath")
        for index in range(1, len(checkpoints))
    )
    checks = {
        "jobSucceeded": job.get("status") == "succeeded",
        "threePacketsCommitted": len(steps) == 3
        and all(step.get("status") == "succeeded" for step in steps),
        "checkpointChainIsCumulative": chain_ok,
        "commandAuditComplete": audit.get("mappedCommandCount")
        == audit.get("commandCount"),
        "timingReportGenerated": timing.get("status") == "succeeded",
        "allCadRunsSucceeded": all(row.get("success") is True for row in cad_results),
        "allSourcesUnchanged": all(
            row.get("sourceAssemblyUnchanged") is True for row in cad_results
        ),
        "allOutputsClosed": all(
            row.get("outputClosedAfterVerification") is True for row in cad_results
        ),
        "allTargetsFullyConstrained": all(
            (row.get("toolResult") or {}).get("TargetFullyConstrained") is True
            for row in cad_results
        ),
        "allMateSolvesClean": all(
            (row.get("toolResult") or {}).get("MateSolveClean") is True
            for row in cad_results
        ),
        "ai00TwoReadOnlyValidationsPassed": (
            len((cad_results[-1].get("toolResult") or {}).get("ValidationResults") or [])
            == 2
            and all(
                row.get("Passed") is True
                for row in (cad_results[-1].get("toolResult") or {}).get(
                    "ValidationResults"
                )
                or []
            )
        ),
        "finalAssemblySaved": final_path.is_file(),
    }
    report = {
        "schemaVersion": "project03-ae00-ad00-ai00-durable-closure/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if all(checks.values()) else "blocked",
        "checks": checks,
        "jobId": job.get("jobId"),
        "releaseId": ((job.get("plan") or {}).get("relationReleaseBinding") or {}).get(
            "releaseId"
        ),
        "commandAuditPath": str(JOB_ROOT / "command-audit.json"),
        "timingReportPath": str(JOB_ROOT / "timing-report.json"),
        "executionDurationSeconds": job.get("executionDurationSeconds"),
        "cadActionDurationSeconds": timing.get("cadActionDurationSeconds"),
        "recoveredRejectedAttemptDurationSeconds": timing.get(
            "recoveredFailedOrInterruptedAttemptDurationSeconds"
        ),
        "finalAssemblyPath": str(final_path),
        "finalAssemblySha256": _sha(final_path) if final_path.is_file() else None,
        "finalAssemblyBytes": final_path.stat().st_size if final_path.is_file() else None,
        "collisionStatus": "not_evaluated",
        "statement": (
            "三包累计装配、命令审计、保存关闭重开和AI00只读距离验证已闭环；"
            "本结论不包含碰撞或B-rep验证。"
        ),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
