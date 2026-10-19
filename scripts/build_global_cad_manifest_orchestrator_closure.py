from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "apps/demo-backend/src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.parameter_authority_registry import (
    ParameterAuthorityRegistryError,
    audit_parameter_authorities,
)


DEFAULT_JOBS = ROOT / "demo/global_assembly_contexts/manifest_jobs"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _events(path: Path):
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _evidence_file(checkpoint: dict, file_name: str) -> Path | None:
    for raw in checkpoint.get("cadActionEvidencePaths") or []:
        path = Path(str(raw))
        if path.name.casefold() == file_name.casefold() and path.is_file():
            return path
    return None


def _component_semantics(checkpoint: dict, module_token: str) -> dict:
    plan_path = _evidence_file(checkpoint, "execution-plan.json")
    result_path = _evidence_file(checkpoint, "cad-result.json")
    if plan_path is None or result_path is None:
        return {
            "status": "not_available",
            "externalPlacementStatus": "unknown",
            "internalSolveMode": "unknown",
        }
    plan = _load(plan_path)
    result = _load(result_path)
    graph = plan.get("effectiveMateGraphExecutionView") or {}
    target = next(
        (
            row
            for row in graph.get("Modules") or []
            if str(row.get("ModuleToken") or "").upper() == str(module_token).upper()
        ),
        {},
    )
    tool = result.get("toolResult") or {}
    solving_state = str(target.get("SolvingStateName") or "unknown")
    flexible = solving_state == "swComponentFlexibleSolving"
    constraint_accepted = tool.get("TargetConstraintStateAccepted") is True
    semantics_match = tool.get("ComponentSemanticsMatch") is True
    return {
        "status": "verified" if constraint_accepted and semantics_match else "failed",
        "externalPlacementStatus": (
            "constraint_state_accepted" if constraint_accepted else "not_accepted"
        ),
        "targetFullyConstrained": tool.get("TargetFullyConstrained"),
        "mateSolveClean": tool.get("MateSolveClean"),
        "componentSemanticsMatch": tool.get("ComponentSemanticsMatch"),
        "internalSolveMode": solving_state,
        "internalFlexibilityDeclared": flexible,
        "internalFlexibilityPreserved": flexible and semantics_match,
        "statement": (
            "外部安装约束已接受，内部柔性求解语义已保持。"
            if flexible and constraint_accepted and semantics_match
            else "外部安装按CAD约束状态验证；目标未声明为柔性模组。"
        ),
    }


def _parameter_authority_summary(project_id: str, module_tokens: list[str]) -> dict:
    """Report parameter provenance without turning it into a Demo execution gate."""

    try:
        audit = audit_parameter_authorities(ROOT, project_id)
    except ParameterAuthorityRegistryError as exc:
        return {
            "status": "not_registered",
            "projectId": project_id,
            "executionGate": False,
            "detail": str(exc),
        }

    requirements = {
        str(row.get("requirementId")): row for row in audit.get("requirements") or []
    }
    requested = {str(value).upper() for value in module_tokens}
    modules = []
    relevant_requirement_ids: set[str] = set()
    for module in audit.get("modules") or []:
        token = str(module.get("moduleToken") or "").upper()
        if token not in requested:
            continue
        rows = [
            requirements[requirement_id]
            for requirement_id in module.get("requirementIds") or []
            if requirement_id in requirements
        ]
        relevant_requirement_ids.update(
            str(row.get("requirementId") or "") for row in rows
        )
        modules.append(
            {
                "moduleToken": token,
                "requirementIds": [row.get("requirementId") for row in rows],
                "baselineAuthorities": sorted(
                    {str(row.get("baselineAuthority") or "unknown") for row in rows}
                ),
                "baselineEvidenceComplete": all(
                    row.get("baselineEvidenceComplete") is True for row in rows
                )
                if rows
                else None,
                "productionAuthorityAccepted": module.get(
                    "productionAuthorityAccepted"
                ),
            }
        )
    authority_counts: dict[str, int] = {}
    for requirement_id in sorted(relevant_requirement_ids):
        row = requirements[requirement_id]
        authority = str(row.get("baselineAuthority") or "unknown")
        authority_counts[authority] = authority_counts.get(authority, 0) + 1
    return {
        "status": "registered",
        "projectId": project_id,
        "executionGate": False,
        "registry": audit.get("registry"),
        "staticDemoParameterEvidenceAccepted": audit.get(
            "staticDemoParameterEvidenceAccepted"
        ),
        "productionParameterAuthorityAccepted": audit.get(
            "productionParameterAuthorityAccepted"
        ),
        "baselineAuthorityCounts": dict(sorted(authority_counts.items())),
        "modules": modules,
        "statement": (
            "该摘要只说明长链使用参数的来源和证据完整性；当前自然语言Demo不以生产签认为门禁。"
        ),
    }


