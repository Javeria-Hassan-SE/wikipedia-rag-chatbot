from __future__ import annotations

from app.services.chunker import CHUNK_SIZE, MIN_CHUNK_LENGTH, split


def _make_text(char_count: int) -> str:
    word = "wikipedia "
    return (word * (char_count // len(word) + 1))[:char_count]


def test_split_empty_string_returns_empty_list():
    assert split("") == []


def test_split_whitespace_only_returns_empty_list():
    assert split("   \n\t  ") == []


def test_split_short_text_below_min_length_is_filtered():
    assert split("too short") == []


def test_split_text_under_chunk_size_returns_single_chunk():
    text = _make_text(CHUNK_SIZE - 10)
    chunks = split(text)
    assert len(chunks) == 1
    assert chunks[0] == text.strip()


def test_split_long_text_produces_multiple_chunks():
    text = _make_text(CHUNK_SIZE * 5)
    chunks = split(text)
    assert len(chunks) > 1


def test_split_all_chunks_within_size_limit():
    text = _make_text(CHUNK_SIZE * 10)
    chunks = split(text)
    for chunk in chunks:
        assert len(chunk) <= CHUNK_SIZE


def test_split_all_chunks_meet_minimum_length():
    text = _make_text(CHUNK_SIZE * 4)
    chunks = split(text)
    for chunk in chunks:
        assert len(chunk) >= MIN_CHUNK_LENGTH


def test_split_consecutive_chunks_overlap():
    # Overlap means the tail of chunk[n] and head of chunk[n+1] share content.
    # We verify this by checking that a substring from the end of chunk[0]
    # appears somewhere in chunk[1].
    text = _make_text(CHUNK_SIZE * 3)
    chunks = split(text)
    assert len(chunks) >= 2
    tail = chunks[0][-20:]
    assert tail in chunks[1]
