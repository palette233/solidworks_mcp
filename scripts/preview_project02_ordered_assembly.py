from __future__ import annotations

import argparse
import json
from pathlib import Path

from demo_backend.semantic_assembly_sequence import preview_project02_ordered_assembly


DEFAULT_REQUIREMENT = (
    "项目02：以A600为基座，先添加A800，再添加A180，然后添加A700，"
    "接着添加A500，最后添加A100。"
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview a controlled Project02 ordered assembly command.")
    parser.add_argument("--requirement", default=DEFAULT_REQUIREMENT)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("demo/semantic_ports/project02_ordered_sequence_preview.json"),
    )
    args = parser.parse_args()
    result = preview_project02_ordered_assembly(args.requirement)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["plan"]["summary"], ensure_ascii=False, indent=2))
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
