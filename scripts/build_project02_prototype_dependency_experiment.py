from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


WORKSPACE = Path(__file__).resolve().parents[1]
BACKEND = WORKSPACE / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.project02_prototype_dependency_experiment import (  # noqa: E402
    build_project02_prototype_dependency_experiment,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-directory",
        default="demo/semantic_ports/project02_nonprototype_initial_pose_v1",
    )
    args = parser.parse_args()
    output = Path(args.output_directory)
    if not output.is_absolute():
        output = WORKSPACE / output
    report = build_project02_prototype_dependency_experiment(WORKSPACE, output)
    report_path = output / "prototype_dependency_audit.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
