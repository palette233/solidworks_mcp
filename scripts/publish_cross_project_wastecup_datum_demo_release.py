#!/usr/bin/env python3
"""Publish and compile the isolated Project05 P000 -> Project02 A600 datum demo."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.global_assembly_workbench import (  # noqa: E402
    apply_command_sequence,
    compile_cad_transaction_manifest,
    create_context,
    preview_command,
)
from demo_backend.global_relation_catalog_release import (  # noqa: E402
    build_relation_catalog_release,
    finalize_relation_catalog_release,
    load_relation_catalog_release,
)


PACKAGE = ROOT / "demo/cross_project_substitution/wastecup-project05-to-project02-v1"
SEMANTIC_PACKAGE = PACKAGE / "semantic-package-v1"
CAD_RESULT = PACKAGE / "project02-A600-project05-P000-datum-v1.context-insert.result.json"
TEMPLATE_ID = "template/project-global/p000-a600-wastecup-datum-demo/218ec01d59"
DEFAULT_RELEASE_ID = "relation-v63-project02-project05-wastecup-datum-demo-20261015"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_new(path: Path, value: dict) -> None:
    if path.exists():
        raise FileExistsError(f"拒绝覆盖不可变证据：{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _write_new_or_verify(path: Path, value: dict) -> None:
    """Keep reruns idempotent without weakening immutable publication."""

    if path.exists():
        if _read(path) != value:
            raise FileExistsError(f"已有不可变文件与本次内容不一致：{path}")
        return
    _write_new(path, value)


def _definition(catalog: dict, project_id: str, module_token: str) -> dict:
    rows = [
        row
        for row in catalog.get("moduleDefinitions") or []
        if any(
            alias.get("projectId") == project_id
            and alias.get("moduleToken") == module_token
            for alias in row.get("projectAliases") or []
        )
    ]
    if len(rows) != 1:
        raise RuntimeError(f"无法唯一找到{project_id}/{module_token}。")
    return rows[0]


def _transaction_projection(value: dict) -> dict:
    return {
        "schemaVersion": value.get("schemaVersion"),
        "contextId": value.get("contextId"),
        "catalogDigest": value.get("catalogDigest"),
        "relationReleaseBinding": value.get("relationReleaseBinding"),
        "status": value.get("status"),
        "packetCount": value.get("packetCount"),
        "packets": [
            {
                "packetId": row.get("packetId"),
                "operation": row.get("operation"),
                "targetModuleDefinitionId": row.get("targetModuleDefinitionId"),
                "connections": [
                    {
                        "portAId": connection.get("portAId"),
                        "portBId": connection.get("portBId"),
                        "globalTemplateId": connection.get("globalTemplateId"),
                        "mates": [
                            {
                                "mateName": mate.get("mateName"),
                                "mateType": mate.get("mateType"),
                                "alignment": mate.get("alignment"),
                                "advancedOptions": mate.get("advancedOptions"),
                            }
                            for mate in connection.get("mates") or []
                        ],
                    }
                    for connection in row.get("connections") or []
                ],
            }
            for row in value.get("packets") or []
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-id", default=DEFAULT_RELEASE_ID)
    parser.add_argument("--semantic-package-name", default="semantic-package-v1")
    parser.add_argument("--context-prefix", default="wastecup-v63")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=ROOT / "demo/global_assembly_catalog/releases",
    )
    args = parser.parse_args()

    semantic_package = PACKAGE / args.semantic_package_name
    catalog_path = semantic_package / "candidate_global_catalog.json"
    catalog = _read(catalog_path)
    derivation = {
        "schemaVersion": "global-relation-derivation-evidence/v1",
        "status": "ready",
        "outputCatalogDigest": catalog["catalogDigest"],
        "derivations": [
            {
                "source": {
                    "semanticPortCatalogPath": (
                        semantic_package / "semantic_port_catalog.json"
                    ).relative_to(ROOT).as_posix(),
                    "liveCadResultPath": CAD_RESULT.relative_to(ROOT).as_posix(),
                },
                "result": {"derivedGlobalTemplateId": TEMPLATE_ID},
            }
        ],
        "statement": (
            "本证据只派生一个跨项目基准放置Demo模板；"
            "不证明P000与A600直接机械接口兼容。"
        ),
    }
    derivation_path = semantic_package / f"{args.release_id}.derivation-evidence.json"
    _write_new_or_verify(derivation_path, derivation)

    released_catalog, manifest = build_relation_catalog_release(
        catalog_path=catalog_path,
        derivation_evidence_path=derivation_path,
        validation_evidence_paths=[CAD_RESULT],
        release_id=args.release_id,
        authorized_driving_template_ids=[TEMPLATE_ID],
        authorized_template_combination_ids=[],
        release_metadata={
            "relationExecutionMode": "datum_placement_demo",
            "templateEvidenceClasses": {TEMPLATE_ID: "datum_placement_demo"},
            "directMechanicalInterfaceCompatible": False,
            "collisionOrBrep": "not_evaluated",
            "statement": (
                "只允许在显式datum_placement_demo模式下执行；"
                "默认direct_installation必须失败关闭。"
            ),
        },
    )
    output = args.output_root.resolve() / args.release_id
    catalog_output = output / "global_module_catalog.json"
    manifest_output = output / "release-manifest.json"
    _write_new_or_verify(catalog_output, released_catalog)
    manifest = finalize_relation_catalog_release(
        manifest,
        released_catalog_path=catalog_output,
        workspace_root=ROOT,
    )
    _write_new_or_verify(manifest_output, manifest)
    load_relation_catalog_release(manifest_output, workspace_root=ROOT)

    a600 = _definition(released_catalog, "project02", "A600")
    p000 = _definition(released_catalog, "project05", "P000")
    base_command = {
        "requirement": "请先建立设备箱体与安装基座。",
        "moduleDefinitionId": a600["moduleDefinitionId"],
    }
    wastecup_command = {
        "requirement": (
            "请在当前设备箱体上安装一套Project05排胶杯模组，"
            "用于收集点胶头排出的废胶。"
        ),
        "moduleDefinitionId": p000["moduleDefinitionId"],
    }
    release_relative = manifest_output.relative_to(ROOT).as_posix()

    direct_id = f"{args.context_prefix}-direct"
    create_context(
        ROOT,
        {
            "contextId": direct_id,
            "displayName": "排胶杯默认直接安装阻断检查",
            "releaseManifestPath": release_relative,
            "overwrite": True,
        },
    )
    apply_command_sequence(
        ROOT, direct_id, {"confirmed": True, "commands": [base_command]}
    )
    direct_preview = preview_command(ROOT, direct_id, wastecup_command)
    if direct_preview.get("status") != "blocked":
        raise RuntimeError("不可变发布在默认直接安装模式下未阻断。")

    demo_id = f"{args.context_prefix}-demo"
    create_context(
        ROOT,
        {
            "contextId": demo_id,
            "displayName": "排胶杯显式基准放置Demo编译",
            "releaseManifestPath": release_relative,
            "overwrite": True,
        },
    )
    sequence = apply_command_sequence(
        ROOT,
        demo_id,
        {
            "confirmed": True,
            "relationExecutionMode": "datum_placement_demo",
            "commands": [base_command, wastecup_command],
        },
    )
    transaction = compile_cad_transaction_manifest(ROOT, demo_id)
    if transaction.get("packetCount") != 1:
        raise RuntimeError("显式Demo编译未生成唯一排胶杯CAD事务包。")
    transaction_path = output / "explicit-demo.cad-transaction-manifest.json"
    if transaction_path.exists():
        recorded_transaction = _read(transaction_path)
        if _transaction_projection(recorded_transaction) != _transaction_projection(
            transaction
        ):
            raise RuntimeError("已封存CAD事务清单与本次语义投影不一致。")
        transaction = recorded_transaction
    else:
        _write_new(transaction_path, transaction)

    comparison = {
        "schemaVersion": "released-wastecup-datum-policy-comparison/v1",
        "success": True,
        "releaseId": args.release_id,
        "releaseManifestPath": release_relative,
        "releaseDigest": manifest["releaseDigest"],
        "authorizedTemplateId": TEMPLATE_ID,
        "defaultDirectInstallation": {
            "status": direct_preview.get("status"),
            "blockers": direct_preview.get("blockers") or [],
        },
        "explicitDatumPlacementDemo": {
            "status": sequence.get("status"),
            "contextId": demo_id,
            "revision": (sequence.get("context") or {}).get("revision"),
            "instanceCount": len((sequence.get("context") or {}).get("instances") or []),
            "connectionCount": len((sequence.get("context") or {}).get("connections") or []),
            "cadTransactionStatus": transaction.get("status"),
            "packetCount": transaction.get("packetCount"),
            "cadTransactionManifestPath": transaction_path.relative_to(ROOT).as_posix(),
        },
        "cadStartedInThisPublish": False,
        "reusedCadEvidencePath": CAD_RESULT.relative_to(ROOT).as_posix(),
        "collisionOrBrep": "not_evaluated",
    }
    comparison_path = output / "release-policy-compilation-comparison.json"
    _write_new_or_verify(comparison_path, comparison)
    print(json.dumps(comparison, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
