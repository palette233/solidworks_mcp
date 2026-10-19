from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.global_relation_edits import (  # noqa: E402
    apply_global_relation_edit,
    preview_global_relation_edit,
)
from demo_backend.global_assembly_context import context_digest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Preview or commit one relation edit to a new global context file."
    )
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--context", required=True, type=Path)
    parser.add_argument(
        "--operation",
        choices=("add", "verify", "replace", "delete"),
        default="add",
    )
    parser.add_argument("--requirement", default="")
    parser.add_argument("--instance-a")
    parser.add_argument("--instance-b")
    parser.add_argument("--connection-id")
    parser.add_argument("--global-template-id")
    parser.add_argument("--port-a-id")
    parser.add_argument("--port-b-id")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--target-context-id")
    parser.add_argument("--preview-output", type=Path)
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()

    catalog = json.loads(args.catalog.resolve().read_text(encoding="utf-8-sig"))
    context = json.loads(args.context.resolve().read_text(encoding="utf-8-sig"))
    payload = {
        "operation": args.operation,
        "requirement": args.requirement,
        "instanceAId": args.instance_a,
        "instanceBId": args.instance_b,
        "connectionId": args.connection_id,
        "globalTemplateId": args.global_template_id,
        "portAId": args.port_a_id,
        "portBId": args.port_b_id,
    }
    preview = preview_global_relation_edit(catalog, context, payload)
    preview_output = (
        args.preview_output.resolve()
        if args.preview_output
        else args.output.resolve().with_suffix(".preview.json")
    )
    preview_output.parent.mkdir(parents=True, exist_ok=True)
    preview_output.write_text(
        json.dumps(preview, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if not args.confirm:
        print(json.dumps({
            "status": preview["status"],
            "previewOutput": str(preview_output),
            "previewDigest": preview["previewDigest"],
            "blockers": preview["blockers"],
        }, ensure_ascii=False, indent=2))
        return 0 if preview["status"] == "ready" else 2

    updated = apply_global_relation_edit(
        context,
        preview,
        preview_digest=preview["previewDigest"],
        confirmed=True,
    )
    if args.target_context_id:
        updated["contextId"] = args.target_context_id
        updated["contextDigest"] = context_digest(updated)
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(updated, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": "committed",
        "previewOutput": str(preview_output),
        "output": str(output),
        "contextId": updated["contextId"],
        "contextDigest": updated["contextDigest"],
        "connectionCount": len(updated.get("connections") or []),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
