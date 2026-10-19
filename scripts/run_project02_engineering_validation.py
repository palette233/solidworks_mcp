#!/usr/bin/env python3
"""Run independent static engineering validation for a Project02 Demo job."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.engineering_validation_jobs import EngineeringValidationJobStore  # noqa: E402
from demo_backend.main import (  # noqa: E402
    _assembly_job_store,
    _run_project02_engineering_validation,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-job-id", required=True)
    parser.add_argument("--idempotency-key")
    args = parser.parse_args()

    assembly_store = _assembly_job_store(ROOT, "project02")
    validation_store = EngineeringValidationJobStore(
        assembly_store.root / "_engineering_validations"
    )
    source = assembly_store.load(args.source_job_id)
    validation = validation_store.create(
        source,
        idempotency_key=args.idempotency_key,
    )
    _run_project02_engineering_validation(ROOT, validation["validationJobId"])
    result = validation_store.load(validation["validationJobId"])
    refreshed_source = assembly_store.load(args.source_job_id)
    print(
        json.dumps(
            {
                "validationJobId": result["validationJobId"],
                "status": result["status"],
                "collisionStatus": result["collisionStatus"],
                "durationSeconds": result.get("durationSeconds"),
                "sourceJobStatus": refreshed_source.get("status"),
                "sourceAssemblyStatus": refreshed_source.get("assemblyStatus"),
                "sourceDemoCheckpoint": refreshed_source.get("demoCheckpoint"),
                "engineeringCheckpoint": refreshed_source.get("engineeringCheckpoint"),
                "evidencePath": result.get("evidencePath"),
                "error": result.get("error"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result["status"] == "succeeded" else 2


if __name__ == "__main__":
    raise SystemExit(main())
