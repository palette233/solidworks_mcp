from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.released_long_chain_evidence import (  # noqa: E402
    write_released_order_compatibility_closure,
)


DEFAULT_RELEASE_ID = (
    "relation-v47-project03-aa00-project01-calibration-transport-driving-20261012"
)
DEFAULT_JOB_A = ROOT / (
    "demo/global_assembly_contexts/manifest_jobs/project01-job-a6148a40bdc8"
)
DEFAULT_JOB_B = ROOT / (
    "demo/global_assembly_contexts/manifest_jobs/project01-job-38931a61c370"
)
DEFAULT_OUTPUT_DIRECTORY = ROOT / (
    "demo/cross_project_substitution/cumulative-project03-v1"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build CAD-backed cross-project cumulative order closure."
    )
    parser.add_argument("--job-a", type=Path, default=DEFAULT_JOB_A)
    parser.add_argument("--job-b", type=Path, default=DEFAULT_JOB_B)
    parser.add_argument("--release-id", default=DEFAULT_RELEASE_ID)
    parser.add_argument("--base-module-token", default="AA00")
    parser.add_argument("--output-directory", type=Path, default=DEFAULT_OUTPUT_DIRECTORY)
    args = parser.parse_args()

    output_directory = args.output_directory.resolve()
    json_path, markdown_path = write_released_order_compatibility_closure(
        [args.job_a, args.job_b],
        output_directory / "order-closure.json",
        expected_orders=[["SS00", "BD00"], ["BD00", "SS00"]],
        expected_release_id=args.release_id,
        base_module_token=args.base_module_token,
        markdown_output=output_directory / "order-closure.md",
    )
    report = json.loads(json_path.read_text(encoding="utf-8-sig"))
    print(
        json.dumps(
            {
                "success": report["status"] == "passed",
                "status": report["status"],
                "semanticResultEquivalent": report["semanticResultEquivalent"],
                "jsonPath": str(json_path),
                "markdownPath": str(markdown_path) if markdown_path else None,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
