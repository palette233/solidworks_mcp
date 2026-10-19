#!/usr/bin/env python3
"""Publish one evidence-backed eight-module Project03 mixed-project chain."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.cross_project_slot_release import (  # noqa: E402
    augment_release_catalog_with_cross_project_template,
)
from demo_backend.driving_relation_release_publisher import (  # noqa: E402
    publish_driving_relation_release,
)
from demo_backend.evidence_backed_long_chain import (  # noqa: E402
    build_evidence_backed_long_chain_plan,
)
from demo_backend.global_relation_catalog_release import (  # noqa: E402
    load_relation_catalog_release,
)


RELEASE_ID = "relation-v62-project03-expanded-cross-project-chain-driving-20261014"
BASE_RELEASE = ROOT / (
    "demo/global_assembly_catalog/releases/"
    "relation-v54-project03-ag00-three-datum-driving-20261014"
)
CROSS_PROJECT_RELEASE = ROOT / (
    "demo/global_assembly_catalog/releases/"
    "relation-v48-project03-aa00-transport-scanner-calibration-driving-20261012"
)
PACKAGE = ROOT / "demo/cross_project_substitution/expanded-project03-v1"


TEMPLATES = [
    {
        "legacyTemplateId": "cross_project_project01_SS00_to_project03_AE00_slot",
        "globalTemplateId": "template/cross-project/ss00-to-project03-ae00-slot/fbc7749921",
        "evidencePath": (
            "demo/global_assembly_contexts/manifest_jobs/project01-job-b601e1a0748d/"
            "packet-runs/packet-001-attempt-01/cad-result.json"
        ),
        "expectedMateCount": 3,
    },
    {
        "legacyTemplateId": "AI00_to_AA00_five_mate_installation",
        "globalTemplateId": "template/project03/ai00-to-aa00-five-mate-installation/0b1374c7f5",
        "evidencePath": (
            "demo/global_assembly_contexts/manifest_jobs/project03-job-d7ecc82db4f1/"
            "packet-runs/packet-003-attempt-02/cad-result.json"
        ),
        "expectedMateCount": 3,
    },
    {
        "legacyTemplateId": "cross_project_project01_BD00_to_project03_AH00_slot",
        "globalTemplateId": "template/cross-project/bd00-to-project03-ah00-slot/f215aabb1a",
        "evidencePath": (
            "demo/global_assembly_contexts/manifest_jobs/project01-job-86a04eaa623c/"
            "packet-runs/packet-001-attempt-01/cad-result.json"
        ),
        "expectedMateCount": 3,
    },
    {
        "legacyTemplateId": "AD00_to_AA00_three_datum_installation",
        "globalTemplateId": "template/project03/ad00-to-aa00-three-datum-installation/357acee2ce",
        "evidencePath": (
            "demo/global_assembly_catalog/v1/combination-v1-preview/"
            "project03-ad00-checkpoint-v1/"
            "project03-ad00-cumulative-nonprototype-checkpoint.result.json"
        ),
        "expectedMateCount": 3,
    },
    {
        "legacyTemplateId": "AJ00_to_AA00_three_datum_installation",
        "globalTemplateId": "template/project03/aj00-to-aa00-three-datum-installation/e323079e41",
        "evidencePath": (
            "demo/global_assembly_catalog/v1/combination-v1-preview/"
            "project03-aj00-checkpoint-v1/"
            "project03-aj00-cumulative-nonprototype-checkpoint.result.json"
        ),
        "expectedMateCount": 3,
    },
    {
        "legacyTemplateId": "AG00_to_AA00_three_datum_installation_v1",
        "globalTemplateId": "template/project03/ag00-to-aa00-three-datum-installation-v1/6787039852",
        "evidencePath": (
            "demo/global_assembly_catalog/coverage-v2/ag00-three-datum-candidate-v1/"
            "project03_AG00_three_datum_checkpoint_v2.result.json"
        ),
        "expectedMateCount": 3,
    },
    {
        "legacyTemplateId": "AB00_to_AA00_complete_three_relation_installation",
        "globalTemplateId": "template/project03/ab00-to-aa00-complete-three-relation-installatio/38c473f7e4",
        "evidencePath": (
            "demo/global_assembly_catalog/coverage-v2/ab00-checkpoint-refresh-v1/"
            "project03_AB00_complete_checkpoint_v1.result.json"
        ),
        "expectedMateCount": 3,
    },
]


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def build_candidate_catalog() -> dict:
    catalog = _read(BASE_RELEASE / "global_module_catalog.json")
    cross_catalog = _read(CROSS_PROJECT_RELEASE / "global_module_catalog.json")
    for legacy_id in (
        "cross_project_project01_SS00_to_project03_AE00_slot",
        "cross_project_project01_BD00_to_project03_AH00_slot",
    ):
        catalog = augment_release_catalog_with_cross_project_template(
            catalog, cross_catalog, legacy_template_id=legacy_id
        )
    return catalog


def build_release_spec(release_id: str, catalog_path: Path) -> dict:
    return {
        "schemaVersion": "driving-relation-release-spec/v1",
        "releaseId": release_id,
        "projectId": "project-global",
        "drivingScope": (
            "project03_AA00_with_project01_SS00_BD00_and_"
            "project03_AI00_AD00_AJ00_AG00_AB00"
        ),
        "catalogPath": catalog_path.resolve().relative_to(ROOT).as_posix(),
        "templates": TEMPLATES,
    }


def _markdown(plan: dict) -> str:
    lines = [
        "# Project03 扩展跨项目累计装配链",
        "",
        f"- 状态：`{plan['status']}`",
        f"- 顶层模组数：{plan['finalTopLevelModuleCount']}",
        f"- 新增模组：{plan['plannedAdditionCount']}",
        f"- 跨项目替换：{plan['crossProjectAdditionCount']}",
        f"- 基座项目原生：{plan['nativeAdditionCount']}",
        "- 原型顶层位姿：禁止使用",
        "- 碰撞/B-rep：本阶段未执行，保持独立后验项",
        "",
        "|顺序|模组|类型|配合模板|剩余自由度|",
        "|---:|---|---|---|---:|",
    ]
    for row in plan["steps"]:
        lines.append(
            f"|{row['order']}|{','.join(row['moduleTokens'])}|"
            f"{row['relationKind']}|`{row['globalTemplateId']}`|"
            f"{row['declaredResidualDof']}|"
        )
    lines.extend(
        [
            "",
            "## 说明",
            "",
            "本链路不是把不兼容的 Project01 模组强行放入 Project03。",
            "跨项目部分只使用已完成真实 CAD 验证的 SS00 与 BD00；其余模组使用 Project03 原生已发布端口。",
            "下一步可从该计划编译自然语言持久任务，再逐包执行并保存重开复核。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-id", default=RELEASE_ID)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()

    PACKAGE.mkdir(parents=True, exist_ok=True)
    catalog_path = PACKAGE / f"{args.release_id}.catalog-preview.json"
    spec_path = PACKAGE / f"{args.release_id}.release-spec.json"
    _write(catalog_path, build_candidate_catalog())
    _write(spec_path, build_release_spec(args.release_id, catalog_path))
    if args.prepare_only:
        print(
            json.dumps(
                {
                    "success": True,
                    "status": "prepared_not_published",
                    "catalogPath": str(catalog_path),
                    "releaseSpecPath": str(spec_path),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    report = publish_driving_relation_release(
        ROOT,
        _read(spec_path),
        output_root=ROOT / "demo/global_assembly_catalog/releases",
    )
    manifest_path = Path(report["manifestPath"])
    catalog, manifest = load_relation_catalog_release(
        manifest_path, workspace_root=ROOT
    )
    plan = build_evidence_backed_long_chain_plan(
        catalog,
        manifest,
        base_module="project03:AA00",
        ordered_modules=[
            "project01:SS00",
            "project03:AI00",
            "project01:BD00",
            "project03:AD00",
            "project03:AJ00",
            "project03:AG00",
            "project03:AB00",
        ],
    )
    plan_path = PACKAGE / "expanded-chain-plan.json"
    markdown_path = PACKAGE / "expanded-chain-plan.md"
    _write(plan_path, plan)
    markdown_path.write_text(_markdown(plan), encoding="utf-8")
    print(
        json.dumps(
            {
                **report,
                "chainPlanStatus": plan["status"],
                "chainPlanPath": str(plan_path),
                "chainPlanMarkdownPath": str(markdown_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if plan["status"] == "ready_for_natural_language_job_compilation" else 2


if __name__ == "__main__":
    raise SystemExit(main())
