"""Compile a controlled Project02 natural-language request without starting CAD."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "apps" / "demo-backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.semantic_port_workbench import (  # noqa: E402
    DEFAULT_NATURAL_LANGUAGE_REQUIREMENT,
    preview_semantic_assembly_intent,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Parse a bounded Project02 engineering request, select semantic ports, "
            "and compile a read-only mate-graph preview."
        )
    )
    parser.add_argument(
        "--requirement",
        default=DEFAULT_NATURAL_LANGUAGE_REQUIREMENT,
        help="Chinese Project02 semantic assembly requirement.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON output path inside the workspace.",
    )
    args = parser.parse_args()
    result = preview_semantic_assembly_intent(
        ROOT, {"requirement": args.requirement}
    )
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output is not None:
        output = args.output.resolve() if args.output.is_absolute() else (ROOT / args.output).resolve()
        output.relative_to(ROOT.resolve())
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
        print(output)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
