from __future__ import annotations

import json
import pickle
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from scipy import sparse
from sklearn.pipeline import FeatureUnion
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


DEFAULT_CHUNK_CHARS = 2600
DEFAULT_OVERLAP_CHARS = 350


@dataclass(frozen=True)
class SourcePage:
    id: str
    url: str
    title: str
    browser_title: str
    text_path: Path
    char_count: int


@dataclass(frozen=True)
class Chunk:
    id: str
    page_id: str
    url: str
    title: str
    text: str
    char_start: int
    char_end: int

    def for_embedding(self) -> str:
        return f"{self.title}\n{self.url}\n\n{self.text}"

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "page_id": self.page_id,
            "url": self.url,
            "title": self.title,
            "text": self.text,
            "char_start": self.char_start,
            "char_end": self.char_end,
        }

    @staticmethod
    def from_json(data: dict[str, Any]) -> "Chunk":
        return Chunk(
            id=data["id"],
            page_id=data["page_id"],
            url=data["url"],
            title=data["title"],
            text=data["text"],
            char_start=int(data["char_start"]),
            char_end=int(data["char_end"]),
        )


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                # The crawler may be appending. Ignore an incomplete final line.
                continue


def resolve_text_path(raw_path: str, pages_path: Path, project_root: Path) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    candidate = project_root / path
    if candidate.exists():
        return candidate
    candidate = pages_path.parent / path
    if candidate.exists():
        return candidate
    return project_root / path


def load_source_pages(pages_path: Path, project_root: Path) -> list[SourcePage]:
    pages: list[SourcePage] = []
    seen_urls: set[str] = set()
    for record in read_jsonl(pages_path):
        url = str(record.get("url") or "")
        text_path = str(record.get("text_path") or "")
        if not url or not text_path or url in seen_urls:
            continue
        path = resolve_text_path(text_path, pages_path, project_root)
        if not path.exists():
            continue
        seen_urls.add(url)
        pages.append(
            SourcePage(
                id=str(record.get("id") or url),
                url=url,
                title=str(record.get("title") or record.get("browser_title") or url),
                browser_title=str(record.get("browser_title") or ""),
                text_path=path,
                char_count=int(record.get("char_count") or 0),
            )
        )
    return pages


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_text(text: str, chunk_chars: int, overlap_chars: int) -> list[tuple[str, int, int]]:
    text = clean_text(text)
    if not text:
        return []
    if len(text) <= chunk_chars:
        return [(text, 0, len(text))]

    chunks: list[tuple[str, int, int]] = []
    start = 0
    while start < len(text):
        hard_end = min(start + chunk_chars, len(text))
        window = text[start:hard_end]

        split_at = max(window.rfind("\n\n"), window.rfind("\n"), window.rfind(". "))
        if split_at < int(chunk_chars * 0.45) or hard_end == len(text):
            end = hard_end
        else:
            end = start + split_at + 1

        chunk = text[start:end].strip()
        if chunk:
            chunks.append((chunk, start, end))

        if end >= len(text):
            break
        start = max(0, end - overlap_chars)

    return chunks


def make_chunks(
    pages: Iterable[SourcePage],
    chunk_chars: int = DEFAULT_CHUNK_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    for page in pages:
        text = page.text_path.read_text(encoding="utf-8", errors="replace")
        for idx, (chunk_text, start, end) in enumerate(
            split_text(text, chunk_chars=chunk_chars, overlap_chars=overlap_chars)
        ):
            chunks.append(
                Chunk(
                    id=f"{page.id}::chunk-{idx:04d}",
                    page_id=page.id,
                    url=page.url,
                    title=page.title,
                    text=chunk_text,
                    char_start=start,
                    char_end=end,
                )
            )
    return chunks


def write_chunks(chunks_path: Path, chunks: Iterable[Chunk]) -> None:
    with chunks_path.open("w", encoding="utf-8") as handle:
        for chunk in chunks:
            handle.write(json.dumps(chunk.to_json(), ensure_ascii=False) + "\n")


def load_chunks(chunks_path: Path) -> list[Chunk]:
    return [Chunk.from_json(record) for record in read_jsonl(chunks_path)]


def build_tfidf(chunks: list[Chunk], index_dir: Path) -> None:
    texts = [chunk.for_embedding() for chunk in chunks]
    vectorizer = FeatureUnion(
        [
            (
                "api_words",
                TfidfVectorizer(
                    analyzer="word",
                    token_pattern=r"(?u)[A-Za-z_][A-Za-z0-9_]*(?:::[A-Za-z_][A-Za-z0-9_]*)?",
                    ngram_range=(1, 2),
                    lowercase=False,
                    min_df=1,
                    max_df=0.98,
                    sublinear_tf=True,
                    norm="l2",
                ),
            ),
            (
                "char_fallback",
                TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=(3, 5),
                    lowercase=True,
                    min_df=1,
                    max_df=0.95,
                    sublinear_tf=True,
                    norm="l2",
                ),
            ),
        ]
    )
    matrix = vectorizer.fit_transform(texts)
    with (index_dir / "tfidf_vectorizer.pkl").open("wb") as handle:
        pickle.dump(vectorizer, handle)
    sparse.save_npz(index_dir / "tfidf_matrix.npz", matrix)


