from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.global_assembly_transactions import compile_global_assembly_transaction_dag  # noqa: E402
from demo_backend.global_cad_transaction_packets import compile_global_cad_transaction_manifest  # noqa: E402
from demo_backend.global_catalog_migration import (  # noqa: E402
    assess_context_catalog_migration,
    migrate_context_catalog_binding,
)
from demo_backend.global_relation_edits import (  # noqa: E402
    apply_global_relation_edit,
    preview_global_relation_edit,
)


GN00_DEFINITION = "cad/fl9c24n074gn00-001/1fe0a530a501"
JJ00_DEFINITION = "cad/fl9c24n074jj00-001/79d4fd749ac0"
GN00_PORT = "cad/fl9c24n074gn00-001/1fe0a530a501::port/gn00-primary-installation/92cbdbc226"
JJ00_PORT = "cad/fl9c24n074jj00-001/79d4fd749ac0::port/jj00-gn00-primary/a9337cc150"
RELATIONS = {
    "coincident": {
        "contextId": "project01-gn00-jj00-coincident-validation-v1",
        "sourceTemplate": "template/project01/gn00-jj00-standalone-coincident/e9a88b60ee",
        "requirement": "验证项目01 GN00安装面与JJ00基准面保持重合",
        "outputName": "project01-coincident-validation-v1",
    },
    "concentric": {
        "contextId": "project01-gn00-jj00-concentric-validation-v1",
        "sourceTemplate": "template/project01/gn00-jj00-standalone-concentric/95d38e785d",
        "requirement": "验证项目01 GN00定位孔与JJ00安装孔保持同轴",
        "outputName": "project01-concentric-validation-v1",
    },
}


def _load(path: Path) -> dict:
    value = json.loads(path.resolve().read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON根节点必须为对象：{path}")
    return value


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _instance(context: dict, definition_id: str) -> str:
    return next(
        row["instanceId"]
        for row in context["instances"]
        if row["moduleDefinitionId"] == definition_id
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare Project01 GN00/JJ00 read-only relation validation."
    )
    parser.add_argument(
        "--relation", choices=sorted(RELATIONS), default="coincident"
    )
    parser.add_argument(
        "--source-catalog",
        type=Path,
        default=ROOT / "demo/global_assembly_catalog/v1/global_module_catalog.relation-v2-preview.json",
    )
    parser.add_argument(
        "--candidate-catalog",
        type=Path,
        default=ROOT / "demo/global_assembly_catalog/v1/global_module_catalog.relation-v5-preview.json",
    )
    parser.add_argument(
        "--source-context",
        type=Path,
        default=ROOT / "demo/global_assembly_contexts/project01-cross-family-relation-v2-v1.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
    )
    args = parser.parse_args()

    relation = RELATIONS[args.relation]
    context_id = relation["contextId"]
    source_catalog = _load(args.source_catalog)
    candidate_catalog = _load(args.candidate_catalog)
    source_context = _load(args.source_context)
    assessment = assess_context_catalog_migration(source_catalog, candidate_catalog, source_context)
    if assessment["status"] != "ready":
        raise RuntimeError(json.dumps(assessment, ensure_ascii=False, indent=2))
    context, binding = migrate_context_catalog_binding(
        source_catalog,
        candidate_catalog,
        source_context,
        target_context_id=context_id,
        expected_assessment_digest=assessment["assessmentDigest"],
        confirmed=True,
    )
    derived = next(
        row
        for row in candidate_catalog["connectionTemplates"]
        if (row.get("provenance") or {}).get("derivedFromGlobalTemplateId")
        == relation["sourceTemplate"]
        and (row.get("provenance") or {}).get("derivationPolicy")
        == "read-only-observation-of-existing-source-mate/v1"
    )
    preview = preview_global_relation_edit(
        candidate_catalog,
        context,
        {
            "operation": "verify",
            "requirement": relation["requirement"],
            "instanceAId": _instance(context, GN00_DEFINITION),
            "instanceBId": _instance(context, JJ00_DEFINITION),
            "globalTemplateId": derived["globalTemplateId"],
            "portAId": GN00_PORT,
            "portBId": JJ00_PORT,
        },
    )
    if preview["status"] != "ready":
        raise RuntimeError(json.dumps(preview, ensure_ascii=False, indent=2))
    context = apply_global_relation_edit(
        context, preview, preview_digest=preview["previewDigest"], confirmed=True
    )

    base_instance = _instance(context, JJ00_DEFINITION)
    dag = compile_global_assembly_transaction_dag(
        candidate_catalog, context, base_instance_id=base_instance
    )
    manifest = compile_global_cad_transaction_manifest(
        candidate_catalog, context, base_instance_id=base_instance
    )
    verification_packet = next(
        packet for packet in manifest["packets"] if packet["operation"] == "VERIFY_RELATION"
    )
    output = (
        args.output_dir.resolve()
        if args.output_dir
        else (ROOT / "demo/global_assembly_contexts" / relation["outputName"]).resolve()
    )
    paths = {
        "catalog": output / f"global_module_catalog.{relation['outputName']}.json",
        "binding": output / "catalog-binding.json",
        "context": output / f"{context_id}.json",
        "dag": output / f"{context_id}.transaction-dag.json",
        "manifest": output / f"{context_id}.cad-transaction-manifest.json",
        "run": output / "preparation-run.json",
    }
    _write(paths["catalog"], candidate_catalog)
    _write(paths["binding"], binding)
    _write(paths["context"], context)
    _write(paths["dag"], dag)
    _write(paths["manifest"], manifest)
    run = {
        "schemaVersion": "project01-relation-validation-preparation/v2",
        "status": "ready" if manifest["status"] == "ready_for_generic_executor_implementation" else "blocked",
        "relation": args.relation,
        "contextId": context_id,
        "derivedTemplateId": derived["globalTemplateId"],
        "verificationPacketId": verification_packet["packetId"],
        "verificationPacketOrder": verification_packet["order"],
        "declaredValidationRelationCount": sum(
            len(row.get("mates") or []) for row in verification_packet["connections"]
        ),
        "expectedMateMutationCount": 0,
        "manifestStatus": manifest["status"],
        "blockers": manifest["blockers"],
        "solidWorksExecuted": False,
        "collisionStatus": "not_evaluated",
        "outputs": {key: str(path) for key, path in paths.items() if key != "run"},
    }
    _write(paths["run"], run)
    print(json.dumps({**run, "runPath": str(paths["run"])}, ensure_ascii=False, indent=2))
    return 0 if run["status"] == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
