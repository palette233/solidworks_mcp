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

from demo_backend.global_assembly_workbench import (
    apply_command_sequence,
    compile_cad_transaction_manifest,
    compile_transaction_dag,
    create_context,
    load_released_relation_catalog,
)


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


def _port(catalog: dict, template: dict, definition_id: str) -> str:
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", required=True)
    parser.add_argument("--context-id", required=True)
    parser.add_argument("--tokens", required=True, help="Comma-separated order after AA00")
    args = parser.parse_args()
    tokens = [value.strip().upper() for value in args.tokens.split(",") if value.strip()]
    if not tokens or len(tokens) != len(set(tokens)):
        raise ValueError("tokens必须是非空且不重复的模组顺序。")

    catalog, release = load_released_relation_catalog(ROOT, args.release)
    authorized = set(
        (release.get("scope") or {}).get("authorizedDrivingTemplateIds") or []
    )
    templates = {}
    for token in tokens:
        matches = [
            row
            for row in catalog["connectionTemplates"]
            if row.get("globalTemplateId") in authorized
            and str(row.get("legacyTemplateId") or "").upper().startswith(f"{token}_TO_AA00_")
        ]
        if len(matches) != 1:
            raise ValueError(f"{token}没有唯一获授权AA00安装模板：{len(matches)}")
        templates[token] = matches[0]

    definitions = {
        token: _definition(catalog, token) for token in ["AA00", *tokens]
    }
    output = ROOT / "demo/global_assembly_contexts" / args.context_id
    created = create_context(
        ROOT,
        {
            "contextId": args.context_id,
            "displayName": f"Project03 AA00/{'/'.join(tokens)} released cumulative transaction",
            "releaseManifestPath": args.release,
            "overwrite": True,
        },
    )
    base_instance_id = "fl9a24d063aa00-001-001"
    commands = [
        {
            "requirement": "先安装项目03 AA00箱体与回流固定环境",
            "moduleDefinitionId": definitions["AA00"]["moduleDefinitionId"],
        }
    ]
    for index, token in enumerate(tokens):
        template = templates[token]
        commands.append(
            {
                "requirement": f"第{index + 2}步把项目03 {token}模组安装到AA00安装位",
                "moduleDefinitionId": definitions[token]["moduleDefinitionId"],
                "existingInstanceId": base_instance_id,
                "newPortId": _port(
                    catalog, template, definitions[token]["moduleDefinitionId"]
                ),
                "existingPortId": _port(
                    catalog, template, definitions["AA00"]["moduleDefinitionId"]
                ),
                "globalTemplateId": template["globalTemplateId"],
                "newSide": "B",
            }
        )
    sequence = apply_command_sequence(
        ROOT, args.context_id, {"confirmed": True, "commands": commands}
    )
    if sequence.get("success") is not True:
        raise RuntimeError(json.dumps(sequence, ensure_ascii=False, indent=2))
    dag = compile_transaction_dag(ROOT, args.context_id)
    manifest = compile_cad_transaction_manifest(ROOT, args.context_id)
    _write(output / "transaction-dag.json", dag)
    _write(output / "cad-transaction-manifest.json", manifest)
    ready = (
        dag.get("status") == "ready_for_generic_cad_executor"
        and manifest.get("status") == "ready_for_generic_executor_implementation"
        and manifest.get("packetCount") == len(tokens)
    )
    report = {
        "schemaVersion": "project03-released-cumulative-transaction/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": "ready_for_generic_cad_executor" if ready else "blocked",
        "releaseId": release["releaseId"],
        "contextPath": created["contextPath"],
        "contextDigest": sequence["context"]["contextDigest"],
        "naturalLanguageCommands": [row["requirement"] for row in commands],
        "selectedTemplateIds": [templates[token]["globalTemplateId"] for token in tokens],
        "cadPacketCount": manifest.get("packetCount"),
        "solidWorksExecutedInThisCompile": False,
        "collisionStatus": "not_evaluated",
    }
    _write(output / "report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
