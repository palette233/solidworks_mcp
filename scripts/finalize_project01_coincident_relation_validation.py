from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JOBS_ROOT = ROOT / "demo/global_assembly_contexts/manifest_jobs"
DEFAULT_OUTPUTS = {
    "coincident": ROOT / "demo/global_assembly_contexts/project01-coincident-validation-v1/final-validation-report.json",
    "concentric": ROOT / "demo/global_assembly_contexts/project01-concentric-validation-v1/final-validation-report.json",
}


def _load(path: Path) -> dict:
    value = json.loads(path.resolve().read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON根节点必须为对象：{path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Finalize Project01 GN00/JJ00 coincidence validation.")
    parser.add_argument("job_id")
    parser.add_argument("--relation", choices=sorted(DEFAULT_OUTPUTS), default="coincident")
    parser.add_argument("--jobs-root", type=Path, default=DEFAULT_JOBS_ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    job_path = args.jobs_root.resolve() / args.job_id / "job.json"
    job = _load(job_path)
    checkpoint = job.get("lastCommittedCheckpoint") or {}
    evidence_path = Path(str(checkpoint.get("evidencePath") or ""))
    evidence = _load(evidence_path)
    run_dir = evidence_path.parent
    cad_path = run_dir / "cad-result.json"
    cad = _load(cad_path)
    relation_type = {
        "coincident": "swMateCOINCIDENT",
        "concentric": "swMateCONCENTRIC",
    }[args.relation]
    measured_relation = next(
        (
            row
            for row in cad.get("validationResults") or []
            if row.get("RelationTypeName") == relation_type
        ),
        None,
    )
    tool = cad.get("toolResult") or {}
    checks = {
        "jobSucceeded": job.get("status") == "succeeded",
        "cadSucceeded": cad.get("success") is True,
        "outputPublished": cad.get("published") is True
        and Path(str(cad.get("outputAssemblyPath") or "")).is_file(),
        "sourceAssemblyUnchanged": cad.get("sourceAssemblyUnchanged") is True,
        "zeroMateMutation": cad.get("noMateMutation") is True
        and tool.get("RequestedMateCount") == 0
        and tool.get("CreatedMateCount") == 0,
        "relationEndpointsResolved": bool(
            measured_relation and measured_relation.get("EndpointsResolved")
        ),
        "relationPassed": bool(
            measured_relation and measured_relation.get("Passed")
        ),
        "saveCloseReopenPassed": bool(tool.get("Reopened") and tool.get("ReopenedMateParametersMatch")),
    }
    report = {
        "schemaVersion": "project01-relation-validation-final/v2",
        "status": "passed" if all(checks.values()) else "failed",
        "projectId": "project01",
        "jobId": args.job_id,
        "relation": (
            "GN00 support plane coincident with JJ00 datum plane"
            if args.relation == "coincident"
            else "GN00 locating-hole axis coaxial with JJ00 mounting-hole axis"
        ),
        "checks": checks,
        "measurement": {
            "expectedDistanceMeters": measured_relation.get("ExpectedDistanceMeters") if measured_relation else None,
            "measuredDistanceMeters": measured_relation.get("MeasuredDistanceMeters") if measured_relation else None,
            "absoluteDistanceErrorMeters": measured_relation.get("AbsoluteErrorMeters") if measured_relation else None,
            "distanceToleranceMeters": measured_relation.get("ToleranceMeters") if measured_relation else None,
            "expectedAngleRadians": measured_relation.get("ExpectedAngleRadians") if measured_relation else None,
            "measuredAngleRadians": measured_relation.get("MeasuredAngleRadians") if measured_relation else None,
            "absoluteAngleErrorRadians": measured_relation.get("AbsoluteAngleErrorRadians") if measured_relation else None,
            "angleToleranceRadians": measured_relation.get("AngleToleranceRadians") if measured_relation else None,
            "endpointResolutionStrategies": measured_relation.get("EndpointResolutionStrategies") if measured_relation else [],
        },
        "timing": {
            "jobDurationSeconds": job.get("executionDurationSeconds"),
            "cadDurationSeconds": cad.get("durationSeconds"),
            "phaseDurationsSeconds": tool.get("PhaseDurationsSeconds") or {},
        },
        "collisionStatus": "not_evaluated_by_current_scope",
        "artifacts": {
            "outputAssembly": cad.get("outputAssemblyPath"),
            "job": str(job_path),
            "cadResult": str(cad_path),
        },
    }
    output = (args.output or DEFAULT_OUTPUTS[args.relation]).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({**report, "reportPath": str(output)}, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
