from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
BACKEND_SRC = WORKSPACE / "apps" / "demo-backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.global_assembly_workbench import (  # noqa: E402
    apply_command,
    compile_execution_manifest,
    create_context,
    load_context,
    preview_command,
)


DEFAULT_COMMANDS = [
    "请先安装A600箱体模组",
    "然后安装A800传输模组",
    "最后安装A180扫描模组",
]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="运行跨项目自然语言增量装配图Demo；不启动SolidWorks，不执行碰撞门禁。"
    )
    parser.add_argument("--context-id", default="global-nl-demo")
    parser.add_argument("--commands", nargs="*", default=DEFAULT_COMMANDS)
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    if args.reset:
        created = create_context(
            WORKSPACE,
            {
                "contextId": args.context_id,
                "displayName": "自然语言跨项目装配Demo",
                "overwrite": True,
            },
        )
        context = created["context"]
    else:
        try:
            context = load_context(WORKSPACE, args.context_id)
        except Exception:
            context = create_context(
                WORKSPACE,
                {"contextId": args.context_id, "displayName": "自然语言跨项目装配Demo"},
            )["context"]

    steps = []
    for index, requirement in enumerate(args.commands, start=1):
        preview = preview_command(
            WORKSPACE,
            args.context_id,
            {"requirement": requirement},
        )
        step = {
            "order": index,
            "requirement": requirement,
            "previewStatus": preview["status"],
            "resolution": preview["resolution"],
            "selectedModuleDefinitionId": preview.get("selectedModuleDefinitionId"),
            "candidateCount": len(preview.get("connectionCandidates") or []),
            "blockers": preview.get("blockers") or [],
            "previewDigest": preview["previewDigest"],
        }
        if preview["status"] != "ready":
            step["applyStatus"] = "not_applied"
            steps.append(step)
            break
        result = apply_command(
            WORKSPACE,
            args.context_id,
            {
                "preview": preview,
                "previewDigest": preview["previewDigest"],
                "confirmed": True,
            },
        )
        context = result["context"]
        step["applyStatus"] = "applied_to_context"
        step["contextRevision"] = context["revision"]
        steps.append(step)

    report = {
        "schemaVersion": "global-natural-language-assembly-demo/v1",
        "contextId": args.context_id,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "success": len(steps) == len(args.commands)
        and all(step.get("applyStatus") == "applied_to_context" for step in steps),
        "steps": steps,
        "finalContext": context,
        "executionBoundary": {
            "solidWorksExecuted": False,
            "collisionGateExecuted": False,
            "resultClass": "auditable_assembly_graph_draft",
        },
    }
    execution_manifest = compile_execution_manifest(WORKSPACE, args.context_id)
    report["executionManifest"] = execution_manifest
    report_path = WORKSPACE / "demo" / "global_assembly_contexts" / f"{args.context_id}.run.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest_path = (
        WORKSPACE
        / "demo"
        / "global_assembly_contexts"
        / f"{args.context_id}.execution-manifest.json"
    )
    manifest_path.write_text(
        json.dumps(execution_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({**report, "reportPath": str(report_path)}, ensure_ascii=False, indent=2))
    return 0 if report["success"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
