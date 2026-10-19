from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JOBS = ROOT / "demo/global_assembly_contexts/manifest_jobs"
OUTPUT = (
    ROOT
    / "demo/global_assembly_contexts/project05-release-permutation-v2/closure-report.json"
)
JOB_CASES = (
    ("project05-job-26669ac03021", ["D000", "F000"]),
    ("project05-job-5a25aa745c3e", ["F000", "D000"]),
)
EXPECTED_RELEASE_ID = "relation-v20-project05-d000-f000-portable-driving-20261011"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _step_summary(step: dict) -> dict:
    checkpoint = step.get("checkpoint") or {}
    evidence_paths = [Path(value) for value in checkpoint.get("cadActionEvidencePaths") or []]
    cad_paths = [path for path in evidence_paths if path.name == "cad-result.json"]
    cad = _read(cad_paths[0]) if len(cad_paths) == 1 and cad_paths[0].is_file() else {}
    tool = cad.get("toolResult") or {}
    output = Path(str(cad.get("outputAssemblyPath") or checkpoint.get("assemblyPath") or ""))
    output_exists = output.is_file()
    output_hash = _sha256(output) if output_exists else None
    recorded_hash = cad.get("outputAssemblySha256")
    fully_constrained = tool.get("TargetFullyConstrained") is True
    constraint_state_accepted = tool.get("TargetConstraintStateAccepted") is True
    checks = {
        "stepSucceeded": step.get("status") == "succeeded" and cad.get("success") is True,
        "requestedMateCountCreated": (
            int(tool.get("RequestedMateCount") or 0) > 0
            and tool.get("RequestedMateCount") == tool.get("CreatedMateCount")
        ),
        "constraintStateAccepted": constraint_state_accepted,
        "mateSolveClean": tool.get("MateSolveClean") is True,
        "savedClosedReopened": (
            tool.get("Reopened") is True
            and tool.get("ReopenedMateParametersMatch") is True
            and cad.get("outputClosedAfterVerification") is True
        ),
        "sourceAssemblyUnchanged": cad.get("sourceAssemblyUnchanged") is True,
        "targetSourceSessionClean": cad.get("targetSourceSessionClean") is True,
        "noCaseAnchor": tool.get("TargetCaseAnchored") is False,
        "noLeafPoseAnchor": (
            tool.get("RequestedTargetLeafPoseAnchorCount") == 0
            and tool.get("AppliedTargetLeafPoseAnchorCount") == 0
        ),
        "outputAssemblyExists": output_exists,
        "outputHashMatchesEvidence": bool(recorded_hash) and output_hash == recorded_hash,
    }
    return {
        "stepId": step.get("stepId"),
        "moduleToken": step.get("moduleToken"),
        "status": "passed" if all(checks.values()) else "blocked",
        "checks": checks,
        "constraintStateObservation": {
            "targetFullyConstrained": fully_constrained,
            "targetConstraintStateAccepted": constraint_state_accepted,
            "acceptedFlexibleInternalState": (
                constraint_state_accepted and not fully_constrained
            ),
            "residualDofScope": "external_module_placement",
        },
        "durationSeconds": (step.get("attempts") or [{}])[-1].get("durationSeconds"),
        "assemblyPath": str(output),
        "assemblySha256": output_hash,
        "cadEvidencePath": str(cad_paths[0]) if len(cad_paths) == 1 else None,
    }


