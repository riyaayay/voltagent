"""Turn extracted pages into retrieval-sized chunks.

Token-aware sliding window with overlap, per page.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

import tiktoken

from voltagent.config import settings
from voltagent.ingestion.loaders import SourcePage

_encoding = tiktoken.get_encoding("cl100k_base")


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    doc_title: str
    page_number: int
    text: str

    def to_payload(self) -> dict:
        """Metadata stored alongside the vector in Qdrant / as an ES doc field."""
        return {
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "doc_title": self.doc_title,
            "page_number": self.page_number,
            "text": self.text,
        }


def _chunk_id(doc_id: str, page_number: int, window_index: int, text: str = "") -> str:
    content_sig = hashlib.sha1(text.encode("utf-8")).hexdigest()[:8] if text else ""
    raw = f"{doc_id}:{page_number}:{window_index}:{content_sig}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def chunk_page(
    page: SourcePage,
    chunk_size_tokens: int | None = None,
    overlap_tokens: int | None = None,
) -> list[Chunk]:
    chunk_size = chunk_size_tokens or settings.chunk_size_tokens
    overlap = overlap_tokens or settings.chunk_overlap_tokens

    tokens = _encoding.encode(page.text)
    if not tokens:
        return []

    if len(tokens) <= chunk_size:
        return [
            Chunk(
                chunk_id=_chunk_id(page.doc_id, page.page_number, 0, text=page.text),
                doc_id=page.doc_id,
                doc_title=page.doc_title,
                page_number=page.page_number,
                text=page.text,
            )
        ]

    chunks: list[Chunk] = []
    start = 0
    window_index = 0
    step = max(chunk_size - overlap, 1)

    while start < len(tokens):
        window = tokens[start : start + chunk_size]
        text = _encoding.decode(window)
        chunks.append(
            Chunk(
                chunk_id=_chunk_id(page.doc_id, page.page_number, window_index, text=text),
                doc_id=page.doc_id,
                doc_title=page.doc_title,
                page_number=page.page_number,
                text=text,
            )
        )
        if start + chunk_size >= len(tokens):
            break
        window_index += 1
        start += step

    return chunks


def chunk_pages(
    pages: list[SourcePage],
    chunk_size_tokens: int | None = None,
    overlap_tokens: int | None = None,
) -> list[Chunk]:
    all_chunks: list[Chunk] = []
    for page in pages:
        all_chunks.extend(chunk_page(page, chunk_size_tokens=chunk_size_tokens, overlap_tokens=overlap_tokens))
    return all_chunks
