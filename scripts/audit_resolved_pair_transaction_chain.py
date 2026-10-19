from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


WORKSPACE = Path(__file__).resolve().parents[1]
BACKEND_SRC = WORKSPACE / "apps/demo-backend/src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from demo_backend.resolved_pair_transaction_chain import (  # noqa: E402
    audit_resolved_pair_transaction_chain,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--terminal-job", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = audit_resolved_pair_transaction_chain(
        WORKSPACE, args.project, args.terminal_job
    )
    output = Path(args.output)
    if not output.is_absolute():
        output = WORKSPACE / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
