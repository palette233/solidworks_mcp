from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

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


CONTEXT_ID = "project01-gn00-ss00-parallel-validation-v1"
GN00_DEFINITION = "cad/fl9c24n074gn00-001/1fe0a530a501"
SS00_DEFINITION = "cad/fl9c24n074ss00-001/ced014a7837b"
GN00_PORT = (
    "cad/fl9c24n074gn00-001/1fe0a530a501::port/gn00-anti-rotation/34f2dd1f2e"
)
SS00_PORT = (
    "cad/fl9c24n074ss00-001/ced014a7837b::port/ss00-gn00-anti-rotation/7342b0dfeb"
)
DERIVATION_POLICY = "read-only-observation-of-existing-source-mate/v1"


def _load(path: Path) -> dict:
    value = json.loads(path.resolve().read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON根节点必须为对象：{path}")
    return value


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _instance(context: dict, definition_id: str) -> str:
    return next(
        row["instanceId"]
        for row in context["instances"]
        if row["moduleDefinitionId"] == definition_id
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare Project01 GN00/SS00 read-only parallel validation."
    )
    parser.add_argument(
        "--source-catalog",
        type=Path,
        default=ROOT
        / "demo/global_assembly_catalog/v1/global_module_catalog.relation-v2-preview.json",
    )
    parser.add_argument(
        "--candidate-catalog",
        type=Path,
        default=ROOT
        / "demo/global_assembly_catalog/v1/global_module_catalog.relation-v3-preview.json",
    )
    parser.add_argument(
        "--source-context",
        type=Path,
        default=ROOT
        / "demo/global_assembly_contexts/project01-cross-family-relation-v2-v1.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "demo/global_assembly_contexts/project01-relation-validation-v1",
    )
    args = parser.parse_args()

    source_catalog = _load(args.source_catalog)
    candidate_catalog = _load(args.candidate_catalog)
    source_context = _load(args.source_context)
    assessment = assess_context_catalog_migration(
        source_catalog, candidate_catalog, source_context
    )
    if assessment["status"] != "ready":
        raise RuntimeError(json.dumps(assessment, ensure_ascii=False, indent=2))
    context, binding = migrate_context_catalog_binding(
        source_catalog,
        candidate_catalog,
        source_context,
        target_context_id=CONTEXT_ID,
        expected_assessment_digest=assessment["assessmentDigest"],
        confirmed=True,
    )
    derived = next(
        row
        for row in candidate_catalog["connectionTemplates"]
        if (row.get("provenance") or {}).get("derivationPolicy")
        == DERIVATION_POLICY
        and (row.get("provenance") or {}).get("projectId") == "project01"
    )
    relation_preview = preview_global_relation_edit(
        candidate_catalog,
        context,
        {
            "operation": "verify",
            "requirement": "验证项目01 GN00防转面与SS00基准面保持平行",
            "instanceAId": _instance(context, GN00_DEFINITION),
            "instanceBId": _instance(context, SS00_DEFINITION),
            "globalTemplateId": derived["globalTemplateId"],
            "portAId": GN00_PORT,
            "portBId": SS00_PORT,
        },
    )
    if relation_preview["status"] != "ready":
        raise RuntimeError(json.dumps(relation_preview, ensure_ascii=False, indent=2))
    context = apply_global_relation_edit(
        context,
        relation_preview,
        preview_digest=relation_preview["previewDigest"],
        confirmed=True,
    )

    base_instance = next(
        row["instanceId"]
        for row in context["instances"]
        if row["moduleDefinitionId"]
        == "cad/fl9c24n074jj00-001/79d4fd749ac0"
    )
    dag = compile_global_assembly_transaction_dag(
        candidate_catalog, context, base_instance_id=base_instance
    )
    manifest = compile_global_cad_transaction_manifest(
        candidate_catalog, context, base_instance_id=base_instance
    )
    verification_packet = next(
        packet for packet in manifest["packets"] if packet["operation"] == "VERIFY_RELATION"
    )

    output = args.output_dir.resolve()
    paths = {
        "catalog": output / "global_module_catalog.project01-validation-v1.json",
        "binding": output / "catalog-binding.json",
        "context": output / f"{CONTEXT_ID}.json",
        "dag": output / f"{CONTEXT_ID}.transaction-dag.json",
        "manifest": output / f"{CONTEXT_ID}.cad-transaction-manifest.json",
        "run": output / "preparation-run.json",
    }
    _write(paths["catalog"], candidate_catalog)
    _write(paths["binding"], binding)
    _write(paths["context"], context)
    _write(paths["dag"], dag)
    _write(paths["manifest"], manifest)
    run = {
        "schemaVersion": "project01-cross-project-relation-validation-preparation/v1",
        "status": (
            "ready"
            if manifest["status"] == "ready_for_generic_executor_implementation"
            else "blocked"
        ),
        "contextId": CONTEXT_ID,
        "derivedTemplateId": derived["globalTemplateId"],
        "sourceRelationApplicationMode": "driving",
        "verificationApplicationMode": "validate_only",
        "verificationPacketId": verification_packet["packetId"],
        "verificationPacketOrder": verification_packet["order"],
        "verificationOperation": verification_packet["operation"],
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
