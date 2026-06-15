#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from solidworks_rag import build_index  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a RAG index from crawled SOLIDWORKS API pages.")
    parser.add_argument(
        "--pages",
        default="data/solidworks_api_2025/pages.jsonl",
        help="Crawler pages.jsonl path.",
    )
    parser.add_argument(
        "--index-dir",
        default="data/solidworks_api_2025/rag_index",
        help="Output directory for the RAG index.",
    )
    parser.add_argument(
        "--backend",
        choices=["tfidf", "sbert"],
        default="tfidf",
        help="Index backend. tfidf is local and dependency-light; sbert uses sentence-transformers.",
    )
    parser.add_argument("--chunk-chars", type=int, default=2600)
    parser.add_argument("--overlap-chars", type=int, default=350)
    parser.add_argument(
        "--sbert-model",
        default="sentence-transformers/all-MiniLM-L6-v2",
        help="SentenceTransformers model name when --backend=sbert.",
    )
    parser.add_argument("--batch-size", type=int, default=32)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = build_index(
        pages_path=Path(args.pages),
        index_dir=Path(args.index_dir),
        project_root=Path.cwd(),
        backend=args.backend,
        chunk_chars=args.chunk_chars,
        overlap_chars=args.overlap_chars,
        sbert_model=args.sbert_model,
        batch_size=args.batch_size,
    )
    print("RAG index built")
    for key, value in manifest.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
