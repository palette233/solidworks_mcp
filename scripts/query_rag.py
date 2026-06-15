#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import textwrap
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from solidworks_rag import RagIndex  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query a local SOLIDWORKS API RAG index.")
    parser.add_argument("query", help="Search query.")
    parser.add_argument(
        "--index-dir",
        default="data/solidworks_api_2025/rag_index",
        help="RAG index directory.",
    )
    parser.add_argument("--top-k", type=int, default=6)
    parser.add_argument(
        "--context",
        action="store_true",
        help="Print concatenated RAG context instead of ranked summaries.",
    )
    parser.add_argument("--max-chars", type=int, default=12000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    index = RagIndex(Path(args.index_dir))

    if args.context:
        print(index.context(args.query, top_k=args.top_k, max_chars=args.max_chars))
        return

    for result in index.search(args.query, top_k=args.top_k):
        snippet = " ".join(result["text"].split())
        snippet = textwrap.shorten(snippet, width=650, placeholder="...")
        print(f"[{result['rank']}] score={result['score']:.4f}")
        print(result["title"])
        print(result["url"])
        print(snippet)
        print()


if __name__ == "__main__":
    main()
