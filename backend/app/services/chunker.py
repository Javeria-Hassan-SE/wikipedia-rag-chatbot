from __future__ import annotations

from langchain_text_splitters import RecursiveCharacterTextSplitter


CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
MIN_CHUNK_LENGTH = 50

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    length_function=len,
)


def split(text: str) -> list[str]:
    if not text.strip():
        return []
    chunks = _splitter.split_text(text)
    return [c for c in chunks if len(c) >= MIN_CHUNK_LENGTH]
