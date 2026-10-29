#!/usr/bin/env python3
"""Build and policy-test an isolated WasteCup datum-demo global catalog."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "apps/demo-backend/src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from demo_backend.cross_project_wastecup_datum_catalog import (  # noqa: E402
    build_wastecup_datum_catalog_package,
)
from demo_backend.global_assembly_compiler import (  # noqa: E402
    compile_global_assembly_execution_manifest,
)
from demo_backend.global_assembly_context import (  # noqa: E402
    apply_global_command_preview,
    create_global_assembly_context,
    preview_global_assembly_command,
)


DEFAULT_ROOT = ROOT / "demo/cross_project_substitution/wastecup-project05-to-project02-v1"
BASE_CATALOG = ROOT / (
    "demo/cross_project_substitution/expanded-project03-v1/"
    "relation-v62-project03-expanded-cross-project-chain-driving-20261014.catalog-preview.json"
)
P02_ENDPOINTS = ROOT / (
    "demo/global_assembly_catalog/v1/combination-v1-preview/"
    "project02-seven-addon-driving-v6/A300/face_endpoint_catalog.json"
)
P05_ENDPOINTS = ROOT / (
    "demo/global_assembly_catalog/v1/combination-v1-preview/"
    "project05-nonanchor-driving-v6/P000/face_endpoint_catalog.json"
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _definition(catalog: dict, project_id: str, module_token: str) -> dict:
    return next(
        row
        for row in catalog["moduleDefinitions"]
        if any(
            alias.get("projectId") == project_id
            and alias.get("moduleToken") == module_token
            for alias in row.get("projectAliases") or []
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--package-name", default="semantic-package-v1")
    parser.add_argument("--context-endpoints", type=Path, default=P02_ENDPOINTS)
    parser.add_argument("--p000-endpoints", type=Path, default=P05_ENDPOINTS)
    args = parser.parse_args()
    root = args.root.resolve()
    package_root = root / args.package_name
    try:
        package_reference = package_root.relative_to(ROOT)
    except ValueError:
        package_reference = package_root
    semantic_rel = package_reference / "semantic_port_catalog.json"
    endpoint_rel = package_reference / "face_endpoint_catalog.json"
    # The current project adapter discovers deterministic source graphs through
    # the base*_graph.json naming contract.  The file itself still contains the
    # target module and mate bundle needed by the generic executor.
    graph_rel = package_reference / "base_wastecup_datum_graph.json"
    package = build_wastecup_datum_catalog_package(
        base_global_catalog=_read(BASE_CATALOG),
        candidate_graph=_read(root / "candidate_effective_mate_graph.json"),
        candidate_audit=_read(root / "candidate_audit.json"),
        context_endpoint_catalog=_read(args.context_endpoints),
        p000_endpoint_catalog=_read(args.p000_endpoints),
        semantic_catalog_path=str(semantic_rel).replace("\\", "/"),
        endpoint_catalog_path=str(endpoint_rel).replace("\\", "/"),
        base_graph_path=str(graph_rel).replace("\\", "/"),
    )
    _write(package_root / "semantic_port_catalog.json", package["semanticCatalog"])
    _write(package_root / "face_endpoint_catalog.json", package["endpointCatalog"])
    _write(package_root / "base_wastecup_datum_graph.json", package["baseGraph"])
    catalog_path = package_root / "candidate_global_catalog.json"
    _write(catalog_path, package["candidateGlobalCatalog"])

    catalog = package["candidateGlobalCatalog"]
    context = create_global_assembly_context(
        "wastecup-datum-policy-check", catalog_digest=catalog["catalogDigest"]
    )
    audit = _read(root / "candidate_audit.json")
    base_definition = _definition(catalog, audit.get("targetProjectId", "project02"), audit.get("targetBaseToken", "A600"))
    p000_definition = _definition(catalog, "project05", "P000")
    base_preview = preview_global_assembly_command(
        catalog,
        context,
        {
            "requirement": "请先建立设备箱体与安装基座。",
            "moduleDefinitionId": base_definition["moduleDefinitionId"],
        },
    )
    context = apply_global_command_preview(
        context,
        base_preview,
        preview_digest=base_preview["previewDigest"],
        confirmed=True,
    )
    requirement = (
        "请在当前设备箱体上安装一套Project05排胶杯模组，"
        "用于收集点胶头排出的废胶。"
    )
    default_preview = preview_global_assembly_command(
        catalog,
        context,
        {
            "requirement": requirement,
            "moduleDefinitionId": p000_definition["moduleDefinitionId"],
        },
    )
    demo_preview = preview_global_assembly_command(
        catalog,
        context,
        {
            "requirement": requirement,
            "moduleDefinitionId": p000_definition["moduleDefinitionId"],
            "relationExecutionMode": "datum_placement_demo",
        },
    )
    if default_preview.get("status") != "blocked":
        raise RuntimeError("默认direct_installation模式未阻断Demo模板。")
    if not any(
        row.get("code") == "RELATION_EXECUTION_MODE_MISMATCH"
        for row in default_preview.get("blockers") or []
    ):
        raise RuntimeError("默认模式缺少证据等级不匹配解释。")
    if demo_preview.get("status") != "ready":
        raise RuntimeError("显式datum_placement_demo模式未进入ready。")
    demo_context = apply_global_command_preview(
        context,
        demo_preview,
        preview_digest=demo_preview["previewDigest"],
        confirmed=True,
    )
    manifest = compile_global_assembly_execution_manifest(ROOT, catalog, demo_context)
    if manifest.get("status") != "ready_for_project_adapter":
        raise RuntimeError("显式Demo上下文未通过最终清单编译。")
    comparison = {
        "schemaVersion": "cross-project-wastecup-datum-policy-comparison/v1",
        "success": True,
        "cadStarted": False,
        "requirement": requirement,
        "candidateCatalogPath": str(catalog_path),
        "globalTemplateId": package["globalTemplateId"],
        "defaultDirectInstallation": {
            "status": default_preview["status"],
            "blockers": default_preview.get("blockers") or [],
        },
        "explicitDatumPlacementDemo": {
            "status": demo_preview["status"],
            "relationExecutionPolicy": demo_preview["relationExecutionPolicy"],
            "connection": (demo_preview.get("proposedPatch") or {}).get("connection"),
            "manifestStatus": manifest["status"],
            "stepCount": manifest["stepCount"],
        },
        "collisionOrBrep": "not_evaluated",
        "statement": (
            "同一自然语言安装需求在默认工程直装模式失败关闭；"
            "只有显式选择基准定位Demo后才生成可执行项目适配器清单。"
        ),
    }
    _write(package_root / "policy-compilation-comparison.json", comparison)
    print(json.dumps(comparison, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
