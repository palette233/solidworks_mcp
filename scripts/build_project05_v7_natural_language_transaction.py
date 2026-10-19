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
    compile_execution_manifest,
    compile_transaction_dag,
    create_context,
    load_released_relation_catalog,
)


DEFAULT_RELEASE = (
    "demo/global_assembly_catalog/releases/"
    "relation-v7-project05-driving-independent-20261011/release-manifest.json"
)
DEFAULT_OUTPUT = ROOT / (
    "demo/global_assembly_contexts/project05-a000-d000-v7-driving-v1"
)


def _definition(catalog: dict, token: str) -> dict:
    return next(
        row
        for row in catalog["moduleDefinitions"]
        if row["moduleDefinitionId"].startswith("cad/fl9c254098")
        and any(
            alias.get("projectId") == "project05"
            and alias.get("moduleToken") == token
            for alias in row.get("projectAliases") or []
        )
    )


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compile the released Project05 A000/D000 natural-language transaction."
    )
    parser.add_argument("--release", default=DEFAULT_RELEASE)
    parser.add_argument("--context-id", default="project05-a000-d000-v7-driving-v1")
    parser.add_argument("--output-directory", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    catalog, release = load_released_relation_catalog(ROOT, args.release)
    a000 = _definition(catalog, "A000")
    d000 = _definition(catalog, "D000")
    created = create_context(
        ROOT,
        {
            "contextId": args.context_id,
            "displayName": "Project05 A000/D000 released driving transaction",
            "releaseManifestPath": args.release,
            "overwrite": True,
        },
    )
    sequence = apply_command_sequence(
        ROOT,
        args.context_id,
        {
            "confirmed": True,
            "commands": [
                {
                    "requirement": "先安装项目05 A000机架基座",
                    "moduleDefinitionId": a000["moduleDefinitionId"],
                },
                {
                    "requirement": "在A000上安装项目05 D000输送模组",
                    "moduleDefinitionId": d000["moduleDefinitionId"],
                },
            ],
        },
    )
    if sequence.get("success") is not True:
        raise RuntimeError(json.dumps(sequence, ensure_ascii=False))

    dag = compile_transaction_dag(ROOT, args.context_id)
    cad = compile_cad_transaction_manifest(ROOT, args.context_id)
    execution = compile_execution_manifest(ROOT, args.context_id)
    output = args.output_directory.resolve()
    _write(output / "transaction-dag.json", dag)
    _write(output / "cad-transaction-manifest.json", cad)
    _write(output / "legacy-project-adapter-manifest.json", execution)
    report = {
        "schemaVersion": "project05-v7-natural-language-transaction/v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": "ready_for_generic_cad_executor",
        "releaseId": release["releaseId"],
        "releaseDigest": release["releaseDigest"],
        "catalogDigest": catalog["catalogDigest"],
        "contextPath": created["contextPath"],
        "contextDigest": sequence["context"]["contextDigest"],
        "naturalLanguageCommands": [
            "先安装项目05 A000机架基座",
            "在A000上安装项目05 D000输送模组",
        ],
        "selectedTemplateId": sequence["context"]["connections"][0][
            "globalTemplateId"
        ],
        "dagStatus": dag["status"],
        "cadManifestStatus": cad["status"],
        "cadPacketCount": cad["packetCount"],
        "releaseBinding": cad["relationReleaseBinding"],
        "legacyAdapterStatus": execution["status"],
        "legacyAdapterBlockers": execution["blockers"],
        "solidWorksExecuted": False,
        "statement": (
            "自然语言、发布授权、上下文、DAG和CAD事务包已绑定同一发布摘要；"
            "真实独立插入CAD证据由v7发布清单引用，本脚本不重复启动SolidWorks。"
        ),
    }
    _write(output / "report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
