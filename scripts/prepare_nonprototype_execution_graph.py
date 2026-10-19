#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "apps/demo-backend/src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.nonprototype_execution_graph import (  # noqa: E402
    prepare_nonprototype_execution_graph,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="生成显式移除目标位姿锚点的非原型执行图。"
    )
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--target", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    source = args.source.resolve()
    output = args.output.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if output.exists():
        raise FileExistsError(f"拒绝覆盖既有执行图：{output}")
    graph = json.loads(source.read_text(encoding="utf-8-sig"))
    prepared = prepare_nonprototype_execution_graph(
        graph,
        target_module_token=args.target,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(prepared, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "success": True,
                "source": str(source),
                "output": str(output),
                "preparation": prepared["NonprototypePreparation"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