def build_sbert(chunks: list[Chunk], index_dir: Path, model_name: str, batch_size: int) -> None:
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name)
    texts = [chunk.for_embedding() for chunk in chunks]
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=True,
        normalize_embeddings=True,
    )
    np.save(index_dir / "sbert_embeddings.npy", embeddings.astype("float32"))


def build_index(
    pages_path: Path,
    index_dir: Path,
    project_root: Path,
    backend: str = "tfidf",
    chunk_chars: int = DEFAULT_CHUNK_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
    sbert_model: str = "sentence-transformers/all-MiniLM-L6-v2",
    batch_size: int = 32,
) -> dict[str, Any]:
    index_dir.mkdir(parents=True, exist_ok=True)
    pages = load_source_pages(pages_path=pages_path, project_root=project_root)
    chunks = make_chunks(pages, chunk_chars=chunk_chars, overlap_chars=overlap_chars)
    if not chunks:
        raise RuntimeError(f"No chunks were produced from {pages_path}")

    chunks_path = index_dir / "chunks.jsonl"
    write_chunks(chunks_path, chunks)

    if backend == "tfidf":
        build_tfidf(chunks, index_dir)
    elif backend == "sbert":
        build_sbert(chunks, index_dir, model_name=sbert_model, batch_size=batch_size)
    else:
        raise ValueError(f"Unsupported backend: {backend}")

    manifest = {
        "backend": backend,
        "pages_path": str(pages_path),
        "page_count": len(pages),
        "chunk_count": len(chunks),
        "chunk_chars": chunk_chars,
        "overlap_chars": overlap_chars,
        "sbert_model": sbert_model if backend == "sbert" else None,
    }
    (index_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest


class RagIndex:
    def __init__(self, index_dir: Path):
        self.index_dir = index_dir
        self.manifest = json.loads((index_dir / "manifest.json").read_text(encoding="utf-8"))
        self.chunks = load_chunks(index_dir / "chunks.jsonl")
        self.backend = self.manifest["backend"]

        if self.backend == "tfidf":
            with (index_dir / "tfidf_vectorizer.pkl").open("rb") as handle:
                self.vectorizer = pickle.load(handle)
            self.matrix = sparse.load_npz(index_dir / "tfidf_matrix.npz")
            self.model = None
            self.embeddings = None
        elif self.backend == "sbert":
            from sentence_transformers import SentenceTransformer

            self.vectorizer = None
            self.matrix = None
            self.embeddings = np.load(index_dir / "sbert_embeddings.npy")
            self.model = SentenceTransformer(self.manifest["sbert_model"])
        else:
            raise ValueError(f"Unsupported backend: {self.backend}")

    def search(self, query: str, top_k: int = 6) -> list[dict[str, Any]]:
        if self.backend == "tfidf":
            query_vector = self.vectorizer.transform([query])
            scores = cosine_similarity(query_vector, self.matrix).ravel()
        else:
            query_embedding = self.model.encode([query], normalize_embeddings=True)
            scores = np.matmul(self.embeddings, query_embedding[0])

        if len(scores) == 0:
            return []
        top_indices = np.argsort(scores)[::-1][:top_k]
        results: list[dict[str, Any]] = []
        for rank, idx in enumerate(top_indices, start=1):
            chunk = self.chunks[int(idx)]
            results.append(
                {
                    "rank": rank,
                    "score": float(scores[int(idx)]),
                    "id": chunk.id,
                    "title": chunk.title,
                    "url": chunk.url,
                    "text": chunk.text,
                    "char_start": chunk.char_start,
                    "char_end": chunk.char_end,
                }
            )
        return results

    def context(self, query: str, top_k: int = 6, max_chars: int = 12000) -> str:
        parts: list[str] = []
        total = 0
        for result in self.search(query, top_k=top_k):
            block = (
                f"[{result['rank']}] {result['title']}\n"
                f"URL: {result['url']}\n"
                f"Score: {result['score']:.4f}\n"
                f"{result['text']}"
            )
            if total + len(block) > max_chars:
                break
            parts.append(block)
            total += len(block)
        return "\n\n---\n\n".join(parts)
