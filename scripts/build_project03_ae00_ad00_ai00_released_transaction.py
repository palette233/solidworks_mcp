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


RELEASE = (
    "demo/global_assembly_catalog/releases/"
    "relation-v13-project03-ae00-ad00-ai00-driving-20261011/release-manifest.json"
)
CONTEXT_ID = "project03-aa00-ae00-ad00-ai00-v13-driving-v1"
OUTPUT = ROOT / f"demo/global_assembly_contexts/{CONTEXT_ID}"
TEMPLATES = {
    "AE00": "template/project03/ae00-to-aa00-three-datum-installation/3665a437a8",
    "AD00": "template/project03/ad00-to-aa00-three-datum-installation/357acee2ce",
    "AI00": "template/project03/ai00-to-aa00-five-mate-installation/0b1374c7f5",
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
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    catalog, release = load_released_relation_catalog(ROOT, RELEASE)
    definitions = {
        token: _definition(catalog, token)
        for token in ("AA00", "AE00", "AD00", "AI00")
    }
    base_instance_id = "fl9a24d063aa00-001-001"
    created = create_context(
        ROOT,
        {
            "contextId": CONTEXT_ID,
            "displayName": "Project03 AA00/AE00/AD00/AI00 v13 cumulative transaction",
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
        ("AI00", "最后把项目03 AI00扫描模组安装到AA00扫描安装位"),
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
        ROOT, CONTEXT_ID, {"confirmed": True, "commands": commands}
    )
    if sequence.get("success") is not True:
        raise RuntimeError(json.dumps(sequence, ensure_ascii=False, indent=2))
    context = sequence["context"]
    dag = compile_transaction_dag(ROOT, CONTEXT_ID)
    cad = compile_cad_transaction_manifest(ROOT, CONTEXT_ID)
    _write(OUTPUT / "transaction-dag.json", dag)
    _write(OUTPUT / "cad-transaction-manifest.json", cad)
    status = (
        "ready_for_generic_cad_executor"
        if dag.get("status") == "ready_for_generic_cad_executor"
        and cad.get("status") == "ready_for_generic_executor_implementation"
        and cad.get("packetCount") == 3
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
        "commandAuditProducedByDurableJob": True,
        "solidWorksExecutedInThisCompile": False,
        "collisionStatus": "not_evaluated",
    }
    _write(OUTPUT / "report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if status == "ready_for_generic_cad_executor" else 2


if __name__ == "__main__":
    raise SystemExit(main())
