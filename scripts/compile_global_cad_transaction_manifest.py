from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.global_assembly_workbench import (  # noqa: E402
    compile_cad_transaction_manifest,
)
from demo_backend.global_cad_transaction_packets import (  # noqa: E402
    compile_global_cad_transaction_manifest,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compile endpoint-complete generic CAD transaction packets."
    )
    parser.add_argument("context_id")
    parser.add_argument("--base-instance-id")
    parser.add_argument(
        "--catalog-path",
        type=Path,
        help=(
            "Optional versioned catalog matching the context. When omitted, use the "
            "active catalog through the workbench."
        ),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.catalog_path:
        catalog_path = args.catalog_path.resolve()
        context_path = (
            ROOT / "demo/global_assembly_contexts" / f"{args.context_id}.json"
        ).resolve()
        catalog = json.loads(catalog_path.read_text(encoding="utf-8-sig"))
        context = json.loads(context_path.read_text(encoding="utf-8-sig"))
        if context.get("catalogDigest") != catalog.get("catalogDigest"):
            raise ValueError("指定目录摘要与上下文目录摘要不一致。")
        result = compile_global_cad_transaction_manifest(
            catalog,
            context,
            base_instance_id=args.base_instance_id,
        )
    else:
        result = compile_cad_transaction_manifest(
            ROOT,
            args.context_id,
            base_instance_id=args.base_instance_id,
        )
    output = args.output or (
        ROOT
        / "demo"
        / "global_assembly_contexts"
        / f"{args.context_id}.cad-transaction-manifest.json"
    )
    if not output.is_absolute():
        output = ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(output),
                "status": result["status"],
                "packetCount": result["packetCount"],
                "blockerCount": len(result["blockers"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
