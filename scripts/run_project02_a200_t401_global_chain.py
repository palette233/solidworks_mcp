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

from demo_backend.global_assembly_compiler import (  # noqa: E402
    compile_global_assembly_execution_manifest,
)
from demo_backend.global_assembly_context import (  # noqa: E402
    apply_global_command_preview,
    create_global_assembly_context,
    preview_global_assembly_command,
)
from demo_backend.global_module_catalog import build_global_module_catalog  # noqa: E402


DEFAULT_OUTPUT = WORKSPACE / "demo/global_assembly_contexts/project02-a200-t401-evidence-v1.json"


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
        description="Run the Project02 A600/A200/T401 semantic graph evidence chain."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    # Use the canonical cross-project catalog so the persisted context remains
    # loadable by the global workbench and downstream project adapter compiler.
    catalog = build_global_module_catalog(WORKSPACE)
    context = create_global_assembly_context(
        "project02-a200-t401-evidence-v1",
        display_name="项目02 CCD 与双供胶语义增量链",
        catalog_digest=catalog["catalogDigest"],
    )
    commands = [
        ("A600", "先安装项目02的A600箱体"),
        ("A200", "再将A200 CCD视觉模组安装到A600"),
        ("T401", "将第一套T401供胶系统安装到A600"),
        ("T401", "将第二套T401供胶系统按原型距离关系安装到A200"),
    ]
    audit: list[dict[str, Any]] = []
    for token, requirement in commands:
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
                "selectedConnection": preview.get("proposedPatch", {}).get("connection"),
                "blockers": preview["blockers"],
                "previewDigest": preview["previewDigest"],
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
    audit_path = output.with_suffix(".run.json")
    manifest_path = output.with_suffix(".execution-manifest.json")
    write_json(
        audit_path,
        {
            "schemaVersion": "project02-a200-t401-global-chain-run/v1",
            "success": True,
            "commands": audit,
            "instanceCount": len(context["instances"]),
            "connectionCount": len(context["connections"]),
            "revision": context["revision"],
            "solidWorksExecuted": False,
            "collisionGateExecuted": False,
        },
    )
    write_json(manifest_path, manifest)
    print(
        json.dumps(
            {
                "success": True,
                "contextPath": str(output),
                "auditPath": str(audit_path),
                "executionManifestPath": str(manifest_path),
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
