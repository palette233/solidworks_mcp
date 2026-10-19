from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.global_assembly_context import (  # noqa: E402
    apply_global_command_preview,
    create_global_assembly_context,
    preview_global_assembly_command,
)
from demo_backend.global_assembly_transactions import (  # noqa: E402
    compile_global_assembly_transaction_dag,
)
from demo_backend.global_assembly_workbench import load_global_catalog  # noqa: E402
from demo_backend.global_cad_transaction_packets import (  # noqa: E402
    compile_global_cad_transaction_manifest,
)


CONTEXT_ID = "project01-cross-family-smoke-v1"
OUTPUT = ROOT / "demo" / "global_assembly_contexts"


def _write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    catalog = load_global_catalog(ROOT)
    context = create_global_assembly_context(
        CONTEXT_ID,
        display_name="项目01跨项目族通用执行器验证：JJ00 + SS00",
        catalog_digest=catalog["catalogDigest"],
    )
    commands = [
        {
            "requirement": "添加项目01箱体与回流固定环境JJ00作为基座",
            "moduleDefinitionId": "cad/fl9c24n074jj00-001/79d4fd749ac0",
        },
        {
            "requirement": "添加项目01上层产品传输模组SS00并连接到JJ00",
            "moduleDefinitionId": "cad/fl9c24n074ss00-001/ced014a7837b",
            "existingInstanceId": "fl9c24n074jj00-001-001",
            "newSide": "B",
            "globalTemplateId": "template/project01/ss00-to-jj00-three-datum-installation/c087ea93d1",
        },
    ]
    for command in commands:
        preview = preview_global_assembly_command(catalog, context, command)
        if preview.get("status") != "ready":
            raise RuntimeError(json.dumps(preview, ensure_ascii=False, indent=2))
        context = apply_global_command_preview(
            context,
            preview,
            preview_digest=preview["previewDigest"],
            confirmed=True,
        )
    dag = compile_global_assembly_transaction_dag(catalog, context)
    manifest = compile_global_cad_transaction_manifest(catalog, context)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    context_path = OUTPUT / f"{CONTEXT_ID}.json"
    dag_path = OUTPUT / f"{CONTEXT_ID}.transaction-dag.json"
    manifest_path = OUTPUT / f"{CONTEXT_ID}.cad-transaction-manifest.json"
    _write(context_path, context)
    _write(dag_path, dag)
    _write(manifest_path, manifest)
    print(
        json.dumps(
            {
                "contextPath": str(context_path),
                "dagPath": str(dag_path),
                "manifestPath": str(manifest_path),
                "manifestStatus": manifest["status"],
                "packetCount": manifest["packetCount"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if manifest["status"] == "ready_for_generic_executor_implementation" else 2


if __name__ == "__main__":
    raise SystemExit(main())
