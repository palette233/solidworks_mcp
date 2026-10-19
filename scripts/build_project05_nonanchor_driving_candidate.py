from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.global_cad_driving_evidence import (  # noqa: E402
    assess_driving_insert_evidence,
)
from demo_backend.global_module_catalog import (  # noqa: E402
    build_global_module_catalog,
    validate_global_module_catalog,
)


SOURCE_ROOT = ROOT / "demo/semantic_ports/project05_global_installation_ports_v1"
DEFAULT_OUTPUT_ROOT = ROOT / (
    "demo/global_assembly_catalog/v1/combination-v1-preview/"
    "project05-nonanchor-driving-v2"
)
DEFAULT_CATALOG = ROOT / (
    "demo/global_assembly_catalog/v1/"
    "global_module_catalog.project05-nonanchor-driving-v2-preview.json"
)
DEFAULT_EVIDENCE = ROOT / (
    "demo/global_assembly_catalog/v1/combination-v1-preview/"
    "project05-nonanchor-driving-v2/candidate-evidence.json"
)
D000_CANDIDATE_SEMANTIC = ROOT / (
    "demo/global_assembly_catalog/v1/driving-v1-preview/"
    "project05_D000_A000_scoped_driving_v2/semantic_port_catalog.json"
)
SUPPORTED = {
    "B000": ROOT / (
        "demo/global_assembly_catalog/v1/combination-v1-preview/"
        "project05-b000-checkpoint-v1/project05-b000-nonanchor-checkpoint.result.json"
    ),
    "F000": ROOT / (
        "demo/global_assembly_catalog/v1/combination-v1-preview/"
        "project05-f000-checkpoint-v1/project05-f000-nonanchor-checkpoint.result.json"
    ),
    "G000": ROOT / (
        "demo/global_assembly_catalog/v1/combination-v1-preview/"
        "project05-g000-checkpoint-v1/project05-g000-nonanchor-checkpoint.result.json"
    ),
    "K000": ROOT / (
        "demo/global_assembly_catalog/v1/combination-v1-preview/"
        "project05-k000-checkpoint-v1/project05-k000-nonanchor-checkpoint.result.json"
    ),
    "M000": ROOT / (
        "demo/global_assembly_catalog/v1/combination-v1-preview/"
        "project05-m000-checkpoint-v1/project05-m000-nonanchor-checkpoint.result.json"
    ),
}


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON根节点必须为对象：{path}")
    return value


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def build_candidate(target: str, checkpoint: Path, package_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    target = target.strip().upper()
    source_dir = SOURCE_ROOT / target
    semantic = _read(source_dir / "semantic_port_catalog.json")
    endpoints = _read(source_dir / "face_endpoint_catalog.json")
    graph = _read(
        ROOT
        / (
            "demo/global_assembly_catalog/v1/combination-v1-preview/"
            f"project05-{target.lower()}-checkpoint-v1/"
            f"project05-{target.lower()}-nonanchor.execution-graph.json"
        )
    )
    target_modules = [
        module
        for module in graph.get("Modules") or []
        if str(module.get("ModuleToken") or "").upper() == target
    ]
    if len(target_modules) != 1:
        raise ValueError(f"{target}在执行图中解析到{len(target_modules)}个模组记录。")
    solving_state_name = str(target_modules[0].get("SolvingStateName") or "")
    internally_flexible = "flex" in solving_state_name.casefold() or "柔性" in solving_state_name
    template = deepcopy((semantic.get("connectionTemplates") or [])[0])
    expected = len(template.get("mateSteps") or [])
    assessment = assess_driving_insert_evidence(
        _read(checkpoint), expected_mate_count=expected
    )
    if assessment.get("checkpointPassed") is not True:
        raise ValueError(
            f"{target}无锚点checkpoint未通过：{', '.join(assessment.get('blockers') or [])}"
        )

    candidate = deepcopy(semantic)
    candidate["schemaVersion"] = "semantic-port-catalog/v2-candidate"
    candidate["catalogPurpose"] = (
        f"Project05 {target}/A000 non-anchor driving candidate proven by a "
        "deterministic independent insert checkpoint."
    )
    candidate["endpointCatalogPath"] = "face_endpoint_catalog.json"
    candidate["effectiveMateGraphPath"] = _relative(
        package_dir / "assembly_plan_effective.json"
    )
    candidate["drivingScope"] = {
        "status": "candidate_only_not_released",
        "allowedModuleTokens": ["A000", target],
        "exactMateBundleRequired": True,
        "checkpointPath": _relative(checkpoint),
        "caseAnchorAllowed": False,
    }
    template["templateId"] = f"{target}_to_A000_nonanchor_driving_v1"
    template["constraintEffect"] = {
        "purpose": f"Drive the proven Project05 {target}-to-A000 installation bundle.",
        "fullyLocatesAddedComponent": True,
        "expectedResidualDof": 0,
        "residualDofPolicy": "closed_by_nonanchor_cad_checkpoint",
        "drivingAuthorization": "candidate_only_not_released",
        "exactMateBundleRequired": True,
        "residualDofScope": "external_module_placement",
        "internalFlexibilityPreserved": internally_flexible,
        "targetSolvingStateName": solving_state_name,
    }
    candidate["connectionTemplates"] = [template]

    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "semantic_port_catalog.json").write_text(
        json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (package_dir / "face_endpoint_catalog.json").write_text(
        json.dumps(endpoints, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (package_dir / "assembly_plan_effective.json").write_text(
        json.dumps(graph, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return candidate, assessment


def main() -> int:
    parser = argparse.ArgumentParser(
        description="把已通过的Project05无锚点checkpoint登记为候选驱动模板。"
    )
    parser.add_argument(
        "--target",
        required=True,
        choices=sorted(SUPPORTED),
        action="append",
        help="可重复指定；多个目标会被合并进同一候选目录。",
    )
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--catalog-output", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--evidence-output", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--reuse-package", action="store_true")
    args = parser.parse_args()
    targets = list(dict.fromkeys(value.upper() for value in args.target))
    if args.checkpoint and len(targets) != 1:
        raise ValueError("--checkpoint只允许与单个--target一起使用。")
    assessments: dict[str, dict[str, Any]] = {}
    checkpoints: dict[str, Path] = {}
    package_dirs: dict[str, Path] = {}
    for target in targets:
        checkpoint = (args.checkpoint or SUPPORTED[target]).resolve()
        package_dir = args.output_root.resolve() / target
        checkpoints[target] = checkpoint
        package_dirs[target] = package_dir
        if package_dir.exists():
            if not args.reuse_package:
                raise FileExistsError(f"拒绝覆盖候选包：{package_dir}")
            candidate = _read(package_dir / "semantic_port_catalog.json")
            expected = len(
                (candidate.get("connectionTemplates") or [{}])[0].get("mateSteps")
                or []
            )
            assessment = assess_driving_insert_evidence(
                _read(checkpoint), expected_mate_count=expected
            )
            if assessment.get("checkpointPassed") is not True:
                raise ValueError(f"{target}已存在候选包绑定的checkpoint不再通过。")
        else:
            _, assessment = build_candidate(target, checkpoint, package_dir)
        assessments[target] = assessment
    catalog = build_global_module_catalog(
        ROOT,
        additional_semantic_catalog_paths=[
            D000_CANDIDATE_SEMANTIC,
            *(
                package_dirs[target] / "semantic_port_catalog.json"
                for target in targets
            ),
        ],
    )
    validate_global_module_catalog(catalog)
    rows: list[dict[str, Any]] = []
    for target in targets:
        source = _relative(package_dirs[target] / "semantic_port_catalog.json")
        matches = [
            row
            for row in catalog.get("connectionTemplates") or []
            if (row.get("provenance") or {}).get("semanticCatalogPath") == source
        ]
        if len(matches) != 1:
            raise ValueError(f"{target}预期一个候选模板，实际为{len(matches)}。")
        template = matches[0]
        rows.append(
            {
                "moduleToken": target,
                "packagePath": _relative(package_dirs[target]),
                "legacyTemplateId": template.get("legacyTemplateId"),
                "globalTemplateId": template.get("globalTemplateId"),
                "checkpointPath": _relative(checkpoints[target]),
                "checkpointAssessment": assessments[target],
            }
        )
    evidence = {
        "schemaVersion": "project05-nonanchor-driving-candidate/v2",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": "ready",
        "projectId": "project05",
        "sourceCatalogPath": _relative(args.catalog_output.resolve()),
        "outputCatalogDigest": catalog.get("catalogDigest"),
        "targetCount": len(rows),
        "targets": rows,
        "collisionStatus": "not_evaluated",
    }
    if len(rows) == 1:
        evidence.update(rows[0])
    args.catalog_output.resolve().write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    args.evidence_output.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.evidence_output.resolve().write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
