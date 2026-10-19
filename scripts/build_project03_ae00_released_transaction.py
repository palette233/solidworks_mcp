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
    compile_cad_transaction_manifest,
    compile_transaction_dag,
    create_context,
    load_released_relation_catalog,
)
from demo_backend.global_command_audit import build_global_command_audit  # noqa: E402


DEFAULT_RELEASE = (
    "demo/global_assembly_catalog/releases/"
    "relation-v11-project03-ae00-driving-20261011/release-manifest.json"
)
DEFAULT_OUTPUT = ROOT / (
    "demo/global_assembly_contexts/project03-aa00-ae00-v11-driving-v1"
)
TEMPLATE_ID = "template/project03/ae00-to-aa00-three-datum-installation/3665a437a8"


def _definition(catalog: dict, token: str) -> dict:
    return next(
        row
        for row in catalog["moduleDefinitions"]
        if any(
            alias.get("projectId") == "project03"
            and alias.get("moduleToken") == token
            for alias in row.get("projectAliases") or []
        )
    )


def _port(catalog: dict, definition_id: str) -> str:
    template = next(
        row
        for row in catalog["connectionTemplates"]
        if row.get("globalTemplateId") == TEMPLATE_ID
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
        description="Compile the released Project03 AA00/AE00 driving transaction."
    )
    parser.add_argument("--release", default=DEFAULT_RELEASE)
    parser.add_argument("--context-id", default="project03-aa00-ae00-v11-driving-v1")
    parser.add_argument("--output-directory", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    catalog, release = load_released_relation_catalog(ROOT, args.release)
    aa00 = _definition(catalog, "AA00")
    ae00 = _definition(catalog, "AE00")
    base_instance_id = "fl9a24d063aa00-001-001"
    created = create_context(
        ROOT,
        {
            "contextId": args.context_id,
            "displayName": "Project03 AA00/AE00 released driving transaction",
            "releaseManifestPath": args.release,
            "overwrite": True,
        },
    )
    commands = [
        {
            "requirement": "先安装项目03 AA00箱体与回流固定环境",
            "moduleDefinitionId": aa00["moduleDefinitionId"],
        },
        {
            "requirement": "再把项目03 AE00传输模组安装到AA00的传输安装位",
            "moduleDefinitionId": ae00["moduleDefinitionId"],
            "existingInstanceId": base_instance_id,
            "newPortId": _port(catalog, ae00["moduleDefinitionId"]),
            "existingPortId": _port(catalog, aa00["moduleDefinitionId"]),
            "globalTemplateId": TEMPLATE_ID,
            "newSide": "B",
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
    dag = compile_transaction_dag(ROOT, args.context_id)
    cad = compile_cad_transaction_manifest(ROOT, args.context_id)
    audit = build_global_command_audit(catalog, context, dag, cad)
    output = args.output_directory.resolve()
    _write(output / "transaction-dag.json", dag)
    _write(output / "cad-transaction-manifest.json", cad)
    _write(output / "command-audit-summary.json", audit)
    status = (
        "ready_for_generic_cad_executor"
        if dag.get("status") == "ready_for_generic_cad_executor"
        and cad.get("status") == "ready_for_generic_executor_implementation"
        and audit.get("mappedCommandCount") == audit.get("commandCount")
        else "blocked"
    )
    report = {
        "schemaVersion": "project03-natural-language-transaction/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "releaseId": release["releaseId"],
        "releaseDigest": release["releaseDigest"],
        "catalogDigest": catalog["catalogDigest"],
        "contextPath": created["contextPath"],
        "contextDigest": context["contextDigest"],
        "naturalLanguageCommands": [row["requirement"] for row in commands],
        "selectedTemplateIds": [TEMPLATE_ID],
        "dagStatus": dag["status"],
        "cadManifestStatus": cad["status"],
        "cadPacketCount": cad["packetCount"],
        "releaseBinding": cad["relationReleaseBinding"],
        "commandAuditStatus": (
            "complete"
            if audit["mappedCommandCount"] == audit["commandCount"]
            else "incomplete"
        ),
        "solidWorksExecutedInThisCompile": False,
        "validationEvidenceAlreadyReleased": True,
        "collisionStatus": "not_evaluated",
        "statement": (
            "两条自然语言命令编译为一条受v11发布白名单约束的Project03"
            "累计CAD事务；AE00真实非原型初始位姿CAD证据已由发布清单绑定。"
        ),
    }
    _write(output / "report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if status == "ready_for_generic_cad_executor" else 1


if __name__ == "__main__":
    raise SystemExit(main())
