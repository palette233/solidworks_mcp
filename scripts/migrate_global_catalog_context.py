from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
BACKEND_SRC = WORKSPACE / "apps/demo-backend/src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.global_assembly_workbench import (  # noqa: E402
    commit_catalog_migration,
    preview_catalog_migration,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preview and optionally commit a non-destructive catalog/context rebind."
    )
    parser.add_argument(
        "--candidate-catalog",
        required=True,
        help="Workspace-relative candidate global catalog path.",
    )
    parser.add_argument(
        "--source-catalog",
        default="demo/global_assembly_catalog/v1/global_module_catalog.json",
    )
    parser.add_argument("--context-id", action="append", required=True)
    parser.add_argument("--plan-output")
    parser.add_argument(
        "--commit-target",
        help="New context id. Only valid when exactly one --context-id is supplied.",
    )
    parser.add_argument("--confirm", action="store_true")
    return parser.parse_args()


def write_json(path_value: str, value: dict) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = WORKSPACE / path
    path = path.resolve()
    path.relative_to(WORKSPACE.resolve())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return path


def main() -> int:
    args = parse_args()
    preview_payload = {
        "sourceCatalogPath": args.source_catalog,
        "candidateCatalogPath": args.candidate_catalog,
        "contextIds": args.context_id,
    }
    plan = preview_catalog_migration(WORKSPACE, preview_payload)
    if args.plan_output:
        plan_path = write_json(args.plan_output, plan)
        print(f"plan={plan_path}")
    print(
        json.dumps(
            {
                "planDigest": plan["planDigest"],
                "summary": plan["summary"],
                "assessments": [
                    {
                        "contextId": row["contextId"],
                        "status": row["status"],
                        "assessmentDigest": row["assessmentDigest"],
                        "blockerCount": len(row["blockers"]),
                        "warningCount": len(row["warnings"]),
                    }
                    for row in plan["contextAssessments"]
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if not args.commit_target:
        return 0
    if len(args.context_id) != 1:
        raise SystemExit("--commit-target requires exactly one --context-id")
    assessment = plan["contextAssessments"][0]
    result = commit_catalog_migration(
        WORKSPACE,
        {
            "sourceCatalogPath": args.source_catalog,
            "candidateCatalogPath": args.candidate_catalog,
            "sourceContextId": args.context_id[0],
            "targetContextId": args.commit_target,
            "expectedAssessmentDigest": assessment["assessmentDigest"],
            "confirmed": args.confirm,
        },
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "sourcePreserved": result["sourcePreserved"],
                "targetContextPath": result["targetContextPath"],
                "bindingPath": result["bindingPath"],
                "targetContextDigest": result["context"]["contextDigest"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
