from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JOB = (
    ROOT
    / "demo/global_assembly_contexts/manifest_jobs/project01-job-8a21b33ff155/job.json"
)
DEFAULT_RUN = (
    ROOT
    / "demo/global_assembly_contexts/manifest_jobs/project01-job-8a21b33ff155/packet-runs/packet-003-attempt-01/cad-result.json"
)
DEFAULT_OUTPUT = (
    ROOT
    / "demo/global_assembly_contexts/project01-relation-validation-v1/final-validation-report.json"
)


def _load(path: Path) -> dict:
    value = json.loads(path.resolve().read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON根节点必须为对象：{path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Finalize Project01 GN00/SS00 read-only parallel validation."
    )
    parser.add_argument("--job", type=Path, default=DEFAULT_JOB)
    parser.add_argument("--cad-result", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    job = _load(args.job)
    cad = _load(args.cad_result)
    validations = cad.get("validationResults") or []
    parallel = next(
        (
            row
            for row in validations
            if row.get("RelationTypeName") == "swMatePARALLEL"
        ),
        None,
    )
    checks = {
        "jobSucceeded": job.get("status") == "succeeded",
        "cadSucceeded": cad.get("success") is True,
        "outputPublished": cad.get("published") is True
        and Path(str(cad.get("outputAssemblyPath") or "")).is_file(),
        "sourceAssemblyUnchanged": cad.get("sourceAssemblyUnchanged") is True,
        "zeroMateMutation": cad.get("noMateMutation") is True
        and (cad.get("toolResult") or {}).get("RequestedMateCount") == 0
        and (cad.get("toolResult") or {}).get("CreatedMateCount") == 0,
        "parallelRelationResolved": bool(parallel and parallel.get("EndpointsResolved")),
        "parallelRelationPassed": bool(parallel and parallel.get("Passed")),
        "saveCloseReopenPassed": bool(
            (cad.get("toolResult") or {}).get("Reopened")
            and (cad.get("toolResult") or {}).get("ReopenedMateParametersMatch")
        ),
    }
    report = {
        "schemaVersion": "project01-cross-project-relation-validation-final/v1",
        "status": "passed" if all(checks.values()) else "failed",
        "projectId": "project01",
        "jobId": job.get("jobId"),
        "relation": "GN00 anti-rotation plane parallel to SS00 datum plane",
        "executionMode": "read_only_existing_relation_verification",
        "checks": checks,
        "measurement": {
            "expectedAngleRadians": parallel.get("ExpectedAngleRadians") if parallel else None,
            "measuredAngleRadians": parallel.get("MeasuredAngleRadians") if parallel else None,
            "absoluteAngleErrorRadians": (
                parallel.get("AbsoluteAngleErrorRadians") if parallel else None
            ),
            "angleToleranceRadians": (
                parallel.get("AngleToleranceRadians") if parallel else None
            ),
            "endpointResolutionStrategies": (
                parallel.get("EndpointResolutionStrategies") if parallel else []
            ),
        },
        "timing": {
            "jobDurationSeconds": job.get("executionDurationSeconds"),
            "cadDurationSeconds": cad.get("durationSeconds"),
            "phaseDurationsSeconds": (
                (cad.get("toolResult") or {}).get("PhaseDurationsSeconds") or {}
            ),
        },
        "collisionStatus": "not_evaluated_by_current_scope",
        "artifacts": {
            "sourceAssembly": cad.get("sourceAssemblyPath"),
            "outputAssembly": cad.get("outputAssemblyPath"),
            "job": str(args.job.resolve()),
            "cadResult": str(args.cad_result.resolve()),
        },
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({**report, "reportPath": str(output)}, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
