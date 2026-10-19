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

from demo_backend.global_assembly_compiler import compile_global_assembly_execution_manifest  # noqa: E402
from demo_backend.global_assembly_context import (  # noqa: E402
    apply_global_command_preview,
    create_global_assembly_context,
    preview_global_assembly_command,
)
from demo_backend.global_module_catalog import build_global_module_catalog  # noqa: E402


DEFAULT_OUTPUT = WORKSPACE / "demo/global_assembly_contexts/project05-full-static-graph-v1.json"
COMMANDS = [
    ("A000", "先安装项目05机架与回流固定环境A000"),
    ("D000", "在A000上安装D000上层产品输送模组"),
    ("K000", "在A000上安装K000双工位顶升定位模组"),
    ("F000", "在A000上安装F000双读头条码扫描模组"),
    ("M000", "在A000上安装M000产品定位CCD模组"),
    ("G000", "在A000上安装G000校准与称重组合模组"),
    ("N000", "在A000上安装N000自动针头清洁模组"),
    ("P000", "在A000上安装P000双杯排胶模组"),
    ("B000", "最后在A000上安装B000龙门与双阀Z轴运动组"),
]


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def definition(catalog: dict[str, Any], token: str) -> dict[str, Any]:
    return next(
        row
        for row in catalog["moduleDefinitions"]
        if any(
            alias["projectId"] == "project05" and alias["moduleToken"] == token
            for alias in row["projectAliases"]
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Project05 global semantic graph chain.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    # Persist contexts against the same cross-project catalog consumed by the
    # workbench/API.  A project-only digest would make the saved context
    # impossible to reopen after the command-line demo ends.
    catalog = build_global_module_catalog(WORKSPACE)
    context = create_global_assembly_context(
        "project05-full-static-graph-v1",
        display_name="项目05九功能对象全局语义图链",
        catalog_digest=catalog["catalogDigest"],
    )
    audit: list[dict[str, Any]] = []
    for token, requirement in COMMANDS:
        selected = definition(catalog, token)
        preview = preview_global_assembly_command(
            catalog,
            context,
            {
                "requirement": requirement,
                "moduleDefinitionId": selected["moduleDefinitionId"],
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
    write_json(output, context)
    write_json(
        output.with_suffix(".run.json"),
        {
            "schemaVersion": "project05-global-semantic-chain-run/v1",
            "success": True,
            "commands": audit,
            "instanceCount": len(context["instances"]),
            "connectionCount": len(context["connections"]),
            "revision": context["revision"],
            "solidWorksExecuted": False,
            "collisionGateExecuted": False,
        },
    )
    write_json(output.with_suffix(".execution-manifest.json"), manifest)
    print(
        json.dumps(
            {
                "success": True,
                "contextPath": str(output),
                "instanceCount": len(context["instances"]),
                "connectionCount": len(context["connections"]),
                "manifestStatus": manifest["status"],
                "manifestStepCount": manifest["stepCount"],
                "solidWorksExecuted": False,
                "collisionGateExecuted": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
