from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.global_assembly_context import context_digest  # noqa: E402
from demo_backend.global_assembly_transactions import (  # noqa: E402
    compile_global_assembly_transaction_dag,
)
from demo_backend.global_template_combination_readiness import (  # noqa: E402
    assess_template_combination_readiness,
)


def _read(path: Path) -> dict:
    return json.loads(path.resolve().read_text(encoding="utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="审计Project03模板闭合语义并执行无原型顶层位姿的DAG编译。"
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=ROOT
        / "demo/global_assembly_catalog/v1/global_module_catalog.combination-v1-preview.json",
    )
    parser.add_argument(
        "--context",
        type=Path,
        default=ROOT
        / "demo/global_assembly_contexts/project03-cross-family-smoke-v1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "demo/global_assembly_catalog/v1/combination-v1-preview/"
        "project03-template-combination-readiness.json",
    )
    args = parser.parse_args()

    catalog = _read(args.catalog)
    context = _read(args.context)
    context["catalogDigest"] = catalog["catalogDigest"]
    context["relationReleaseBinding"] = None
    context["contextDigest"] = context_digest(context)
    dag = compile_global_assembly_transaction_dag(catalog, context)
    readiness = assess_template_combination_readiness(
        catalog,
        project_id="project03",
    )
    selected_steps = [
        {
            "stepId": step["stepId"],
            "status": step["status"],
            "targetDisplayName": step.get("targetDisplayName"),
            "selectedTemplateIds": [
                row["globalTemplateId"] for row in step.get("connections") or []
            ],
            "constraintAssessment": step["constraintAssessment"],
            "positioningStandardBinding": step.get("positioningStandardBinding"),
            "blockers": step["blockers"],
        }
        for step in dag["steps"]
    ]
    report = {
        "schemaVersion": "project03-template-combination-audit/v1",
        "status": (
            "compiled_without_prototype_pose_closure"
            if dag["status"] == "ready_for_generic_cad_executor"
            and all(row["positioningStandardBinding"] is None for row in selected_steps)
            else "blocked"
        ),
        "catalogPath": str(args.catalog.resolve()),
        "contextPath": str(args.context.resolve()),
        "readiness": readiness,
        "smokeCompile": {
            "dagStatus": dag["status"],
            "transactionCount": dag["transactionCount"],
            "steps": selected_steps,
            "prototypeTopLevelPoseUsedToCloseDof": False,
        },
        "conclusion": (
            "AE00三基准模板可作为Project03原子闭合正例；AG00诊断模板仍余1自由度且"
            "没有声明补充组合，必须失败关闭；含prototype/anchor语义的模板需另做去锚点审计。"
        ),
        "solidWorksExecuted": False,
        "collisionStatus": "not_evaluated",
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "compiled_without_prototype_pose_closure" else 2


if __name__ == "__main__":
    raise SystemExit(main())
