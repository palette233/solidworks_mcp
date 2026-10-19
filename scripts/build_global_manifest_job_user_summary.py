#!/usr/bin/env python3
"""Build compact JSON/Markdown evidence for one durable manifest job."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.global_manifest_job_user_summary import (  # noqa: E402
    write_global_manifest_job_user_summary,
)


DEFAULT_JOBS_ROOT = ROOT / "demo/global_assembly_contexts/manifest_jobs"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job_id")
    parser.add_argument("--jobs-root", type=Path, default=DEFAULT_JOBS_ROOT)
    args = parser.parse_args()

    job_dir = args.jobs_root.resolve() / args.job_id
    job = _read(job_dir / "job.json")
    written = write_global_manifest_job_user_summary(job, job_dir)
    summary = _read(Path(str(written["jsonPath"])))
    print(
        json.dumps(
            {
                "success": summary["status"] == "passed",
                "jobId": args.job_id,
                "summaryPath": written["jsonPath"],
                "markdownPath": written["markdownPath"],
                "resultAssemblyPath": summary.get("resultAssemblyPath"),
                "collisionStatus": summary.get("collisionStatus"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if summary["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
