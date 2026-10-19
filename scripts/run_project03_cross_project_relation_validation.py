from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.global_assembly_context import (  # noqa: E402
    apply_global_command_preview,
    create_global_assembly_context,
    preview_global_assembly_command,
)
from demo_backend.global_assembly_transactions import (  # noqa: E402
    compile_global_assembly_transaction_dag,
)
from demo_backend.global_cad_transaction_packets import (  # noqa: E402
    compile_global_cad_transaction_manifest,
)
from demo_backend.global_relation_edits import (  # noqa: E402
    apply_global_relation_edit,
    preview_global_relation_edit,
)
from demo_backend.global_relation_template_derivation import (  # noqa: E402
    derive_standalone_validation_relation,
)


CONTEXT_ID = "project03-aa00-ab00-distance5-validation-v1"
SOURCE_TEMPLATE = (
    "template/project03/ab00-to-aa00-partial-anchored-installation/05116b19ae"
)
AA00_DEFINITION = "cad/fl9a24d063aa00-001/dc4bbec17218"
AB00_DEFINITION = "cad/fl9a24d063ab00-001/61489551a4d8"
AA00_PORT = (
    "cad/fl9a24d063aa00-001/dc4bbec17218::port/aa00-ab00-installation/6d167eda9b"
)
AB00_PORT = (
    "cad/fl9a24d063ab00-001/61489551a4d8::port/ab00-frame-installation/d7ea221f77"
)


def _load(path: Path) -> dict:
    return json.loads(path.resolve().read_text(encoding="utf-8-sig"))


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
        description="Prepare Project03 AA00/AB00 Distance5 cross-project validation."
    )
    parser.add_argument(
        "--source-catalog",
        type=Path,
        default=ROOT
        / "demo/global_assembly_catalog/v1/global_module_catalog.relation-v2-preview.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "demo/global_assembly_contexts/project03-relation-validation-v1",
    )
    args = parser.parse_args()

    source_catalog = _load(args.source_catalog)
    catalog, derivation = derive_standalone_validation_relation(
        source_catalog,
        source_global_template_id=SOURCE_TEMPLATE,
        mate_name="距离5",
    )
    derived_template = derivation["derivedGlobalTemplateId"]
    context = create_global_assembly_context(
        CONTEXT_ID,
        display_name="Project03跨项目验证：AA00—AB00距离5只读复核",
        catalog_digest=catalog["catalogDigest"],
    )
    base_preview = preview_global_assembly_command(
        catalog,
        context,
        {
            "requirement": "添加项目03 AA00箱体与回流固定环境作为基座",
            "moduleDefinitionId": AA00_DEFINITION,
        },
    )
    if base_preview["status"] != "ready":
        raise RuntimeError(json.dumps(base_preview, ensure_ascii=False, indent=2))
    context = apply_global_command_preview(
        context,
        base_preview,
        preview_digest=base_preview["previewDigest"],
        confirmed=True,
    )
    install_preview = preview_global_assembly_command(
        catalog,
        context,
        {
            "requirement": "将项目03 AB00龙门与双阀点胶运动组安装到AA00",
            "moduleDefinitionId": AB00_DEFINITION,
            "existingInstanceId": _instance(context, AA00_DEFINITION),
            "newSide": "B",
            "globalTemplateId": SOURCE_TEMPLATE,
            "newPortId": AB00_PORT,
            "existingPortId": AA00_PORT,
        },
    )
    if install_preview["status"] != "ready":
        raise RuntimeError(json.dumps(install_preview, ensure_ascii=False, indent=2))
    context = apply_global_command_preview(
        context,
        install_preview,
        preview_digest=install_preview["previewDigest"],
        confirmed=True,
    )
    relation_preview = preview_global_relation_edit(
        catalog,
        context,
        {
            "operation": "verify",
            "requirement": "验证项目03 AA00与AB00保持40mm距离",
            "instanceAId": _instance(context, AA00_DEFINITION),
            "instanceBId": _instance(context, AB00_DEFINITION),
            "globalTemplateId": derived_template,
            "portAId": AA00_PORT,
            "portBId": AB00_PORT,
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

    dag = compile_global_assembly_transaction_dag(
        catalog, context, base_instance_id=_instance(context, AA00_DEFINITION)
    )
    manifest = compile_global_cad_transaction_manifest(
        catalog, context, base_instance_id=_instance(context, AA00_DEFINITION)
    )
    output = args.output_dir.resolve()
    paths = {
        "catalog": output / "global_module_catalog.project03-validation-v1.json",
        "derivation": output / "template-derivation-evidence.json",
        "context": output / f"{CONTEXT_ID}.json",
        "dag": output / f"{CONTEXT_ID}.transaction-dag.json",
        "manifest": output / f"{CONTEXT_ID}.cad-transaction-manifest.json",
        "run": output / "preparation-run.json",
    }
    _write(paths["catalog"], catalog)
    _write(paths["derivation"], derivation)
    _write(paths["context"], context)
    _write(paths["dag"], dag)
    _write(paths["manifest"], manifest)
    verification_packet = next(
        packet for packet in manifest["packets"] if packet["operation"] == "VERIFY_RELATION"
    )
    run = {
        "schemaVersion": "project03-cross-project-relation-validation-preparation/v1",
        "status": "ready" if manifest["status"] == "ready_for_generic_executor_implementation" else "blocked",
        "contextId": CONTEXT_ID,
        "derivedTemplateId": derived_template,
        "requestedDistanceMeters": 0.04,
        "verificationPacketId": verification_packet["packetId"],
        "verificationOperation": verification_packet["operation"],
        "verificationMateCount": sum(
            len(row.get("mates") or []) for row in verification_packet["connections"]
        ),
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
