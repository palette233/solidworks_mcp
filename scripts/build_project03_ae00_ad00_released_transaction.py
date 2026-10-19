from __future__ import annotations

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


RELEASE = (
    "demo/global_assembly_catalog/releases/"
    "relation-v12-project03-ae00-ad00-driving-20261011/release-manifest.json"
)
OUTPUT = ROOT / (
    "demo/global_assembly_contexts/project03-aa00-ae00-ad00-v12-driving-v1"
)
TEMPLATES = {
    "AE00": "template/project03/ae00-to-aa00-three-datum-installation/3665a437a8",
    "AD00": "template/project03/ad00-to-aa00-three-datum-installation/357acee2ce",
}


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


def _port(catalog: dict, template_id: str, definition_id: str) -> str:
    template = next(
        row
        for row in catalog["connectionTemplates"]
        if row.get("globalTemplateId") == template_id
    )
    candidates = set(
        (template.get("candidatePortIdsA") or [])
        + (template.get("candidatePortIdsB") or [])
    )
    return next(
        row["globalPortId"]
        for row in catalog["semanticPorts"]
        if row.get("globalPortId") in candidates
        and row.get("moduleDefinitionId") == definition_id
    )


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    catalog, release = load_released_relation_catalog(ROOT, RELEASE)
    definitions = {token: _definition(catalog, token) for token in ("AA00", "AE00", "AD00")}
    context_id = "project03-aa00-ae00-ad00-v12-driving-v1"
    base_instance_id = "fl9a24d063aa00-001-001"
    created = create_context(
        ROOT,
        {
            "contextId": context_id,
            "displayName": "Project03 AA00/AE00/AD00 v12 cumulative transaction",
            "releaseManifestPath": RELEASE,
            "overwrite": True,
        },
    )
    commands = [
        {
            "requirement": "先安装项目03 AA00箱体与回流固定环境",
            "moduleDefinitionId": definitions["AA00"]["moduleDefinitionId"],
        }
    ]
    for token, text in (
        ("AE00", "再把项目03 AE00传输模组安装到AA00传输安装位"),
        ("AD00", "然后把项目03 AD00功能模组安装到AA00功能安装位"),
    ):
        template_id = TEMPLATES[token]
        commands.append(
            {
                "requirement": text,
                "moduleDefinitionId": definitions[token]["moduleDefinitionId"],
                "existingInstanceId": base_instance_id,
                "newPortId": _port(
                    catalog, template_id, definitions[token]["moduleDefinitionId"]
                ),
                "existingPortId": _port(
                    catalog, template_id, definitions["AA00"]["moduleDefinitionId"]
                ),
                "globalTemplateId": template_id,
                "newSide": "B",
            }
        )
    sequence = apply_command_sequence(
        ROOT,
        context_id,
        {"confirmed": True, "commands": commands},
    )
    if sequence.get("success") is not True:
        raise RuntimeError(json.dumps(sequence, ensure_ascii=False, indent=2))
    context = sequence["context"]
    dag = compile_transaction_dag(ROOT, context_id)
    cad = compile_cad_transaction_manifest(ROOT, context_id)
    audit = build_global_command_audit(catalog, context, dag, cad)
    _write(OUTPUT / "transaction-dag.json", dag)
    _write(OUTPUT / "cad-transaction-manifest.json", cad)
    _write(OUTPUT / "command-audit-summary.json", audit)
    status = (
        "ready_for_generic_cad_executor"
        if dag.get("status") == "ready_for_generic_cad_executor"
        and cad.get("status") == "ready_for_generic_executor_implementation"
        and cad.get("packetCount") == 2
        and audit.get("mappedCommandCount") == audit.get("commandCount")
        else "blocked"
    )
    report = {
        "schemaVersion": "project03-natural-language-cumulative-transaction/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "releaseId": release["releaseId"],
        "releaseDigest": release["releaseDigest"],
        "catalogDigest": catalog["catalogDigest"],
        "contextPath": created["contextPath"],
        "contextDigest": context["contextDigest"],
        "naturalLanguageCommands": [row["requirement"] for row in commands],
        "selectedTemplateIds": sorted(TEMPLATES.values()),
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
        "collisionStatus": "not_evaluated",
    }
    _write(OUTPUT / "report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if status == "ready_for_generic_cad_executor" else 2


if __name__ == "__main__":
    raise SystemExit(main())
