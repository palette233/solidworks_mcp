from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


WORKSPACE = Path(__file__).resolve().parents[1]
BACKEND_SRC = WORKSPACE / "apps" / "demo-backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.global_assembly_compiler import compile_global_assembly_execution_manifest
from demo_backend.global_assembly_context import (
    apply_global_command_preview,
    create_global_assembly_context,
    preview_global_assembly_command,
)
from demo_backend.global_module_catalog import build_global_module_catalog
from demo_backend.global_project_adapter_plan import compile_global_project_adapter_plan


DEFAULT_OUTPUT = WORKSPACE / "demo/global_assembly_contexts/project02-full-static-graph-v1.json"
COMMANDS = [
    ("A600", "先安装项目02的A600箱体"),
    ("A800", "将A800传输模组安装到A600"),
    ("A180", "将A180扫描模组安装到A600"),
    ("A700", "将A700清洁称重模组安装到A600"),
    ("A300", "将A300排胶模组安装到A600"),
    ("A500", "将A500校准模组安装到A600"),
    ("A100", "将A100龙门模组安装到A600"),
    ("A200", "将A200 CCD模组安装到A600"),
    ("T401", "将第一套T401供胶系统安装到A600"),
    ("T401", "将第二套T401供胶系统安装到A200"),
]


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def definition(catalog: dict[str, Any], token: str) -> dict[str, Any]:
    return next(
        row
        for row in catalog["moduleDefinitions"]
        if any(
            alias["projectId"] == "project02" and alias["moduleToken"] == token
            for alias in row["projectAliases"]
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compile the complete Project02 semantic graph and adapter plan."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    catalog = build_global_module_catalog(WORKSPACE)
    context = create_global_assembly_context(
        "project02-full-static-graph-v1",
        display_name="项目02十实例完整静态语义图链",
        catalog_digest=catalog["catalogDigest"],
    )
    audit: list[dict[str, Any]] = []
    for token, requirement in COMMANDS:
        preview = preview_global_assembly_command(
            catalog,
            context,
            {
                "requirement": requirement,
                "moduleDefinitionId": definition(catalog, token)["moduleDefinitionId"],
            },
        )
        audit.append(
            {
                "token": token,
                "requirement": requirement,
                "status": preview["status"],
                "candidateCount": len(preview["connectionCandidates"]),
                "selectedConnection": (preview.get("proposedPatch") or {}).get("connection"),
                "blockers": preview["blockers"],
            }
        )
        if preview["status"] != "ready":
            raise RuntimeError(json.dumps(audit[-1], ensure_ascii=False))
        context = apply_global_command_preview(
            context,
            preview,
            preview_digest=preview["previewDigest"],
            confirmed=True,
        )

    manifest = compile_global_assembly_execution_manifest(WORKSPACE, catalog, context)
    adapter_plan = compile_global_project_adapter_plan(
        WORKSPACE,
        catalog,
        context,
        manifest,
    )
    write_json(output, context)
    write_json(
        output.with_suffix(".run.json"),
        {
            "schemaVersion": "project02-full-global-semantic-chain-run/v1",
            "success": True,
            "commands": audit,
            "instanceCount": len(context["instances"]),
            "connectionCount": len(context["connections"]),
            "solidWorksExecuted": False,
            "collisionGateExecuted": False,
        },
    )
    write_json(output.with_suffix(".execution-manifest.json"), manifest)
    write_json(output.with_suffix(".project-adapter-plan.json"), adapter_plan)
    print(
        json.dumps(
            {
                "success": adapter_plan["safeToCreateDurableJob"],
                "contextPath": str(output),
                "instanceCount": len(context["instances"]),
                "connectionCount": len(context["connections"]),
                "manifestStatus": manifest["status"],
                "adapterStatus": adapter_plan["status"],
                "adapterStepCount": adapter_plan["stepCount"],
                "groupedInstanceTokens": adapter_plan["runnerBinding"][
                    "groupedInstanceTokens"
                ],
                "solidWorksExecuted": False,
                "collisionGateExecuted": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if adapter_plan["safeToCreateDurableJob"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
