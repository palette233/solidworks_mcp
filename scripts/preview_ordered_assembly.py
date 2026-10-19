from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/demo-backend/src"))

from demo_backend.ordered_assembly_planner import preview_ordered_assembly


DEFAULT_COMMANDS = {
    "project01": "项目01：以JJ00为基座，先添加SS00，再添加FF00，然后添加SM00，接着添加GN00，再添加BD00，然后添加GJ00，最后添加LM00。",
    "project03": "项目03：以AA00为基座，先添加AE00，再添加AD00，然后添加AI00，接着添加AG00，再添加AH00，然后添加AJ00，最后添加AB00。",
}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Preview a versioned cross-project ordered assembly command."
    )
    parser.add_argument("--project", choices=sorted(DEFAULT_COMMANDS), required=True)
    parser.add_argument("--command")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = preview_ordered_assembly(
        args.project, args.command or DEFAULT_COMMANDS[args.project]
    )
    output = args.output or (
        ROOT
        / "demo/semantic_ports"
        / f"{args.project}_ordered_preview.json"
    )
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["plan"]["summary"]["orderValid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
