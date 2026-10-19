from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.global_assembly_workbench import (  # noqa: E402
    apply_command_sequence,
    apply_relation_edit,
    compile_cad_transaction_manifest,
    compile_execution_manifest,
    compile_transaction_dag,
    create_context,
    load_released_relation_catalog,
    preview_relation_edit,
)
from demo_backend.global_command_audit import build_global_command_audit  # noqa: E402


DEFAULT_RELEASE = (
    "demo/global_assembly_catalog/releases/"
    "relation-v9-project01-driving-independent-20261011/release-manifest.json"
)
DEFAULT_OUTPUT = ROOT / (
    "demo/global_assembly_contexts/project01-jj00-ss00-gn00-v8-driving-v1"
)
ANTI_ROTATION_TEMPLATE_ID = (
    "template/project01/gn00-ss00-standalone-parallel/5df3a32e59"
)
SS00_TEMPLATE_ID = (
    "template/project01/ss00-to-jj00-three-datum-installation/c087ea93d1"
)
GN00_PRIMARY_TEMPLATE_ID = (
    "template/project01/gn00-to-jj00-primary/8ff522aead"
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


def _instance(context: dict, definition_id: str) -> dict:
    return next(
        row
        for row in context["instances"]
        if row.get("moduleDefinitionId") == definition_id
    )


def _port_for_definition(catalog: dict, template_id: str, definition_id: str) -> str:
    template = next(
        row
        for row in catalog["connectionTemplates"]
        if row.get("globalTemplateId") == template_id
    )
    candidate_ids = set(
        (template.get("candidatePortIdsA") or [])
        + (template.get("candidatePortIdsB") or [])
    )
    return next(
        row["globalPortId"]
        for row in catalog["semanticPorts"]
        if row.get("globalPortId") in candidate_ids
        and row.get("moduleDefinitionId") == definition_id
    )


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compile the released Project01 JJ00/SS00/GN00 natural-language "
            "transaction with an authorized anti-rotation relation edit."
        )
    )
    parser.add_argument("--release", default=DEFAULT_RELEASE)
    parser.add_argument(
        "--context-id", default="project01-jj00-ss00-gn00-v8-driving-v1"
    )
    parser.add_argument("--output-directory", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    catalog, release = load_released_relation_catalog(ROOT, args.release)
    jj00 = _definition(catalog, "JJ00")
    ss00 = _definition(catalog, "SS00")
    gn00 = _definition(catalog, "GN00")
    jj00_instance_id = "fl9c24n074jj00-001-001"
    created = create_context(
        ROOT,
        {
            "contextId": args.context_id,
            "displayName": "Project01 JJ00/SS00/GN00 released driving transaction",
            "releaseManifestPath": args.release,
            "overwrite": True,
        },
    )
    commands = [
        {
            "requirement": "先安装项目01 JJ00机架基座",
            "moduleDefinitionId": jj00["moduleDefinitionId"],
        },
        {
            "requirement": "在JJ00上安装项目01 SS00输送模组",
            "moduleDefinitionId": ss00["moduleDefinitionId"],
            "existingInstanceId": jj00_instance_id,
            "newPortId": _port_for_definition(
                catalog, SS00_TEMPLATE_ID, ss00["moduleDefinitionId"]
            ),
            "existingPortId": _port_for_definition(
                catalog, SS00_TEMPLATE_ID, jj00["moduleDefinitionId"]
            ),
            "globalTemplateId": SS00_TEMPLATE_ID,
            "newSide": "B",
        },
        {
            "requirement": "在JJ00上安装项目01 GN00模组",
            "moduleDefinitionId": gn00["moduleDefinitionId"],
            "existingInstanceId": jj00_instance_id,
            "newPortId": _port_for_definition(
                catalog, GN00_PRIMARY_TEMPLATE_ID, gn00["moduleDefinitionId"]
            ),
            "existingPortId": _port_for_definition(
                catalog, GN00_PRIMARY_TEMPLATE_ID, jj00["moduleDefinitionId"]
            ),
            "globalTemplateId": GN00_PRIMARY_TEMPLATE_ID,
            "newSide": "A",
        },
    ]
    sequence = apply_command_sequence(
        ROOT,
        args.context_id,
        {"confirmed": True, "commands": commands},
    )
    if sequence.get("success") is not True:
        raise RuntimeError(json.dumps(sequence, ensure_ascii=False, indent=2))

    context = sequence["context"]
    edit_preview = preview_relation_edit(
        ROOT,
        args.context_id,
        {
            "operation": "add",
            "requirement": "让项目01 GN00防转面与SS00基准面保持平行",
            "instanceAId": _instance(context, gn00["moduleDefinitionId"])["instanceId"],
            "instanceBId": _instance(context, ss00["moduleDefinitionId"])["instanceId"],
            "globalTemplateId": ANTI_ROTATION_TEMPLATE_ID,
        },
    )
    if edit_preview.get("status") != "ready":
        raise RuntimeError(json.dumps(edit_preview, ensure_ascii=False, indent=2))
    edited = apply_relation_edit(
        ROOT,
        args.context_id,
        {
            "preview": edit_preview,
            "previewDigest": edit_preview["previewDigest"],
            "confirmed": True,
        },
    )

    dag = compile_transaction_dag(ROOT, args.context_id)
    cad = compile_cad_transaction_manifest(ROOT, args.context_id)
    execution = compile_execution_manifest(ROOT, args.context_id)
    command_audit = build_global_command_audit(
        catalog,
        edited["context"],
        dag,
        cad,
    )
    output = args.output_directory.resolve()
    _write(output / "relation-edit-preview.json", edit_preview)
    _write(output / "transaction-dag.json", dag)
    _write(output / "cad-transaction-manifest.json", cad)
    _write(output / "legacy-project-adapter-manifest.json", execution)
    _write(output / "command-audit-summary.json", command_audit)
    report = {
        "schemaVersion": "project01-natural-language-transaction/v2",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": (
            "ready_for_generic_cad_executor"
            if dag.get("status") == "ready_for_generic_cad_executor"
            and cad.get("status") == "ready_for_generic_executor_implementation"
            else "blocked"
        ),
        "releaseId": release["releaseId"],
        "releaseDigest": release["releaseDigest"],
        "catalogDigest": catalog["catalogDigest"],
        "contextPath": created["contextPath"],
        "contextDigest": edited["context"]["contextDigest"],
        "naturalLanguageCommands": [row["requirement"] for row in commands]
        + ["让项目01 GN00防转面与SS00基准面保持平行"],
        "selectedTemplateIds": sorted(
            {
                row["globalTemplateId"]
                for row in edited["context"]["connections"]
            }
        ),
        "dagStatus": dag["status"],
        "cadManifestStatus": cad["status"],
        "cadPacketCount": cad["packetCount"],
        "releaseBinding": cad["relationReleaseBinding"],
        "legacyAdapterStatus": execution["status"],
        "legacyAdapterBlockers": execution["blockers"],
        "commandAuditPath": str(output / "command-audit-summary.json"),
        "commandAuditStatus": (
            "complete"
            if command_audit["mappedCommandCount"] == command_audit["commandCount"]
            else "incomplete"
        ),
        "solidWorksExecuted": False,
        "statement": (
            "三条自然语言安装/配合命令被编译为两步累计CAD事务；"
            f"所有驱动模板均受{release['releaseId']}发布白名单约束，"
            "未执行碰撞/B-rep。"
        ),
    }
    _write(output / "report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ready_for_generic_cad_executor" else 1


if __name__ == "__main__":
    raise SystemExit(main())
