#!/usr/bin/env python3
"""Rebuild the Project01 GN00 declared relation-combination experiment.

The experiment starts from the signed two-module Project01 context, migrates it
to a candidate catalog, adds GN00 through its primary locating template and then
adds the explicitly complementary anti-rotation relation.  No CAD or collision
engine is invoked; the outputs are semantic DAG and CAD transaction contracts.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "demo-backend" / "src"))

from demo_backend.global_assembly_context import (  # noqa: E402
    apply_global_command_preview,
    preview_global_assembly_command,
)
from demo_backend.global_assembly_transactions import (  # noqa: E402
    compile_global_assembly_transaction_dag,
)
from demo_backend.global_cad_transaction_packets import (  # noqa: E402
    compile_global_cad_transaction_manifest,
)
from demo_backend.global_catalog_migration import (  # noqa: E402
    assess_context_catalog_migration,
    migrate_context_catalog_binding,
)
from demo_backend.global_relation_edits import (  # noqa: E402
    apply_global_relation_edit,
    preview_global_relation_edit,
)


def _load(path: Path) -> dict:
    return json.loads(path.resolve().read_text(encoding="utf-8-sig"))


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _definition(catalog: dict, token: str) -> dict:
    return next(
        row
        for row in catalog["moduleDefinitions"]
        if any(
            alias.get("projectId") == "project01"
            and alias.get("moduleToken") == token
            for alias in row.get("projectAliases") or []
        )
    )


def _template(catalog: dict, legacy_id: str) -> dict:
    return next(
        row
        for row in catalog["connectionTemplates"]
        if row.get("legacyTemplateId") == legacy_id
    )


def _port(catalog: dict, alias: str) -> dict:
    return next(
        row
        for row in catalog["semanticPorts"]
        if alias in (row.get("aliases") or [])
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="验证Project01主定位与防转关系的显式组合闭合。"
    )
    parser.add_argument(
        "--source-catalog",
        type=Path,
        default=ROOT
        / "demo/global_assembly_catalog/v1/global_module_catalog.json",
    )
    parser.add_argument(
        "--candidate-catalog",
        type=Path,
        default=ROOT
        / "demo/global_assembly_catalog/v1/global_module_catalog.relation-v2-preview.json",
    )
    parser.add_argument(
        "--source-context",
        type=Path,
        default=ROOT / "demo/global_assembly_contexts/project01-cross-family-smoke-v1.json",
    )
    parser.add_argument(
        "--output-context",
        type=Path,
        default=ROOT
        / "demo/global_assembly_contexts/project01-cross-family-relation-v2-v1.json",
    )
    parser.add_argument(
        "--evidence",
        type=Path,
        default=ROOT
        / "demo/global_assembly_catalog/v1/relation-v2-preview/project01-gn00-standalone-parallel-closure.json",
    )
    parser.add_argument(
        "--dag-output",
        type=Path,
        default=ROOT
        / "demo/global_assembly_contexts/project01-cross-family-relation-v2-v1.transaction-dag.json",
    )
    parser.add_argument(
        "--manifest-output",
        type=Path,
        default=ROOT
        / "demo/global_assembly_contexts/project01-cross-family-relation-v2-v1.cad-transaction-manifest.json",
    )
    args = parser.parse_args()

    source_catalog = _load(args.source_catalog)
    candidate_catalog = _load(args.candidate_catalog)
    source_context = _load(args.source_context)
    assessment = assess_context_catalog_migration(
        source_catalog, candidate_catalog, source_context
    )
    if assessment["status"] != "ready":
        raise RuntimeError(f"目录迁移被阻止：{assessment['blockers']}")
    context, binding = migrate_context_catalog_binding(
        source_catalog,
        candidate_catalog,
        source_context,
        target_context_id="project01-cross-family-relation-v2-v1",
        expected_assessment_digest=assessment["assessmentDigest"],
        confirmed=True,
    )

    gn00 = _definition(candidate_catalog, "GN00")
    primary = _template(candidate_catalog, "GN00_to_JJ00_primary")
    gn00_primary_port = _port(candidate_catalog, "GN00.primary_installation")
    jj00_primary_port = _port(candidate_catalog, "JJ00.gn00_primary")
    add_preview = preview_global_assembly_command(
        candidate_catalog,
        context,
        {
            "requirement": "在项目01 JJ00上安装GN00模组",
            "moduleDefinitionId": gn00["moduleDefinitionId"],
            "globalTemplateId": primary["globalTemplateId"],
            "newPortId": gn00_primary_port["globalPortId"],
            "existingPortId": jj00_primary_port["globalPortId"],
            "newSide": "A",
        },
    )
    if add_preview["status"] != "ready":
        raise RuntimeError(f"GN00插入预览被阻止：{add_preview['blockers']}")
    context = apply_global_command_preview(
        context,
        add_preview,
        preview_digest=add_preview["previewDigest"],
        confirmed=True,
    )

    gn00_instance = next(
        row["instanceId"]
        for row in context["instances"]
        if row["moduleDefinitionId"] == gn00["moduleDefinitionId"]
    )
    ss00_definition = _definition(candidate_catalog, "SS00")
    ss00_instance = next(
        row["instanceId"]
        for row in context["instances"]
        if row["moduleDefinitionId"] == ss00_definition["moduleDefinitionId"]
    )
    anti_rotation = _template(
        candidate_catalog, "GN00_SS00_standalone_parallel"
    )
    gn00_anti_rotation_port = _port(candidate_catalog, "GN00.anti_rotation")
    ss00_anti_rotation_port = _port(
        candidate_catalog, "SS00.gn00_anti_rotation"
    )
    relation_preview = preview_global_relation_edit(
        candidate_catalog,
        context,
        {
            "operation": "add",
            "requirement": "让项目01 GN00防转面与SS00基准面保持平行",
            "instanceAId": gn00_instance,
            "instanceBId": ss00_instance,
            "globalTemplateId": anti_rotation["globalTemplateId"],
            "portAId": gn00_anti_rotation_port["globalPortId"],
            "portBId": ss00_anti_rotation_port["globalPortId"],
        },
    )
    if relation_preview["status"] != "ready":
        raise RuntimeError(f"防转关系预览被阻止：{relation_preview['blockers']}")
    context = apply_global_relation_edit(
        context,
        relation_preview,
        preview_digest=relation_preview["previewDigest"],
        confirmed=True,
    )

    dag = compile_global_assembly_transaction_dag(candidate_catalog, context)
    manifest = compile_global_cad_transaction_manifest(candidate_catalog, context)
    closure_step = next(
        step
        for step in dag["steps"]
        if step["constraintAssessment"]["state"]
        == "closed_by_declared_template_combination"
    )
    evidence = {
        "schemaVersion": "declared-relation-combination-evidence/v1",
        "contextId": context["contextId"],
        "catalogDigest": candidate_catalog["catalogDigest"],
        "migrationAssessment": assessment,
        "catalogBinding": binding,
        "addPreview": add_preview,
        "relationPreview": relation_preview,
        "closure": {
            "status": "passed",
            "stepId": closure_step["stepId"],
            "connectionIds": [
                row["connectionId"] for row in closure_step["connections"]
            ],
            "constraintAssessment": closure_step["constraintAssessment"],
        },
        "transactionDag": dag,
        "cadTransactionManifest": manifest,
        "solidWorksExecuted": False,
        "collisionStatus": "not_evaluated",
    }
    _write(args.output_context.resolve(), context)
    _write(args.dag_output.resolve(), dag)
    _write(args.manifest_output.resolve(), manifest)
    _write(args.evidence.resolve(), evidence)
    print(
        json.dumps(
            {
                "context": str(args.output_context.resolve()),
                "evidence": str(args.evidence.resolve()),
                "transactionDag": str(args.dag_output.resolve()),
                "cadTransactionManifest": str(args.manifest_output.resolve()),
                "catalogDigest": candidate_catalog["catalogDigest"],
                "dagStatus": dag["status"],
                "manifestStatus": manifest["status"],
                "transactionCount": dag["transactionCount"],
                "closureState": closure_step["constraintAssessment"]["state"],
                "closureConnectionCount": len(closure_step["connections"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
