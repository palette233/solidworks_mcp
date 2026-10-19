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


CONTEXT_ID = "project03-cross-family-smoke-v1"
OUTPUT = ROOT / "demo" / "global_assembly_contexts"


def _write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    catalog = load_global_catalog(ROOT)
    context = create_global_assembly_context(
        CONTEXT_ID,
        display_name="项目03跨项目族通用执行器验证：AA00 + AE00",
        catalog_digest=catalog["catalogDigest"],
    )
    commands = [
        {
            "requirement": "添加项目03箱体与回流固定环境AA00作为基座",
            "moduleDefinitionId": "cad/fl9a24d063aa00-001/dc4bbec17218",
        },
        {
            "requirement": "添加项目03上层产品传输模组AE00并连接到AA00",
            "moduleDefinitionId": "cad/fl9a24d063ae00-001/de8d7b88328e",
            "existingInstanceId": "fl9a24d063aa00-001-001",
            "newSide": "B",
            "globalTemplateId": "template/project03/ae00-to-aa00-three-datum-installation/3665a437a8",
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
    paths = {
        "contextPath": OUTPUT / f"{CONTEXT_ID}.json",
        "dagPath": OUTPUT / f"{CONTEXT_ID}.transaction-dag.json",
        "manifestPath": OUTPUT / f"{CONTEXT_ID}.cad-transaction-manifest.json",
    }
    _write(paths["contextPath"], context)
    _write(paths["dagPath"], dag)
    _write(paths["manifestPath"], manifest)
    print(
        json.dumps(
            {
                **{key: str(value) for key, value in paths.items()},
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
