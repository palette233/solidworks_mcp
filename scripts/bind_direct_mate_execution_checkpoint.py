#!/usr/bin/env python3
"""Bind a successful direct mate-edit artifact to a conversation checkpoint."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/demo-backend/src"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from demo_backend.assembly_conversation import (
    bind_direct_mate_execution,
    conversation_snapshot,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--context", required=True, type=Path)
    parser.add_argument("--execution", required=True, type=Path)
    args = parser.parse_args()
    context_path = args.context.resolve()
    execution_path = args.execution.resolve()
    context = json.loads(context_path.read_text(encoding="utf-8-sig"))
    execution = json.loads(execution_path.read_text(encoding="utf-8-sig"))
    bind_direct_mate_execution(
        context_path,
        context,
        execution,
        execution_path=execution_path,
    )
    snapshot = conversation_snapshot(context_path, context)
    print(json.dumps({
        "success": True,
        "turnCount": snapshot["turnCount"],
        "continuationReady": snapshot["continuationReady"],
        "latestSuccessfulDemo": snapshot["latestSuccessfulDemo"],
        "ledgerPath": snapshot["ledgerPath"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
