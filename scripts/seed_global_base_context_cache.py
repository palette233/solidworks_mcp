from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.global_cad_base_context_cache import (  # noqa: E402
    BASE_CONTEXT_WRAPPER_ADAPTER_VERSION,
    build_base_context_cache_descriptor,
    publish_base_context_cache,
)
from demo_backend.global_cad_packet_executor import sha256_file  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="将既有且已通过验收的单组件基座包装结果导入内容寻址缓存。"
    )
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--assembly", type=Path)
    parser.add_argument(
        "--cache-root",
        type=Path,
        default=ROOT / "demo/global_assembly_contexts/base_wrapper_cache",
    )
    args = parser.parse_args()

    evidence_path = args.evidence.resolve()
    evidence = json.loads(evidence_path.read_text(encoding="utf-8-sig"))
    source = Path(str(evidence["sourceModulePath"])).resolve()
    assembly = (
        args.assembly.resolve()
        if args.assembly
        else Path(str(evidence["outputAssemblyPath"])).resolve()
    )
    if not source.is_file():
        raise FileNotFoundError(f"源模组不存在：{source}")
    if not assembly.is_file():
        raise FileNotFoundError(f"包装装配体不存在：{assembly}")
    descriptor = build_base_context_cache_descriptor(
        source_assembly_path=source,
        source_assembly_sha256=sha256_file(source),
        base_context_module_token=str(evidence["baseContextModuleToken"]),
        base_context_transform=list(evidence["baseContextTransform"]),
        adapter_version=BASE_CONTEXT_WRAPPER_ADAPTER_VERSION,
    )
    result = publish_base_context_cache(
        args.cache_root,
        descriptor,
        assembly_path=assembly,
        evidence_path=evidence_path,
    )
    print(
        json.dumps(
            {
                "descriptor": descriptor,
                "cache": result,
                "sourceAssemblySha256": sha256_file(source),
                "assemblySha256": sha256_file(assembly),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