def _job_summary(
    job_id: str, expected_order: list[str], expected_release_id: str
) -> dict:
    job_path = JOBS / job_id / "job.json"
    job = _read(job_path)
    plan = job.get("plan") or {}
    authority = plan.get("releaseAuthority") or {}
    binding = authority.get("binding") or {}
    steps = [_step_summary(step) for step in job.get("steps") or []]
    actual_order = [str(step.get("moduleToken") or "") for step in job.get("steps") or []]
    checks = {
        "jobSucceeded": job.get("status") == "succeeded",
        "assemblyCompleted": job.get("assemblyStatus") == "assembled",
        "expectedOrderExecuted": actual_order == expected_order,
        "releaseAuthorityVerified": authority.get("status") == "verified",
        "expectedReleaseBound": binding.get("releaseId") == expected_release_id,
        "allPacketsPassed": bool(steps) and all(step["status"] == "passed" for step in steps),
        "collisionDeliberatelyNotEvaluated": job.get("collisionStatus") == "not_evaluated",
    }
    final_path = Path(str((job.get("lastCommittedCheckpoint") or {}).get("assemblyPath") or ""))
    return {
        "jobId": job_id,
        "jobPath": str(job_path),
        "status": "passed" if all(checks.values()) else "blocked",
        "checks": checks,
        "expectedOrder": expected_order,
        "actualOrder": actual_order,
        "executionDurationSeconds": job.get("executionDurationSeconds"),
        "releaseId": binding.get("releaseId"),
        "releaseDigest": binding.get("releaseDigest"),
        "steps": steps,
        "finalAssemblyPath": str(final_path),
        "finalAssemblyExists": final_path.is_file(),
        "finalAssemblySha256": _sha256(final_path) if final_path.is_file() else None,
    }


def build_report(
    job_cases: tuple[tuple[str, list[str]], ...] = JOB_CASES,
    expected_release_id: str = EXPECTED_RELEASE_ID,
) -> dict:
    cases = [
        _job_summary(job_id, order, expected_release_id)
        for job_id, order in job_cases
    ]
    expected_tokens = set(cases[0]["actualOrder"]) if cases else set()
    checks = {
        "bothPermutationsPassed": len(cases) == 2 and all(case["status"] == "passed" for case in cases),
        "ordersAreReversePermutations": (
            len(cases) == 2
            and cases[0]["actualOrder"] == list(reversed(cases[1]["actualOrder"]))
            and expected_tokens == set(cases[1]["actualOrder"])
            and len(expected_tokens) == len(cases[0]["actualOrder"])
        ),
        "sameImmutableReleaseUsed": (
            len({case["releaseId"] for case in cases}) == 1
            and len({case["releaseDigest"] for case in cases}) == 1
        ),
        "bothFinalAssembliesExist": all(case["finalAssemblyExists"] for case in cases),
        "cadActuallyExecuted": all(
            all(step["cadEvidencePath"] for step in case["steps"]) for case in cases
        ),
    }
    return {
        "schemaVersion": "project05-released-permutation-cad-closure/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if all(checks.values()) else "blocked",
        "checks": checks,
        "releaseId": expected_release_id,
        "cases": cases,
        "collisionStatus": "not_evaluated",
        "statement": (
            "Project05 A000基座上的获授权附加模组已在同一不可变关系发布下，"
            "按两种反向顺序完成真实CAD累计装配、逐包保存关闭重开及配合复核。"
            "本报告证明所列发布模组链的顺序兼容性，不包含实体干涉/B-rep验收。"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="汇总Project05发布绑定正反顺序真实CAD闭环证据。"
    )
    parser.add_argument(
        "--case",
        action="append",
        help="格式为jobId:TOKEN1,TOKEN2；必须提供两组反向顺序。",
    )
    parser.add_argument("--release-id", default=EXPECTED_RELEASE_ID)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    job_cases = JOB_CASES
    if args.case:
        parsed: list[tuple[str, list[str]]] = []
        for value in args.case:
            job_id, separator, tokens = value.partition(":")
            order = [token.strip().upper() for token in tokens.split(",") if token.strip()]
            if not separator or not job_id.strip() or not order:
                raise ValueError(f"无效--case：{value}")
            parsed.append((job_id.strip(), order))
        if len(parsed) != 2:
            raise ValueError("必须提供恰好两组--case。")
        job_cases = tuple(parsed)
    report = build_report(job_cases, args.release_id)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