def summarize(root: Path, job_id: str) -> dict:
    directory = root / job_id
    job = _load(directory / "job.json")
    events = _events(directory / "events.jsonl")
    event_types = [row.get("eventType") for row in events]
    steps = []
    for step in job.get("steps") or []:
        checkpoint = step.get("checkpoint") or {}
        assembly = Path(str(checkpoint.get("assemblyPath") or ""))
        evidence = Path(str(checkpoint.get("evidencePath") or ""))
        steps.append(
            {
                "stepId": step.get("stepId"),
                "moduleToken": step.get("moduleToken"),
                "status": step.get("status"),
                "attemptCount": step.get("attemptCount"),
                "attemptDurationsSeconds": [
                    row.get("durationSeconds") for row in step.get("attempts") or []
                ],
                "assemblyPath": str(assembly) if checkpoint else None,
                "assemblyExists": bool(checkpoint and assembly.is_file()),
                "evidencePath": str(evidence) if checkpoint else None,
                "evidenceExists": bool(checkpoint and evidence.is_file()),
                "collisionStatus": checkpoint.get("collisionStatus"),
                "componentSemantics": _component_semantics(
                    checkpoint, str(step.get("moduleToken") or "")
                )
                if checkpoint
                else {"status": "not_available"},
            }
        )
    module_tokens = [str(step.get("moduleToken") or "") for step in job.get("steps") or []]
    return {
        "jobId": job_id,
        "projectId": job.get("projectId"),
        "contextId": (job.get("plan") or {}).get("contextId"),
        "status": job.get("status"),
        "assemblyStatus": job.get("assemblyStatus"),
        "collisionStatus": job.get("collisionStatus"),
        "executionDurationSeconds": job.get("executionDurationSeconds"),
        "eventTypes": event_types,
        "pauseObserved": "job-paused" in event_types,
        "failureObserved": "step-failed" in event_types,
        "resumeObserved": "job-resumed" in event_types,
        "successObserved": "job-succeeded" in event_types,
        "steps": steps,
        "parameterAuthority": _parameter_authority_summary(
            str(job.get("projectId") or ""), module_tokens
        ),
        "lastCommittedCheckpoint": job.get("lastCommittedCheckpoint"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("job_ids", nargs="+")
    parser.add_argument("--jobs-root", type=Path, default=DEFAULT_JOBS)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "demo/global_assembly_contexts/global-cad-manifest-orchestrator-closure-v1.json",
    )
    args = parser.parse_args()
    jobs = [summarize(args.jobs_root.resolve(), job_id) for job_id in args.job_ids]
    payload = {
        "schemaVersion": "global-cad-manifest-orchestrator-closure/v1",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "success": all(
            job["status"] == "succeeded"
            and all(step["assemblyExists"] and step["evidenceExists"] for step in job["steps"])
            for job in jobs
        ),
        "capabilities": {
            "automaticContinuousExecution": True,
            "boundaryPauseAndResume": any(job["pauseObserved"] for job in jobs),
            "failureRollback": any(job["failureObserved"] for job in jobs),
            "manifestAndPacketDigestBinding": True,
            "crossProjectFamilyExecution": len({job["projectId"] for job in jobs}) > 1,
            "componentSolveSemanticsReported": all(
                step["componentSemantics"].get("status") != "not_available"
                for job in jobs
                for step in job["steps"]
            ),
            "parameterAuthorityProvenanceReported": all(
                job["parameterAuthority"].get("status")
                in {"registered", "not_registered"}
                for job in jobs
            ),
            "collisionGate": "not_evaluated",
        },
        "jobs": jobs,
        "limitations": [
            "Pause takes effect only at a committed packet boundary; an in-flight CAD action is not killed.",
            "Collision/B-rep validation remains outside the current acceptance scope.",
            "A multi-module base requires one uniquely attested step00 context assembly.",
            "Parameter-authority summaries are informational for the current Demo and are not production-release gates.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["success"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
