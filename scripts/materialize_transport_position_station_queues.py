#!/usr/bin/env python3
"""Materialize confirmed transport station plans through the common CAD queue."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from time import perf_counter


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.parameterized_datum_validation_execution import (  # noqa: E402
    materialize_station_candidate_validation_queue,
    plan_next_parameterized_datum_validation,
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def _short_identity(value: str) -> str:
    project, token = value.split("::", 1)
    match = re.fullmatch(r"project(\d+)", project)
    prefix = f"p{int(match.group(1)):02d}" if match else project
    slug = f"{prefix}-{token.lower()}"
    if not re.fullmatch(r"[a-z0-9-]+", slug):
        raise ValueError(f"unsafe module identity for queue path: {value}")
    return slug


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--planning-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report_path = (ROOT / args.planning_report).resolve()
    output = (ROOT / args.output).resolve()
    report_path.relative_to(ROOT)
    output.relative_to(ROOT)
    if not report_path.is_file():
        raise FileNotFoundError(report_path)
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite transport queue evidence: {output}")
    report = _read(report_path)
    if report.get("schemaVersion") != "transport-position-station-planning-report/v1":
        raise ValueError("unsupported transport planning report")
    rows = report.get("results") or []
    if len(rows) != report.get("candidateCount"):
        raise ValueError("transport planning report count mismatch")
    output.mkdir(parents=True)
    started_at = datetime.now(timezone.utc).astimezone().isoformat()
    started = perf_counter()
    results = []
    for row in rows:
        source = str(row.get("sourceModuleDefinitionId") or "")
        target = str(row.get("targetBaseDefinitionId") or "")
        queue_name = _short_identity(source) + "--" + _short_identity(target)
        package_path = ROOT / str(row.get("candidatePackagePath") or "")
        queue_dir = output / queue_name
        item_started = perf_counter()
        try:
            if row.get("planned") is not True or row.get("validationPackagePrepared") is not True:
                raise ValueError("candidate was not fully planned")
            if not package_path.is_file():
                raise FileNotFoundError(package_path)
            materialized = materialize_station_candidate_validation_queue(
                ROOT, package_path, queue_dir
            )
            execution_plan = plan_next_parameterized_datum_validation(ROOT, queue_dir)
            results.append({
                "ruleId": row["ruleId"],
                "sourceModuleDefinitionId": source,
                "targetBaseDefinitionId": target,
                "status": "ready_for_nonprototype_cad_validation",
                "queueDirectory": str(queue_dir.relative_to(ROOT)).replace("\\", "/"),
                "queueDigest": materialized["queueDigest"],
                "candidateDirectory": str(Path(materialized["candidateDirectory"]).relative_to(ROOT)).replace("\\", "/"),
                "executionPlan": {
                    "packageKind": execution_plan["packageKind"],
                    "preconditions": execution_plan["preconditions"],
                    "requiresTargetStationPostcheckBeforePublication": execution_plan[
                        "requiresTargetStationPostcheckBeforePublication"
                    ],
                },
                "durationSeconds": perf_counter() - item_started,
            })
        except Exception as exc:
            results.append({
                "ruleId": row.get("ruleId"),
                "sourceModuleDefinitionId": source,
                "targetBaseDefinitionId": target,
                "status": "materialization_failed",
                "queueDirectory": str(queue_dir.relative_to(ROOT)).replace("\\", "/"),
                "errorType": type(exc).__name__,
                "message": str(exc),
                "durationSeconds": perf_counter() - item_started,
            })
    summary = {
        "schemaVersion": "transport-position-station-validation-queue-batch/v1",
        "sourcePlanningReportPath": str(report_path.relative_to(ROOT)).replace("\\", "/"),
        "candidateCount": len(results),
        "readyCount": sum(row["status"] == "ready_for_nonprototype_cad_validation" for row in results),
        "failedCount": sum(row["status"] == "materialization_failed" for row in results),
        "startedAt": started_at,
        "finishedAt": datetime.now(timezone.utc).astimezone().isoformat(),
        "durationSeconds": perf_counter() - started,
        "results": results,
        "cadStarted": False,
        "claimBoundary": (
            "Queue materialization and execution planning only. Each pair still requires "
            "an empty SolidWorks session, non-prototype CAD execution, save/reopen and "
            "target-station postcheck. Fastening and collision/B-rep remain separate."
        ),
    }
    _write(output / "batch-report.json", summary)
    print(json.dumps({key: summary[key] for key in (
        "candidateCount", "readyCount", "failedCount", "durationSeconds", "cadStarted"
    )}, ensure_ascii=False))
    return 0 if summary["failedCount"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
