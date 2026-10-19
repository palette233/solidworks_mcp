#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "apps/demo-backend/src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.mate_graph_edit import MateGraphEditError, compile_mate_graph_patch


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile an editable module-mate graph patch.")
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--patch", required=True, type=Path)
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    source = args.source.resolve()
    patch_path = args.patch.resolve()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit(f"Refusing to overwrite existing effective graph: {output}")
    try:
        graph = compile_mate_graph_patch(
            json.loads(source.read_text(encoding="utf-8-sig")),
            json.loads(patch_path.read_text(encoding="utf-8-sig")),
            json.loads(args.catalog.resolve().read_text(encoding="utf-8-sig")) if args.catalog else None,
        )
    except (OSError, json.JSONDecodeError, MateGraphEditError) as exc:
        raise SystemExit(str(exc)) from exc
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(graph, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "success": True,
                "output": str(output),
                "moduleCount": graph["ModuleCount"],
                "mateCount": graph["InterModuleMateCount"],
                "operationCount": graph["PatchAudit"]["operationCount"],
                "warnings": graph["PatchAudit"]["warnings"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
