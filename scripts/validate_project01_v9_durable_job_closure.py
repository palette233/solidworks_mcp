from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JOB_ID = "project01-job-9cb5c4c0c647"
DEFAULT_OUTPUT = ROOT / (
    "demo/global_assembly_contexts/project01-jj00-ss00-gn00-v8-driving-v1/"
    "durable-executor-closure.json"
)
EXPECTED_RELEASE_ID = "relation-v9-project01-driving-independent-20261011"
EXPECTED_TEMPLATE_IDS = {
    "template/project01/ss00-to-jj00-three-datum-installation/c087ea93d1",
    "template/project01/gn00-to-jj00-primary/8ff522aead",
    "template/project01/gn00-ss00-standalone-parallel/5df3a32e59",
}


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON根节点必须是对象：{path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _cad_checks(payload: dict[str, Any]) -> dict[str, bool]:
    tool = payload.get("toolResult") or {}
    requested = int(tool.get("RequestedMateCount") or 0)
    mate_results = tool.get("MateResults") or []
    verifications = tool.get("MateVerifications") or []
    return {
        "success": payload.get("success") is True and tool.get("Success") is True,
        "sourceUnchanged": payload.get("sourceAssemblyUnchanged") is True,
        "documentsClosed": (
            payload.get("outputClosedAfterVerification") is True
            and payload.get("targetSourceClosedAfterVerification") is True
            and payload.get("targetSourceSessionClean") is True
        ),
        "threeOfThreeMates": (
            requested == 3
            and int(tool.get("CreatedMateCount") or 0) == 3
            and len(mate_results) == 3
            and all(row.get("Success") is True for row in mate_results)
            and len(verifications) == 3
            and all(row.get("Found") is True for row in verifications)
        ),
        "independentInsert": (
            tool.get("IndependentComponentInserted") is True
            and tool.get("TargetCaseAnchored") is False
            and tool.get("OriginalComponentRemoved") is True
        ),
        "constraintSolveAccepted": (
            tool.get("TargetFullyConstrained") is True
            and tool.get("TargetConstraintStateAccepted") is True
            and tool.get("MateSolveClean") is True
        ),
        "saveCloseReopenVerified": (
            tool.get("Reopened") is True
            and tool.get("ReopenedMateParametersMatch") is True
            and tool.get("ComponentSemanticsMatch") is True
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the Project01 v9 released durable CAD job closure."
    )
    parser.add_argument("--job-id", default=DEFAULT_JOB_ID)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    job_root = ROOT / "demo/global_assembly_contexts/manifest_jobs" / args.job_id
    job = _read(job_root / "job.json")
    binding = (job.get("plan") or {}).get("relationReleaseBinding") or {}
    authority = (job.get("plan") or {}).get("releaseAuthority") or {}
    step_rows = []
    all_cad_checks: list[bool] = []
    for step in job.get("steps") or []:
        checkpoint = step.get("checkpoint") or {}
        result_path = next(
            Path(value)
            for value in checkpoint.get("cadActionEvidencePaths") or []
            if str(value).endswith("cad-result.json")
        )
        result = _read(result_path)
        output_path = Path(checkpoint["assemblyPath"])
        checks = _cad_checks(result)
        all_cad_checks.extend(checks.values())
        step_rows.append(
            {
                "stepId": step["stepId"],
                "moduleToken": step["moduleToken"],
                "attemptCount": step["attemptCount"],
                "durationSeconds": step["attempts"][-1]["durationSeconds"],
                "cadDurationSeconds": result.get("durationSeconds"),
                "assemblyPath": str(output_path),
                "assemblySizeBytes": output_path.stat().st_size,
                "assemblySha256": _sha256(output_path),
                "reportedAssemblySha256": result.get("outputAssemblySha256"),
                "checks": checks,
            }
        )

    global_checks = {
        "jobSucceeded": job.get("status") == "succeeded",
        "assemblyStatusAccepted": job.get("assemblyStatus") == "assembled",
        "twoPacketsCommitted": (
            len(step_rows) == 2
            and [row["moduleToken"] for row in step_rows] == ["SS00", "GN00"]
            and all(row["attemptCount"] == 1 for row in step_rows)
        ),
        "releaseAuthorityVerified": (
            binding.get("releaseId") == EXPECTED_RELEASE_ID
            and authority.get("status") == "verified"
            and set(authority.get("authorizedDrivingTemplateIds") or [])
            == EXPECTED_TEMPLATE_IDS
            and set(authority.get("usedDrivingTemplateIds") or [])
            == EXPECTED_TEMPLATE_IDS
        ),
        "outputDigestsMatch": all(
            row["assemblySha256"] == row["reportedAssemblySha256"]
            for row in step_rows
        ),
        "allCadChecksPassed": all(all_cad_checks),
        "collisionScopeRespected": job.get("collisionStatus") == "not_evaluated",
    }
    report = {
        "schemaVersion": "project01-v9-durable-executor-closure/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if all(global_checks.values()) else "failed",
        "jobId": args.job_id,
        "releaseId": binding.get("releaseId"),
        "contextId": (job.get("plan") or {}).get("contextId"),
        "executionDurationSeconds": job.get("executionDurationSeconds"),
        "globalChecks": global_checks,
        "steps": step_rows,
        "finalAssemblyPath": step_rows[-1]["assemblyPath"],
        "collisionStatus": "not_evaluated",
        "statement": (
            "Project01已由发布绑定的自然语言事务完成JJ00/SS00/GN00两包累计装配；"
            "每包均完成独立插入、3/3配合、保存关闭重开复核。"
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
