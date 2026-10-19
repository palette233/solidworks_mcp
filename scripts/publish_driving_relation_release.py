from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.driving_relation_release_publisher import (  # noqa: E402
    publish_driving_relation_release,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Publish an immutable driving-relation release from a declarative "
            "template/evidence specification."
        )
    )
    parser.add_argument("spec", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    spec_path = args.spec.resolve() if args.spec.is_absolute() else (ROOT / args.spec).resolve()
    spec = json.loads(spec_path.read_text(encoding="utf-8-sig"))
    output_root = args.output_root
    if output_root is not None and not output_root.is_absolute():
        output_root = (ROOT / output_root).resolve()
    result = publish_driving_relation_release(
        ROOT,
        spec,
        output_root=output_root,
        overwrite=args.overwrite,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
